# Read-only review: Homa-inspired AtMem scheduling experiment

Review only the supplied material. No tools, file writes, execution or claims of
validation. Identify conceptual flaws and propose a minimal testable correction.

Existing research runner: one worker, bounded queue of 24, real AtMem recall,
writes including vector synchronization, encrypted evidence capture. Each task
is non-preemptible. Current scheduler gives every fifth dispatch to bulk, then
sorts by (has_deadline, earliest_deadline, static_estimated_cost, arrival).
Cost guesses: artifact 4ms, recall 12ms, write 40ms. All recalls get arrival+1s
deadline. Bulk consists of writes and image/audio/video evidence capture.
Current workload repeats 16 recalls, 3 writes, 1 artifact. FIFO uses a different
executor path than the policy, so the harness itself is a confound. Report calls
substring presence 'output parity', which is not byte-exact baseline parity.
Earlier results were 300/300 completions both; interactive p95 median 395ms FIFO
and 362ms policy; bulk 484ms FIFO and 555ms policy. Small noisy local trials.

Primary Homa docs: SRPT with receiver grants and bounded incoming bytes; a small
fraction of link bandwidth reserved for the oldest message in grants and sender
pacer. RFC suggests 5% FIFO safeguard. This protects against starvation but does
not guarantee bulk completion time no worse than FIFO. DRR tracks service units
rather than job counts. CPU/store service time is not message byte size.

Proposed experiment: shared single-worker dispatcher for all policies. FIFO,
legacy, shortest estimated job first plus measured-service FIFO debt (5%), and
a time-share bulk reservation policy (e.g. fixed 40%, observed actual service
charging), with oldest bulk chosen for owed bulk service. Online per-operation
EWMA estimates initialized from separate calibration; never use future duration.
Priority is service debt first, then urgent trusted deadline, then estimated
service. Negative debt should be bounded so a long non-preemptible job cannot
buy an unlimited future starvation interval. Idle classes do not bank credit.
Explicitly no claim of a hard latency bound without bounded atomic service.
No production mutation. Exact recall comparisons need a stable canonical
snapshot; use separate read and write fixture subjects and canonical oracle
digests outside timed region, and mark authorization-at-release unknown.

Freeze policy parameters before evaluation. Randomize mixes (80/15/5,
50/40/10, 90/5/5), size variation independently; 5 held-out seeds per profile,
balanced randomized trial order, identical dispatcher and budgets, strong FIFO
baseline, all outcomes/evidence/lag reported, paired uncertainty. Measure short
p95, bulk p95 and throughput/progress. Reject universal speedup claims; a preset
bulk <=5% p95 regression tolerance must hold per scenario to accept a candidate.
Can use a separate simulation for chunked/preemptible jobs but never label it
real AtMem throughput. No rerunning parameter searches on held-out results.

Please review fairness debt accounting, how to avoid overfit, deadline interaction,
safe write/read ordering, impossible guarantees, and which minimal candidate is
worth testing first. Be critical and concise (under 1000 words).
