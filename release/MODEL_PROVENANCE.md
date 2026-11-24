# Model and dataset provenance register — v1.0.2

Status: **RELEASE CANDIDATE — owner sign-off required before commercial publication.**

| Item | Evidence recorded | Commercial check still required |
|---|---|---|
| Base model | `Qwen/Qwen3-8B`; the official model card lists `apache-2.0`. | Capture the exact upstream revision/hash actually used during merge and retain the complete Apache 2.0 notice. |
| Fine-tuning adapter | Local adapter config identifies `unsloth/qwen3-8b-unsloth-bnb-4bit` as its training base. | Record the exact adapter build command, training run, source revision, and any Unsloth redistribution requirements. |
| Release model | `qwen3-vex.gguf` SHA-256: `BC2A142BFF4361D096B50F9D7E56A4005A487C4CF80ADF418D22E87004E0531A`. | Confirm that this exact hash is the model encrypted into the release vault, or rebuild the vault and record its source hash. |
| Training/evaluation data | Local manifests describe generated Houdini VEX instruction datasets and compiler checks. | Obtain written confirmation that every prompt, code sample, API signature, and documentation-derived material is owned, licensed, or otherwise permitted for commercial model training and redistribution. |
| Third-party engine | Bundled llama.cpp/ggml binary; MIT notice is included. | Preserve the exact upstream binary version/source and satisfy all license-notice obligations. |

## Development model v55 (2026-11-12)

Not yet part of a packaged release; recorded here so that the register is complete when it becomes one.

| Item | Evidence recorded | Commercial check still required |
|---|---|---|
| Model file | `Qwen3-8B-Houdini-VEX-v55-nf4deq-Q6_K.gguf`, 6,725,899,168 bytes, SHA-256 `545EF4A57C7246F07F138E92700BA6CCF08CEA67AC4ACD0C1713973A9D3286BB`. | Record the hash of the vault built from it. |
| Base model | `unsloth/Qwen3-8B`, loaded in 4-bit for training. | As above: exact upstream revision and Apache 2.0 notice. |
| Fine-tuning | QLoRA with Unsloth on Google Colab (T4): rank 64, alpha 128, all attention and MLP projections, learning rate 5e-5 (cosine), one epoch, seed 3407, started from the v54 adapter. The snapshot of step 203 of 271 was chosen on held-out results. | Keep the training log and the adapter archive with the release records. |
| Export | The adapter is merged into the 16-bit base weights after they have been passed through the same 4-bit quantisation as in training ("nf4deq"), then quantised to Q6_K with llama.cpp. | Record the llama.cpp revision used for the conversion. |
| Training data | 4,323 rows: 3,123 from 458 concept cards written for this project (every card's reference code was executed in Houdini 21.0.440 and its results checked), 900 rows kept from the v51 training set, 300 rows of answers and compile-error repairs produced by earlier versions of the model and selected automatically. | The 900 older rows have the status of the earlier generated datasets (see the table above). About 1,500 prompts contain function signatures and one-line summaries from the SideFX documentation as context: confirm that this use is permitted. |
| Evaluation | 284 held-out tasks in six suites, results checked on the cooked geometry: 166 solved by the model alone, 199 with the plugin pipeline. The suites are not distributed. | None. |
| Runtime data | Example bank, search phrases and usage notes in `data/` were written for this project. The function reference is built on the user's machine from the user's own Houdini help and is not distributed. `data/vex_signatures_vcc.json` lists function signatures as printed by the VEX compiler (`vcc -X cvex`). `data/vex_1115_compact.json` (the database of the older retrieval path, distributed since September 2026) holds signatures and one-line function descriptions based on the SideFX documentation. | Confirm that distributing the signature list and the older database is permitted. |

Approval record (required before public release):

- Business owner: ____________________ Date: __________
- Legal/IP reviewer: __________________ Date: __________
- Model/data owner: __________________ Date: __________

This register is operational documentation, not legal advice.
