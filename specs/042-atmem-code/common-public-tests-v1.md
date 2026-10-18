# Common public test access — prospective v1

Under T077, give native, pack-only and pack-plus-retrieval arms the same
benchmark-only run_public_tests tool using AtMem's existing MCP transport.
The operator freezes the public source/modes, immutable image, worker source,
protected evidence scope and execution limits. The model can supply only a
bounded UTF-8 unified diff and bounded public pytest selectors. No private
grader, hidden tests, reference patches or image/socket/host-path selection.

Explicit semantics: tests apply the **submitted patch to the public base**,
not an assumed current agent worktree. Empty patch tests the unchanged base.
Apply data-only text patches in a new disposable container copy; reject
out-of-scope paths, binary, symlink, submodule and rename/copy patches. Git
exits before descriptor-relative stopped-copy capture. The existing public
worker then validates original Git identity, removes image Git history and
runs only public tests. No untrusted repository script runs before that step.
Final private grading still requires the actual stopped agent workspace;
public tool results never replace it or become a task pass by themselves.

Reuse the qualified worker/controller limits, network isolation, no host mounts,
capability drop and memory/PID/CPU/output/cleanup guards. Public responses show
at most the last 12,000 output bytes and report display/worker truncation
separately. Preserve the entire request, actual tested candidate, raw output,
source/patch identity and result through AtMem's full protected evidence service.
Encryption or evidence failure withholds a result; no plaintext fallback.
Use at most 20 public-test calls per attempt, equally across arms. Initial
scope is the already qualified Marshmallow task, not the entire task catalog.

Before agent scoring, verify unchanged public tests, a changed-source patch,
malformed/escaping/unsupported patch refusal and actual MCP request binding on
Windows. Verify the privileged Docker broker is not directly executable from
the agent's denied native sandbox. Its registered server accepts no generic
execution tool. Existing owner CLI configuration and Docker group memberships
remain unchanged. Record all failures; no output is an independent anti-cheating,
agent outcome or token-saving guarantee. Freeze matched Windows manifests next.
