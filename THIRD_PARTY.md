# Upstream projects

| Component | Source |
|---|---|
| Ternary Bonsai 2 27B | [PrismML model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) |
| MTP weights and embedding patch | [ProCreations](https://huggingface.co/ProCreations/Ternary-Bonsai-2-27B-MTP) |
| Prism llama.cpp | [Source and license](https://github.com/PrismML-Eng/llama.cpp/blob/d8f26eec76da6d09bb708bcba51ef64b8cd868a3/LICENSE) |
| OpenCode | [Source and license](https://github.com/anomalyco/opencode/tree/v1.18.31) |
| KV-cache guidance | [PrismML](https://github.com/PrismML-Eng/Bonsai-demo/blob/main/KV-CACHE.md) |
| vLLM GGUF format support | [vLLM GGUF plugin](https://github.com/vllm-project/vllm-gguf-plugin/blob/main/vllm_gguf_plugin/quantization/utils.py) |

Model weights, CUDA libraries, and OpenCode are downloaded from their upstream releases and retain their respective licenses. `artifacts.json` pins revisions and checksums. The included runtime patches target the MIT-licensed llama.cpp source; its license is reproduced in `mtp/patches/LICENSE.llama.cpp`.

An [abliterated Bonsai 2 derivative](https://huggingface.co/BoldingBuilds/Ternary-Bonsai-2-27B-Abliterated-PTQ1_0-GGUF) is available separately. It is not included in this setup or its benchmarks.
