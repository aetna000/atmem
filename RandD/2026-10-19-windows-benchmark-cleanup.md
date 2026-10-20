# Windows benchmark scratch cleanup completed

Removed **111 old benchmark source workspaces**, containing 5,218,136,910 bytes
of regular-file payload. The owned source-scratch directory is now empty.
Only exact `atmem-swe-lite-<32 hex digits>` children of
`/home/user/atmem-swebench-20261019/sources` were eligible.

The entire source-scratch collection was archived to MEM before deletion:
`/Volumes/MEM/AtMem-SWEbench-Threeway-20261019/windows-source-workspaces/sources.tar.gz.aesgcm`.
Compressed archive size: 2,932,696,226 bytes. AES-256-GCM authentication,
independent decryption and plaintext SHA256 verification passed:
`32249c72506f0a42cd03ab1fd347048eeb1fd15e63ab6e08f08f979933620c44`.

Recovery key and nonce remain in a mode-0600 file under the mode-0700 local
`/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/windows-source-workspace-recovery-20261019/`.
The MEM manifest holds the authentication tag, original directory inventory,
checksums and exact source root. Recover by authenticating/decrypting with this
key and manifest, verifying the SHA256 above, then extracting the resulting
gzip tar into an explicitly chosen empty source-recovery directory. Do not
overwrite a current project or extract an unauthenticated archive.

Each source tree's path/type/size/mtime/ctime fingerprint was rechecked before
deletion. Docker had to be idle, and was rechecked for every exact deletion.
The temporary Windows tar was removed after verified transfer. Windows
databases, run results, Cognee states, runtimes, harness, Docker images,
unrelated projects and owner repositories were not deleted. No global prune,
disk format, volume compaction or system-wide TRIM was performed. The payload
count is not a claim that the Windows host VHD shrank by the same amount.

The first inventory and archive transport waits hit their time limits before
any deletion. Resumed the retained complete gzip archive, validated its CRC
and checksum, then transferred and authenticated it; no model trial was rerun
and no source was discarded to bypass those checks.

Machine-readable completion receipt: `2026-10-19-windows-benchmark-cleanup.json`.
