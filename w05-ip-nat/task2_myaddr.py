#!/usr/bin/env python3
"""Week 5 · Task 2 — Where exactly are you on the internet?

Textbook §4.3.2 (addressing, DHCP) and §4.3.3 (NAT).

This is the hands-on task. It asks what address your machine has, what address
the rest of the world sees, and why those two are usually different.

    python3 task2_myaddr.py --collect     # gather what your OS will tell you
    python3 task2_myaddr.py --report      # your analysis

Run it on **two networks**. Campus Wi-Fi and phone tethering behave differently
here, and the difference is the lesson.
"""
import argparse, json, os, platform, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def sh(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout
    except Exception as e:
        return f"<failed: {e}>"


def local_facts():
    """Raw output only. Reading it is your job, not this script's."""
    osname = platform.system()
    if osname == "Darwin":
        return {"os": osname,
                "ifconfig": sh("ifconfig"),
                "route": sh("route", "-n", "get", "default"),
                "dns": sh("scutil", "--dns")}
    if osname == "Linux":
        return {"os": osname,
                "ip_addr": sh("ip", "addr"),
                "ip_route": sh("ip", "route"),
                "dns": sh("cat", "/etc/resolv.conf")}
    return {"os": osname,
            "ipconfig": sh("ipconfig", "/all"),
            "route": sh("route", "print")}


def public_address():
    """What a server on the outside says your address is."""
    out = sh("curl", "-s", "--max-time", "10", "https://api.ipify.org")
    return out.strip() or None


def collect(label):
    os.makedirs(OUT, exist_ok=True)
    record = {"label": label, "local": local_facts(), "public": public_address()}
    path = os.path.join(OUT, "addresses.json")
    all_records = json.load(open(path)) if os.path.exists(path) else []
    all_records.append(record)
    json.dump(all_records, open(path, "w"), indent=2)
    print(f"  public address seen from outside: {record['public']}")
    print(f"  -> out/addresses.json  ({len(all_records)} record(s))")
    print("\n  Now read the raw output yourself and answer the questions in task2.md.")
    print("  The script deliberately does not parse it for you.")


def report():
    """Write a report scaffold tied to the records collected by --collect.

    This deliberately marks unavailable measurements instead of inventing them.
    The student should verify the raw interface details and collect on a second
    real network before treating the report as a complete personal observation.
    """
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "addresses.json")
    records = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
    lines = [
        "# Week 5 · Address study, DHCP, and NAT",
        "",
        "> Measurement note: this report is generated from the local records in",
        "> `addresses.json`. An unavailable value is left explicitly unavailable;",
        "> it must not be replaced with a guessed public address or a fictional network.",
        "",
        "## Part A/B — Address records",
        "",
    ]
    if not records:
        lines += ["No records found. Run `python task2_myaddr.py --collect \"network label\"` on the machine and network being studied.", ""]
    for i, record in enumerate(records, 1):
        lines += [f"### Network {i}: {record.get('label', 'unlabelled')}", ""]
        public = record.get("public")
        lines += [f"- Public address observed by external service: `{public}`" if public else
                  "- Public address: **not observed** (the external lookup returned no result)."]
        local = record.get("local", {})
        os_name = local.get("os", "unknown OS")
        lines += [f"- Operating system recorded: {os_name}",
                  "- Raw interface, route, and DNS output is stored in `addresses.json`; use it to identify the IPv4 address, subnet mask/prefix, and default gateway.",
                  "- For the subnet range, mask the host address to find the network address; the broadcast address sets all host bits to 1. Check the endpoints against Task 1.",
                  ""]
    if len(records) < 2:
        lines += ["**Second network still required.** Re-run collection on a genuinely different network (for example, phone tethering); do not duplicate the first record.", ""]
    if not records or any(not r.get("public") for r in records):
        lines += ["**NAT conclusion is incomplete.** Without the externally observed public address, this record cannot establish the outside address or distinguish one NAT layer from carrier-grade/double NAT. A local RFC 1918 address alone indicates a private address, not the exact number of NAT layers.", ""]
    lines += [
        "## Part C — DHCP DORA questions",
        "",
        "Use the DHCP packets in `out/dhcp.pcapng` and read the lease option in the Offer/Ack. If the included file is labelled as a generated teaching trace, treat these values as an example only, not as a live capture from this machine.",
        "",
        "- **Discover source/destination:** a client with no configured IPv4 address uses source `0.0.0.0`; it broadcasts to `255.255.255.255` because it does not yet know the DHCP server or assigned subnet.",
        "- **Lease time:** read DHCP option 51 from the Offer (and verify whether Ack repeats it).",
        "- **Why Ack may be unicast:** after selecting a server and assigning an address, the server knows the offered client address and link-layer destination; if the client's DHCP broadcast flag permits it, the server can deliver the Ack by unicast.",
        "",
        "## Conclusion",
        "",
        "Do not infer an exact NAT count from a private address alone. Compare the private address with the outside address, and look for a `100.64.0.0/10` carrier-grade NAT address on the upstream side to distinguish likely double NAT from a single home/campus NAT. A second real network and a live/official DHCP trace are needed to finish the personal measurement portion.",
        "",
    ]
    out_path = os.path.join(OUT, "report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  -> out/report.md ({len(records)} address record(s))")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--collect", metavar="LABEL",
                   help='where you are, e.g. "campus wifi"')
    p.add_argument("--report", action="store_true")
    a = p.parse_args()
    if a.collect:
        collect(a.collect)
    elif a.report:
        report()
    else:
        p.print_help()
