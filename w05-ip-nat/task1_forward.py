#!/usr/bin/env python3
"""Week 5 · Task 1 — IPv4 CIDR ranges and longest-prefix forwarding.

This implementation deliberately uses 32-bit integers, shifts and masks; it
uses neither ipaddress nor socket.inet_aton.
"""
import argparse

_MASK32 = 0xFFFFFFFF


def ipv4_to_int(address):
    """Convert dotted-decimal IPv4 text to an unsigned 32-bit integer."""
    if not isinstance(address, str):
        raise ValueError("IPv4 address must be a string")
    pieces = address.split(".")
    if len(pieces) != 4:
        raise ValueError(f"invalid IPv4 address: {address!r}")
    octets = []
    for piece in pieces:
        if not piece or not piece.isascii() or not piece.isdigit():
            raise ValueError(f"invalid IPv4 address: {address!r}")
        value = int(piece, 10)
        if not 0 <= value <= 255:
            raise ValueError(f"IPv4 octet out of range: {piece!r}")
        octets.append(value)
    return (octets[0] << 24) | (octets[1] << 16) | (octets[2] << 8) | octets[3]


def int_to_ipv4(value):
    """Convert an unsigned 32-bit integer to dotted-decimal IPv4 text."""
    if not isinstance(value, int) or not 0 <= value <= _MASK32:
        raise ValueError("IPv4 integer must be in the range 0..2^32-1")
    return ".".join(str((value >> shift) & 0xFF) for shift in (24, 16, 8, 0))


def prefix_mask(prefix_len):
    if not isinstance(prefix_len, int) or isinstance(prefix_len, bool) or not 0 <= prefix_len <= 32:
        raise ValueError("prefix length must be an integer from 0 to 32")
    if prefix_len == 0:
        return 0
    return (_MASK32 << (32 - prefix_len)) & _MASK32


def parse_cidr(cidr):
    """Parse canonical CIDR text as ``(network_integer, prefix_length)``.

    Rejects invalid octets, invalid prefix lengths, and addresses with host
    bits set (e.g. 163.152.6.5/24).
    """
    if not isinstance(cidr, str) or cidr.count("/") != 1:
        raise ValueError("CIDR must have the form A.B.C.D/prefix")
    address, prefix_text = cidr.split("/")
    if not prefix_text or not prefix_text.isascii() or not prefix_text.isdigit():
        raise ValueError("prefix length must be an integer from 0 to 32")
    prefix_len = int(prefix_text)
    mask = prefix_mask(prefix_len)
    address_int = ipv4_to_int(address)
    network = address_int & mask
    if network != address_int:
        raise ValueError(f"CIDR address has host bits set: {cidr}")
    return network, prefix_len


def network_range(cidr):
    """Return (first usable, last usable, broadcast) as dotted-decimal strings.

    For /31, follows RFC 3021 point-to-point semantics: both addresses are
    usable, and the third tuple field repeats the upper address as a display
    convention (there is no directed broadcast on a /31 link). For /32, the
    one address is returned for all three fields because it is a host route,
    not a multi-host subnet with a meaningful broadcast address.
    """
    network, prefix_len = parse_cidr(cidr)
    mask = prefix_mask(prefix_len)
    broadcast = network | (_MASK32 ^ mask)
    if prefix_len <= 30:
        first, last = network + 1, broadcast - 1
    elif prefix_len == 31:
        first, last = network, broadcast
    else:  # /32: one host address
        first = last = network
    return int_to_ipv4(first), int_to_ipv4(last), int_to_ipv4(broadcast)


class ForwardingTable:
    """Forward packets using longest-prefix match.

    Adding the same network/prefix twice with different next hops is rejected
    as ambiguous. An identical duplicate is harmless and leaves the route as
    originally installed. Distinct equal-length prefixes are valid, since they
    cannot both match the same address.
    """

    def __init__(self):
        self._entries = []  # (network_int, prefix_len, next_hop)
        self._by_prefix = {}

    def add(self, cidr, next_hop):
        network, prefix_len = parse_cidr(cidr)
        key = (network, prefix_len)
        if key in self._by_prefix:
            prior = self._by_prefix[key]
            if prior != next_hop:
                raise ValueError(f"conflicting next hops for {cidr}: {prior!r} vs {next_hop!r}")
            return
        self._by_prefix[key] = next_hop
        self._entries.append((network, prefix_len, next_hop))

    def lookup(self, address):
        address_int = ipv4_to_int(address)
        best_prefix = -1
        best_hop = None
        for network, prefix_len, next_hop in self._entries:
            if prefix_len > best_prefix and (address_int & prefix_mask(prefix_len)) == network:
                best_prefix = prefix_len
                best_hop = next_hop
        return best_hop


# ------------------------------------------------------------------- harness
RANGE_CASES = [
    ("192.168.0.0/24",  "192.168.0.1",   "192.168.0.254",  "192.168.0.255"),
    ("10.0.0.0/8",      "10.0.0.1",      "10.255.255.254", "10.255.255.255"),
    ("172.16.32.0/20",  "172.16.32.1",   "172.16.47.254",  "172.16.47.255"),
    ("203.0.113.64/26", "203.0.113.65",  "203.0.113.126",  "203.0.113.127"),
]

TABLE = [
    ("0.0.0.0/0",       "default-gw"),
    ("10.0.0.0/8",      "campus"),
    ("10.20.0.0/16",    "eng-building"),
    ("10.20.30.0/24",   "lab-floor"),
    ("10.20.30.64/26",  "lab-rack-2"),
    ("192.168.1.0/24",  "home"),
]

LOOKUP_CASES = [
    ("10.20.30.70",   "lab-rack-2"),
    ("10.20.30.10",   "lab-floor"),
    ("10.20.99.1",    "eng-building"),
    ("10.99.0.1",     "campus"),
    ("8.8.8.8",       "default-gw"),
    ("192.168.1.77",  "home"),
]


def verify():
    fails = 0
    for cidr, first, last, bcast in RANGE_CASES:
        try:
            got = network_range(cidr)
        except Exception as e:
            print(f"  FAIL  {cidr:<18} raised {e!r}")
            fails += 1
            continue
        ok = tuple(got) == (first, last, bcast)
        print(f"  {'ok  ' if ok else 'FAIL'}  {cidr:<18} {got}")
        fails += not ok

    t = ForwardingTable()
    try:
        for cidr, hop in TABLE:
            t.add(cidr, hop)
    except Exception as e:
        print(f"  FAIL  forwarding table setup raised {e!r}")
        return 1
    for addr, expect in LOOKUP_CASES:
        try:
            got = t.lookup(addr)
        except Exception as e:
            print(f"  FAIL  {addr:<16} raised {e!r}")
            fails += 1
            continue
        ok = got == expect
        print(f"  {'ok  ' if ok else 'FAIL'}  {addr:<16} -> {got}  (want {expect})")
        fails += not ok
    total = len(RANGE_CASES) + len(LOOKUP_CASES)
    print(f"\n  {total - fails}/{total} ok")
    return 1 if fails else 0


def _verify_validation():
    """Small extra validation suite used manually during development."""
    invalid = ["163.152.6.5/24", "10.0.0.0/33", "10.0.0.0/-1", "256.0.0.0/8", "10.0.0/24"]
    for text in invalid:
        try:
            parse_cidr(text)
        except ValueError:
            continue
        raise AssertionError(f"expected rejection: {text}")
    assert network_range("192.0.2.0/31") == ("192.0.2.0", "192.0.2.1", "192.0.2.1")
    assert network_range("192.0.2.7/32") == ("192.0.2.7", "192.0.2.7", "192.0.2.7")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verify", action="store_true")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        _verify_validation()
        print("  extra edge cases ok")
    else:
        raise SystemExit(verify() if a.verify else p.print_help())
