#!/usr/bin/env python3
"""Week 4 · Task 3 — Beat the fixed window.

Textbook §3.7.

`FixedWindow` is a sender that never adapts. It picks a window and keeps it,
forever, no matter what the network says back. It is not a strawman: it is what
you get if you skip congestion control entirely, and it was the internet's
actual failure mode in October 1986.

Write `YourControl` and beat it on the harness:

    python3 bench.py
    python3 bench.py --yours

The interface is two events and one number:

    .window        how many packets you are willing to have in flight
    .on_ack()      one packet made it there and back
    .on_loss()     a packet was dropped, or timed out waiting for its ACK

That is all the information a real TCP sender has. It cannot see the queue,
it cannot see the link rate, and neither can you. You infer them from these
two events, which is the entire idea of §3.7.
"""


class FixedWindow:
    """Send 64 packets at a time and never listen."""

    def __init__(self):
        self.window = 64

    def on_ack(self):
        pass

    def on_loss(self):
        pass


class YourControl:
    """Your congestion control.

    Things worth knowing before you start:

    * The link drains one packet per slot and the round trip is 20 slots, so
      the pipe holds about 20 packets. Above that you are only filling a queue.
    * The queue is 10 packets deep and drops from the tail. Filling it does not
      make you faster - it makes you slower, and everybody behind you too.
    * Cutting hard on every loss costs you throughput. Not cutting costs you
      correctness. §3.7 is the argument about where between those to sit.
    * You are allowed to grow differently before and after your first loss.
      That distinction has a name in the textbook.
    """

    # The bandwidth-delay product is 1 packet/slot * 20 slots = 20 packets.
    # A small amount of queueing headroom keeps the link busy without filling it.
    MAX_WINDOW = 24.0
    INITIAL_SSTHRESH = 12.0
    BACKOFF = 0.80

    def __init__(self):
        self.window = 1.0
        self.ssthresh = self.INITIAL_SSTHRESH
        # A single timeout can expose several packets dropped in one burst.
        # Treat losses within one window of ACK progress as one congestion event.
        self.acks_since_loss = 10**9
        self.loss_recovery_acks = 1

    def on_ack(self):
        if self.window < self.ssthresh:
            # Slow start: roughly doubles the window every RTT.
            self.window += 1.0
        else:
            # Congestion avoidance: additive increase of about one packet/RTT.
            self.window += 1.0 / max(self.window, 1.0)

        self.window = min(self.window, self.MAX_WINDOW)
        self.acks_since_loss += 1

    def on_loss(self):
        # Several timed-out packets may be reported back-to-back by the harness.
        # Do not multiply-backoff repeatedly for the same loss burst.
        if self.acks_since_loss < max(self.loss_recovery_acks, 20):
            return

        self.window = max(2.0, self.window * self.BACKOFF)
        self.ssthresh = self.window
        self.loss_recovery_acks = max(1, int(self.window))
        self.acks_since_loss = 0
