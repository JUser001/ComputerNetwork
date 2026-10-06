# Observations

## Task 1
The root server returned a delegation to the `.kr` name servers instead of an A record because it directs queries to the next level of the DNS hierarchy; it does not store each host's address. When a delegation has no usable glue, my resolver looks up the NS hostname in a separate walk from a root server, tries alternate servers, and caps recursion depth to avoid loops.

## Task 2
My rule says “third party” when a CNAME ends outside the queried site's registrable domain; it gets `www.wikipedia.org` wrong because `wikimedia.org` is also operated by the Wikimedia Foundation. **8 of 12** sites differed across system, Google, and Quad9 on Network 1 and **8 of 12** on Wi-Fi; comparing the same resolver across networks, **2 of 12** differed. This shows resolver- or network-dependent answers, not necessarily geographic proximity.
In the capture, packet 2 is a delegation (zero answers, six authority NS records) and packet 6 is an A answer (one answer); the largest response was 394 bytes on the wire (352 bytes of DNS message).

## Task 3
The fewest possible is **275 upstream queries** for this workload: each name's first request needs an upstream answer, and after its TTL expires the next request must fetch a fresh answer. My TTL-aware cache reaches that floor with zero stale answers; caching longer would return expired data.
