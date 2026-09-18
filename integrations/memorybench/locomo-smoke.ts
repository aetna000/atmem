// Copy to the pinned MemoryBench checkout root. Plumbing check, NOT a score.
import { createHash } from "node:crypto"
import { mkdtemp, readFile, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { createProvider } from "./src/providers"
import { LoCoMoBenchmark } from "./src/benchmarks/locomo"

const root = await mkdtemp(join(tmpdir(), "atmem-locomo-smoke-"))
process.env.ATMEM_BENCHMARK_ROOT = root
process.env.ATMEM_BENCHMARK_EMBEDDING = "hashing"
try {
  const benchmark = new LoCoMoBenchmark()
  await benchmark.load()
  const questions = benchmark.getQuestions({ limit: 5 })
  const sessions = new Map(questions.flatMap(q => benchmark.getHaystackSessions(q.questionId)).map(s => [s.sessionId, s]))
  const provider = createProvider("atmem")
  await provider.initialize({ apiKey: "" })
  const start = performance.now()
  const receipt = await provider.ingest([...sessions.values()], { containerTag: "locomo-smoke" })
  await provider.awaitIndexing(receipt, "locomo-smoke")
  const ingestionMs = Math.round(performance.now() - start)
  const results = []
  for (const q of questions) {
    const start = performance.now()
    const context = await provider.search(q.question, { containerTag: "locomo-smoke", threshold: 0.3 })
    if (!context.length) throw new Error(`No context for smoke question ${q.questionId}`)
    results.push({ questionId: q.questionId, contextReturned: true, searchMs: Math.round(performance.now() - start) })
  }
  const dataset = await readFile("data/benchmarks/locomo/locomo10.json")
  console.log(JSON.stringify({ diagnosticOnly: true, accuracyScore: null, embedding: "hashing",
    datasetSha256: createHash("sha256").update(dataset).digest("hex"),
    sessions: sessions.size, chunks: receipt.documentIds.length, ingestionMs, results }, null, 2))
} finally {
  await rm(root, { recursive: true, force: true })
}
