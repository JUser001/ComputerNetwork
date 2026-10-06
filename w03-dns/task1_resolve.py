#!/usr/bin/env python3
"""Week 3 · Task 1 — Build your own iterative resolver.

Textbook §2.4.2 - §2.4.3.

`dig +trace` walks root -> TLD -> authoritative for you. In this task you do
that walk yourself: start at a root server, read the delegation it returns,
ask the next server, and keep going until somebody answers authoritatively.

You may shell out to `dig` for the transport, or use a DNS library
(`dnspython` is in the container). Either is fine - what matters is that
*you* follow the delegations rather than letting a tool do it.

    python3 task1_resolve.py www.korea.ac.kr
    python3 task1_resolve.py --verify        # check yourself against dig

Pass condition
--------------
`--verify` resolves five names with your resolver and with `dig`, and the
addresses must agree. A name behind a CDN may legitimately return a different
address each time; the harness compares the *set of authoritative nameservers*
you ended at for those, not the address.
"""
import argparse, ipaddress, os, shutil, socket, struct, subprocess, sys

try:
    import dns.flags
    import dns.message
    import dns.name
    import dns.query
    import dns.rdatatype
except ImportError:  # dnspython is optional when running in the Docker lab image
    dns = None

# Root servers. Everything starts here; there is no earlier step.
ROOT_SERVERS = [
    "198.41.0.4",       # a.root-servers.net
    "199.9.14.201",     # b.root-servers.net
    "192.33.4.12",      # c.root-servers.net
]

# (name, kind).  "stable" names must match dig exactly.  "cdn" names are served
# from many replicas and may legitimately give you a different address than dig
# got a second earlier - for those we only require that you reached an answer.
VERIFY_NAMES = [
    ("www.korea.ac.kr", "stable"),
    ("dns.google", "stable"),
    ("en.wikipedia.org", "stable"),
    ("www.stanford.edu", "stable"),
    ("www.microsoft.com", "cdn"),
]


class Resolver:
    """Your iterative resolver.

    The whole point is that you never ask a server to recurse for you.
    You ask one server, it says "not mine, ask over there", and you go there.

    Suggested shape - but it is yours to design:

        resolve(name) -> (address, path)
            address : the A record you ended up with, as a string
            path    : the servers you asked, in order, so you can show your work

    Things you will hit, in roughly this order:

    1.  A delegation gives you NS *names*, sometimes with glue A records and
        sometimes without. No glue means you have to resolve that nameserver's
        name first - which is another walk. Decide what you do there.
    2.  A server may not answer. Try the next one rather than giving up.
    3.  CNAMEs. The answer you get back may be a different name than the one
        you asked for, and you have to start again with that name.
    4.  Loops. Cap your depth.

    If you shell out to dig, the flag you want is `+norecurse`, so that the
    server you ask replies with a delegation instead of doing the work:

        dig @198.41.0.4 www.korea.ac.kr +norecurse
    """

    TIMEOUT = 2.0
    MAX_DEPTH = 20

    def _ask(self, server, name):
        """Send one non-recursive A query and return the DNS response."""
        if dns is None:
            if shutil.which("dig"):
                proc = subprocess.run(
                    # Keep dig's section headings: _parse_dig uses them to
                    # distinguish an answer from a referral and glue records.
                    ["dig", f"@{server}", name, "A", "+norecurse"],
                    capture_output=True, text=True, timeout=self.TIMEOUT + 1)
                return self._parse_dig(proc.stdout)
            return self._ask_stdlib(server, name)
        q = dns.message.make_query(name, dns.rdatatype.A)
        q.flags &= ~dns.flags.RD
        return dns.query.udp(q, server, timeout=self.TIMEOUT)

    @staticmethod
    def _encode_name(name):
        labels = name.rstrip(".").split(".")
        return b"".join(bytes([len(label.encode("idna"))]) + label.encode("idna")
                        for label in labels) + b"\0"

    @staticmethod
    def _decode_name(packet, offset):
        labels, next_offset, jumped, seen = [], offset, False, set()
        while True:
            if offset >= len(packet):
                raise ValueError("truncated DNS name")
            length = packet[offset]
            if length & 0xC0 == 0xC0:
                if offset + 1 >= len(packet):
                    raise ValueError("truncated DNS compression pointer")
                pointer = ((length & 0x3F) << 8) | packet[offset + 1]
                if pointer in seen:
                    raise ValueError("DNS compression loop")
                seen.add(pointer)
                if not jumped:
                    next_offset = offset + 2
                    jumped = True
                offset = pointer
                continue
            offset += 1
            if length == 0:
                return ".".join(labels), (next_offset if jumped else offset)
            if length & 0xC0:
                raise ValueError("invalid DNS label encoding")
            labels.append(packet[offset:offset + length].decode("ascii"))
            offset += length

    def _ask_stdlib(self, server, name):
        """Minimal RFC 1035 UDP client used when neither dnspython nor dig exists."""
        ident = int.from_bytes(os.urandom(2), "big")
        question = self._encode_name(name) + struct.pack("!HH", 1, 1)
        request = struct.pack("!HHHHHH", ident, 0, 1, 0, 0, 0) + question
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.TIMEOUT)
            sock.sendto(request, (server, 53))
            packet, _ = sock.recvfrom(65535)
        if len(packet) < 12 or struct.unpack_from("!H", packet)[0] != ident:
            raise ValueError("invalid DNS response")
        _, flags, qd, an, ns, ar = struct.unpack_from("!HHHHHH", packet)
        if flags & 0x0200:
            raise RuntimeError("truncated DNS response")
        offset = 12
        for _ in range(qd):
            _, offset = self._decode_name(packet, offset)
            offset += 4

        def read_records(count):
            nonlocal offset
            records = []
            for _ in range(count):
                owner, offset = self._decode_name(packet, offset)
                rtype, rclass, ttl, rdlength = struct.unpack_from("!HHIH", packet, offset)
                offset += 10
                start, end = offset, offset + rdlength
                if end > len(packet):
                    raise ValueError("truncated DNS resource record")
                if rtype == 1 and rdlength == 4:
                    kind, value = "A", socket.inet_ntoa(packet[start:end])
                elif rtype in (2, 5):
                    kind = "NS" if rtype == 2 else "CNAME"
                    value, _ = self._decode_name(packet, start)
                else:
                    kind, value = str(rtype), ""
                records.append([owner, ttl, "IN" if rclass == 1 else str(rclass), kind, value])
                offset = end
            return records

        return {"answer": read_records(an), "authority": read_records(ns),
                "additional": read_records(ar), "rcode": flags & 0x000F}

    @staticmethod
    def _parse_dig(output):
        """Small dig-text adapter, retaining answer, authority and glue sections."""
        sections, current = {"answer": [], "authority": [], "additional": []}, None
        for line in output.splitlines():
            if line.startswith(";; ANSWER SECTION:"): current = "answer"
            elif line.startswith(";; AUTHORITY SECTION:"): current = "authority"
            elif line.startswith(";; ADDITIONAL SECTION:"): current = "additional"
            elif line.startswith(";;"): current = None
            elif current and line.strip(): sections[current].append(line.split())
        return sections

    @staticmethod
    def _records(response, section):
        if isinstance(response, dict):
            return response[section]
        return list(getattr(response, section))

    @staticmethod
    def _record_parts(record):
        if isinstance(record, list):  # dig: owner ttl class type rdata
            return record[0].rstrip("."), record[-2].upper(), record[-1].rstrip(".")
        return record.name.to_text().rstrip("."), dns.rdatatype.to_text(record.rdtype), \
            record[0].to_text().rstrip(".")

    def resolve(self, name):
        path = []

        def walk(qname, depth, seen):
            qname = qname.rstrip(".").lower()
            if depth > self.MAX_DEPTH:
                raise RuntimeError(f"maximum delegation/CNAME depth exceeded at {qname}")
            if qname in seen:
                raise RuntimeError(f"DNS alias/delegation loop at {qname}")
            seen = seen | {qname}
            servers = list(ROOT_SERVERS)
            for _ in range(self.MAX_DEPTH):
                response = None
                for server in servers:
                    path.append(server)
                    try:
                        response = self._ask(server, qname)
                        break
                    except (OSError, TimeoutError, subprocess.SubprocessError):
                        continue
                if response is None:
                    raise RuntimeError(f"all name servers failed for {qname}")

                answer = self._records(response, "answer")
                for record in answer:
                    owner, kind, value = self._record_parts(record)
                    if kind == "A" and owner.lower() == qname:
                        return value, path
                    if kind == "CNAME" and owner.lower() == qname:
                        return walk(value, depth + 1, seen)

                authority = self._records(response, "authority")
                ns_names = [self._record_parts(r)[2] for r in authority
                            if self._record_parts(r)[1] == "NS"]
                if not ns_names:
                    raise RuntimeError(f"no A answer or NS referral for {qname}")

                # Use in-bailiwick glue when supplied. Otherwise resolve the NS
                # hostname with another root-to-authority walk.
                glue = {}
                for record in self._records(response, "additional"):
                    owner, kind, value = self._record_parts(record)
                    if kind == "A" and owner.lower() in {n.lower() for n in ns_names}:
                        glue.setdefault(owner.lower(), []).append(value)
                next_servers = [ip for ns in ns_names
                                for ip in glue.get(ns.lower(), [])]
                if not next_servers:
                    for ns in ns_names:
                        try:
                            ip, _ = walk(ns, depth + 1, seen)
                            next_servers.append(ip)
                        except (OSError, RuntimeError, subprocess.SubprocessError):
                            continue
                if not next_servers:
                    raise RuntimeError(f"could not resolve any delegated NS for {qname}")
                servers = next_servers
            raise RuntimeError(f"too many referrals while resolving {qname}")

        return walk(name, 0, set())


# ------------------------------------------------------------------- harness
def dig_answer(name):
    """What the system resolver says, for comparison."""
    if shutil.which("dig"):
        out = subprocess.run(["dig", "+short", name, "A"],
                             capture_output=True, text=True).stdout
        return [l for l in out.split() if l and l[0].isdigit()]
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell:
        command = (f"Resolve-DnsName -Name '{name}' -Type A -DnsOnly "
                   "-QuickTimeout -ErrorAction Stop | Select-Object -ExpandProperty IPAddress")
        proc = subprocess.run([powershell, "-NoProfile", "-Command", command],
                              capture_output=True, text=True, timeout=8)
        return [line.strip() for line in proc.stdout.splitlines()
                if line.strip() and _is_ipv4(line.strip())]
    return []


def _is_ipv4(value):
    try:
        ipaddress.IPv4Address(value)
        return True
    except ipaddress.AddressValueError:
        return False


def verify():
    r, failures = Resolver(), 0
    for name, kind in VERIFY_NAMES:
        try:
            addr, path = r.resolve(name)
        except NotImplementedError:
            print("Nothing implemented yet - write Resolver.resolve first.")
            return 1
        except Exception as e:
            print(f"  FAIL  {name:<22} your resolver raised {e!r}")
            failures += 1
            continue
        expected = dig_answer(name)
        if addr in expected:
            note = ""
        elif kind == "cdn":
            note = "  <- differs, but this name is CDN-hosted. Explain it."
        else:
            note = "  <- should have matched"
            failures += 1
        print(f"  {'FAIL' if note.endswith('matched') else 'ok  '}  {name:<22} "
              f"you={addr:<16} dig={','.join(expected) or '-'}   "
              f"hops={len(path)}{note}")
    print(f"\n  {len(VERIFY_NAMES) - failures}/{len(VERIFY_NAMES)} ok")
    return 1 if failures else 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name", nargs="?", default="www.korea.ac.kr")
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()

    if a.verify:
        sys.exit(verify())

    addr, path = Resolver().resolve(a.name)
    for i, server in enumerate(path, 1):
        print(f"  {i}. asked {server}")
    print(f"\n  {a.name} -> {addr}")


if __name__ == "__main__":
    main()
