# Governed multimodal observations

AtMem stores scoped artifact references and derived observations for images,
audio, video, files and tool artifacts. In the 2.3.4b1 configured full-fidelity
Black Box profile, available original bytes are copied into protected AtMem
evidence and its artifact vault. The host reference remains provenance, not
a recovery dependency. Metadata-only/off capture cannot claim original-byte
reconstruction. Derived observations and exact evidence are distinct: a caption
does not replace the image, audio or video. A thumbnail or transcode must name
its source and copied-byte digest.

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
