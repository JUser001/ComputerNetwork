# Observations — Week 5

## Task 1 — Subnets and longest-prefix match

- `172.26.39.201/22` belongs to `172.26.36.0/22`; mask `255.255.252.0`, usable range `172.26.36.1`–`172.26.39.254`, broadcast `172.26.39.255`.
- `172.26.36.1` is inside the subnet and can serve as the directly reachable default gateway. Task 1's CIDR parser and longest-prefix matching tests passed 10/10 cases.

## Task 2 — Single available network and DHCP

- Only one interface was observed (`172.26.39.201/22`) and it belongs to the assistant's remote sandbox, not the student's PC. Public IP lookup failed, so NAT-layer count is unknown and no second-network comparison is claimed.
- `dhcp.pcapng` is a synthetic teaching example: Discover is `0.0.0.0` → `255.255.255.255` and its sample lease is 86,400 seconds. Replace it with a live capture or official course trace for genuine DHCP evidence.

## Task 3 — Faster LPM

- The prefix-length hash maps search from `/32` down to `/0`, requiring at most 33 prefix probes rather than a scan over every route.
- The benchmark checked 20,000 queries against the linear table with zero wrong answers; the recorded baseline comparison was about 335× faster in the latest standalone run, with timing varying by run.
