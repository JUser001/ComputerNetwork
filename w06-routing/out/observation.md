# Observations

## Task 1
The router chooses the lexicographically smallest first hop when equal-cost paths tie; real OSPF routers can install multiple equal-cost next hops (ECMP). From `u`, traffic to `w` leaves through `x` because `u-x-y-w` costs 3, less than the direct `u-w` link's cost of 5.
After `u-x` fails, `v` keeps next hop `v`; `x`, `w`, `y`, and `z` use `v` instead. `x` remains reachable through `u-v-x`, so the failure changes its next hop rather than making it unreachable.

## Task 2
The Korea University trace stayed on private/campus-looking hops and 163.152.x.x addresses; it did not show a campus exit. The Stanford hostname resolved through `stanford.netlifyglobalcdn.com`; the RTT rose at hops 4–5, then fell to 6–12 ms, so this trace does not identify an ocean-crossing hop or a specific cable. For 1.1.1.1, the last responding hop was 12 (`141.101.82.12`, Cloudflare), suggesting a nearby anycast replica, though timeouts mean the full path is hidden.
`* * *` can mean a router suppressed/rate-limited its TTL-expired reply, or that the destination/path filters the probe or its reply. In the OSPF tables each router learned remote networks; for example, r1 learned 172.20.0.0/16 through both neighbors, although its direct OSPF links were 172.21.0.0/16 and 172.22.0.0/16.
The recorded link-down, link-restoration, and cost-change detections were each about 1 second. The topology uses default OSPF timers (Hello 10 s, Dead 40 s), but administratively lowering the interface reports a link-state change immediately; the script's one-second polling is too coarse to compare sub-second convergence or demonstrate the dead timer. A cost LSA can flood without waiting for a missing Hello, so a silent failure would normally take longer to detect.

## Task 3
`YourRouter` retains the forwarding table and one distance label per reachable router (O(V) extra state). It skips SPF when a removed/increased link was not on a selected shortest route, and when an added/decreased link cannot tie or improve either endpoint's route; otherwise it calls the provided `dijkstra_table()`.
The benchmark kept every table correct and used 373 SPF runs instead of 1,001, avoiding 63%. Wall time was slower (1.55 s vs 0.96 s) because the incremental checks and Python bookkeeping cost more in this small simulation; on a router, saving CPU-heavy SPF work across a large area can still be worthwhile, even if the bookkeeping takes more time here.
