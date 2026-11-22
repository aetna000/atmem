// Single-turn reader for the synthetic temporal presentation benchmark on macOS 26+.
import Foundation
import FoundationModels

let prompt = String(decoding: FileHandle.standardInput.readDataToEndOfFile(), as: UTF8.self)
let session = LanguageModelSession(model: .default)
let response = try await session.respond(
    to: prompt, options: GenerationOptions(sampling: .greedy, maximumResponseTokens: 48)
)
print(response.content)
