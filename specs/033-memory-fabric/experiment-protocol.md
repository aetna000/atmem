# Experimental protocol — draft, not measured results

## Hypotheses

- H1: Under mixed load with measurable queue contention, scheduling improves
  authorized on-time interactive goodput relative to strong simple baselines.
- H2: Revalidation and evidence costs can be quantified without bypassing them.
- H3: Reserved bulk/tenant service bounds interference under declared admission
  and non-preemption assumptions, at a measurable interactive-latency cost.
- H0: Simpler isolated worker pools or the unchanged local path are as good or
  better. Retain and report this result if observed.

## Measurement definitions

One monotonic clock per local experiment; all times in seconds since the declared
start. For request i: scheduled arrival a, observed admission b, worker start s,
terminal time t and optional deadline d. End-to-end successful latency is t-a;
generator lag is b-a; queue wait is s-b. Missing admission/start is null, not zero.
A finite observation horizon H censors unfinished work; arrivals satisfy
0 <= a < H, and observed events must be <= H. All timestamps share the same
monotonic origin. Admission after H is not an observed event in that run.
A request completing at or after its deadline is not an on-time delivery.

Every offered request has exactly one observed outcome: completed, refused,
expired, cancelled, error or censored. Completion describes observed work ending,
not successful governed disclosure. Independent nullable boolean fields record
authorization at release, evidence completeness and output parity. Authorized
on-time goodput is unavailable when any completed row has indeterminate verification
(no false flag and at least one unknown flag);
otherwise only on-time completions with all three true qualify. Known false
values are reported as verification failures, never converted into goodput.
Synthetic booleans are fixture assertions, not proof of runtime safety.
Known-failed, indeterminate, verified-late and verified-on-time categories
partition completed work. Goodput is scoped to completions observed within H,
not a forecast of eventual outcomes for censored work. A separate record digest
binds the observation set and horizon; the workload digest intentionally stays
the same across policies with the same requests.

The authority's first linearized terminal event wins; later worker events remain
in the raw event history and cannot rewrite it. P0a validates supplied terminal
observations, not event reduction or the authority itself. P1 defines the ordering
of simultaneous events explicitly (revocation/cancel/expiry before release at a
tie). A deadline passed by H makes on-time success impossible, but absent an
observed terminal event the row remains censored with a deadline-missed flag;
the report must not invent an observed expiry. Cancellation/resource cleanup
remain separate. Optional numeric authority generation and revocation ACK time
are retained as uninterpreted synthetic metadata, not authorization evidence.

Report:

- offered count and every outcome count/rate, globally and per lane;
- completed-latency p50/p95/p99 using nearest rank (ceil(p*n), 1-indexed), both
  scheduled-arrival-to-terminal and admission-to-terminal; each summary includes
  sample count, offered denominator, failure and censor rates;
- completed count / H and completed bytes / H, separately per lane;
- interactive deadline success / all offered deadline-bearing interactive work;
- generator lag, queue wait, service time, oldest pending age, max bulk wait,
  and uncertainty/unknown values where not instrumented;
- policy/capture/version identity, hardware, warmup, arrivals, raw observations,
  dependencies, seed, git revision and dirty state.

Do not assign a fake latency to dropped requests or silently exclude their
counts. Always place survivor latency next to on-time goodput and outcome rates.
Byte throughput is not interchangeable with completed recall requests per second.
For non-delivered work, distinguish revocation withholding from deadline expiry.

Empty percentile samples yield null. Only 0 < p <= 1 is accepted; ties retain
their observed value. Also report all-offered on-time-verified completion bounds:
rank against all offered requests, treating non-successes as infinite; an
unattainable quantile is explicitly labeled, not serialized as JSON infinity.
This is a success-bound diagnostic, not a latency estimate for withheld work.
Cross-policy survivor-percentile comparisons require predeclared outcome-rate
tolerance; until configured, they are descriptive only.

P0a has a versioned, closed field schema with no arbitrary content/metadata dicts,
synthetic request IDs and controlled reason categories. It imports no AtMem
runtime, reads no user home/environment and does no file I/O. Callers may choose
where to save synthetic reports. This restriction prevents accidental content
capture; it is not a general detector for secrets encoded in numeric fields.
Real reports additionally require an explicit generator-lag budget; exceedance
invalidates comparative results, while preserving samples. The budget is frozen
before running, not adjusted after inspecting results.

## Workloads and comparisons

P0a implements only schedule generation and report accounting. Real P0b runs use
unchanged APIs with synthetic retained content and protected evidence. Compare
fixed-rate and seeded Poisson arrivals, plus bursts, at load points from light
load through saturation. Distinguish offered/admitted load and bounded backlog.
Keep byte-size and compute-cost distributions independent.

Include interactive-only, mixed recall/write/artifact capture, continuous bulk,
tenant skew, bad estimates, revocation/delete races, cancellations and evidence
failure. Test text and original multimodal fixture bytes. The source PDF's
80/15/5 mixture is one calibration profile, not the whole result.

Before final measurements, freeze a machine-readable manifest with dataset and
configuration digests, all load points, capacities, seeds, observation/warmup
windows and the statistical method. Use at least five independent runs per
configuration for a pilot; choose final repeat/sample counts from a separate
precision study, not from whether results look favorable. Use paired workloads
and bootstrap uncertainty across independent runs (not individual correlated
requests). Keep workload tuning seeds separate from held-out evaluation seeds.
Held-out mixtures must also differ from tuning mixtures. Give every policy the
same maximum tuning-trial budget; disclose its search space (identical parameter
grids are not meaningful for policies with different parameters).

Before P0b final runs, select the primary load point, primary comparison and
minimum practically meaningful effect using pilot data. The primary metric is
authorized on-time interactive completions per second; the primary comparator
is the best simple baseline selected on calibration data, then frozen. Specify
the CI half-width target, stopping/sample-count rule and secondary-comparison
multiplicity treatment in the frozen manifest. Until those fields are set, runs
are exploratory only and cannot support a superiority claim.

At equal total budgets compare FIFO, fixed isolated pools, EDF, estimated-size,
DRR and the combined scheduler. Record preemption/chunk settings explicitly;
chunking enabled for only one variant is a separate ablation, not a fair baseline.
Practical policies do not know future actual service time. Do not compare an
in-process local baseline directly with networked results as a scheduler gain.

## Reporting gate

No target speedup is guaranteed. Report negative runs and dropped work. A result
is publishable only with actual end-to-end integration, safety tests, useful
throughput and fairness context for the claimed deployment. Simulation may be
published separately as mechanism analysis, explicitly bounded by its model.
