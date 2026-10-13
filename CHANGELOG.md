# 📜 Houdini AI Attribute Wrangle — Changelog & Iteration History

All notable releases and neural iterations of the **Houdini VEX Copilot** model and digital asset suite are documented here.

---

## [Version 46 Grandmaster Omniverse] — 2026-10-13

### 🧠 Model Architecture & Cloud Training
- **Base Architecture**: `unsloth/Qwen3-8B` (Qwen 3 Causal LM)
- **Adapter Weights**: [`anshulVashist/qwen3-vex-master-v46-lora`](https://huggingface.co/anshulVashist/qwen3-vex-master-v46-lora)
- **Standalone Quantized Weights**: [`anshulVashist/Qwen3-8B-Houdini-VEX-v46`](https://huggingface.co/anshulVashist/Qwen3-8B-Houdini-VEX-v46) (`Qwen3-8B-Houdini-VEX-v46-Q5_K_M.gguf`, 5.85 GB)
- **Training Environment**: Google Colab (Tesla T4 GPU, 14.56 GB VRAM) — 135 steps, ORPO / SFT-Grounded RLVR.
- **Dataset**: 1,815 physical handcrafted pairs across 14 procedural domains, verified in native SideFX Houdini 21.0.440.

### 🧪 Physical Houdini 21 CITL Verification
- **Multi-Domain Benchmark**: **60 / 60 PASSED (100.0%)** across all 13 domains (Spatial queries, Half-edges, SIMD prims, Detail geometry, Vertex attributes, OpenVDB/SDF, Dynamics/POPs, Vellum/PBD, KineFX transforms, Solaris USD LOPs, Advanced Math/Attractors, Bitwise/Morton, Layman Metaphors).
- **Layman English Zero-Shot Generalization**: **5 / 5 PASSED (100.0%)**.
- **Key Enhancements**:
  - `do...while` loop safety guard protection against infinite C++ thread locks.
  - Quaternion vs 4x4 matrix rotation separation (`rotate(m, angle, axis)` vs `qrotate(q, v)`).
  - Native `volumegradient` 3D vector evaluation.
  - Spatial `xyzdist` 4-argument integer primitive index normalization.
  - Dynamic UI parameter synthesis with non-zero safe fallbacks.
  - Automatic HDA `OnCreated` active engine discovery.

---

## [Version 30 Master] — 2026-10-03

### 🧠 Model Architecture & Cloud Training
- **Base Architecture**: `unsloth/Qwen3-8B` (Qwen 3 Causal LM)
- **Adapter Weights**: [`anshulVashist/qwen3-vex-master-v30-lora`](https://huggingface.co/anshulVashist/qwen3-vex-master-v30-lora)
- **Training Environment**: Google Colab (Tesla T4 GPU, 14.56 GB VRAM)
- **Dataset Size**: **2,451 live CITL-verified records** across SOPs, DOPs, POPs, OpenVDB, KineFX, Solaris LOPs/USD, and Position-Based Dynamics (PBD).
- **Hyperparameters**: Effective Batch Size = 16 (1 x 16 gradient accumulation), `learning_rate = 2.5e-4`, LoRA Rank = 64, Alpha = 128 across all 7 linear projection layers.
- **Terminal Losses**:
  - **Training Loss**: `0.324893`
  - **Validation Loss**: `0.390048` (tight generalization across 204 unseen evaluation cases, zero overfitting).
- **Local Deployment**: Merged & quantized to standalone `Qwen3-8B-Houdini-VEX-v30-Q5_K_M.gguf` (5.45 GB) via zero-bloat pipeline purging 14GB 16-bit intermediate merge files.

### 🧪 Physical Houdini 21 CITL Verification
- Executed 25-node physical stress test suite in native Houdini 21 runtime (`hython.exe`):
  - **16 / 25 PASSED (64.0%)** on first-pass zero-shot physical execution.
  - **Key Architectural Fixes Over v29**:
    - `pointcloud_pcopen_iteration`: 5-argument handle iteration (`pcopen` -> `pciterate` -> `pcclose`) now compiles and cooks cleanly with zero errors.
    - `volumetric_density_gradient`: Replaced non-existent `volumeval` with native `volumegradient(1, "density", @P)` and `volumesample(1, "density", @P)`.
    - `color_spline_ramp_mapping`: 5-argument `fit(dist, 0.0, max_d, 0.0, 1.0)` now adheres to exact SideFX VEX function signatures.
    - `v30_kinefx_matrix_to_quaternion` & `v30_kinefx_lookat_setcomp`: Matrix construction and orthonormalization with `quaternion(m)` pass 100%.
    - `v30_usd_camera_clipping_authoring`: Solaris LOP clippingRange authoring via `usd_setattrib` passes 100%.
    - `v30_layman_wobble_jelly` & `v30_layman_tear_cloth`: Layman artist prompts successfully translate to pure physical geometry updates.
    - `v30_vellum_pbd_distance_constraint`: Position-Based Dynamics distance constraint passes with accurate mass-weighted delta projection.
- **Artifacts Generated**:
  - Persistent scene: `VEX_v30_Stress_Test.hip`
  - Detailed telemetry: `ai_model_training/iterative_workflow/benchmarks/stress_test_v30_live.json`

---

## [Version 29 Master] — 2026-10-02
- **Training**: 2,351 records on Google Colab (Tesla T4 GPU, 294 steps).
- **Physical Test**: 20 / 25 PASSED (80.0%) in Houdini 21.
- **Quantization**: `models/Qwen3-8B-Houdini-VEX-v29-Q5_K_M.gguf` (5.45 GB).

---

## [Version 23 Master] — 2026-09-21
- **Training**: 1,810 records on Google Colab.
- **Physical Test**: 10 / 10 PASSED (100%) on golden benchmark test suite.
- **Quantization**: `models/Qwen3-8B-Houdini-VEX-v23-Q5_K_M.gguf` (5.45 GB).

---

## [Version 11 Master] — 2026-09-15
- **Dataset**: `qwen_vex_v11_master.jsonl` (6,167 CITL records).
- **Hugging Face**: [`anshulVashist/Qwen3-8B-Houdini-VEX-v10`](https://huggingface.co/anshulVashist/Qwen3-8B-Houdini-VEX-v10)
- **Quantization**: `models/Qwen3-8B-Houdini-VEX-v11-Q5_K_M.gguf`.
