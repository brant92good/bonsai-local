# Bonsai Local

**Long-context coding agents on a single RTX 3090.**

Run Ternary Bonsai 2 27B with MTP speculative decoding, Q8 KV cache, and OpenCode. Two agents share one local server, each with a 131,072-token context window.

- **88 tokens/sec combined** in the two-agent coding test; 26% shorter completion time with MTP.
- **120K-token retrieval verified**, with all four target fields recovered.
- **22.5 GiB total VRAM** observed with the default profile, including Windows and desktop applications.
- Pinned dependencies, verified downloads, and reproducible benchmarks.

## Quick start

Windows x64 · RTX 3090 24 GB · 32 GB RAM · Python 3.11+ · Git · CUDA Toolkit 13.3 · Visual Studio 2022 C++ Build Tools with CMake and Ninja. Allow 20 GB of free disk space for the default installation and build.

```powershell
git clone https://github.com/brant92good/bonsai-local.git
cd bonsai-local
.\Setup.ps1
.\Start-GPU-after-gaming.cmd
```

In another terminal:

```powershell
.\OpenCode-Bonsai.ps1 -ProjectPath C:\path\to\your\project
```

`Setup.ps1` downloads and builds without loading the model. `Stop-Bonsai.cmd` releases its VRAM. `Preview-settings-no-GPU.cmd` previews the serving configuration.

## Default profile

| Setting | Value |
|---|---|
| Model | Ternary Bonsai 2 27B, PQ2 + Q8 MTP head |
| KV cache | Q8 K / Q8 V |
| Speculative decoding | MTP, 2 draft tokens |
| Concurrent requests | 2 |
| Context per request | 131,072 tokens, including the response |
| API | `http://127.0.0.1:18080/v1` |
| Model ID | `bonsai2-27b` |

OpenCode passed a live tool-use test. Codex CLI currently fails on Responses API compatibility; Claude Code is untested. Serving uses the Prism llama.cpp fork; stock vLLM does not support the model's PTQ1/PQ2 formats.

The model's native context limit is 262,144 tokens. [Profiles and configuration](docs/configuration.md) cover single-agent operation and MTP controls.

## Performance

RTX 3090, Q8 KV cache, matched MTP on/off settings:

| Workload | MTP off | MTP on |
|---|---:|---:|
| Two concurrent coding tasks, 2 × 131K slots | 64.8 tok/s | **87.7 tok/s** |
| Two cached 6K prompts, 2 × 131K slots | **83.0 tok/s** | 77.6 tok/s |
| Four cached 6K prompts, 4 × 8K slots | 80.8 tok/s | **113.7 tok/s** |

Rates are combined output across requests. MTP gains vary by workload. Both MTP modes passed 5/6 coding checks; Q4 cache passed 4/6. These are small local tests, with greedy sampling and thinking disabled. [Results and methodology](docs/benchmarks.md).

[Model](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) · [MTP weights](https://huggingface.co/ProCreations/Ternary-Bonsai-2-27B-MTP) · [Runtime](https://github.com/PrismML-Eng/llama.cpp) · [Attribution](THIRD_PARTY.md)
