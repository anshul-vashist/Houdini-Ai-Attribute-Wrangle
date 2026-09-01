# Model and dataset provenance register — v1.0.2

Status: **RELEASE CANDIDATE — owner sign-off required before commercial publication.**

| Item | Evidence recorded | Commercial check still required |
|---|---|---|
| Base model | `Qwen/Qwen3-8B`; the official model card lists `apache-2.0`. | Capture the exact upstream revision/hash actually used during merge and retain the complete Apache 2.0 notice. |
| Fine-tuning adapter | Local adapter config identifies `unsloth/qwen3-8b-unsloth-bnb-4bit` as its training base. | Record the exact adapter build command, training run, source revision, and any Unsloth redistribution requirements. |
| Release model | `qwen3-vex.gguf` SHA-256: `BC2A142BFF4361D096B50F9D7E56A4005A487C4CF80ADF418D22E87004E0531A`. | Confirm that this exact hash is the model encrypted into the release vault, or rebuild the vault and record its source hash. |
| Training/evaluation data | Local manifests describe generated Houdini VEX instruction datasets and compiler checks. | Obtain written confirmation that every prompt, code sample, API signature, and documentation-derived material is owned, licensed, or otherwise permitted for commercial model training and redistribution. |
| Third-party engine | Bundled llama.cpp/ggml binary; MIT notice is included. | Preserve the exact upstream binary version/source and satisfy all license-notice obligations. |

Approval record (required before public release):

- Business owner: ____________________ Date: __________
- Legal/IP reviewer: __________________ Date: __________
- Model/data owner: __________________ Date: __________

This register is operational documentation, not legal advice.
