import { createCipheriv, createDecipheriv, randomBytes, randomUUID } from "node:crypto";
import { chmod, mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";

export interface SpoolEnvelope {
  event_id: string;
  producer_instance_id: string;
  producer_epoch: string;
  producer_sequence: number;
  event_time: string;
  [key: string]: unknown;
}

interface SpoolState {
  format: "atmem-openclaw-execution-spool-v1";
  producerInstanceId: string;
  producerEpoch: string;
  nextSequence: number;
  pending: SpoolEnvelope[];
}

interface EncryptedSpool {
  format: "atmem-openclaw-encrypted-execution-spool-v2";
  suite: "AES-256-GCM";
  nonce: string;
  ciphertext: string;
  tag: string;
}

const SPOOL_AAD = Buffer.from("atmem-openclaw-encrypted-execution-spool-v2", "utf8");

/** A bounded, atomic local spool. Removal requires a durable terminal receipt. */
export class ExecutionSpool {
  private state: SpoolState | null = null;
  private serial: Promise<unknown> = Promise.resolve();

  constructor(
    private readonly filePath: string,
    private readonly maxPending = 2048,
    private readonly maxAgeMs = 7 * 24 * 60 * 60 * 1000,
    private readonly keyPath = path.resolve(
      path.dirname(filePath), "..", ".atmem-evidence-keys", "openclaw-spool.key",
    ),
  ) {
    if (maxPending < 2) throw new Error("execution spool capacity must be at least 2");
  }

  enqueue(value: Record<string, unknown>): Promise<SpoolEnvelope> {
    return this.exclusive(async () => {
      const state = await this.load();
      this.expirePending(state, Date.now() - this.maxAgeMs);
      const envelope: SpoolEnvelope = {
        ...value,
        event_id: randomUUID(),
        producer_instance_id: state.producerInstanceId,
        producer_epoch: state.producerEpoch,
        producer_sequence: state.nextSequence++,
        event_time: new Date().toISOString(),
      };
      state.pending.push(envelope);
      if (state.pending.length > this.maxPending) {
        const dropped = state.pending.length - this.maxPending + 1;
        const removed = state.pending.splice(0, dropped);
        state.pending.unshift({
          event_type: "capture.gap",
          run_id: String(envelope.run_id ?? "capture-spool"),
          payload: {
            reason: "spool_capacity_exceeded",
            dropped_count: removed.length,
            first_sequence: removed[0]?.producer_sequence,
            last_sequence: removed.at(-1)?.producer_sequence,
          },
          event_id: randomUUID(),
          producer_instance_id: state.producerInstanceId,
          producer_epoch: state.producerEpoch,
          producer_sequence: state.nextSequence++,
          event_time: new Date().toISOString(),
        });
      }
      await this.persist(state);
      return envelope;
    });
  }

  flush(send: (event: SpoolEnvelope) => Promise<unknown>): Promise<number> {
    return this.exclusive(async () => {
      const state = await this.load();
      let acknowledged = 0;
      while (state.pending.length) {
        const result = await send(state.pending[0]);
        const receipt = result as {
          decision?: unknown; durably_accepted?: unknown; durably_classified?: unknown;
        } | null;
        const accepted = receipt?.durably_accepted === true;
        const classifiedConflict = receipt?.decision === "conflict" &&
          receipt?.durably_classified === true;
        if (!accepted && !classifiedConflict) {
          throw new Error("AtMem did not confirm a durable terminal execution-event decision");
        }
        state.pending.shift();
        acknowledged += 1;
        await this.persist(state);
      }
      return acknowledged;
    });
  }

  async snapshot(): Promise<Readonly<SpoolState>> {
    return this.exclusive(async () => ({ ...(await this.load()), pending: [...(await this.load()).pending] }));
  }

  private exclusive<T>(action: () => Promise<T>): Promise<T> {
    const next = this.serial.then(action, action);
    this.serial = next.then(() => undefined, () => undefined);
    return next;
  }

  private async load(): Promise<SpoolState> {
    if (this.state) return this.state;
    try {
      const wrapper = JSON.parse(await readFile(this.filePath, "utf8")) as EncryptedSpool;
      if (wrapper.format !== "atmem-openclaw-encrypted-execution-spool-v2") {
        throw new Error("unsupported execution spool format");
      }
      const key = await this.loadOrCreateKey();
      const decipher = createDecipheriv(
        "aes-256-gcm", key, Buffer.from(wrapper.nonce, "base64"),
      );
      decipher.setAAD(SPOOL_AAD);
      decipher.setAuthTag(Buffer.from(wrapper.tag, "base64"));
      const plain = Buffer.concat([
        decipher.update(Buffer.from(wrapper.ciphertext, "base64")), decipher.final(),
      ]).toString("utf8");
      const value = JSON.parse(plain) as SpoolState;
      if (value.format !== "atmem-openclaw-execution-spool-v1" || !Array.isArray(value.pending)) {
        throw new Error("unsupported decrypted execution spool state");
      }
      // Pending events retain their original epoch. New events get a fresh
      // epoch and sequence after every plugin process start.
      this.state = {
        ...value,
        producerEpoch: randomUUID(),
        nextSequence: 1,
      };
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code !== "ENOENT") throw error;
      this.state = {
        format: "atmem-openclaw-execution-spool-v1",
        producerInstanceId: randomUUID(),
        producerEpoch: randomUUID(),
        nextSequence: 1,
        pending: [],
      };
    }
    await this.persist(this.state);
    return this.state;
  }

  private async persist(state: SpoolState): Promise<void> {
    await mkdir(path.dirname(this.filePath), { recursive: true, mode: 0o700 });
    const key = await this.loadOrCreateKey();
    const nonce = randomBytes(12);
    const cipher = createCipheriv("aes-256-gcm", key, nonce);
    cipher.setAAD(SPOOL_AAD);
    const ciphertext = Buffer.concat([
      cipher.update(JSON.stringify(state), "utf8"), cipher.final(),
    ]);
    const wrapper: EncryptedSpool = {
      format: "atmem-openclaw-encrypted-execution-spool-v2",
      suite: "AES-256-GCM",
      nonce: nonce.toString("base64"),
      ciphertext: ciphertext.toString("base64"),
      tag: cipher.getAuthTag().toString("base64"),
    };
    const temporary = `${this.filePath}.${process.pid}.${randomUUID()}.tmp`;
    await writeFile(temporary, `${JSON.stringify(wrapper)}\n`, { encoding: "utf8", mode: 0o600 });
    await rename(temporary, this.filePath);
    await chmod(this.filePath, 0o600);
  }

  private async loadOrCreateKey(): Promise<Buffer> {
    await mkdir(path.dirname(this.keyPath), { recursive: true, mode: 0o700 });
    try {
      const encoded = (await readFile(this.keyPath, "utf8")).trim();
      const key = Buffer.from(encoded, "base64");
      if (key.length !== 32) throw new Error("execution spool key must be 256 bits");
      return key;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      const key = randomBytes(32);
      await writeFile(this.keyPath, `${key.toString("base64")}\n`, {
        encoding: "utf8", mode: 0o600, flag: "wx",
      });
      await chmod(this.keyPath, 0o600);
      return key;
    }
  }

  private expirePending(state: SpoolState, cutoff: number): void {
    const expired = state.pending.filter(event => Date.parse(event.event_time) < cutoff);
    if (!expired.length) return;
    state.pending = state.pending.filter(event => Date.parse(event.event_time) >= cutoff);
    state.pending.unshift({
      event_type: "capture.gap",
      run_id: String(expired.at(-1)?.run_id ?? "capture-spool"),
      payload: {
        reason: "spool_retention_expired",
        dropped_count: expired.length,
        first_sequence: expired[0].producer_sequence,
        last_sequence: expired.at(-1)?.producer_sequence,
      },
      event_id: randomUUID(),
      producer_instance_id: state.producerInstanceId,
      producer_epoch: state.producerEpoch,
      producer_sequence: state.nextSequence++,
      event_time: new Date().toISOString(),
    });
  }
}
