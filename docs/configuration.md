# Configuration

## Serving

The default launcher enables MTP with Q8 K/V cache, two 131,072-token slots, batch size 2048, and microbatch size 512. The API listens on localhost port 18080.

```powershell
# Default: two long-context agents
.\Start-Bonsai.ps1 -EnableGpu -Mtp -Profile balanced -BatchSize 2048 -MicroBatchSize 512

# Same model and runtime, MTP disabled
.\Start-Bonsai.ps1 -EnableGpu -Mtp -DisableSpeculation -Profile balanced -BatchSize 2048 -MicroBatchSize 512

# Four short-context agents: the measured throughput profile
.\Start-Bonsai.ps1 -EnableGpu -Mtp -ParallelRequests 4 -ContextPerUser 8192 -BatchSize 2048 -MicroBatchSize 512

# Native 262K capacity; requires Setup.ps1 -AllModels
.\Start-Bonsai.ps1 -EnableGpu -Packing PTQ1_0 -Profile long-context
```

Omit `-EnableGpu` to preview any configuration. The context limit includes input and output. Requests beyond the available slots queue on the server.

The 262K PTQ1/Q8 profile passed startup and a short reply. Retrieval was tested at 119,816 prompt tokens. Four simultaneous 131K Q8 contexts were not tested on the 24 GB GPU.

## OpenCode

```powershell
.\OpenCode-Bonsai.ps1 -ProjectPath C:\src\my-project
```

The bundled OpenCode 1.18.31 uses `opencode.bonsai.example.json`. Its settings and sessions live under `clients/opencode/user-state`. Project files are accessed through OpenCode's tools and permissions.

For another OpenAI-compatible client:

| Field | Value |
|---|---|
| Base URL | `http://127.0.0.1:18080/v1` |
| Model | `bonsai2-27b` |
| API key field | `local-bonsai` |
| Context limit | `131072` |
| Output limit | `8192` |

The local server does not require authentication by default. LAN binding requires `-ListenAddress 0.0.0.0 -ApiKeyFile <path>`.

## Installation

```powershell
.\Setup.ps1 -InstallDir F:\bonsai2
.\Setup.ps1 -SkipBuild
.\Setup.ps1 -AllModels
```

Default downloads: MTP weights, the stock Windows runtime, CUDA 12.4 runtime DLLs for the stock fallback, and OpenCode. The MTP runtime builds from the pinned Prism source with CUDA Toolkit 13.3. Its default CUDA architecture is 86 (RTX 3090).

`-AllModels` adds stock PTQ1, stock PQ2, and the vision projector. Vision is untested. Downloads resume through `.part` files and must match the recorded size and SHA-256 checksum. Model files and build outputs stay outside Git.

## Runtime status

```powershell
(Invoke-RestMethod http://127.0.0.1:18080/props).default_generation_settings.params.'speculative.types'
```

The enabled MTP runtime reports `none,draft-mtp`. Generation timings expose `draft_n` and `draft_n_accepted`.

Codex CLI 0.155.0 fails with unsupported Responses tool types and a chat-template system-message error. Claude Code integration is untested.
