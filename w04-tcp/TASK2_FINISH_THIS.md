# Task 2 — finish on your own computer

The package cannot measure your local network or capture your network interface from here. Keep `out/throughput.json` as `[]` until you have real measurements; do not use invented values. The fastest fallback when you only have one network and little time is documented in `TASK2_NOW_AND_10MIN.md`.

## Fast route: same network now and about 10 minutes later

1. Open Wireshark on the interface actually carrying traffic. Use capture filter `tcp port 443` and start capturing.
2. From this folder, run:
   `python3 task2_measure.py --label "Wi-Fi_now"`
3. Stop the capture and save as `out/tcp.pcapng`.
4. About 10 minutes later, while still on the same network, run:
   `python3 task2_measure.py --label "Wi-Fi_10min_later"`
5. Keep both records in `out/throughput.json`. Each invocation performs five transfers and appends its data.
6. Fill the measured medians, spreads, and handshake timings into `out/observation.md`; explicitly disclose the 10-minute interval limitation.

## Handshake analysis

In Wireshark, use `tcp.flags.syn == 1` to locate SYN and SYN-ACK, then locate the final ACK in the same TCP stream. Record packet numbers and raw initial sequence numbers (disable relative sequence numbers in TCP preferences if needed). Expand TCP options to read MSS, Window Scale and SACK Permitted. Effective advertised window is the 16-bit advertised window multiplied by `2^(window-scale shift count)`. Compare this value with bytes in flight later in the transfer.

If live capture is blocked, use the official Kurose–Ross trace archive and explicitly state that it is the authors' trace, not your traffic: https://www-net.cs.umass.edu/wireshark-labs/wireshark-traces-9e.zip. The official lab page is https://www-net.cs.umass.edu/kurose_ross/wireshark.php.

## Limitation to disclose

The assignment asks for two networks, or—if only one network is available—measurements at two very different times of day. Two samples 10 minutes apart are a practical time-limited fallback, but they do not fully meet that comparison requirement and could receive a deduction. Do not claim the samples came from different networks.
