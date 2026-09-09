# Governed multimodal observations

AtMem stores scoped artifact references and derived observations for images,
audio, video, files and tool artifacts. Original bytes remain in host custody
by default. A controlled copy, thumbnail or transcode requires an explicit
storage policy and a receipt naming the copied-byte digest.

Supported locators are secret-free `host`, `openclaw`, `file` and `tool`
references resolved through a bounded host callback. Credentials, query
parameters and fragments are rejected. The host is responsible for access
control, stable exact-byte digests, malware checks, retention and deletion of
host-held originals.

Processors receive only authorized bounded bytes. Hosted processing requires
explicit egress approval; receipts record local/hosted execution, redaction,
model/provider/revision, prompt/configuration digest and evidence region.
Observations are model inferences with confidence and provenance, not ground
truth.

Consent and scope are revalidated before storage, indexing, retrieval and
delivery. Revocation increments the consent generation, tombstones controlled
observations and indexes, and prevents late processor output from activating.
Receipts honestly distinguish controlled copies from host originals and from
backup copies governed by the declared backup-retention policy.
