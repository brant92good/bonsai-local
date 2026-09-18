# Configuration

## Serving

The standard launcher enables MTP with four draft tokens; the abliterated launcher defaults to two. Both use Q8 K/V cache, two 131,072-token slots, batch size 2048, and microbatch size 512. The API listens on localhost port 18080.

~~~powershell
# Standard model: two long-context agents
.\Start-Bonsai.ps1 -EnableGpu -Mtp -Profile balanced -BatchSize 2048 -MicroBatchSize 512

# Abliterated model: matching MTP weights and alias
.\Start-Bonsai.ps1 -EnableGpu -Abliterated -Profile balanced -BatchSize 2048 -MicroBatchSize 512

# Standard MTP model with speculation disabled
.\Start-Bonsai.ps1 -EnableGpu -Mtp -DisableSpeculation -Profile balanced -BatchSize 2048 -MicroBatchSize 512

# Four short-context agents
.\Start-Bonsai.ps1 -EnableGpu -Mtp -ParallelRequests 4 -ContextPerUser 8192 -BatchSize 2048 -MicroBatchSize 512

# Native 262K capacity; requires Setup.ps1 -AllModels
.\Start-Bonsai.ps1 -EnableGpu -Packing PTQ1_0 -Profile long-context
~~~

Omit -EnableGpu to preview any configuration. The context limit includes input and output. Requests beyond the available slots queue on the server. Override MTP depth with -DraftTokens 1 through -DraftTokens 8.

The 262K PTQ1/Q8 profile passed startup and a short reply. Retrieval was tested at 119,816 prompt tokens. Four simultaneous 131K Q8 contexts were not tested on the 24 GB GPU.

## OpenCode

~~~powershell
.\Install-OpenCode-Global.ps1
bonsai-standard C:\src\my-project
bonsai-abliterated C:\src\my-project
~~~

The global launch commands load and verify the selected server before opening OpenCode. OpenCode-Bonsai.ps1 provides the same behavior through the bundled client. A model selection made inside an already-open client does not reload weights.

| Field | Standard | Abliterated |
|---|---|---|
| Base URL | http://127.0.0.1:18080/v1 | http://127.0.0.1:18080/v1 |
| Model | bonsai2-27b | bonsai2-27b-abliterated |
| Context limit | 131072 | 131072 |
| Output limit | 8192 | 8192 |

The local server does not require authentication by default. LAN binding requires -ListenAddress 0.0.0.0 -ApiKeyFile PATH.

## Installation

~~~powershell
.\Setup.ps1 -InstallDir F:\bonsai2
.\Setup.ps1 -Abliterated
.\Setup.ps1 -SkipBuild
.\Setup.ps1 -AllModels
~~~

Default downloads include the standard MTP weights, stock Windows runtime, CUDA runtime DLLs, and OpenCode. -Abliterated adds the pinned abliterated PQ2 + MTP file. -AllModels adds every optional model and the vision projector. Downloads resume through .part files and must match the recorded size and SHA-256 checksum.

## Runtime status

~~~powershell
(Invoke-RestMethod http://127.0.0.1:18080/props).default_generation_settings.params.'speculative.types'
~~~

The enabled runtime reports none,draft-mtp. Generation timings expose draft_n and draft_n_accepted.
