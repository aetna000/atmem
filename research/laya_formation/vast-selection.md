# Vast.ai selection worksheet

**Queried:** 2026-10-11 (live on-demand marketplace)
**State:** selection prepared; authentication required before rental
**Spend so far:** USD 0

## Frozen eligibility

- one verified, rentable CUDA GPU;
- provider reliability at least `0.99`;
- at least 24 GiB advertised VRAM (stricter than FR-021's 16 GiB floor);
- at least 100 GB available disk and one direct port;
- exclude VM-deverified offers;
- on-demand only until off-instance checkpoint synchronization is proven.

## Preferred class

The live query found non-VM-deverified RTX 5090 offers with 32,607 MiB VRAM at
approximately USD 0.469/hour. The preferred offer at query time combined about
`0.9961` reliability, `199.1` DLPerf, 6.2 GB/s reported disk bandwidth and
roughly 559/494 Mbit/s download/upload. Offer IDs are ephemeral, so eligibility
and total cost must be re-evaluated immediately before creation rather than
treating this snapshot as a reservation.

RTX 3090 offers were cheaper but are not selected for the requested few-hour
turnaround. RTX 4090/A100 alternatives remain fallbacks if the 5090 image fails
the pinned PyTorch/Laya smoke or the qualifying 5090 offer disappears.

## Cost ceiling

For a conservative eight-hour 5090 allowance and 100 GB disk:

- compute: approximately `8 * 0.467 = USD 3.74`;
- storage: approximately `8 * (100 * 0.333 / 720) = USD 0.37`;
- transfer: reserve `USD 0.25` for synthetic inputs and recovered artifacts;
- reliability/retry reserve: one additional eight-hour attempt, `USD 4.36`;
- expected worst planned total: approximately `USD 8.72`.

This is below the USD 20 hard ceiling. There is no automatic top-up. The first
rental must run the representative smoke, prove fresh-process restart, and copy
a checksum-verified checkpoint to owner-controlled storage before the full run.
Re-query and recalculate before creation; destroy the instance after verified
artifact recovery.

## Authentication gate

The isolated official Vast CLI can perform anonymous offer search, but no Vast
API credential is available locally and the authenticated user check returns
HTTP 403. Do not place a key in this file, shell history, process arguments or
the repository. Supply it through an approved secret store or an interactive
CLI login before rental.
