# Single-image amd64 runtime control — prospective v1

External metadata preflight selected six tasks without outcomes; all six recipe
and identity checks passed. Registry descriptors resolve all six mutable tags
to amd64 digests, each roughly 1 GB compressed. No image was pulled in metadata
preflight, and none of these tasks is environment/reference/model-qualified.

This separate control takes ONLY the first already-selected task,
`marshmallow-code__marshmallow-1229`, at the already-recorded immutable registry
digest. No task replacement or recipe rewrite. Verify selection/metadata/registry
bindings before dispatch. Pull at most this one image: 180-second limit, 8 GiB
minimum host free space, 2 MB diagnostic-output limit. If the guard fails, retain
that failure instead of proceeding with the batch. Shared cache layers are not
pruned or removed. No broad Docker or host cleanup is permitted.

Then run one disposable labeled container for at most 30 seconds with no mounts,
network disabled, read-only root, all capabilities dropped, no-new-privileges,
1 CPU, 512 MiB memory, 64 PIDs and a 64 MiB noexec/nosuid/nodev tmpfs. Override
the entrypoint. Run only `uname -m` and the supplied testbed interpreter with
`-I -S` on a fixed standard-library version/platform query. No repository setup,
tests, gold patch, model, task statement or owner credentials are supplied.
Remove only this exact task-created container if timeout requires cleanup.

Record architecture, version and actual unpacked image size, raw output,
runtime/resource observations and any failure. A successful control proves only
that this image's shell/interpreter can execute under constrained amd64 emulation
on the current ARM worker. It does not qualify repository dependencies, hidden
tests, reference behavior, AtMem extraction or coding-model performance.
