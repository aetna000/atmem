"""Install the reviewed AtMem overlay in an isolated MemoryBench checkout."""
import argparse
from pathlib import Path


def install(root: Path):
    changes = {
        "src/providers/index.ts": [
            ('import { RAGProvider } from "./rag"', 'import { RAGProvider } from "./rag"\nimport { AtMemProvider } from "./atmem"'),
            ('  rag: RAGProvider,', '  rag: RAGProvider,\n  atmem: AtMemProvider,'),
        ],
        "src/types/provider.ts": [
            (' | "rag"', ' | "rag" | "atmem"'),
        ],
        "src/utils/config.ts": [
            ('    case "rag":', '    case "atmem":\n      return { apiKey: config.openaiApiKey }\n    case "rag":'),
        ],
        "src/cli/index.ts": [
            ('                 Requires: OPENAI_API_KEY (for memory extraction via gpt-4o-mini + embeddings)',
             '                 Requires: OPENAI_API_KEY (for memory extraction via gpt-4o-mini + embeddings)\n\n  atmem          AtMem governed hybrid retrieval\n                 Raw corpus admission, OpenAI embeddings, governed context.\n                 Requires: OPENAI_API_KEY (no AtBot or local model)'),
            ('  -p rag            Use hybrid RAG memory (OpenClaw/QMD style)',
             '  -p rag            Use hybrid RAG memory (OpenClaw/QMD style)\n  -p atmem          Use AtMem governed memory'),
        ],
    }
    updates = {}
    for name, replacements in changes.items():
        path = root / name
        text = path.read_text()
        for old, new in replacements:
            if new in text:
                continue
            if text.count(old) != 1:
                raise ValueError(f"upstream contract changed: {name}")
            text = text.replace(old, new)
        updates[path] = text
    target = root / "src/providers/atmem/index.ts"
    provider = Path(__file__).with_name("index.ts").read_text()
    if target.exists() and target.read_text() != provider:
        raise ValueError("refusing to overwrite a different AtMem provider")
    for path, text in updates.items():
        path.write_text(text)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(provider)
    print("Registered provider: atmem")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    install(parser.parse_args().checkout.resolve())
