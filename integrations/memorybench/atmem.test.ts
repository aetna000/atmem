import { test, expect } from "bun:test"
import { mkdtemp, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { createProvider, getAvailableProviders } from "./src/providers"

test("AtMem is registered and survives the real Python worker lifecycle", async () => {
  const root = await mkdtemp(join(tmpdir(), "atmem-memorybench-test-"))
  process.env.ATMEM_BENCHMARK_ROOT = root
  process.env.ATMEM_BENCHMARK_EMBEDDING = "hashing"
  try {
    expect(getAvailableProviders()).toContain("atmem")
    const provider = createProvider("atmem")
    await provider.initialize({ apiKey: "" })
    const sessions = [{ sessionId: "session-1", messages: [{ role: "user" as const, content: "My preferred airport is Sydney Airport." }] }]
    const receipt = await provider.ingest(sessions, { containerTag: "test" })
    expect(receipt.documentIds.length).toBeGreaterThan(0)
    expect((await provider.ingest(sessions, { containerTag: "test" })).documentIds).toEqual(receipt.documentIds)
    await provider.awaitIndexing(receipt, "test")
    const rows = await provider.search("preferred airport", { containerTag: "test" })
    expect(JSON.stringify(rows)).toContain("Sydney Airport")
    await provider.clear("test")
    await expect(provider.search("airport", { containerTag: "test" })).rejects.toThrow()
  } finally {
    await rm(root, { recursive: true, force: true })
    delete process.env.ATMEM_BENCHMARK_ROOT
    delete process.env.ATMEM_BENCHMARK_EMBEDDING
  }
}, 30000)
