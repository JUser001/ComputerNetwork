#!/usr/bin/env python3
"""Week 7 · Task 3 — A switch that runs out of room.

Textbook §6.4.3.

A switch does not have room for every station on the network. Its forwarding
table sits in a fixed amount of fast memory, and when that fills, something has
to go. Whatever goes gets **flooded** the next time anyone sends to it - out of
every port, to every station that did not ask for it.

`NaiveSwitch` handles a full table the simplest way: throw out whichever entry
has been there longest. That is a perfectly reasonable first idea and it is
close to the worst thing you can do with this traffic.

    python3 bench.py
    python3 bench.py --yours

Correctness first: every frame whose destination is reachable must still reach
it. A switch that floods less because it delivers less is not a switch.
"""
from collections import OrderedDict


class NaiveSwitch:
    """Correct. Evicts the oldest entry, which is not the least useful one."""

    BROADCAST = "ff:ff:ff:ff:ff:ff"

    def __init__(self, ports, capacity):
        self.ports = ports
        self.capacity = capacity
        self.table = OrderedDict()                 # mac -> port, insertion order

    def handle(self, frame, in_port):
        src, dst, now = frame
        if src not in self.table and len(self.table) >= self.capacity:
            self.table.popitem(last=False)         # throw out the oldest arrival
        self.table[src] = in_port

        if dst == self.BROADCAST or dst not in self.table:
            return [p for p in range(self.ports) if p != in_port]
        out = self.table[dst]
        return [] if out == in_port else [out]


class YourSwitch:
    """Your switch. Same interface, same deliveries, far less flooding.

        __init__(ports, capacity)
        handle((src, dst, time), in_port) -> ports to forward out of

    `self.table` must exist and must never hold more than `capacity` entries.
    The harness checks this after every frame.

    What the baseline gets wrong: it decides what to keep by **when the entry
    arrived**, and that has nothing to do with whether it is about to be needed.
    On this trace a handful of stations carry most of the traffic, and the
    baseline keeps throwing them out to make room for stations that spoke once.

    Two questions worth separating:

      * which entry should leave when the table is full?
      * should learning a new source ever be *declined*?

    The second one is less obvious and is worth thinking about before you
    dismiss it.

    Note what you are NOT allowed to do: you cannot look at `where`, you cannot
    see the future, and you cannot hold more than `capacity` entries. Everything
    you know comes from the frames you have already handled.
    """

    BROADCAST = "ff:ff:ff:ff:ff:ff"

    # How many stations we keep a popularity counter for, as a multiple of the
    # table size. The counters are *evidence*, not forwarding entries: they are
    # cheap, never used to forward, and bounded - so the switch's total memory
    # is still a fixed multiple of `capacity`, whatever the network size.
    EVIDENCE_FACTOR = 4

    def __init__(self, ports, capacity):
        self.ports = ports
        self.capacity = capacity
        self.table = {}                      # mac -> port   (<= capacity)
        self.limit = self.EVIDENCE_FACTOR * capacity
        self.seen = {}                       # mac -> popularity (<= limit)

    def _count(self, mac, keep=None):
        """Bounded popularity counters (a frequency count with a fixed budget).

        A tracked station just gets +1. When the counters are full, a newcomer
        replaces the least popular tracked station and starts again from 1 - it
        does NOT inherit the evicted count. (The classic Space-Saving rule does
        inherit it; measured here, that lets a stream of forged one-off
        addresses inflate its own counts until they look popular, and 45 of
        them ended up in the table. Starting at 1 keeps them at 1.)

        `keep` is a station that must not be pushed out by this call.
        """
        c = self.seen
        if mac in c:
            c[mac] += 1
        elif len(c) < self.limit:
            c[mac] = 1
        else:
            quiet = min((m for m in c if m != keep), key=c.get)
            del c[quiet]
            c[mac] = 1

    def handle(self, frame, in_port):
        src, dst, now = frame

        # Evidence: a station is "popular" if it is heard from OR asked for.
        # Being asked for is the direct cost signal - a missing destination is
        # exactly what gets flooded.
        self._count(src)
        if dst != self.BROADCAST:
            self._count(dst, keep=src)       # asking for dst must not erase src

        # Learn. A station we already hold is always refreshed (it may have
        # moved - newest evidence wins). A newcomer is admitted only if there is
        # room, or if it is strictly more popular than the entry it would evict.
        # Ties and one-off talkers are declined: the table keeps what it has.
        if src in self.table or len(self.table) < self.capacity:
            self.table[src] = in_port
        else:
            weakest = min(self.table, key=lambda m: self.seen.get(m, 0))
            if self.seen.get(src, 0) > self.seen.get(weakest, 0):
                del self.table[weakest]
                self.table[src] = in_port

        # Forward. Declining to learn a source never loses a delivery: if its
        # table entry is absent we flood, and flooding always reaches it.
        if dst == self.BROADCAST or dst not in self.table:
            return [p for p in range(self.ports) if p != in_port]
        out = self.table[dst]
        return [] if out == in_port else [out]
