# Declared operator usability protocol

**Owner**: Spec 001 measurement artifacts; Spec 021 investigation tasks; Spec 022 UI integration; Spec 025 connection tasks.
**Status**: Acceptance protocol; no participant results are claimed.

Before recruiting, publish the tested build, deployment/adapter versions, fixture set, task instructions, participant eligibility, timing rules, permitted assistance and failure rubric. Use intended operators who did not build the tested feature. A cohort contains exactly ten participants. Each participant must finish all assigned primary tasks correctly within the specified per-task time limit; report task-level outcomes as well as participant pass/fail.

Investigation tasks require locating the relevant observed failure or evidence gap, identifying affected declared work or unknown impact, and selecting an evidence-justified next action within two minutes. Include successful and recovered executions as controls. Connection tasks require setup through disabled registration within ten minutes with identity infrastructure provisioned, plus identifying authority, authentication and delivery assurance within two minutes. Declare external consent/approval waiting separately. No moderator coaching, developer console or CLI assistance is permitted on the measured UI tasks.

The acceptance rule is **at least 9 of 10 participants**, replicated in a **second independent cohort of ten new participants** before the corresponding usability capability is advertised. Publish both cohorts separately, including all failures, incomplete tasks, exclusions and elapsed times. Do not pool cohorts to hide a miss or replace failed participants. A material UI/task change requires a new versioned protocol and replication on the changed build. Counterbalance task order and avoid reusing training answers as test tasks.

This is an operational acceptance rule for a declared protocol, not a statistical estimate that 90% of all customers will succeed. Any statistical inference must disclose its method and uncertainty. Automated, fake-host and synthetic tests cannot substitute for human measurements.

The M0 engineering preview may reach users after its technical acceptance gates, with usability explicitly unvalidated. A first cohort informs iteration; two passing independent cohorts are required before advertising the measured find-the-break usability capability. The complete provider, enterprise or multi-framework product is not a prerequisite for measuring the M0 interface.

Task ownership: 021 T020 is the independently completable technical UI gate. 021 T024 owns registration, execution and publication of both usability cohorts. Only T024 gates the advertised measured usability claim; it is not a dependency of M0 preview availability.
