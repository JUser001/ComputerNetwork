#!/usr/bin/env python3
"""Week 6 · Task 3 — Reconverge without recomputing the world.

Textbook §5.2.1, §5.3.

A link flaps. Every router in the area has to decide what changed. `FullRecompute`
does the honest thing: throw the table away and run Dijkstra again, from scratch,
for every event. It is correct and it is what the first implementations did.

It is also why a single flapping link in a large area used to melt the CPU of
every router that could see it.

Beat it:

    python3 bench.py
    python3 bench.py --yours

Correctness first. `bench.py` compares your table against a full recompute after
**every single event**. A router that is fast and wrong black-holes traffic.
"""
import heapq
import math

# The harness counts how many times you run a full SPF. This is the score:
# wall-clock time in Python says more about dictionary overhead than about
# routing, but "how many times did the CPU have to recompute the world" is
# exactly what melted real routers.
SPF_RUNS = 0


def dijkstra_table(graph, source):
    """Reference shortest-path-first. Returns {destination: first_hop}.

    Use THIS function whenever you need a full recompute. Rolling your own to
    dodge the counter is not an optimisation, it is cheating the meter.
    """
    global SPF_RUNS
    SPF_RUNS += 1
    best = {source: (0, None)}
    pq, done = [(0, source, None)], set()
    while pq:
        cost, node, first_hop = heapq.heappop(pq)
        if node in done:
            continue
        done.add(node)
        best[node] = (cost, first_hop)
        for nbr, w in sorted(graph[node].items()):
            if nbr in done:
                continue
            hop = nbr if node == source else first_hop
            if cost + w < best.get(nbr, (float("inf"), None))[0]:
                best[nbr] = (cost + w, hop)
                heapq.heappush(pq, (cost + w, nbr, hop))
    return {d: h for d, (_, h) in best.items() if d != source and h}


class FullRecompute:
    """On every event, forget everything and run SPF again."""

    def __init__(self, graph, source):
        self.graph = {n: dict(e) for n, e in graph.items()}
        self.source = source
        self.table = dijkstra_table(self.graph, source)

    def link_change(self, a, b, cost):
        """cost=None means the link went down."""
        if cost is None:
            self.graph[a].pop(b, None)
            self.graph[b].pop(a, None)
        else:
            self.graph[a][b] = cost
            self.graph[b][a] = cost
        self.table = dijkstra_table(self.graph, self.source)


class YourRouter:
    """Your router. Same two methods, same table, less work per event.

    What is actually true after one link changes:

      * most destinations are not affected at all
      * a link that is not on any of your shortest paths, going *up*, can only
        matter if it creates something shorter
      * a link going *down* only matters if you were using it

    Deciding which of those applies, cheaply, without getting it wrong, is the
    task. Getting it wrong is worse than being slow - the harness will catch it
    on the event where it happens.
    """

    def __init__(self, graph, source):
        self.graph = {node: dict(edges) for node, edges in graph.items()}
        self.source = source
        self.table = dijkstra_table(self.graph, self.source)
        self.distances = self._distances_for_table()

    def _distances_for_table(self):
        """Recover distances along the already selected first-hop branches.

        dijkstra_table remains the authority for the forwarding table. These
        labels retain the extra information needed to decide whether a later
        edge event can affect that table without running another full SPF.
        """
        distances = {self.source: 0}
        queue = [(0, self.source)]
        while queue:
            distance, node = heapq.heappop(queue)
            if distance != distances.get(node):
                continue
            branch = None if node == self.source else self.table.get(node)
            for neighbor, cost in self.graph[node].items():
                if neighbor == self.source or neighbor not in self.table:
                    continue
                expected_branch = neighbor if node == self.source else branch
                if self.table[neighbor] != expected_branch:
                    continue
                candidate = distance + cost
                if candidate < distances.get(neighbor, math.inf):
                    distances[neighbor] = candidate
                    heapq.heappush(queue, (candidate, neighbor))
        return distances

    def _first_hop_via(self, node, neighbor):
        return neighbor if node == self.source else self.table.get(node)

    def _edge_is_on_selected_route(self, a, b, cost):
        """Whether this edge is a shortest-path step in a selected branch."""
        da = self.distances.get(a, math.inf)
        db = self.distances.get(b, math.inf)
        forward = (math.isfinite(da) and math.isfinite(db)
                   and da + cost == db
                   and self.table.get(b) == self._first_hop_via(a, b))
        reverse = (math.isfinite(da) and math.isfinite(db)
                   and db + cost == da
                   and self.table.get(a) == self._first_hop_via(b, a))
        return forward or reverse

    def _new_link_can_change_table(self, a, b, cost):
        """A new/decreased edge matters only if it can tie or improve a route."""
        da = self.distances.get(a, math.inf)
        db = self.distances.get(b, math.inf)
        return ((math.isfinite(da) and da + cost <= db)
                or (math.isfinite(db) and db + cost <= da))

    def _recompute(self):
        self.table = dijkstra_table(self.graph, self.source)
        self.distances = self._distances_for_table()

    def link_change(self, a, b, cost):
        old_cost = self.graph[a].get(b)

        if cost is None:
            if old_cost is None:
                return
            must_recompute = self._edge_is_on_selected_route(a, b, old_cost)
            self.graph[a].pop(b, None)
            self.graph[b].pop(a, None)
        elif old_cost is None:
            must_recompute = self._new_link_can_change_table(a, b, cost)
            self.graph[a][b] = cost
            self.graph[b][a] = cost
        elif cost == old_cost:
            return
        elif cost > old_cost:
            must_recompute = self._edge_is_on_selected_route(a, b, old_cost)
            self.graph[a][b] = cost
            self.graph[b][a] = cost
        else:
            must_recompute = self._new_link_can_change_table(a, b, cost)
            self.graph[a][b] = cost
            self.graph[b][a] = cost

        if must_recompute:
            self._recompute()
