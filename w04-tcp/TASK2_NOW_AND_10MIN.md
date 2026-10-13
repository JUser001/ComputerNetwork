# Task 2 quick path — one network, two measurements 10 minutes apart

This is the quickest honest fallback if you cannot use a second network or wait for morning/evening. It is **not exactly the time-of-day comparison specified in the lab**, so mention the limitation in `out/observation.md`.

## First run — now

1. Open a terminal in this `w04-tcp` folder.
2. Start Wireshark on the interface carrying your traffic. Set the **capture filter** to `tcp port 443` and start capturing.
3. Run this command; it takes five measurements and appends them to `out/throughput.json`:

   ```bash
   python3 task2_measure.py --label "Wi-Fi_now"
   ```

4. Stop Wireshark and save the capture as `out/tcp.pcapng`.

## Second run — about 10 minutes later

Stay on the **same network** and run:

```bash
python3 task2_measure.py --label "Wi-Fi_10min_later"
```

The script appends a second labelled record. Do **not** delete `out/throughput.json` between the runs. Each run defaults to five transfers and records the individual rates, median, min/max spread, and median TCP connect/handshake timing.

## Finish the report

- Open `out/throughput.json` and copy each label's median Mbps, min/max spread, and median handshake time into `out/observation.md`.
- State that both samples used the same network only 10 minutes apart; this is a time-limited comparison, not two networks or two very different times of day.
- In Wireshark, find the SYN, SYN-ACK and final ACK for one TCP stream, then record packet numbers, raw initial sequence numbers, MSS, window scale and SACK-permitted. Calculate the scaled advertised receive window and compare it with bytes in flight.
- Run `python3 test_tasks.py --task 2`. A capture and both actual five-run measurement records must exist for the checks to pass.

## Important

Do not create fake measurements or label the second sample as a different network. This two-label approach may satisfy the basic file-format checks, but the instructor may still treat the 10-minute interval as a deviation from the lab's stated fallback.
