#!/usr/bin/env python3
"""Week 5 · Task 3 — Fast longest-prefix-match lookup.

A direct-address hash table is kept for each prefix length. Lookup probes the
33 possible prefix lengths from /32 down to /0 and returns at the first hit.
This uses more memory than one linear list but avoids inspecting every route.
"""

_MASK32 = 0xFFFFFFFF


def _mask(prefix_len):
    if not isinstance(prefix_len, int) or isinstance(prefix_len, bool) or not 0 <= prefix_len <= 32:
        raise ValueError("prefix length must be an integer from 0 to 32")
    return 0 if prefix_len == 0 else (_MASK32 << (32 - prefix_len)) & _MASK32


class LinearTable:
    """Correct, slow reference implementation, retained for the harness."""

    def __init__(self):
        self.entries = []

    def add(self, network, prefix_len, next_hop):
        self.entries.append((prefix_len, network, next_hop))

    def lookup(self, address):
        best = None
        for plen, net, hop in self.entries:
            mask = (_MASK32 << (32 - plen)) & _MASK32
            if address & mask == net and (best is None or plen > best[0]):
                best = (plen, hop)
        return best[1] if best else None


class YourTable:
    """LPM implemented as 33 prefix-length hash maps.

    For a given length, the key is the masked network integer. setdefault keeps
    the first route for a duplicate prefix, matching LinearTable's tie behavior.
    """

    def __init__(self):
        self._routes = [{} for _ in range(33)]
        self._masks = [_mask(length) for length in range(33)]

    def add(self, network, prefix_len, next_hop):
        if not isinstance(network, int) or isinstance(network, bool) or not 0 <= network <= _MASK32:
            raise ValueError("network must be a 32-bit integer")
        if not isinstance(prefix_len, int) or isinstance(prefix_len, bool) or not 0 <= prefix_len <= 32:
            raise ValueError("prefix length must be an integer from 0 to 32")
        mask = self._masks[prefix_len]
        if network & mask != network:
            raise ValueError("network integer has host bits set for this prefix length")
        self._routes[prefix_len].setdefault(network, next_hop)

    def lookup(self, address):
        if not isinstance(address, int) or isinstance(address, bool) or not 0 <= address <= _MASK32:
            raise ValueError("address must be a 32-bit integer")
        for prefix_len in range(32, -1, -1):
            network = address & self._masks[prefix_len]
            hop = self._routes[prefix_len].get(network)
            if hop is not None:
                return hop
            # A route could theoretically have None as its next hop; in that
            # case presence, not value, distinguishes a hit from a miss.
            if network in self._routes[prefix_len]:
                return None
        return None
