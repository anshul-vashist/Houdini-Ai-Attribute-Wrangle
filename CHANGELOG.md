# 📜 Houdini AI Attribute Wrangle — Changelog & Iteration History

All notable releases and neural iterations of the **Houdini VEX Copilot** model and digital asset suite are documented here.

---

## [v55 shipped, function lookup, prompt layout, review fixes] — 2026-11-12

- **Function lookup on by default** (`python/vex_function_index.py`): for a task the prompt lists the documented
  signatures of the ten functions it most probably needs, found through the Houdini function reference
  (`data/vex_function_reference.json`), plain-language search phrases for 367 functions
  (`data/vex_function_aliases.json`) and the verified cards. On the open cards the list contains 71% of the
  functions a solution needs (keyword matcher: 13%). `AI_WRANGLE_FUNCTION_INDEX=0` restores the keyword matcher,
  `AI_WRANGLE_FUNCTION_INDEX_K` sets the number of functions.
- **Prompt layout**: the reference block now sits directly in front of the task instead of at the top
  (`AI_WRANGLE_REFERENCE_LAST=0` restores the old place); the "blueprint" patterns chosen by trigger words are off
  (`AI_WRANGLE_BLUEPRINTS=1` restores them); the repair prompt builds its block from the task alone.
- **Compile-error hints on by default** (`python/vex_api_hints.py`; `AI_WRANGLE_API_HINTS=0` turns them off): a
  made-up function name is matched to the real function by spelling, by prefix and by the words of the name
  (`polar` -> `polardecomp`, `npointsinGroup` -> `npointsgroup`); wrong arguments get the documented usage; an
  undeclared name is explained as an attribute or a parameter.
- **Result with v53b** (the plugin's model until v55): sealed suites B-F 127 -> 139 of 227 (22 tasks gained, 10 lost; unseen
  tasks 69 -> 74 of 133), with suite A 188 of 284; open dev prompts 46 -> 54 of 84.
- **Fix**: when the model used its whole token budget on thinking (deep-reasoning mode, auto-repair) the request
  raised "engine unavailable" and Generate ended in a traceback. The plugin now asks once more without thinking,
  shows separately returned thinking in the Reasoning Trace, and a failed repair request ends the repair with the
  compile error.
- **Example bank**: 410 verified examples (`data/vex_card_bank.json`), with the cards written by five author agents
  (c21-c25). 56 more cards (c31-c32), one for each of 56 functions that had none, are verified and go into the
  bank together with v55.
- **Usage notes** for 140 functions (`data/vex_function_notes.json`: argument order, special argument values,
  return conventions) and a better choice of the overloads shown (`noise(vector pos)` instead of only
  `noise(float pos)`): in the code, switched off until measured (`AI_WRANGLE_FUNCTION_NOTES=1`,
  `AI_WRANGLE_FUNCTION_USAGE_LINES=3`).
- **v54** (339 cards): better than v53b on its own (sealed 93 -> 109, unseen tasks 51 -> 59) but not inside the
  plugin (125-130 against 127-139), because it makes less use of what the prompt offers; not shipped.
- **v55** (458 cards; training prompts whose reference block contains the functions of the answer, so that the
  model would learn to read it; 271 steps): it learned its new cards (86 of 90 sampled prompts) and equals v53b
  inside the plugin in total (sealed 140 against 139) while solving different tasks (25 that v53b misses, 24 the
  other way; unseen tasks 79 against 74, oldest suite B 21 against 25). It did not learn to read the reference
  block: with a perfect function list it gains 2 of 126 dev prompts. Its final snapshot lost older skills when
  used alone; the snapshot of step 203 is the best of the three.
- **Shipped model: v55 (step 203)**, `models/Qwen3-8B-Houdini-VEX-v55-nf4deq-Q6_K.gguf`, now the plugin's Auto
  model (v53b stays selectable). Suites A-F: 166 of 284 alone (v53b 138; sealed part 44 tasks gained, 21 lost),
  199 with the plugin (v53b 188; 34 gained, 23 lost, not statistically solid: +12 on the newest suite F, +5 on A,
  -6 on the older suites B-E); unseen sealed tasks 82 of 133 (v53b 74). Blends of the adapters gave nothing.
  See `ai_model_training/v53_cards/README.md`.
- **Review** (four reviewers, each reproducing its findings) and its fixes: Optimize / Explain could replace the
  user's snippet with an empty answer when the model returned only thinking (now refused); Esc during auto-repair
  is reported as a cancel; a made-up getter name is no longer answered with the setter, wrong letter case gets the
  real function, a bare built-in name (`P`, `ptnum`) gets its one binding; run-together names are cut at word
  borders; seven usage notes corrected after measuring them in Houdini (`volumesamplev` by primitive number, the
  centre of a triangle in `primuv`, `append` mode); four card prompts reworded; `build_v55.py` no longer leaves a
  stale reference block in older rows; dev runs record the settings and module versions they ran with; the paired
  comparison scripts report missing or duplicated rows.
- Evaluation: runs are compared task by task (`ai_model_training/v53_cards/sealed_pair.py`, counts and a sign
  test), because a prompt change flips 10-15% of the tasks in both directions. Plugin tests: 131 checks.
- **Function reference built on the user's machine** (`python/vex_function_reference.py`): the reference holds
  summary lines from the SideFX documentation, so it is no longer a file of the repository. The lookup builds it
  from the help of the local Houdini installation the first time it is needed (0.2 s, stored as
  `data/vex_function_reference.json`; the build from Houdini 21.0.440 is byte-identical to the file all
  measurements above used) and offers nothing when the help is not installed. `AI_WRANGLE_BUILD_REFERENCE=0`
  switches the build off; `tools/build_function_reference.py` rebuilds it by hand. Plugin tests: 139 checks.
- **Repository**: README rewritten for the current pipeline with the held-out results; release notes and the
  model provenance register updated for v55; installers no longer point to v10 / v11; `scratch/`, the held-out
  benchmark suites and the working notes of AI assistants are git-ignored.

## [Master analysis, concept cards, v53b, verified-example retrieval] — 2026-11-11

- Analysis of everything done so far (`ai_model_training/MASTER_ANALYSIS.md`): no measurable gain on independent
  tasks since v48; the data covered 138 verified concepts with template prompts; failures are near misses on API
  knowledge; retrieval rarely fired and its hand-written signature file had 10 wrong entries (fixed, checked by
  `tools/validate_signatures.py` against the compiler's 951 signatures in `data/vex_signatures_vcc.json`).
- Benchmark harness: the equivalence checker now compares connectivity and primitive type, integers exactly,
  quaternions up to sign and dictionary attributes; tasks can have parameters (tested with two value sets), frames,
  order-insensitive matching and 20 more input geometries. New sealed suite F (`benchmarks/heldout_f`, 120 tasks
  by independent authors, each blind-solved).
- Export: adapters are merged into the dequantised 4-bit base they were trained against
  (`ai_model_training/export_nf4deq.py`, `bnb4bit_to_fp16.py`); small gain, now the default.
- Concept cards (`ai_model_training/v53_cards/`): 327 teacher-written problems (three phrasings, derivation, gold
  program) verified in Houdini by reference equivalence on several inputs; they follow the function usage measured
  in the 4,686 wrangle snippets that ship with Houdini.
- **v53b** (`models/Qwen3-8B-Houdini-VEX-v53b-nf4deq-Q6_K.gguf`, the plugin's Auto model): trained on 262 cards
  with code-dominant answers plus repairs of the model's own verified failures. Sealed suites B-F (227 tasks):
  76 -> 93 alone, 99 -> 114 with the plugin pipeline. An overlap check afterwards showed where the gain is: all of
  it on the 90 tasks whose solution resembles a training card (25 -> 42 alone); none on the 137 unlike any card
  (51 -> 51). 10 of the 90 are near-duplicates. (An earlier run, v53, with long prose derivations as targets and a
  low learning rate, did not learn the cards.)
- **Verified-example retrieval** (`python/vex_example_bank.py`, `data/vex_card_bank.json`, 339 examples, built by
  `tools/build_card_bank.py`): the plugin adds the two most similar verified card solutions to the prompt. Sealed
  suites with the full pipeline: 114 -> 126 (bank of 339) and 132 (bank of 262) of 227 (94 -> 106 and 111 on the 198 tasks not
  close to a card; 41 -> 47 of 84 on open dev prompts of unseen concepts), most of it on suite F; about neutral on
  the older suites. On by default; `AI_WRANGLE_EXAMPLES=0` turns it off.
- Evaluation hygiene: `v53_cards/screen_sealed.py` screens every card against every sealed task (ids only) and
  `sealed_clean_subset.py` reports each result in total and on the tasks not close to any card.
- Prepared for the next model: 84 more cards (c12, c13) for functions that had none, each measured in Houdini first
  (`scratch/vexlab.py`); `build_v54.py` builds the v54 set with plugin rows that carry worked examples retrieved
  leave-one-out (`configs/v54.json`).
- Plugin tests no longer hard-code a model version (`tools/test_hda_hython.py`, 83 checks).
- Fix: the GPU temperature watchdog crashed on fractional readings (`scratch/hda_review/gpu_throttle.py`).

---

## [VEX intelligence program: audit, benchmark D, v50, v51 pipeline] — 2026-11-05

- Audit (`ai_model_training/audit/AUDIT.md`, `audit_dataset.py`): v49 data is mostly one-liners (median answer
  90 chars, 110 rows ≥ 25 lines), 14% exact duplicates, simulation domains nearly absent, no validation split.
- `tools/vex_validate.py`: compile-and-cook any snippet in a Houdini scene (mesh, sphere, volumes); used to check
  all 593 legacy rows (all compile; none had a semantic check).
- Benchmark D (`benchmarks/heldout_d`, sealed, 30 tasks): particles, forces, collision, fluid fields, RBD, volumes,
  solvers, analysis, graph algorithms, debugging. Gold 30/30, empty code 0/30. New runner inputs: particles,
  packed pieces, velocity/density volumes, three-box mesh.
- `benchmarks/fourway.py`: base / fine-tuned / + context & RAG / full pipeline on A–D. v50: 9% → 53% → 67% → 68%.
- v50 (plugin-prompt-format training) shipped as `Qwen3-8B-Houdini-VEX-v50-f16merge-Q6_K.gguf`: plugin score on
  A+B+C 76 → 79 of 114.
- v51 data (`ai_model_training/v51_domains/`): new-domain families with multi-step programs and per-row provenance,
  600 repair pairs from real compile errors on training tasks, deduplicated retention; 3,182 Houdini-verified rows.
  Training is config-driven (`ai_model_training/colab_train.py`, `configs/v51.json`) with adapter snapshots and
  dev-set checkpoint selection (`eval_dev.py`); snapshots export with `ai_model_training/export_snapshot.py`.
  The first v51 run stopped at step ~90/199 when the Colab free GPU quota ran out; the second (170 steps,
  185 min) completed. Snapshot dev scores (new domains / retention): step 42 92/57, 85 103/57,
  128 110/57, 170 111/57 of 128/60. Shipped: `models/Qwen3-8B-Houdini-VEX-v51-f16merge-Q6_K.gguf` (now the
  plugin's Auto model). Full plugin pipeline on A–D: 98 → 103 of 144; raw 76 → 78.
- Plugin: `build_generation_prompt` / `build_repair_prompt` are now separate functions (training data uses them).
- Fixes: benchmark runner no longer kills other programs' llama-server; Colab upload helper only targets the
  Files panel (it had attached files to the Gemini chat box, nothing was sent).

## [GGUF export fix] — 2026-11-04

- `iterative_workflow/model_exporter.py` now merges LoRA adapters into an unquantized F16 base
  (`models/Qwen3-8B-F16.gguf`) and quantizes once; it falls back to the Q5 base with a warning if the F16 file is missing.
- New `iterative_workflow/build_f16_base.py`: builds the F16 base from the official Qwen/Qwen3-8B weights and
  re-exports existing adapters (`--rebuild v49 --suffix=-f16merge --qtypes Q5_K_M,Q6_K`).
- New models: `Qwen3-8B-Houdini-VEX-v49-f16merge-Q5_K_M.gguf` and `...-Q6_K.gguf`. Held-out raw total
  (A+B+C, 114 tasks): old v49 58 → 61 (Q5_K_M) / 63 (Q6_K). See `benchmarks/heldout_semantic/README.md`.
- Old `Qwen3-8B-Houdini-VEX-v49-Q5_K_M.gguf` renamed to `.gguf.bak`; "Auto" now loads the F16-merge Q6_K.
- Plugin: generated sliders default to the value the code falls back to when the slider is unset
  (`float s = chf("step"); if (s == 0.0) s = 0.1;` → slider default 0.1, not a generic 1.0). Untouched sliders
  follow a new answer's fallback; values the artist set are never changed.
- Plugin: best-of-N candidate 2 is generated in the exact training prompt format (`generate_vex_training_format`):
  the long plugin prompt pulled the fine-tune back to base-model habits. Product mode A+B+C: 67 → 71 (sliders)
  → 76 (best-of-3, the default).
- `run_eval.py`: stops only the llama-server it started (it used to kill every llama-server, including the
  plugin's); `--lora-scaled` uses the current `FILE:SCALE` syntax.

## [HDA & controller review] — 2026-11-04

Verified with `hython tools/test_hda_hython.py` (64 checks, LLM mocked) and the held-out Houdini
benchmarks (v49 through the full plugin: A 36 → 37/57, sealed B 18 → 19/31, 20% fewer repair calls).

### HDA (`otls/ai_attribwrangle.hda`)
- Removed an embedded copy of SideFX's `Sop/attribwrangle` that overrode the native Attribute Wrangle in every scene.
- OnCreated is now flagged as Python (it ran as HScript and failed on every node creation).
- `ai_model_select` is a string menu keyed by file name (the ordinal menu pointed at a different model whenever one was added).
- Added a help page. `tools/fix_hda.py` reproduces these edits.

### Controller (`python/houdini_ai_wrangle.py`, `engine_manager.py`)
- Compile-first: model output is applied untouched when it compiles; the regex sanitizer only runs on rejected code.
- Sanitizer rules that corrupted valid code fixed or removed (`nearpoint` normaliser, `<` → `<=` flips, unbalanced `primpoints` rewrite, `quaternion(matrix3(...))` on vectors, `f[]@x` renumbering).
- Loop guard rewritten with real parenthesis matching (`while (C)` → equivalent bounded `for`): no more corrupted conditions, broken braceless `if`, or legit loops cut at 10,000 iterations.
- Any compile/cook error now counts as failure (keyword whitelist let "Empty array index", "Error in VOP" etc. pass as success).
- Failed generations keep the user's working snippet and slider values; the failed attempt goes to Reasoning Trace. Empty/prose model output is never applied.
- Model discovery: Auto = newest fine-tuned model (v49), no hard-coded v46 lists, no network probe on node creation; "Custom Model File" choice works.
- Engine: never kills other programs' llama-server processes, finds a free port when 58421/58321 are reserved, ctx 8192, NameError that hid engine errors fixed.
- LLM requests run on a worker thread with an interruptible progress dialog (Esc cancels).
- Large-geometry performance (1M points): introspection 11.4 s → 0.02 s, post-apply checks 7.1 s → 0.03 s; NaN/Inf scan now covers every element.
- No more force-cooking of downstream nodes (solvers / file caches) on each attempt; history capped at 50 entries with one undo step per navigation.
- Export .h produces a real VEX function (bindings become by-reference arguments) that compiles and matches the snippet's results; asks before overwriting.
- Interface upgrade no longer deletes generated sliders, user spare parms or bindings.

### Follow-up (same day)
- Model loading shows an interruptible progress dialog (cold load measured at 45 s); Esc cancels cleanly.
- Choosing a model only records it (loads on next Generate or via Switch Model); Auto always means the newest model.
- llama-server runs in a Windows kill-on-close job object: it dies with Houdini even on a crash (verified by hard-killing hython).
- Per-session API key on the local engine (unauthenticated requests get 401).
- Refine button reuses the Generate pipeline (≈120 duplicated lines removed); one Generate = one undo step;
  variant switching is a single undo step and keeps slider values; "Fork to Branch" fixed (hou.Node has no copy()).
- Engine manager: hard-coded v11–v42 label ladder removed.
- Repo package template (`ai_attribwrangle.json`) works for a clone into `$HOUDINI_USER_PREF_DIR/packages/` (verified on a clean prefs dir).
- Hugging Face token removed from all scripts: live tools read `.secrets/hf_token` (git-ignored) via `tools/hf_secret.py`.
- Live engine test: `hython tools/test_engine_live.py`; HDA suite now 73 checks.

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
