# Investigate in the dashboard

## Start with the question
| View | What it answers |
| --- | --- |
| Sessions | What did this conversation or run do? |
| Memory | What is retained and eligible for retrieval? |
| Decisions | Why was context selected or withheld? |
| Audit | Which operations and governance changes were recorded? |
| Settings | How is capture, access and integration configured? |

## Go from summary to evidence
Open a session, inspect its request and response, then the context disposition and
individual tool events. An Investigator can inspect retained text and play captured
media; a Viewer sees metadata/hashes only. Export requires Evidence Collector or
Administrator access.

## Interpret gaps honestly
Prepared memory is not delivery confirmation. An absent image can mean the host
did not expose bytes, data capture was disabled, or the event predates supported
capture. A legacy hash cannot restore the missing content. Inspect coverage rather
than interpreting a green integrity check as proof of a complete real-world outcome.

## If the page or run looks stale
Check the installed AtMem and bridge versions, restart long-running clients after
upgrading and run one fresh supported-host turn. Never relabel old incomplete
evidence as complete just because the bridge was upgraded.
