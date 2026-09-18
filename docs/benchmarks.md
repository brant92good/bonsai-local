# RTX 3090 benchmarks

2026-09-19 · Windows x64 · RTX 3090 24 GiB · i5-13600K · 31.7 GiB RAM

## MTP

Both arms use identical PQ2 + Q8 MTP weights, the patched CUDA 13.3 runtime, Q8 K/V cache, and 2048/512 batch settings. MTP uses two draft tokens.

| Workload | Slots | MTP off | MTP on |
|---|---|---:|---:|
| Two generated Python functions | 2 × 131,072 | 64.8 tok/s | 87.7 tok/s |
| Cached 6K prompts, two requests | 2 × 131,072 | 83.0 tok/s | 77.6 tok/s |
| Cached 6K prompts, four requests | 4 × 8,192 | 80.8 tok/s | 113.7 tok/s |
| Cold 1K prompts, four requests | 4 × 8,192 | 64.1 tok/s | 79.2 tok/s |
| Cold 6K prompts, four requests | 4 × 8,192 | 24.4 tok/s | 25.4 tok/s |

All rates are aggregate output tokens per elapsed second. The coding pair produced 566 tokens in 8.73 seconds with MTP off and 6.45 seconds with it on; both functions passed their edge cases. The four-request cached result is 41% above its matched MTP-off control, and 22% above the best stock PQ2 runtime result (93.1 tok/s).

## Correctness

| Configuration | Python functions | Tool call round-trip |
|---|---:|---|
| Stock PTQ1, FP16 cache | 5/6 | Pass |
| Stock PTQ1, Q8 cache | 5/6 | Pass |
| Stock PTQ1, Q4 cache | 4/6 | Pass |
| Stock PQ2, Q8 cache | 5/6 | Pass |
| PQ2 + MTP head, MTP off, Q8 cache | 5/6 | Pass |
| PQ2 + MTP head, MTP on, Q8 cache | 5/6 | Pass |

Every mode used a prohibited import on the rate-limiter task. Q4 also merged disjoint intervals. All answers were rescored with the same input-preservation and edge-case checks. Q8 remains the default; no Q4 calibration was performed.

The MTP file preserves all 851 stock PQ2 tensors byte for byte and adds 15 tensors. These tests do not measure accuracy against an uncompressed reference model.

## Context and memory

The default MTP profile allocates two independent 131,072-token contexts. Total GPU memory reached approximately 22.5 GiB, including the desktop. The server's approximate increment was 19 GiB. Additional GPU applications reduce the available headroom.

At 119,816 prompt tokens, MTP recovered all four target fields in 192.7 seconds. The test covers early, middle, and late records plus a superseding configuration value. Full 262,144-token retrieval was not tested.

Q8 K/V cache uses approximately 34 KiB per token: 8.5 GiB for two 131K contexts. The MTP weight file is 7.13 GiB; recurrent state and runtime buffers consume additional memory.

## Clients

| Client or API | Result |
|---|---|
| OpenCode 1.18.31 | Read a fixture through its tool and returned the correct code |
| Chat Completions | Tool arguments and tool-result round-trip passed |
| Responses / Messages | Basic reply passed |
| Codex CLI 0.155.0 | Failed: unsupported tool types and system-message template error |
| Claude Code | Untested |

## Reproduce

```powershell
$env:BONSAI_ROOT = 'F:\bonsai2'
python .\benchmarks\run.py --enable-gpu --suite two-agent
python .\benchmarks\run.py --enable-gpu --suite mtp
python .\benchmarks\run.py --enable-gpu --suite long-context
```

The runner uses port 18081 and stops the model when each suite finishes. Results are saved under `benchmark-runs/`. [Recorded results](../benchmarks/results/2026-09-19/results.jsonl) include requests, responses, token counts, and timings. [Throughput summary](../benchmarks/results/2026-09-19/throughput-summary.csv) includes the earlier cache comparisons.

Greedy sampling; thinking disabled; synthetic prompts; no vision. Cached tests reuse 6,164 prompt tokens per request and exclude cache warm-up. The paired MTP comparisons have one measured run per workload. Desktop activity and thermal variation remain uncontrolled. Cold workloads include prompt processing, and their work-item labels vary by run. These measurements are a local screening set, not a broad coding-agent evaluation.
