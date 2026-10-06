#!/usr/bin/env python3
"""Week 3 · Task 2 — Does DNS actually steer you? Measure it.

Textbook §2.4.3 (records) and §2.5 (CDNs).

The lecture claims two things:

    (a) most large sites are served by a CDN, reached through a CNAME chain
    (b) DNS steers each user to a *nearby* replica

Both are testable from your laptop, and one of them is harder to prove than
the slide makes it look. Your job is to produce the evidence and a number.

    python3 task2_steering.py --collect        # gather the raw data
    python3 task2_steering.py --report         # your analysis

What you have to build
----------------------
1.  For each hostname in SITES, follow the CNAME chain to its end and record
    every hop. `--collect` should leave the raw data in out/chains.json.

2.  Decide, for each site, whether it is served by a **third party**.
    This is the hard part and there is no single right answer:

      - `www.microsoft.com` ends at `akamaiedge.net`     - clearly third party
      - `www.netflix.com`   stops inside `netflix.com`   - own CDN, not third party
      - some sites have no CNAME at all and still sit behind a CDN (anycast)
      - `foo.cloudfront.net` and `foo.s3.amazonaws.com` are both Amazon,
        but they are not the same service

    Write down the rule you used and **defend it in observation.md**. A rule
    that just compares the last two labels will be wrong on at least one of
    the sites below; find which, and say so.

3.  Ask **two different resolvers** for the same name and compare the
    addresses you get back. If DNS really steers by location, a CDN-hosted
    name should answer differently to resolvers sitting in different places.

        RESOLVERS below has your system resolver and two public ones.

    Report: of N CDN-hosted sites, how many returned a different address set
    from a different resolver? Claim (b) predicts most of them. Check it.

Pass condition
--------------
There is no fixed answer. You pass by producing, in out/report.md:

  - the table: site | chain length | final zone | third party? | your rule's verdict
  - the steering number: "X of N sites answered differently to a different resolver"
  - at least one site where your classification rule was wrong, and why
"""
import argparse, ipaddress, json, os, shutil, subprocess, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

SITES = [
    "www.microsoft.com",     # Akamai, multi-hop
    "www.netflix.com",       # own CDN
    "www.adobe.com",
    "www.cnn.com",
    "www.apple.com",
    "www.korea.ac.kr",       # no CDN at all
    "www.stanford.edu",
    "www.bbc.co.uk",
    "www.spotify.com",
    "www.github.com",
    "www.wikipedia.org",
    "www.nytimes.com",
]

RESOLVERS = {
    "system": None,          # whatever is in your resolv.conf
    "google": "8.8.8.8",
    "quad9":  "9.9.9.9",
}


def dig(name, rtype="A", server=None):
    """Raw lookup. Transport only - the thinking is yours."""
    args = ["dig", "+short", name, rtype]
    if server:
        args.insert(1, f"@{server}")
    if shutil.which("dig"):
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("dig is unavailable or DNS timed out; use the lab container") from exc
        if proc.returncode and not proc.stdout.strip():
            raise RuntimeError(proc.stderr.strip() or f"dig failed for {name} {rtype}")
        return [l.strip() for l in proc.stdout.splitlines() if l.strip()]

    # Windows host fallback: use the OS DNS client. The course container uses
    # dig; this branch also makes the collector usable without installing it.
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell:
        ps = (f"$r=Resolve-DnsName -Name '{name}' -Type {rtype} -DnsOnly "
              "-QuickTimeout -ErrorAction Stop")
        if server:
            ps = ps.replace("-DnsOnly", f"-Server '{server}' -DnsOnly")
        ps += "; $r | Select-Object Name,Type,NameHost,IPAddress | ConvertTo-Json -Compress"
        try:
            proc = subprocess.run([powershell, "-NoProfile", "-Command", ps],
                                  capture_output=True, text=True, timeout=4)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"DNS timed out for {name} via {server or 'system'}") from exc
        if proc.returncode:
            raise RuntimeError((proc.stderr or proc.stdout).strip() or f"DNS failed for {name}")
        try:
            records = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"could not parse Windows DNS response for {name}") from exc
        if not isinstance(records, list):
            records = [records]
        field = "NameHost" if rtype.upper() == "CNAME" else "IPAddress"
        return sorted({str(row[field]).rstrip(".") for row in records
                       if isinstance(row, dict) and row.get(field)})

    raise RuntimeError("dig is unavailable (run in the lab container)")


def collect(vantage="current network"):
    """Gather raw chains and per-resolver answers into out/chains.json.

    You write this. Roughly:
      for each site: follow CNAMEs to the end, then for each resolver in
      RESOLVERS record the A records it returns.
    """
    os.makedirs(OUT, exist_ok=True)
    run = {"collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "vantage": vantage, "sites": {}}
    def get_chain(site):
        chain, current, seen = [], site.rstrip("."), set()
        chain_error = None
        try:
            for _ in range(16):
                key = current.lower()
                if key in seen:
                    chain.append({"name": current, "error": "CNAME loop"})
                    break
                seen.add(key)
                targets = dig(current, "CNAME")
                if not targets:
                    break
                target = targets[0].rstrip(".")
                chain.append({"name": current, "cname": target})
                current = target
            else:
                chain.append({"name": current, "error": "CNAME depth limit"})
        except RuntimeError as exc:
            chain_error = str(exc)
        return site, chain, current, chain_error

    # Independent sites/resolvers are queried concurrently to keep ordinary
    # DNS timeouts from turning the collection into a multi-minute run.
    with ThreadPoolExecutor(max_workers=12) as pool:
        chain_results = list(pool.map(get_chain, SITES))
    for site, chain, current, chain_error in chain_results:
        answers, errors = {}, {}

        def get_answer(pair):
            label, server = pair
            try:
                # Query the original name: recursive resolvers return its
                # current final A set, which is what steering compares.
                # Some `dig +short A` versions also print CNAME targets. Keep
                # only IPv4 addresses so those names cannot skew the comparison.
                addresses = set()
                for value in dig(site, "A", server):
                    try:
                        address = ipaddress.ip_address(value)
                    except ValueError:
                        continue
                    if address.version == 4:
                        addresses.add(str(address))
                return label, sorted(addresses), None
            except RuntimeError as exc:
                return label, [], str(exc)

        with ThreadPoolExecutor(max_workers=3) as pool:
            for label, result, error in pool.map(get_answer, RESOLVERS.items()):
                answers[label] = result
                if error:
                    errors[label] = error
        run["sites"][site] = {"chain": chain, "final_name": current,
                              "answers": answers, "errors": errors,
                              "chain_error": chain_error}

    path = os.path.join(OUT, "chains.json")
    networks = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                old = json.load(f)
            if isinstance(old.get("networks"), dict):
                networks.update(old["networks"])
            elif isinstance(old.get("sites"), dict):
                # Keep the initial single-vantage file when adding a second run.
                networks["Network 1 (before move)"] = old
        except (OSError, json.JSONDecodeError):
            pass
    networks[vantage] = run
    data = {"latest_vantage": vantage, "networks": networks}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {path}")


def report():
    """Read out/chains.json and produce out/report.md.

    You write this too - including the classification rule that decides
    whether a site is on a third-party CDN.
    """
    path = os.path.join(OUT, "chains.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # The hand-classification column records known ownership/provider facts;
    # the intentionally simple rule is just “CNAME leaves the site's domain”.
    # It can confuse a related operational domain with a third party.
    third_party_zones = ("akamaiedge.net", "akamai.net", "edgesuite.net",
                         "edgekey.net", "fastly.net", "cloudfront.net",
                         "azureedge.net", "cloudflare.net", "cloudflare.com",
                         "netlifyglobalcdn.com")
    own_cdn = {"www.netflix.com", "www.wikipedia.org"}
    no_cdn = {"www.korea.ac.kr"}
    anycast_note = {"www.github.com"}

    def site_domain(host):
        labels = host.rstrip(".").lower().split(".")
        # The sites are known inputs; this simple registrable-domain helper
        # handles the country suffix used in this list.
        return ".".join(labels[-3:]) if len(labels) >= 3 and labels[-2] in {"co", "ac"} else ".".join(labels[-2:])

    networks = data.get("networks")
    if not isinstance(networks, dict):
        networks = {data.get("vantage", "single network"): data}
    labels = list(networks)
    primary_label = labels[0]
    primary = networks[primary_label]
    rows = []
    for site in SITES:
        item = primary.get("sites", {}).get(site, {})
        chain = item.get("chain", [])
        final = item.get("final_name", site)
        final_zone = site_domain(final)
        provider_hit = any(final.lower().endswith(z) for z in third_party_zones)
        if site in own_cdn or site in no_cdn:
            actual = "no"
        elif provider_hit:
            actual = "yes"
        elif site in anycast_note:
            actual = "yes (anycast inference)"
        else:
            actual = "unknown"
        verdict = "yes" if chain and site_domain(final) != site_domain(site) else "no"
        rows.append((site, len(chain), final_zone, actual, verdict))

    def resolver_diff(run):
        changed, complete = [], True
        for site in SITES:
            answers = run.get("sites", {}).get(site, {}).get("answers", {})
            values = [set(answers.get(label, [])) for label in RESOLVERS]
            if any(not value for value in values):
                complete = False
            elif any(a != b for i, a in enumerate(values) for b in values[i + 1:]):
                changed.append(site)
        return changed, complete

    steering = []
    for label, run in networks.items():
        changed, complete = resolver_diff(run)
        if complete:
            steering.append(f"- **{label}:** {len(changed)} of {len(SITES)} sites answered differently to a different resolver (system, Google, Quad9).")
        else:
            steering.append(f"- **{label}:** incomplete; one or more resolver queries failed, so its count is a lower bound ({len(changed)} observed differences).")

    cross_note = "A second network was not measured yet."
    if len(labels) >= 2:
        first_label, second_label = labels[0], labels[-1]
        first_sites, second_sites = networks[first_label].get("sites", {}), networks[second_label].get("sites", {})
        cross = []
        for site in SITES:
            a = first_sites.get(site, {}).get("answers", {})
            b = second_sites.get(site, {}).get("answers", {})
            shared = [key for key in RESOLVERS if a.get(key) and b.get(key)]
            if any(set(a[key]) != set(b[key]) for key in shared):
                cross.append(site)
        cross_note = (f"Comparing the same resolver across **{first_label}** and **{second_label}**, "
                      f"{len(cross)} of {len(SITES)} sites returned different address sets.")

    lines = ["# DNS and CDN measurement", "",
             "Measurement runs: " + "; ".join(f"{label} ({run.get('collected_at', 'unknown')})" for label, run in networks.items()),
             f"CNAME table uses the chain collected at **{primary_label}**.", "",
             "The rule verdict is **yes** only when a CNAME chain exists and its final name has a different registrable domain from the queried site. The third-party column uses known provider zones and ownership context; `unknown` means DNS names alone do not establish ownership.", "",
             "| Site | Chain length | Final zone | Third party? | Rule verdict |",
             "|---|---:|---|---|---|"]
    lines.extend(f"| `{site}` | {length} | `{zone}` | {actual} | {verdict} |"
                 for site, length, zone, actual, verdict in rows)
    lines += ["", "## Steering", ""] + steering + ["", cross_note, "",
              "Different DNS answers show resolver- or network-dependent steering; they do not by themselves prove that a user was sent to a geographically nearby replica. The rule gets `www.wikipedia.org` wrong: its chain ends in `wikimedia.org`, a different registrable domain, but that is operated by the Wikimedia Foundation rather than a third-party CDN. `www.github.com`'s anycast/third-party status remains an inference, not something established by its DNS chain.", ""]
    with open(os.path.join(OUT, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {os.path.join(OUT, 'report.md')}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--collect", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--vantage", default="current network",
                   help="label this measurement location; earlier runs are retained")
    a = p.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.collect:
        collect(a.vantage)
    elif a.report:
        report()
    else:
        p.print_help()
