// Copy to MemoryBench src/providers/atmem/index.ts using install.py.
import { spawn } from "node:child_process"
import type { Provider, ProviderConfig, IngestOptions, IngestResult, SearchOptions, IndexingProgressCallback } from "../../types/provider"
import type { UnifiedSession } from "../../types/unified"

export class AtMemProvider implements Provider {
  name = "atmem"
  concurrency = { default: 1, ingest: 1, indexing: 1, search: 1 }
  private key = ""
  private ready = false
  async initialize(config: ProviderConfig): Promise<void> {
    this.key = config.apiKey || process.env.OPENAI_API_KEY || ""
    if ((process.env.ATMEM_BENCHMARK_EMBEDDING || "openai") === "openai" && !this.key) {
      throw new Error("AtMem benchmark requires OPENAI_API_KEY (or hashing for diagnostic tests)")
    }
    this.ready = true
  }
  private call<T>(body: Record<string, unknown>): Promise<T> {
    if (!this.ready) throw new Error("AtMem provider is not initialized")
    return new Promise((resolve, reject) => {
      const child = spawn(process.env.ATMEM_BENCHMARK_PYTHON || "python3",
        ["-m", "atmem.benchmark.memorybench"], {
          env: { ...process.env, OPENAI_API_KEY: this.key }, stdio: ["pipe", "pipe", "pipe"],
        })
      let out = "", err = ""
      const timer = setTimeout(() => { child.kill("SIGTERM"); reject(new Error("AtMem benchmark worker timed out")) }, 600000)
      child.stdout.on("data", data => { out += data.toString() })
      child.stderr.on("data", data => { err = (err + data.toString()).slice(-4000) })
      child.on("error", error => { clearTimeout(timer); reject(error) })
      child.stdin.on("error", () => {})
      child.on("close", code => {
        clearTimeout(timer)
        if (code !== 0) return reject(new Error(`AtMem worker failed (${code}): ${err}`))
        try { resolve(JSON.parse(out) as T) } catch { reject(new Error("Invalid AtMem worker response")) }
      })
      child.stdin.end(JSON.stringify({ ...body, embedding: process.env.ATMEM_BENCHMARK_EMBEDDING || "openai" }))
    })
  }
  async ingest(sessions: UnifiedSession[], options: IngestOptions): Promise<IngestResult> {
    return this.call({ operation: "ingest", sessions, containerTag: options.containerTag })
  }
  async awaitIndexing(result: IngestResult, containerTag: string, onProgress?: IndexingProgressCallback): Promise<void> {
    if (result.documentIds.length) await this.call({ operation: "index", containerTag })
    onProgress?.({ completedIds: result.documentIds, failedIds: [], total: result.documentIds.length })
  }
  async search(query: string, options: SearchOptions): Promise<unknown[]> {
    return this.call({ operation: "search", query, containerTag: options.containerTag,
      limit: options.limit || 10, threshold: options.threshold ?? 0.3,
      budget: Number(process.env.ATMEM_BENCHMARK_CONTEXT_CHARS || 16000) })
  }
  async clear(containerTag: string): Promise<void> {
    await this.call({ operation: "clear", containerTag })
  }
}
