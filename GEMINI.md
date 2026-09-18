# ⚡ Houdini AI Attribute Wrangle — Project Context & Rules

This document serves as the persistent memory and technical directive for the **AI Attribute Wrangle** repository. It is automatically loaded by Antigravity at the start of every session.

---

## 📌 Executive Overview

- **Project**: AI Attribute Wrangle (`ai_attribwrangle.hda`)
- **Target Platform**: SideFX Houdini 20.0, 20.5, 21.0+ (Windows x64 / Python 3.10 & 3.11)
- **Core Purpose**: A commercial-grade, 100% offline, zero-cloud AI copilot embedded inside SideFX Houdini for procedural geometry, dynamic parameter synthesis, and autonomous VEX code generation/refinement.
- **Key Architectures**:
  - Embedded local inference via `bin/llama-server.exe` (Port `58421`).
  - Native Houdini Digital Asset (`otls/ai_attribwrangle.hda`).
  - Compiler-in-the-Loop (CITL) autonomous self-healing via `vcc` and syntax sanitizers.
  - Upstream geometry introspection & Micro-RAG (`vex_rag_engine.py`).
  - Hardware-locked RSA cryptographic licensing (`license_validator.py`).

---

## 🧠 Fine-Tuned Model Specifications

The project uses a domain-specialized, fine-tuned neural model trained specifically on Houdini procedural geometry and VEX programming:

| Specification | Details |
| :--- | :--- |
| **Base Model** | `unsloth/Qwen3-8B` (Qwen 3 Causal LM) |
| **Model Variants** | **v10 Master** (`Qwen3-8B-Houdini-VEX-v10`) & **v11 Grandmaster** (`Qwen3-8B-Houdini-VEX-v11`) |
| **Hugging Face** | [`anshulVashist/Qwen3-8B-Houdini-VEX-v10`](https://huggingface.co/anshulVashist/Qwen3-8B-Houdini-VEX-v10) |
| **Training Pipeline** | Unsloth 4-bit NF4 with gradient checkpointing on PyTorch/CUDA |
| **LoRA Config** | **Rank 64, Alpha 128** across all 7 linear projection layers (`q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`) |
| **Loss Masking** | Completion-only loss masking (calculating loss strictly on reasoning traces and VEX code) |
| **Training Dataset** | `qwen_vex_v11_master.jsonl` (6,167 live CITL-verified records across SOPs, DOPs, POPs, OpenVDB, CHOPs, COPs, LOPs/USD, KineFX, and Position-Based Dynamics) |
| **API Coverage** | Complete 1,115 SideFX VEX function catalog with exact parameter signatures and context restrictions |
| **Quantization & Delivery** | Standalone merged GGUF formats: `Q5_K_M` (~5.45–5.85 GB, optimal for 6–8 GB VRAM) and `Q8_0` (Production, 12 GB+ VRAM) |
| **Runtime Serving** | Embedded `llama-server.exe` running locally on port `58421` (silent `CREATE_NO_WINDOW` background management) |

### Dual-Mode Intelligence Architecture
1. **⚡ Turbo Fast Mode**: Generates instant, pure VEX code (<2s) with zero conversational chatter or markdown fences. Ideal for rapid iteration.
2. **🧠 Deep Reasoning Mode**: Conducts 3D vector space analysis, trigonometric calculations, and algorithmic planning inside an explicit `<think>...</think>` block before emitting pristine VEX code.

### Sampling & System Prompt Directives
- **System Prompt**:
  ```text
  You are an expert Houdini VEX programmer. Write pure VEX code to solve the user's task in the specified context without explanation or markdown formatting.
  ```
- **Sampling Parameters**: `temperature: 0.1`, `top_p: 0.95`
- **Stop Tokens**: `<|im_end|>`, `<|endoftext|>`

---

## 🗂️ Master Codebase Structure

```
E:\#AI#\Houdini Attribute Wrangle/
├── GEMINI.md                                  # Persistent Project Context & Rules (This file)
├── README.md                                  # Public documentation and quickstart guide
├── COMMERCIAL_READINESS_BLUEPRINT.md          # Architectural and commercial deployment blueprint
├── installer_gui.py / Setup_AI_Wrangle.exe    # 1-Click GUI installer for Houdini package setup
├── install_in_houdini.py                      # Drag-and-drop in-viewport Houdini installer script
├── Modelfile                                  # Ollama / Llama runtime configuration
│
├── python/                                    # Core Houdini Controller & Engines
│   ├── houdini_ai_wrangle.py                  # Main HDA callback controller, parameter synthesis, VEX Time Machine
│   ├── vex_rag_engine.py                      # Geometry introspection (@P, @N, @v, @Cd, bbox) & RAG prompt builder
│   ├── engine_manager.py                      # Lifecycle manager for local llama-server.exe (Port 58421)
│   ├── license_validator.py                   # RSA-2048 cryptographic signature and hardware-lock validator
│   └── model_vault.py                         # AES-256-GCM model decryption & security vault
│
├── bin/                                       # Bundled C++ inference binaries
│   ├── llama-server.exe                       # Standalone Windows x64 inference engine
│   └── *.dll                                  # 22 bundled runtime DLLs (OpenMP, ggml, Vulkan, mtmd)
│
├── otls/                                      # Houdini Digital Assets
│   └── ai_attribwrangle.hda                   # The shipping Houdini SOP asset
│
├── models/                                    # GGUF weights & LoRA adapters
│   ├── Qwen3-8B-Houdini-VEX-v10-Q5_K_M.gguf  # Production v10 weights
│   ├── Qwen3-8B-Houdini-VEX-v11-Q5_K_M.gguf  # Grandmaster v11 weights
│   └── qwen3-vex-v10-lora.gguf                # Standalone LoRA adapters
│
├── houdini_hda_package/                       # Houdini package distribution template
├── ai_model_training/                         # Training datasets, synthetic generation, and benchmarks
└── benchmarks/                                # CITL stress tests, Hython test runners, and evaluation suites
```

---

## ⚙️ Developer Guidelines & Operational Rules

Whenever assisting with or modifying this codebase, the AI must strictly adhere to the following rules:

### 1. Compiler-in-the-Loop (CITL) Self-Correction
- Always validate Python code with `ast.parse` before writing or proposing.
- Any VEX code generated or modified must conform to SideFX Houdini VEX compilation standards (`vcc`).
- Never hallucinate non-existent VEX functions or C++/Python constructs. Always refer to Houdini's native VEX function library.

### 2. Mandatory VEX Syntax & Anti-Pattern Protections
- **Vectors**: Never use `vector3` or `Vector3`; VEX syntax is strictly `vector`.
- **Quaternions**: Never use `quaternion q = ...`; use `vector4 q = ...`.
- **Vector4 / Quaternion Reading**: To read a `vector4`/quaternion parameter from UI, use `chp("name")`. `ch4("name")` reads a 4x4 `matrix` in VEX, NOT a vector4.
- **Vector4 Swizzling**: VEX does NOT support `.xyz` swizzle on `vector4`. Must use `set(v.x, v.y, v.z)`.
- **In-Place Array Operations**: Functions like `sort()`, `reverse()`, and `insert()` modify arrays in-place and return `void`. Never assign their output back:
  - ❌ `arr = sort(arr);`
  - ✅ `sort(arr);`
- **Array Min/Max**: `min(arr)` and `max(arr)` take only the array as an argument; do not pass a second comparison argument.
- **Matrix Operations**: VEX matrices do not have `.row(i)` methods; access components via vector slicing or `set()`.
- **Polymorphic Return in VEX**: `chramp()` returns polymorphic `vector`/`float`. Passing it directly into polymorphic functions like `setpointattrib(0, "Cd", pt, chramp(...), "set")` triggers compile ambiguity. Always assign to an explicit `vector` variable first.
- **Untyped Function Returns**: `point(0, "attrib", pt)` returns polymorphic `untyped`. Never pass directly into polymorphic functions like `distance()` or `lerp()` without assigning to a typed variable first.
- **Half-Edge Traversal**: VEX uses `hedge_nextequiv(0, hedge)` to query opposing boundary half-edges; returns `-1` if on an open boundary. `hedge_equivelem()` does NOT exist.

### 3. Dynamic Parameter Synthesis Awareness
- Ensure generated VEX code utilizes standard Houdini channel evaluations so `houdini_ai_wrangle.py` can automatically bind dynamic UI controls:
  - `chf("name")` for float sliders
  - `chi("name")` for integer controls
  - `chv("name")` for 3D vector fields
  - `chs("name")` for string parameters
  - `chramp("name", val)` for spline color/value ramps
  - `chp("name")` for 4D vector / quaternion parameters

### 4. Houdini Scripts Directory Precedence
- `C:\Users\Anshul\Documents\houdini21.0\scripts\python\` takes precedence over `package.json` `pythonpath`. Whenever modifying Python files in `E:\#AI#\Houdini Attribute Wrangle\python\`, also copy them to `C:\Users\Anshul\Documents\houdini21.0\scripts\python\` and trigger `importlib.reload()`.

### 5. Zero Cloud & Security Integrity
- Never introduce cloud-dependent API calls (OpenAI, Anthropic, external web requests) into the core Houdini plugin runtime.
- Preserve the 100% offline, local-first isolation of `engine_manager.py` and `bin/llama-server.exe`.
- Protect the hardware-locking and cryptographic licensing logic in `license_validator.py`.
