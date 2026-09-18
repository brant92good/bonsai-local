# Bonsai Local

**Long-context coding agents on one RTX 3090.**

Run Ternary Bonsai 2 27B through an OpenAI-compatible local server with Q8 KV cache, MTP speculative decoding, and OpenCode.

- **124.2 tokens/sec combined** in the two-agent draft-length sweep.
- **131,072 tokens per agent** with two concurrent slots.
- **120K-token retrieval verified** across early, middle, and late records.
- **23.0 GiB total VRAM** observed with the default profile.
- Standard and abliterated MTP variants.
- Verified 1-, 2-, 4-, and 8-request serving profiles.

## Quick start

Windows x64, RTX 3090 24 GB, 32 GB RAM, Python 3.11+, Git, CUDA Toolkit 13.3, and Visual Studio 2022 C++ Build Tools with CMake and Ninja.

~~~powershell
git clone https://github.com/brant92good/bonsai-local.git
cd bonsai-local
.\Setup.ps1
.\Install-OpenCode-Global.ps1
.\Start-GPU-after-gaming.cmd
~~~

In another terminal:

~~~powershell
bonsai-standard C:\path\to\your\project
~~~

Setup.ps1 downloads and builds without loading the model. Stop-Bonsai.cmd releases VRAM. Preview-settings-no-GPU.cmd previews the server command.

## Launch profiles

| Standard | Abliterated | Slots | Context per slot |
|---|---|---:|---:|
| `bonsai-long` | `bonsai-abliterated-long` | 1 | 204,800 |
| `bonsai-standard` | `bonsai-abliterated` | 2 | 131,072 |
| `bonsai-agents-4` | `bonsai-abliterated-agents-4` | 4 | 32,768 |
| `bonsai-agents-8` | `bonsai-abliterated-agents-8` | 8 | 16,384 |

Pass a project directory as the optional first argument. The launcher verifies the loaded weights, slot count, and context size before opening OpenCode.

## Abliterated variant

~~~powershell
.\Setup.ps1 -Abliterated
.\Start-Bonsai.ps1 -EnableGpu -Abliterated -Profile balanced -BatchSize 2048 -MicroBatchSize 512
bonsai-abliterated C:\path\to\your\project
~~~

The abliterated model has separate verified weights, server alias, and OpenCode profile. Its launcher defaults to two draft tokens.

Only one model fits in VRAM at a time. The global launch commands stop the owned server when necessary, load the requested weights, verify the active alias, and then open OpenCode. Selecting a model inside an already-open client does not reload server weights.

## Default profile

| Setting | Value |
|---|---|
| Model | Ternary Bonsai 2 27B, PQ2 + Q8 MTP head |
| KV cache | Q8 K / Q8 V |
| Standard speculation | MTP, 4 draft tokens |
| Abliterated speculation | MTP, 2 draft tokens |
| Concurrent requests | 2 |
| Context per request | 131,072 tokens, including output |
| API | http://127.0.0.1:18080/v1 |
| Standard model ID | bonsai2-27b |
| Abliterated model ID | bonsai2-27b-abliterated |

The native model limit is 262,144 tokens. [Profiles and configuration](docs/configuration.md) cover single-agent operation, MTP controls, and LAN access.

## Performance

RTX 3090, two 131K slots, Q8 K/V cache, three runs per mode:

| Draft length | Two-agent coding | Cached 6K prompts | Coding checks |
|---|---:|---:|---:|
| MTP off | 81.6 tok/s | 86.0 tok/s | 3/3 |
| 1 | 93.8 tok/s | 85.9 tok/s | 3/3 |
| 2 | 106.4 tok/s | 91.3 tok/s | 3/3 |
| 3 | 109.6 tok/s | 89.1 tok/s | 3/3 |
| **4** | **124.2 tok/s** | **101.2 tok/s** | **3/3** |

Rates combine both requests. The sweep used fixed-order local runs; desktop activity and thermals were monitored but not controlled. [Results and methodology](docs/benchmarks.md).

OpenCode 1.18.31 passed live model discovery and tool use. Serving uses the Prism llama.cpp fork; stock vLLM does not support the model's PTQ1/PQ2 formats.

[Model](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) | [MTP weights](https://huggingface.co/ProCreations/Ternary-Bonsai-2-27B-MTP) | [Abliterated MTP](https://huggingface.co/BoldingBuilds/Ternary-Bonsai-2-27B-Abliterated-PQ2_0-MTP-GGUF) | [Runtime](https://github.com/PrismML-Eng/llama.cpp) | [Attribution](THIRD_PARTY.md) | [MIT license](LICENSE)
