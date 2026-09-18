# Configuration

## Serving

The standard model uses four MTP draft tokens; the abliterated model uses two. All profiles use Q8 K/V cache and localhost port 18080.

| Profile | Max slots | Shared KV pool | Batch / microbatch |
|---|---:|---:|---:|
| `single-200k` | 1 | 204,800 | 1024 / 256 |
| `balanced` | 2 | 204,800 | 2048 / 512 |
| `agents-4` | 4 | 204,800 | 2048 / 512 |
| `agents-8` | 8 | 204,800 | 2048 / 512 |

```powershell
.\Start-Bonsai.ps1 -EnableGpu -Mtp -Profile single-200k
.\Start-Bonsai.ps1 -EnableGpu -Abliterated -Profile agents-4
.\Start-Bonsai.ps1 -EnableGpu -Abliterated -Profile agents-8
```

All active requests share one unified KV pool; slot count controls scheduling capacity and does not divide the pool. A single request can use most of the pool while other slots are idle. The combined cached tokens cannot exceed the pool.

Omit `-EnableGpu` to preview a configuration. Override the pool with `-TotalContext`; the limit includes input and output. Requests beyond the slot count queue on the server. Override MTP depth with `-DraftTokens 1` through `-DraftTokens 8`.

## OpenCode

```powershell
.\Install-OpenCode-Global.ps1
bonsai-standard C:\src\my-project
bonsai-long C:\src\my-project
bonsai-agents-4 C:\src\my-project
bonsai-agents-8 C:\src\my-project
```

Abliterated commands are `bonsai-abliterated`, `bonsai-abliterated-long`, `bonsai-abliterated-agents-4`, and `bonsai-abliterated-agents-8`. The global commands verify the model alias, context size, and slot count before opening OpenCode. A model selection inside an already-open client cannot reload server weights.

The local server does not require authentication by default. LAN binding requires `-ListenAddress 0.0.0.0 -ApiKeyFile PATH`.

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
