import assert from "node:assert/strict";
import {
  createHash,
  createPublicKey,
  verify as verifySignature,
} from "node:crypto";
import { readFileSync } from "node:fs";
import { TextDecoder } from "node:util";

const CONTRACT_ID = "atmem.delegated-context-provider.v1";
const SIGNATURE_DOMAIN = Buffer.from("ATMEM-DELEGATED-CONTEXT-V1\0", "ascii");
const MAX_BYTES = 262_144;
const MAX_LIFETIME_MS = 300_000;
const CLOCK_SKEW_MS = 30_000;
const FIXTURE_ROOT = new URL(
  "../../../docs/contracts/delegated-context-provider-v1/",
  import.meta.url,
);

const TOP_LEVEL_FIELDS = [
  "binding",
  "context",
  "contract_id",
  "created_at",
  "decision",
  "expires_at",
  "idempotency_key",
  "nonce",
  "provider",
  "receipt",
  "signature",
  "source_refs",
  "withhold_reason",
];
const BINDING_FIELDS = [
  "agent_id",
  "run_id",
  "session_id",
  "turn_id",
  "user_id",
  "workspace_id",
];

function fixture(name) {
  return JSON.parse(readFileSync(new URL(name, FIXTURE_ROOT), "utf8"));
}

function clone(value) {
  return structuredClone(value);
}

function fail(code) {
  throw new Error(code);
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

// The contract's fixtures use a restricted RFC 8785 profile: JSON values,
// integral numbers, and fixed ASCII object keys. This is deliberately local to
// the conformance test rather than AtMem's existing canonical JSON helper.
function canonicalJson(value) {
  if (value === null || typeof value === "boolean" || typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) fail("contract_shape");
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  if (typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  fail("contract_shape");
}

function canonicalBytes(value) {
  return Buffer.from(canonicalJson(value), "utf8");
}

function exactFields(value, expected) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    fail("contract_shape");
  }
  const actual = Object.keys(value).sort();
  if (
    actual.length !== expected.length ||
    actual.some((field, index) => field !== [...expected].sort()[index])
  ) {
    fail("contract_shape");
  }
}

function identifier(value, maximum = 256) {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.length > maximum ||
    value.trim() !== value
  ) {
    fail("contract_shape");
  }
}

function strictBase64(value, code) {
  if (
    typeof value !== "string" ||
    !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)
  ) {
    fail(code);
  }
  const decoded = Buffer.from(value, "base64");
  if (decoded.toString("base64") !== value) fail(code);
  return decoded;
}

function validateShape(envelope) {
  exactFields(envelope, TOP_LEVEL_FIELDS);
  if (envelope.contract_id !== CONTRACT_ID) fail("contract_shape");

  exactFields(envelope.provider, ["id", "instance_id", "version"]);
  Object.values(envelope.provider).forEach((value) => identifier(value));

  exactFields(envelope.binding, BINDING_FIELDS);
  Object.values(envelope.binding).forEach((value) => identifier(value));

  exactFields(envelope.receipt, ["contract_id", "id", "sha256"]);
  identifier(envelope.receipt.id, 512);
  identifier(envelope.receipt.contract_id);
  if (!/^[0-9a-f]{64}$/.test(envelope.receipt.sha256)) fail("contract_shape");

  if (typeof envelope.created_at !== "string" || !envelope.created_at.endsWith("Z")) {
    fail("contract_shape");
  }
  if (typeof envelope.expires_at !== "string" || !envelope.expires_at.endsWith("Z")) {
    fail("contract_shape");
  }
  if (!/^[A-Za-z0-9_-]{22,128}$/.test(envelope.nonce)) fail("contract_shape");
  if (!/^dcp-[0-9a-f]{64}$/.test(envelope.idempotency_key)) fail("contract_shape");
  if (
    !Array.isArray(envelope.source_refs) ||
    envelope.source_refs.length > 32 ||
    new Set(envelope.source_refs).size !== envelope.source_refs.length
  ) {
    fail("contract_shape");
  }
  envelope.source_refs.forEach((value) => identifier(value, 512));

  exactFields(envelope.signature, [
    "algorithm",
    "key_id",
    "profile",
    "signed_payload_sha256",
    "value_base64",
  ]);
  if (
    envelope.signature.algorithm !== "ed25519" ||
    envelope.signature.profile !== "ed25519-jcs-subset-v1" ||
    !/^[0-9a-f]{64}$/.test(envelope.signature.signed_payload_sha256)
  ) {
    fail("contract_shape");
  }
  identifier(envelope.signature.key_id);

  if (envelope.decision === "inject") {
    if (envelope.withhold_reason !== null) fail("contract_shape");
    exactFields(envelope.context, [
      "byte_length",
      "bytes_base64",
      "encoding",
      "media_type",
      "sha256",
    ]);
    if (
      envelope.context.encoding !== "base64" ||
      envelope.context.media_type !== "text/plain; charset=utf-8" ||
      !Number.isSafeInteger(envelope.context.byte_length) ||
      envelope.context.byte_length < 1 ||
      envelope.context.byte_length > MAX_BYTES ||
      !/^[0-9a-f]{64}$/.test(envelope.context.sha256)
    ) {
      fail("contract_shape");
    }
  } else if (envelope.decision === "withhold") {
    if (envelope.context !== null) fail("contract_shape");
    exactFields(envelope.withhold_reason, ["code", "retryable"]);
    if (
      !/^[A-Z][A-Z0-9_]{2,63}$/.test(envelope.withhold_reason.code) ||
      typeof envelope.withhold_reason.retryable !== "boolean"
    ) {
      fail("contract_shape");
    }
  } else {
    fail("contract_shape");
  }
}

function idempotencyKey(envelope) {
  const identity = {
    contract_id: envelope.contract_id,
    provider: envelope.provider,
    binding: envelope.binding,
    decision: envelope.decision,
    context_sha256: envelope.context?.sha256 ?? null,
    receipt_id: envelope.receipt.id,
    receipt_sha256: envelope.receipt.sha256,
    source_refs: envelope.source_refs,
    withhold_reason: envelope.withhold_reason,
  };
  return `dcp-${sha256(canonicalBytes(identity))}`;
}

function signingBytes(envelope) {
  const unsigned = clone(envelope);
  delete unsigned.signature;
  return Buffer.concat([SIGNATURE_DOMAIN, canonicalBytes(unsigned)]);
}

function publicKey(trust) {
  const raw = strictBase64(trust.public_key_base64, "trusted_provider");
  if (raw.length !== 32) fail("trusted_provider");
  const ed25519SpkiPrefix = Buffer.from("302a300506032b6570032100", "hex");
  return createPublicKey({
    key: Buffer.concat([ed25519SpkiPrefix, raw]),
    format: "der",
    type: "spki",
  });
}

function trustedRegistration(envelope, trustEntries) {
  const trust = trustEntries.find(
    (entry) =>
      entry.provider_id === envelope.provider.id &&
      entry.provider_version === envelope.provider.version &&
      entry.provider_instance_id === envelope.provider.instance_id &&
      entry.key_id === envelope.signature.key_id,
  );
  if (!trust) fail("trusted_provider");
  for (const [scope, binding] of [
    ["workspace_ids", "workspace_id"],
    ["agent_ids", "agent_id"],
    ["user_ids", "user_id"],
  ]) {
    if (!trust[scope].includes("*") && !trust[scope].includes(envelope.binding[binding])) {
      fail("trusted_provider");
    }
  }
  return trust;
}

function verifyEnvelope(
  envelope,
  { trustEntries, expectedBinding, now, maxLifetimeMs = MAX_LIFETIME_MS },
) {
  validateShape(envelope);

  for (const field of BINDING_FIELDS) {
    if (envelope.binding[field] !== expectedBinding[field]) fail("turn_scope_binding");
  }

  const trust = trustedRegistration(envelope, trustEntries);
  const created = Date.parse(envelope.created_at);
  const expires = Date.parse(envelope.expires_at);
  if (!Number.isFinite(created) || !Number.isFinite(expires) || created >= expires) {
    fail("time_order");
  }
  if (expires - created > maxLifetimeMs) fail("lifetime");
  if (created > now + CLOCK_SKEW_MS) fail("not_created_in_future");
  if (now >= expires) fail("not_expired");

  let contextBytes = Buffer.alloc(0);
  if (envelope.decision === "inject") {
    contextBytes = strictBase64(envelope.context.bytes_base64, "context_base64");
    if (contextBytes.length !== envelope.context.byte_length) fail("context_byte_length");
    try {
      new TextDecoder("utf-8", { fatal: true }).decode(contextBytes);
    } catch {
      fail("context_utf8");
    }
    if (sha256(contextBytes) !== envelope.context.sha256) fail("context_sha256");
  }

  if (idempotencyKey(envelope) !== envelope.idempotency_key) fail("idempotency_binding");

  const signedBytes = signingBytes(envelope);
  if (sha256(signedBytes) !== envelope.signature.signed_payload_sha256) {
    fail("signed_payload_sha256");
  }
  const signature = strictBase64(envelope.signature.value_base64, "signature");
  if (signature.length !== 64 || !verifySignature(null, signedBytes, publicKey(trust), signature)) {
    fail("signature");
  }
  return { contextBytes, decision: envelope.decision };
}

class ReferenceAcceptor {
  constructor(trustEntries) {
    this.trustEntries = trustEntries;
    this.byTurn = new Map();
    this.byNonce = new Map();
    this.byIdempotency = new Map();
  }

  accept(envelope, expectedBinding, now) {
    const verified = verifyEnvelope(envelope, {
      trustEntries: this.trustEntries,
      expectedBinding,
      now,
    });
    const digest = sha256(canonicalBytes(envelope));
    const instance = envelope.provider.instance_id;
    const keys = {
      turn: canonicalJson(envelope.binding),
      nonce: `${instance}\0${envelope.nonce}`,
      idempotency: `${instance}\0${envelope.idempotency_key}`,
    };
    const maps = {
      turn: this.byTurn,
      nonce: this.byNonce,
      idempotency: this.byIdempotency,
    };
    for (const name of ["turn", "nonce", "idempotency"]) {
      const previous = maps[name].get(keys[name]);
      if (previous && previous !== digest) fail(name);
    }
    const idempotent = Object.entries(maps).some(
      ([name, map]) => map.get(keys[name]) === digest,
    );
    for (const [name, map] of Object.entries(maps)) map.set(keys[name], digest);
    return { ...verified, idempotent };
  }
}

const trust = fixture("trust.json");
const inject = fixture("inject.valid.json");
const withhold = fixture("withhold.valid.json");
const replay = fixture("inject.next-turn-same-nonce.valid.json");
const vectors = fixture("test-vectors.json");
const verificationTime = Date.parse(vectors.verification_time);

const acceptedInject = verifyEnvelope(inject, {
  trustEntries: [trust],
  expectedBinding: inject.binding,
  now: verificationTime,
});
assert.deepEqual(
  acceptedInject.contextBytes,
  Buffer.from("Reviewed context 🧠\r\nKeep these bytes.", "utf8"),
);
assert.equal(acceptedInject.decision, "inject");

const acceptedWithhold = verifyEnvelope(withhold, {
  trustEntries: [trust],
  expectedBinding: withhold.binding,
  now: verificationTime,
});
assert.equal(acceptedWithhold.contextBytes.length, 0);
assert.equal(acceptedWithhold.decision, "withhold");

const retryAcceptor = new ReferenceAcceptor([trust]);
assert.equal(retryAcceptor.accept(inject, inject.binding, verificationTime).idempotent, false);
assert.equal(retryAcceptor.accept(inject, inject.binding, verificationTime).idempotent, true);

const executedNegativeIds = [];
function expectFailure(id, expectedCode, action) {
  assert.throws(action, (error) => error instanceof Error && error.message === expectedCode);
  executedNegativeIds.push(id);
}

expectFailure("untrusted-provider", "trusted_provider", () =>
  verifyEnvelope(inject, {
    trustEntries: [],
    expectedBinding: inject.binding,
    now: verificationTime,
  }),
);

for (const field of ["run_id", "turn_id", "session_id", "agent_id", "user_id", "workspace_id"]) {
  const id = `wrong-${field.replace("_id", "")}-binding`;
  expectFailure(id, "turn_scope_binding", () =>
    verifyEnvelope(inject, {
      trustEntries: [trust],
      expectedBinding: { ...inject.binding, [field]: `wrong-${field}` },
      now: verificationTime,
    }),
  );
}

expectFailure("expired", "not_expired", () =>
  verifyEnvelope(inject, {
    trustEntries: [trust],
    expectedBinding: inject.binding,
    now: Date.parse(inject.expires_at),
  }),
);
expectFailure("future-created", "not_created_in_future", () =>
  verifyEnvelope(inject, {
    trustEntries: [trust],
    expectedBinding: inject.binding,
    now: Date.parse("2026-09-01T11:59:00Z"),
  }),
);
expectFailure("excessive-lifetime", "lifetime", () => {
  const changed = clone(inject);
  changed.expires_at = "2026-09-01T12:10:00Z";
  verifyEnvelope(changed, {
    trustEntries: [trust],
    expectedBinding: changed.binding,
    now: verificationTime,
  });
});
expectFailure("context-digest-mismatch", "context_sha256", () => {
  const changed = clone(inject);
  changed.context.sha256 = "b".repeat(64);
  verifyEnvelope(changed, {
    trustEntries: [trust],
    expectedBinding: changed.binding,
    now: verificationTime,
  });
});
expectFailure("context-length-mismatch", "context_byte_length", () => {
  const changed = clone(inject);
  changed.context.byte_length += 1;
  verifyEnvelope(changed, {
    trustEntries: [trust],
    expectedBinding: changed.binding,
    now: verificationTime,
  });
});
expectFailure("invalid-base64", "context_base64", () => {
  const changed = clone(inject);
  changed.context.bytes_base64 = "not base64";
  verifyEnvelope(changed, {
    trustEntries: [trust],
    expectedBinding: changed.binding,
    now: verificationTime,
  });
});
expectFailure("signature-tamper", "signature", () => {
  const changed = clone(inject);
  const signature = Buffer.from(changed.signature.value_base64, "base64");
  signature[0] ^= 1;
  changed.signature.value_base64 = signature.toString("base64");
  verifyEnvelope(changed, {
    trustEntries: [trust],
    expectedBinding: changed.binding,
    now: verificationTime,
  });
});
expectFailure("idempotency-tamper", "idempotency_binding", () => {
  const changed = clone(inject);
  changed.idempotency_key = `dcp-${"0".repeat(64)}`;
  verifyEnvelope(changed, {
    trustEntries: [trust],
    expectedBinding: changed.binding,
    now: verificationTime,
  });
});
expectFailure("unknown-field", "contract_shape", () => {
  const changed = clone(inject);
  changed.raw_prompt = "must never be accepted";
  verifyEnvelope(changed, {
    trustEntries: [trust],
    expectedBinding: changed.binding,
    now: verificationTime,
  });
});
expectFailure("inject-with-reason", "contract_shape", () => {
  const changed = clone(inject);
  changed.withhold_reason = { code: "POLICY_DENIED", retryable: false };
  verifyEnvelope(changed, {
    trustEntries: [trust],
    expectedBinding: changed.binding,
    now: verificationTime,
  });
});
expectFailure("withhold-with-context", "contract_shape", () => {
  const changed = clone(withhold);
  changed.context = clone(inject.context);
  verifyEnvelope(changed, {
    trustEntries: [trust],
    expectedBinding: changed.binding,
    now: verificationTime,
  });
});
expectFailure("second-result-same-turn", "turn", () => {
  const acceptor = new ReferenceAcceptor([trust]);
  acceptor.accept(inject, inject.binding, verificationTime);
  acceptor.accept(withhold, withhold.binding, verificationTime);
});
expectFailure("nonce-replay-other-turn", "nonce", () => {
  const acceptor = new ReferenceAcceptor([trust]);
  acceptor.accept(inject, inject.binding, verificationTime);
  acceptor.accept(replay, replay.binding, verificationTime);
});

assert.equal(vectors.positive.length, 3);
assert.equal(vectors.negative.length, 20);
assert.deepEqual(
  executedNegativeIds.sort(),
  vectors.negative.map((vector) => vector.id).sort(),
);

console.log("delegated context contract: 3 positive and 20 negative/stateful vectors passed");
