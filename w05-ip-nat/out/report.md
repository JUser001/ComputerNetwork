# Week 5 — Single-Network Address Study, DHCP, and NAT

> **Scope and limitation:** This is the requested one-network version. The only interface data available was observed in a remote Linux execution sandbox, **not on the student's PC**. No second network was measured, and public-IP lookup failed. These data are therefore a demonstrative network observation, not a claim about the student's personal network. The lab's original two-network comparison condition remains unmet.

## Part A — One observed network

The available execution environment reported interface `eth0` as `172.26.39.201/22` and the default gateway as `172.26.36.1`.

| Field | Observed or calculated value |
|---|---|
| Interface | `eth0` |
| IPv4 address / prefix | `172.26.39.201/22` |
| Subnet mask | `255.255.252.0` |
| Network address | `172.26.36.0` |
| Usable host range | `172.26.36.1`–`172.26.39.254` |
| Broadcast address | `172.26.39.255` |
| Default gateway | `172.26.36.1` |
| Public IPv4 address | **Not measured** — external lookup failed because DNS resolution was unavailable |

### Subnet calculation and gateway

A `/22` leaves 10 host bits and corresponds to mask `255.255.252.0`. The third octet advances in blocks of four; `39` belongs to the `36`–`39` block. Therefore the network is `172.26.36.0/22`, the broadcast address is `172.26.39.255`, and the conventional usable range is `172.26.36.1` through `172.26.39.254`. The reported gateway `172.26.36.1` lies inside that subnet, so it is reachable as a local next hop.

### Private/public addressing and NAT

`172.26.39.201` is within RFC 1918's private range `172.16.0.0/12`. The public address could not be observed. Because there is no reliable external address to compare with the private interface address, the public/private difference and exact NAT-layer count cannot be confirmed from this run. An upstream interface in `100.64.0.0/10` can indicate carrier-grade NAT, but such upstream evidence is not available here.

## Part B — Second network not measured

Only one network was available, as requested. No second record or comparison has been fabricated. Consequently, whether the private address, gateway, or public address would change on a second network is **not determined**. This is a deviation from the original lab requirement, which asks for two labelled network records and a comparison.

## Part C — DHCP DORA learning trace

`out/dhcp.pcapng` is a **synthetic educational example**, not a live capture from this computer and not the course-provided official trace. It illustrates the DORA sequence (Discover, Offer, Request, Ack), but should not be represented as evidence of a real DHCP exchange.

- **Discover addressing in the example:** source `0.0.0.0`, destination `255.255.255.255`. The client has not yet obtained a configured IPv4 address, so it uses the unspecified source and broadcasts to find a DHCP server on the local link.
- **Example lease time:** `86,400` seconds (24 hours), as represented by DHCP option 51 in the prepared example.
- **Why Ack may be unicast:** after the server selects an address and identifies the client, a unicast reply can be possible when the client's state and broadcast flag permit it. Actual exchanges may still use broadcast depending on client behavior and flags.

For a fully evidenced submission, replace the example trace with the official `traces/` file supplied with the lab or a genuine Wireshark capture. Do not claim that this example came from a live capture.

## Submission status

Task 1 and Task 3 are implemented and tested separately; the latest standalone Task 3 benchmark showed about 335× speedup with zero mismatches. This one-network Task 2 report documents the subnet math and the available interface data, but the personal address measurement, public IP, second-network comparison, and genuine/official DHCP evidence are not established by the available environment. The one-network variant is therefore **partial, not a full pass** under the original task rubric.
