"""
Houdini AI VEX Assistant & Copilot Module (v3.5 - Dual-Mode Intelligence)

Features:
  1. 🧠 Deep Reasoning Mode (CoT Thinking Monologue & Math Blueprint)
  2. ⚡ Turbo Fast Mode (1-2s Instant Pure VEX Generation)
  3. 🧠 Upstream Geometry Introspection (Live Attribs, Groups, Bounding Box, Volume Fields)
  4. ⏳ The VEX Time Machine (Non-Destructive Version History, Prev/Next Rollback)
  5. ⚡ SIMD Performance Profiler & AI Optimizer (Cook Micro-benchmarks, SIMD Hoisting)
  6. 💡 Inline Math Explanation & Auto-Documentation
  7. 🎛️ Dynamic Spare Parameter Generation (chf, chi, chv, chramp, chs)
  8. 🎯 Context Auto-Detection (Point, Prim, Detail, Vertex)
  9. 🛡️ Autonomous 1-Shot CITL Self-Repair
  10. 🛠️ 1-Click Shelf Tool Suite
"""
from __future__ import annotations

import os
import json
import re
import time
import math
import urllib.request
import urllib.error
try:
    import hou
except ImportError:
    hou = None

try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    try:
        from PySide2 import QtWidgets, QtCore, QtGui
    except ImportError:
        QtWidgets = None
        QtCore = None
        QtGui = None

try:
    from .vex_rag_engine import get_vex_rag_engine
except ImportError:
    try:
        from vex_rag_engine import get_vex_rag_engine
    except ImportError:
        get_vex_rag_engine = None

# ---------------------------------------------------------------------------
# Backend & Endpoint Configuration
# ---------------------------------------------------------------------------
LOCAL_API_URL = os.getenv("HOUDINI_VEX_AI_URL", "http://127.0.0.1:11434/api/generate")
LOCAL_MODEL_NAME = os.getenv("HOUDINI_VEX_AI_MODEL", "qwen3-vex:latest")

TURBO_SYSTEM_PROMPT = (
    "You are an expert SideFX Houdini VEX programmer and technical director.\n"
    "Output only valid Houdini VEX code with no markdown fences or conversational text.\n"
    "Follow these hard VEX API rules:\n"
    "- Mesh vs Single Point Invariant: In Point Wrangles, when moving or deforming a 3D mesh along a path/curve from Input 1, never assign '@P = target_pos;' which collapses all mesh vertices to a single point. Always apply relative centroid translation: '@P += (target_pos - getbbox_center(0));'.\n"
    "- Multi-Input Queries: Strictly query the correct input index (Input 0 for self/neighbours, Input 1 for external guide curve, collision surface, or volume).\n"
    "- Conditionals: Strictly use C-style if/else or ternary (cond ? a : b). Never use Python ternary ('a if cond else b').\n"
    "- Parallel SIMD Execution: In Point Wrangles operate directly on @ptnum. In Primitive Wrangles operate directly on @primnum. Do not loop over all points or primitives unless in a Detail Wrangle.\n"
    "- Attribute Binding: Export attributes with explicit type prefixes: f@mass, i@id, v@pos, s@name, p@orient, 4@transform. Never rely on dead local variables.\n"
    "- Vector Rotation: Rotate vectors using quaternion(radians(angle), axis) and qrotate(q, v), or a matrix transform. Never call rotate() directly on a vector.\n"
    "- Parameter Hoisting: Strictly do not use 'param.float' or 'param.vector'. Use float freq = chf(\"freq\"); vector off = chv(\"offset\"); or local variable declarations.\n"
    "- Array Sizing: Strictly use len(array) for array length. Never use array.size(), size(array), or sizeof().\n"
    "- Array Appending: Strictly use functional append(array, value). Never use array.append(value) or array.push(value).\n"
    "- Dynamic Vectors: Strictly construct dynamic vectors using set(x, y, z). Never use curly braces {x, y, z} with non-constant variables or vector(x, y, z).\n"
    "- Math Constants: Strictly use uppercase PI (e.g. 2.0 * PI). Lowercase pi is not defined.\n"
    "- Point Cloud iteration: int handle = pcopen(0, \"P\", @P, search_rad, maxpts); while (pciterate(handle)) { vector p; pcimport(handle, \"P\", p); ... } pcclose(handle);\n"
    "- Point Cloud array: int pts[] = pcfind(0, \"P\", @P, rad, maxpts); foreach (int pt; pts) { vector col = point(0, \"Cd\", pt); ... }\n"
    "- Surface queries: int hit_prim; vector hit_uv; float dist = xyzdist(1, @P, hit_prim, hit_uv); vector pos = primuv(1, \"P\", hit_prim, hit_uv);\n"
    "- Curve creation: int prim = addprim(0, \"polyline\"); int pt = addpoint(0, pos); addvertex(0, prim, pt);\n"
    "- Volume sampling: vector grad = volumegradient(1, \"density\", @P); float dens = volumesample(1, \"density\", @P);\n"
    "- Topology: int nbs[] = neighbours(0, @ptnum); int num_nbs = neighbourcount(0, @ptnum);\n"
    "- Groups: setpointgroup(0, \"group_name\", @ptnum, 1); inpointgroup(0, \"group_name\", @ptnum);\n"
    "- Half-Edge Traversal: int hedge = pointhedge(0, @ptnum); while (hedge != -1) { if (hedge_nextequiv(0, hedge) == hedge) { setpointgroup(0, \"boundary\", @ptnum, 1); break; } hedge = pointhedgenext(0, hedge); }\n"
    "- Quaternions: vector4 q_align = dihedral({0,1,0}, normalize(v@v)); vector4 q_spin = quaternion(angle, axis); p@orient = qmultiply(q_spin, q_align);\n"
    "- Math functions: square is pow(x, 2.0) or x * x. Smooth interpolation is smooth(min, max, val). Value remapping is fit(val, omin, omax, nmin, nmax).\n"
    "- Standard Bindings: access position via @P, normal via @N, velocity via v@v, color via @Cd."
)

REASONING_SYSTEM_PROMPT = (
    "You are an expert SideFX Houdini VEX programmer and technical director.\n"
    "When presented with a task, FIRST think carefully in a structured <think>...</think> block (max 3-5 sentences):\n"
    "  1. Topology & Dimensionality: Inspect incoming geometry from context (Input 0 mesh vs point cloud vs curve; Input 1 target surface/curve/volume).\n"
    "  2. Spatial Invariant: In Point Wrangles, code executes in parallel per-point (@ptnum). If translating/deforming a 3D mesh (e.g. following a curve from Input 1), NEVER assign absolute coordinates '@P = target;' which collapses all mesh vertices into a single point. Always use relative translation: '@P += (target - getbbox_center(0));'.\n"
    "  3. Multi-Input Mapping: Ensure queries use the correct input index (e.g. primuv(1, ...), xyzdist(1, ...), volumesample(1, ...)).\n"
    "  4. Robust Parameters: Expose intuitive sliders (chf, chi, chv, chramp) with safe non-zero defaults.\n"
    "Close the </think> tag promptly, then output ONLY the pure, verified Houdini VEX code.\n"
    "Follow these hard VEX API rules:\n"
    "- Mesh vs Single Point Invariant: In Point Wrangles, when moving or deforming a 3D mesh along a path/curve from Input 1, never assign '@P = target_pos;' which collapses all mesh vertices to a single point. Always apply relative centroid translation: '@P += (target_pos - getbbox_center(0));'.\n"
    "- Multi-Input Queries: Strictly query the correct input index (Input 0 for self/neighbours, Input 1 for external guide curve, collision surface, or volume).\n"
    "- Conditionals: Strictly use C-style if/else or ternary (cond ? a : b). Never use Python ternary ('a if cond else b').\n"
    "- Parallel SIMD Execution: In Point Wrangles operate directly on @ptnum. In Primitive Wrangles operate directly on @primnum. Do not loop over all points or primitives unless in a Detail Wrangle.\n"
    "- Attribute Binding: Export attributes with explicit type prefixes: f@mass, i@id, v@pos, s@name, p@orient, 4@transform. Never rely on dead local variables.\n"
    "- Vector Rotation: Rotate vectors using quaternion(radians(angle), axis) and qrotate(q, v), or a matrix transform. Never call rotate() directly on a vector.\n"
    "- Parameter Hoisting: Strictly do not use 'param.float' or 'param.vector'. Use float freq = chf(\"freq\"); vector off = chv(\"offset\"); or local variable declarations.\n"
    "- Array Sizing: Strictly use len(array) for array length. Never use array.size(), size(array), or sizeof().\n"
    "- Array Appending: Strictly use functional append(array, value). Never use array.append(value) or array.push(value).\n"
    "- Dynamic Vectors: Strictly construct dynamic vectors using set(x, y, z). Never use curly braces {x, y, z} with non-constant variables or vector(x, y, z).\n"
    "- Math Constants: Strictly use uppercase PI (e.g. 2.0 * PI). Lowercase pi is not defined.\n"
    "- Point Cloud iteration: int handle = pcopen(0, \"P\", @P, search_rad, maxpts); while (pciterate(handle)) { vector p; pcimport(handle, \"P\", p); ... } pcclose(handle);\n"
    "- Point Cloud array: int pts[] = pcfind(0, \"P\", @P, rad, maxpts); foreach (int pt; pts) { vector col = point(0, \"Cd\", pt); ... }\n"
    "- Surface queries: int hit_prim; vector hit_uv; float dist = xyzdist(1, @P, hit_prim, hit_uv); vector pos = primuv(1, \"P\", hit_prim, hit_uv);\n"
    "- Curve creation: int prim = addprim(0, \"polyline\"); int pt = addpoint(0, pos); addvertex(0, prim, pt);\n"
    "- Volume sampling: vector grad = volumegradient(1, \"density\", @P); float dens = volumesample(1, \"density\", @P);\n"
    "- Topology: int nbs[] = neighbours(0, @ptnum); int num_nbs = neighbourcount(0, @ptnum);\n"
    "- Groups: setpointgroup(0, \"group_name\", @ptnum, 1); inpointgroup(0, \"group_name\", @ptnum);\n"
    "- Half-Edge Traversal: int hedge = pointhedge(0, @ptnum); while (hedge != -1) { if (hedge_nextequiv(0, hedge) == hedge) { setpointgroup(0, \"boundary\", @ptnum, 1); break; } hedge = pointhedgenext(0, hedge); }\n"
    "- Quaternions: vector4 q_align = dihedral({0,1,0}, normalize(v@v)); vector4 q_spin = quaternion(angle, axis); p@orient = qmultiply(q_spin, q_align);\n"
    "- Math functions: square is pow(x, 2.0) or x * x. Smooth interpolation is smooth(min, max, val). Value remapping is fit(val, omin, omax, nmin, nmax).\n"
    "- Standard Bindings: access position via @P, normal via @N, velocity via v@v, color via @Cd."
)

CLASS_MAP = {
    0: "detail wrangle",
    1: "primitive wrangle",
    2: "point wrangle",
    3: "vertex wrangle",
}

# ---------------------------------------------------------------------------
# Embedded Engine Auto-Start (Background Thread)
# ---------------------------------------------------------------------------
_engine_singleton = None
_engine_error = ""


def _package_root() -> str:
    """Return the installed package root without relying on the current HIP."""
    return os.environ.get("AI_WRANGLE_ROOT") or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )


class _engine_load_progress:
    """Interruptible progress dialog while the engine loads a model (first Generate / model switch),
    so loading several GB of weights never looks like a hang and Esc / Cancel aborts it."""

    def __init__(self, model_path):
        self.label = f"AI VEX Copilot: loading {os.path.basename(model_path or 'model')} (Esc / Cancel to stop)"
        self.op = None

    def __enter__(self):
        try:
            self.op = hou.InterruptableOperation(self.label, open_interrupt_dialog=True)
            self.op.__enter__()
        except Exception:
            self.op = None
        return self.tick

    def tick(self):
        if self.op is not None:
            self.op.updateProgress(-1.0)  # raises hou.OperationInterrupted on cancel

    def __exit__(self, *exc):
        if self.op is not None:
            try:
                self.op.__exit__(None, None, None)
            except Exception:
                pass
        return False


def ensure_embedded_engine(target_model_path: str = None) -> bool:
    """Start and verify the bundled engine when it is first needed.

    If target_model_path is provided, ensures that the running engine is serving that
    specific model weights file, switching it if necessary.
    """
    global _engine_singleton, _engine_error
    if _engine_singleton and _engine_singleton.is_healthy():
        if not target_model_path:
            return True
        target_name = os.path.basename(target_model_path)
        active_info = _engine_singleton.get_model_info_string()
        if target_name in active_info or (getattr(_engine_singleton, "active_model_name", None) == target_name):
            return True
    try:
        pkg_root = _package_root()
        import sys
        for p in [pkg_root, os.path.join(pkg_root, "python")]:
            if os.path.isdir(p) and p not in sys.path:
                sys.path.insert(0, p)

        try:
            from engine_manager import EngineManager
        except ImportError:
            try:
                from .engine_manager import EngineManager
            except ImportError as err:
                _engine_error = f"Cannot import engine_manager: {err}"
                return False

        import shutil

        # Discover inference engine binary
        engine_env = os.environ.get("AI_WRANGLE_ENGINE_BIN")
        winget_engine = os.path.expanduser(
            r"~\AppData\Local\Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-server.exe"
        )
        engine_candidates = [
            engine_env,
            os.path.join(pkg_root, "bin", "llama-server.exe"),
            shutil.which("llama-server.exe"),
            shutil.which("llama-server"),
            winget_engine,
            r"C:\Program Files\llama.cpp\llama-server.exe",
        ]
        # Wildcard search for any WinGet llama-server installation
        try:
            import glob
            wg_matches = glob.glob(
                os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\*llama*\**\llama-server.exe"),
                recursive=True
            )
            if wg_matches:
                engine_candidates.extend(wg_matches)
        except Exception:
            pass

        engine_bin = next((b for b in engine_candidates if b and os.path.isfile(b)), None)

        # Discover AI model weights: explicit selection, else env override / newest fine-tuned model
        model_dir = os.path.join(pkg_root, "models")
        model_path = target_model_path if (target_model_path and os.path.isfile(target_model_path)) else None
        if not model_path:
            model_path = _default_model_path()
            if not model_path and os.path.isfile(os.path.join(pkg_root, "qwen3-vex.gguf")):
                model_path = os.path.join(pkg_root, "qwen3-vex.gguf")

        if not engine_bin or not os.path.exists(engine_bin):
            _engine_error = (
                f"Inference engine 'llama-server.exe' not found.\n"
                f"• Searched path: {os.path.join(pkg_root, 'bin', 'llama-server.exe')}\n\n"
                "To fix in 10 seconds:\n"
                "1. Open PowerShell / Command Prompt and run:\n"
                "   winget install ggml.llamacpp\n"
                "2. OR place 'llama-server.exe' inside your plugin 'bin/' folder."
            )
            return False
        if not model_path or not os.path.exists(model_path):
            _engine_error = (
                "AI model weights not found. Please place model weights "
                "into the 'models/' folder."
            )
            return False

        if _engine_singleton and _engine_singleton.is_healthy():
            target_name = os.path.basename(model_path)
            active_info = _engine_singleton.get_model_info_string()
            if target_name in active_info or (getattr(_engine_singleton, "active_model_name", None) == target_name):
                return True
            with _engine_load_progress(model_path) as cb:
                switched = _engine_singleton.switch_model(engine_bin, model_path, wait_callback=cb)
            if switched:
                _engine_error = ""
                return True
            _engine_error = _engine_singleton.last_error or "Could not switch to selected model."
            return False

        mgr = EngineManager()
        with _engine_load_progress(model_path) as cb:
            started = mgr.start_embedded_engine(engine_bin, model_path, wait_callback=cb)
        if started:
            _engine_singleton = mgr
            _engine_error = ""
            import atexit
            atexit.register(_shutdown_embedded_engine)
            return True
        _engine_error = mgr.last_error or "The bundled inference engine did not become healthy."
        return False
    except Exception as exc:
        _engine_error = str(exc)
        return False


def _engine_port() -> int:
    """Port of the running engine, else the port a new engine would use."""
    port = getattr(_engine_singleton, "port", None)
    if port:
        return int(port)
    try:
        import engine_manager
        return int(engine_manager.DEFAULT_PORT)
    except Exception:
        return int(os.getenv("AI_WRANGLE_PORT") or 58321)


def _shutdown_embedded_engine():
    """Cleanup handler registered with atexit."""
    global _engine_singleton
    if _engine_singleton:
        _engine_singleton.stop_engine()
        _engine_singleton.cleanup_cache()
        _engine_singleton = None


# ---------------------------------------------------------------------------
# Model Resolution & Parsing
# ---------------------------------------------------------------------------

# Held-out Houdini benchmarks (tasks checked on cooked geometry): model alone / full plugin pipeline.
# v51 and v53: six suites A-F, 284 tasks (benchmarks/, 2026-11-11). Older entries: suite A only (57 tasks).
# Shown in the model menu and info field.
_MODEL_NOTES = {
    55: "held-out 166/284 alone, 199/284 with plugin - Recommended",
    53: "held-out 138/284 alone, 188/284 with plugin",
    51: "held-out 117/284 alone, 143/284 with plugin",
    49: "held-out 33/57 raw, 36/57 with plugin",
    48: "held-out 29/57 raw, 36/57 with plugin",
    47: "held-out 16/57 raw",
    46: "held-out 19/57 raw, 32/57 with plugin",
}
_FINETUNE_RE = re.compile(r"houdini-vex-v(\d+)", re.IGNORECASE)


def _model_version(name: str) -> int:
    """Version of a fine-tuned 'Qwen3-8B-Houdini-VEX-vNN' weights file, -1 for anything else."""
    m = _FINETUNE_RE.search(os.path.basename(name))
    return int(m.group(1)) if m else -1


def _discover_models() -> list[str]:
    """Absolute paths of selectable full-model GGUF/DAT files in models/, best first:
    fine-tuned versions newest-first, then anything else (base models) by name."""
    model_dir = os.path.join(_package_root(), "models")
    if not os.path.isdir(model_dir):
        return []
    found = []
    for f in os.listdir(model_dir):
        fl = f.lower()
        if fl.startswith(".") or "lora" in fl or "merged-16bit" in fl:
            continue
        if fl.endswith((".gguf", ".dat")):
            found.append(os.path.join(model_dir, f))
    found.sort(key=lambda p: (_model_version(p), os.path.basename(p).lower()), reverse=True)
    return found


def _default_model_path() -> str | None:
    """Model used for 'Auto': AI_WRANGLE_MODEL_PATH override, else the newest fine-tuned model."""
    env = os.environ.get("AI_WRANGLE_MODEL_PATH")
    if env and os.path.isfile(env):
        return env
    models = _discover_models()
    return models[0] if models else None


def _describe_model(path_or_name: str) -> str:
    name = os.path.basename(path_or_name)
    v = _model_version(name)
    if v < 0:
        return name
    note = _MODEL_NOTES.get(v)
    return f"{name} (v{v}{', ' + note if note else ''})"


def get_active_ai_model_display_string() -> str:
    """Human-readable name of the model in use. Never touches the network: this runs on node
    creation (OnCreated) and must not stall the UI."""
    if _engine_singleton is not None:
        active = getattr(_engine_singleton, "active_model_name", None)
        if active:
            return _describe_model(active)
    default = _default_model_path()
    if default:
        return _describe_model(default) + " [not loaded yet]"
    return "No model found in models/ (place a Qwen3-8B-Houdini-VEX GGUF there)"


# ---------------------------------------------------------------------------
# Dynamic Model Menu & Engine Switching
# ---------------------------------------------------------------------------

def get_available_models_menu_items() -> list[str]:
    """Dynamically enumerates available GGUF/DAT models in the models directory for Houdini Menu scripts.
    Returns a flat list of token-label pairs: [token1, label1, token2, label2, ...]
    """
    default = _default_model_path()
    auto_label = f"Auto ({os.path.basename(default)})" if default else "Auto (no model found)"
    items = ["auto", auto_label]
    for path in _discover_models():
        v = _model_version(path)
        note = _MODEL_NOTES.get(v)
        name = os.path.basename(path)
        label = f"v{v} - {note}" if (v >= 0 and note) else (f"v{v} ({name})" if v >= 0 else name)
        items.extend([name, label])  # token is the file name: stable when new models are added
    items.extend(["custom", "Custom Model File..."])
    return items


def resolve_selected_model_path(node: hou.Node = None) -> str | None:
    """Returns absolute path to the selected model weights file, or None for auto default."""
    if not node:
        return None
    try:
        model_parm = node.parm("ai_model_select")
        if not model_parm:
            return None
        choice = model_parm.evalAsString()
        if not choice or choice == "auto":
            return _default_model_path()
        if choice == "custom":
            custom_path = node.evalParm("ai_custom_model_path")
            if custom_path and os.path.isfile(custom_path):
                return custom_path
            return None
        pkg_root = _package_root()
        candidate = os.path.join(pkg_root, "models", choice)
        if os.path.isfile(candidate):
            return candidate
    except Exception:
        pass
    return None


def switch_active_model(target_model_path: str = None, node: hou.Node = None) -> bool:
    """Switches the running local inference engine to the specified model."""
    global _engine_singleton, _engine_error
    if node:
        try:
            status_p = node.parm("ai_status")
            if status_p:
                status_p.set("Switching inference engine model...")
        except Exception:
            pass

    success = ensure_embedded_engine(target_model_path)
    if success:
        display_str = get_active_ai_model_display_string()
        if node:
            try:
                info_p = node.parm("ai_model_info")
                if info_p:
                    info_p.set(display_str)
                status_p = node.parm("ai_status")
                if status_p:
                    status_p.set(f"Ready — Active Engine: {display_str}")
            except Exception:
                pass
        return True
    else:
        err_msg = _engine_error or "Failed to switch model."
        if node:
            try:
                status_p = node.parm("ai_status")
                if status_p:
                    status_p.set(f"Error switching model: {err_msg[:60]}")
            except Exception:
                pass
        return False


def on_model_select_changed(kwargs: dict) -> None:
    """Triggered when the user picks a model from ai_model_select dropdown."""
    node = kwargs.get("node")
    if not node:
        return
    choice = node.parm("ai_model_select").evalAsString()
    if choice == "custom":
        status_p = node.parm("ai_status")
        if status_p:
            status_p.set("Custom model selected — choose file path and click 'Switch Model'.")
        return
    # Picking from the menu only records the choice: loading several GB of weights on a menu change
    # froze Houdini. The engine switches on the next Generate, or now via "Switch Model".
    model_path = resolve_selected_model_path(node) or _default_model_path()
    status_p = node.parm("ai_status")
    if status_p:
        status_p.set(f"Model set to {os.path.basename(model_path) if model_path else 'Auto'} - loads on next Generate "
                     f"(or press Switch Model to load now).")
    info_p = node.parm("ai_model_info")
    if info_p and model_path:
        info_p.set(_describe_model(model_path) + " [selected]")


def on_switch_model_clicked(kwargs: dict) -> None:
    """Triggered when the user clicks 'Switch Model' button."""
    node = kwargs.get("node")
    if not node:
        return
    model_path = resolve_selected_model_path(node)
    switch_active_model(model_path, node)


def resolve_model_name() -> str:
    model = LOCAL_MODEL_NAME
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            installed = [m["name"] for m in data.get("models", [])]
            for inst in installed:
                if inst == model or inst.startswith(f"{model}:"):
                    return inst
            for preferred in ["qwen3-vex:latest", "qwen3-vex", "qwen2.5-coder:7b"]:
                for inst in installed:
                    if inst == preferred or inst.startswith(f"{preferred}:"):
                        return inst
            if installed:
                return installed[0]
    except Exception:
        pass
    return model


def extract_thought_and_code(raw_output: str) -> tuple[str, str]:
    """
    Extracts the <think> reasoning monologue and the pure VEX code.
    Returns (thought_trace, pure_vex_code).
    """
    raw = raw_output.strip()
    thought_trace = ""
    code = raw

    if "<think>" in raw:
        if "</think>" in raw:
            parts = raw.split("</think>", 1)
            thought_part = parts[0].split("<think>", 1)[-1].strip()
            thought_trace = thought_part
            code = parts[1].strip()
        else:
            thought_trace = raw.replace("<think>", "").strip()
            code = ""
    elif "</think>" in raw:
        parts = raw.split("</think>", 1)
        thought_trace = parts[0].strip()
        code = parts[1].strip()

    # Extract from markdown code fences if present
    if "```" in code:
        m = re.search(r"```[a-zA-Z0-9_-]*\s*([\s\S]*?)\s*```", code)
        if m:
            code = m.group(1).strip()
        else:
            lines = [l for l in code.splitlines() if not l.strip().startswith("```")]
            code = "\n".join(lines).strip()

    return thought_trace, code


def sanitize_vex_syntax(code: str) -> str:
    """Pass-through for pure neural model generation with safety alias normalization."""
    if not code:
        return ""
    c = code.strip()
    c = re.sub(r'\bcurlnoise(?:2d|3d|4d)?\b', 'curlnoise', c, flags=re.IGNORECASE)
    c = re.sub(r'\bsnoise(?:2d|3d|4d)?\b', 'snoise', c, flags=re.IGNORECASE)
    c = re.sub(r'\bpnoise(?:2d|3d|4d)?\b', 'pnoise', c, flags=re.IGNORECASE)
    c = re.sub(r'\bxnoise(?:2d|3d|4d)?\b', 'xnoise', c, flags=re.IGNORECASE)
    c = re.sub(r'\bprimcenter\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)', r'primuv(\1, "P", \2, set(0.5, 0.5, 0.0))', c, flags=re.IGNORECASE)
    c = re.sub(r'\b(?:dist|pointdistance)\s*\(', 'distance(', c, flags=re.IGNORECASE)
    c = re.sub(r'\bmag\s*\(', 'length(', c, flags=re.IGNORECASE)
    c = re.sub(r'\bnorm\s*\(', 'normalize(', c, flags=re.IGNORECASE)
    c = re.sub(r'\bquat\s*\(', 'quaternion(', c, flags=re.IGNORECASE)
    c = re.sub(r'\bvec[234]\s*\(', 'set(', c)
    c = re.sub(r'(?<![a-zA-Z0-9_])@UV\b', 'v@uv', c)
    c = re.sub(r'</?think>', '', c)

    # Normalize non-existent exists() to hasattrib()
    c = re.sub(r'(!?)\bexists\s*\(\s*(?:[vspif4]?@)?([a-zA-Z0-9_]+)\s*\)', r'\1hasattrib(0, "point", "\2")', c)

    # Normalize accidental C-style foreach loops (e.g. foreach (int i = 0; i < len; i++)) to standard for loops
    c = re.sub(r'\bforeach\s*\(\s*(?:int\s+)?([a-zA-Z0-9_]+\s*=[^;]+;[^;]+;[^)]+)\)', r'for (int \1)', c)

    # Normalize 3-argument nearpoint(input, pt, int_seed_var) where 3rd argument is an integer point index instead of float maxdist
    def _normalize_nearpoint(m):
        geo = m.group(1).strip()
        pos = m.group(2).strip()
        arg3 = m.group(3).strip()
        if any(k in arg3.lower() for k in ("pt", "seed", "[", "point", "prim")):
            return f"nearpoint({geo}, {pos})"
        return m.group(0)

    c = re.sub(
        r'\bnearpoint\s*\(\s*([^,;()\n]+)\s*,\s*([^,;()\n]+)\s*,\s*([^,;()\n]+)\s*\)',
        _normalize_nearpoint,
        c
    )

    # Normalize invalid 4-argument setattrib(geohandle, name, elemnum, value)
    def _normalize_setattrib(m):
        geo = m.group(1).strip()
        name = m.group(2).strip()
        elem = m.group(3).strip()
        val = m.group(4).strip()
        elem_lower = elem.lower()
        if any(k in elem_lower for k in ("pt", "point", "vtx", "vertex")):
            return f"setpointattrib({geo}, {name}, {elem}, {val})"
        return f"setprimattrib({geo}, {name}, {elem}, {val})"

    c = re.sub(
        r'\bsetattrib\s*\(\s*([^,]+)\s*,\s*("[^"]+"|\'[^\']+\')\s*,\s*([^,]+)\s*,\s*([^,)]+)\s*\)',
        _normalize_setattrib,
        c
    )

    # Resolve chramp() polymorphic ambiguity in set*attrib() calls.
    c = _resolve_chramp_polymorphic_ambiguity(c)

    # Clean up bogus isvalidindex checks and simplify file-path ramp strings to clean parameter names
    c = re.sub(r'if\s*\(!isvalidindex\s*\([^)]+\)\)\s*\{[^}]*\}', '', c)
    c = re.sub(r'string\s+ramp_name\s*=\s*"[^"]*/([^/.]+)[^"]*";', r'string ramp_name = "\1";', c)
    c = re.sub(r'chramp\s*\(\s*["\'][^"\']*/([^"\'/]+)\.ramp["\']', r'chramp("\1"', c)

    # Inline local string variables passed into chramp(var, ...) so Houdini can build the ramp UI parameter
    str_vars = dict(re.findall(r'string\s+([a-zA-Z0-9_]+)\s*=\s*["\']([^"\']+)["\'];', c))
    for var, val in str_vars.items():
        c = re.sub(rf'\bchramp\s*\(\s*{var}\s*,', f'chramp("{val}",', c)

    # Normalize undeclared standalone P to @P (strictly outside of string quotes and member access)
    if not re.search(r'\b(?:vector|float|int|matrix)\s+P\b', c):
        c = re.sub(r'(?<![@a-zA-Z0-9_"\'.])P(?![a-zA-Z0-9_"\'])', '@P', c)

    # Normalize invalid @ prefix inside attribute string literals (e.g. "@P" -> "P", "@Cd" -> "Cd")
    c = re.sub(r'(["\'])@([a-zA-Z_][a-zA-Z0-9_]*)\1', r'\1\2\1', c)

    # Auto-repair half-edge boundary condition: hedge_nextequiv(geo, h) == -1 -> hedge_nextequiv(geo, h) == h
    c = re.sub(r'hedge_nextequiv\s*\(\s*([^,]+)\s*,\s*([a-zA-Z0-9_]+)\s*\)\s*==\s*-1', r'hedge_nextequiv(\1, \2) == \2', c)
    c = re.sub(r'([a-zA-Z0-9_]+)\s*=\s*hedge_nextequiv\s*\(\s*([^,]+)\s*,\s*([a-zA-Z0-9_]+)\s*\);\s*if\s*\(\s*\1\s*==\s*-1', r'\1 = hedge_nextequiv(\2, \3);\n    if (\1 == \3', c)

    # Auto-repair invalid 5-argument xyzdist(input, "P", pos, prim, uv) -> xyzdist(input, pos, prim, uv)
    c = re.sub(r'\bxyzdist\s*\(\s*([^,]+)\s*,\s*["\']P["\']\s*,', r'xyzdist(\1, ', c)

    # Normalize pclose() typo to pcclose()
    c = re.sub(r'\bpclose\s*\(', 'pcclose(', c)

    # Normalize 2-argument addvertex(prim, pt) to addvertex(0, prim, pt)
    c = re.sub(r'\baddvertex\s*\(\s*([a-zA-Z0-9_]+)\s*,\s*([a-zA-Z0-9_]+)\s*\)', r'addvertex(0, \1, \2)', c)

    # Normalize reserved keyword @break to @broken to prevent C++ VEX parser crash
    c = re.sub(r'([vspif4]?@)break\b', r'\1broken', c)

    # Normalize 2-argument volumegradient(input, pos) missing field name string
    c = re.sub(r'\bvolumegradient\s*\(\s*([^,\r\n]+)\s*,\s*(@?[a-zA-Z0-9_]+)\s*\)', r'volumegradient(\1, "density", \2)', c)

    # Normalize half-edge aliases & typo hedgeprim -> hedge_prim
    c = re.sub(r'\bhedgeprim\s*\(', 'hedge_prim(', c)
    c = re.sub(r'\bpointhedgeother\s*\(', 'hedge_dstpoint(', c)
    c = re.sub(r'\bhedge_point\s*\(', 'hedge_dstpoint(', c)

    # Normalize C-style bitwise shift operators (<< and >>) to native VEX shl() and shr()
    c = re.sub(r'([a-zA-Z0-9_]+|\([^)]+\))\s*>>\s*([a-zA-Z0-9_]+|\([^)]+\))', r'shr(\1, \2)', c)
    c = re.sub(r'([a-zA-Z0-9_]+|\([^)]+\))\s*<<\s*([a-zA-Z0-9_]+|\([^)]+\))', r'shl(\1, \2)', c)

    # Normalize 3-argument volumegradient(input, pos, out_var) to out_var = volumegradient(input, "density", pos)
    c = re.sub(r'\bvolumegradient\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([a-zA-Z0-9_]+)\s*\);', r'\3 = volumegradient(\1, "density", \2);', c)

    # Normalize invalid 4-argument minpos(geo, pos, prim, uv) to xyzdist(geo, pos, prim, uv)
    c = re.sub(r'\bminpos\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)', r'xyzdist(\1, \2, \3, \4)', c)

    # Normalize matrix assigned directly to quaternion p@orient -> quaternion(matrix3(...))
    def _normalize_orient_assign(m):
        var = m.group(1).strip()
        if var.startswith('q') or var.startswith('orient') or f"vector4 {var}" in c:
            return m.group(0)
        if var in ('m', 'mat', 'rot_m', 'xform', 'transform', 'localtransform') or f"matrix {var}" in c or f"matrix3 {var}" in c or var.startswith('4@'):
            return f"p@orient = quaternion(matrix3({var}));"
        return m.group(0)
    c = re.sub(r'p@orient\s*=\s*([a-zA-Z0-9_]+)\s*;', _normalize_orient_assign, c)

    # Normalize invalid p@P to standard @P
    c = re.sub(r'\bp@P\b', '@P', c)

    # Normalize C-style casts (float)x -> float(x), (int)x -> int(x)
    c = re.sub(r'\(\s*(float|int)\s*\)\s*([a-zA-Z0-9_]+|\([^)]+\))', r'\1(\2)', c)

    # Normalize 5-argument usd_setattrib(stage, primpath, name, type_str, val) -> usd_setattrib(stage, primpath, name, val)
    c = re.sub(r'\busd_setattrib\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*["\'](?:float|int|string|vector|vector4|matrix)["\']\s*,\s*([^)]+)\s*\)', r'usd_setattrib(\1, \2, \3, \4)', c)

    # Normalize invalid qrotate call attempting to rotate a matrix in place
    c = re.sub(r'qrotate\s*\(\s*quaternion\s*\((.+),\s*([a-zA-Z0-9_]+)\s*\)\s*\)\s*;', r'rotate(\2, \1);', c)

    # Normalize invalid volumenormal on surface geometry
    c = re.sub(r'\bdistance\s*\(\s*@P\s*,\s*volumenormal\s*\([^)]*\)\s*\)', r'abs(noise_val - threshold)', c)
    c = re.sub(r'\bvolumenormal\s*\([^)]*\)', r'@N', c)

    # Normalize non-standard fpoint/vpoint/ipoint aliases to point(0, attrib, pt)
    c = re.sub(r'\b[fvi]point\s*\(\s*([^,]+)\s*,\s*("[^"]+"|\'[^\']+\')\s*\)', r'point(0, \2, \1)', c)

    # Protect against accidental 3D mesh collapse when sampling curve trajectories:
    # @P = path_pos -> @P += (path_pos - getbbox_center(0))
    if ("primuv" in c or "path_pos" in c or "curve_pos" in c) and "@P =" in c:
        c = re.sub(
            r'@P\s*=\s*([a-zA-Z0-9_]*(?:path|curve|pos)[a-zA-Z0-9_]*)\s*;',
            r'@P += (\1 - getbbox_center(0));',
            c
        )

    # Ensure speed channel has a non-zero runtime fallback if multiplied with @Time
    if re.search(r'@Time\s*\*\s*speed\b', c) and "if (speed == 0.0)" not in c:
        c = re.sub(
            r'(float\s+speed\s*=\s*chf\s*\(\s*["\']speed["\']\s*\)\s*;)',
            r'\1\nif (speed == 0.0) speed = 0.5;',
            c
        )

    # Auto-repair 4-argument minpos(input, pos, prim, uv) -> xyzdist + primuv
    c = re.sub(
        r'vector\s+([a-zA-Z0-9_]+)\s*=\s*minpos\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\);',
        r'xyzdist(\2, \3, \4, \5);\nvector \1 = primuv(\2, "P", \4, \5);',
        c
    )

    # Auto-repair matrix = quaternion(...) assignment
    c = re.sub(r'\bmatrix\s+([a-zA-Z0-9_]+)\s*=\s*(quaternion\s*\([^;]+\));', r'vector4 \1 = \2;', c)
    c = re.sub(r'\bmatrix3\s+([a-zA-Z0-9_]+)\s*=\s*(quaternion\s*\([^;]+\));', r'vector4 \1 = \2;', c)

    # Auto-repair split matrix declaration and quaternion assignment
    c = re.sub(
        r'(\bmatrix\s+([a-zA-Z0-9_]+)\s*;\s*[\r\n]+(?:\s*[^\r\n]+[\r\n]+)*?\s*)\2\s*=\s*(quaternion\s*\([^;]+\));',
        r'vector4 \2 = \3;',
        c
    )

    # Auto-repair quaternion assigned and multiplied into 4@localtransform or matrix
    c = re.sub(
        r'([a-zA-Z0-9_]+)\s*=\s*quaternion\s*\((.*?)\);\s*[\r\n]+\s*(?:4@localtransform|4@transform|([a-zA-Z0-9_]+))\s*=\s*([a-zA-Z0-9_]+)\s*\*\s*\1\s*;',
        r'rotate(\4, radians(chf("angle")), set(0, 1, 0));\n4@localtransform = \4;',
        c
    )

    # Auto-repair qrotate on 4x4 matrix: qrotate(rot, m) -> rotate(m, angle, axis)
    c = re.sub(r'([a-zA-Z0-9_]+)\s*=\s*qrotate\s*\(\s*[^,]+\s*,\s*\1\s*\);', r'rotate(\1, radians(chf("angle")), set(0, 1, 0));', c)

    # Auto-repair neighbours() type mismatch: int n = neighbours( -> int n[] = neighbours(
    c = re.sub(r'\bint\s+([a-zA-Z0-9_]+)\s*=\s*neighbours\s*\(', r'int \1[] = neighbours(', c)
    c = re.sub(
        r'if\s*\(\s*([a-zA-Z0-9_]+)\s*>=\s*0\s*\)\s*\{\s*vector\s+([a-zA-Z0-9_]+)\s*=\s*point\s*\(\s*0\s*,\s*["\']P["\']\s*,\s*\1\s*\);',
        r'if (len(\1) > 0) {\n    int _first_nb = \1[0];\n    vector \2 = point(0, "P", _first_nb);',
        c
    )

    # Auto-repair 2-argument curlnoise with float: curlnoise(pos, float) -> curlnoise(pos)
    c = re.sub(r'\bcurlnoise\s*\(\s*([^,]+)\s*,\s*[0-9.]+(?:f)?\s*\)', r'curlnoise(\1)', c)

    # Auto-repair intersect argument ordering where hit_prim was passed 4th instead of return value
    c = re.sub(
        r'\bintersect\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([a-zA-Z0-9_]+)\s*,\s*([a-zA-Z0-9_]+)\s*,\s*([a-zA-Z0-9_]+)\s*\);',
        r'\4 = intersect(\1, \2, \3, \5, \6);',
        c
    )

    # Auto-repair sqr(x) pseudo-code to VEX pow(x, 2)
    c = re.sub(r'\bsqr\s*\(\s*([^()]+)\s*\)', r'pow(\1, 2)', c)

    # Auto-repair makeidentity() alias to native VEX ident()
    c = re.sub(r'\bmakeidentity\s*\(\s*\)', 'ident()', c)

    # Auto-repair GLSL vector rotate bleed: rotate(vec, angle, axis) -> qrotate(quaternion(angle, axis), vec)
    c = re.sub(
        r'\brotate\s*\(\s*([a-zA-Z0-9_@.]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)',
        lambda m: f"rotate({m.group(1)}, {m.group(2)}, {m.group(3)})" if (m.group(1).strip() in ('m', 'mat', 'rot', 'r', 'xform', 'transform', 'localtransform', 'worldtransform') or f"matrix {m.group(1).strip()}" in c or f"matrix3 {m.group(1).strip()}" in c or m.group(1).startswith(('4@', '3@'))) else f"qrotate(quaternion({m.group(2)}, {m.group(3)}), {m.group(1)})",
        c
    )

    # Auto-repair quaternion variable type declaration: quaternion q = -> vector4 q =
    c = re.sub(r'\bquaternion\s+([a-zA-Z0-9_]+)\s*=', r'vector4 \1 =', c)

    # Auto-repair scalar point attribute array indexing: f@attr[n] -> point(0, "attr", n)
    c = re.sub(r'([fvi])@([a-zA-Z0-9_]+)\[([a-zA-Z0-9_]+)\]', r'point(0, "\2", \3)', c)

    # Auto-repair primpoints scalar count assignment: int n = primpoints(...) -> int n = len(primpoints(...))
    c = re.sub(r'\bint\s+([a-zA-Z0-9_]+)\s*=\s*primpoints\s*\(([^;]*)\)\s*;', r'int \1 = len(primpoints(\2));', c)

    # Auto-repair 4x4 matrix passed to quaternion(): quaternion(m) -> quaternion(matrix3(m))
    _mat4_vars = set(re.findall(r'\bmatrix\s+([a-zA-Z0-9_]+)', c))
    c = re.sub(r'\bquaternion\s*\(\s*([a-zA-Z0-9_]+)\s*\)',
               lambda m: f"quaternion(matrix3({m.group(1)}))" if m.group(1) in _mat4_vars else m.group(0), c)

    # Auto-repair xyzdist 4th argument parameter ordering when float dist was passed:
    if re.search(r'\bxyzdist\s*\(\s*[^,]+\s*,\s*[^,]+\s*,\s*[^,]+\s*,\s*dist\s*\)', c):
        c = re.sub(
            r'xyzdist\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*dist\s*\);',
            r'vector uv;\nfloat dist = xyzdist(\1, \2, \3, uv);',
            c
        )
        c = re.sub(r'\bfloat\s+dist\s*;\s*', '', c)
        c = re.sub(r'\bvector\s+uv\s*;\s*', '', c)
        c = re.sub(r'\bprimuv\s*\(\s*([^,]+)\s*,\s*["\']uv["\']\s*,\s*([a-zA-Z0-9_]+)\s*,\s*uv\s*\);\s*', '', c)

    # Auto-repair m = rotate(m, ...) in-place void assignment
    c = re.sub(r'([a-zA-Z0-9_]+)\s*=\s*rotate\s*\(\s*\1\s*,', r'rotate(\1,', c)

    # Auto-repair C/C++ fixed-width integer types (int16, int32, int64, uint, uint32, etc.) to native VEX int
    c = re.sub(r'\b(?:u?int(?:8|16|32|64)|uint)\b', 'int', c)

    # Auto-repair hallucinated SDF sphere distance helper: sphere_distance(pos) -> (length(pos) - 1.0)
    c = re.sub(r'\bsphere_distance\s*\(\s*([^)]+)\s*\)', r'(length(\1) - 1.0)', c)

    # Auto-repair 2-arg xyzdist or malformed hit_pos ordering before declaration
    if "xyzdist(1, @P, hit_prim)" in c and "primuv(1, \"P\", hit_prim)" in c:
        c = re.sub(
            r'int\s+hit_prim;\s*\n\s*xyzdist\(1,\s*@P,\s*hit_prim\);\s*\n\s*float\s+dist\s*=\s*distance\(@P,\s*hit_pos\);\s*\n\s*vector\s+hit_pos\s*=\s*primuv\(1,\s*"P",\s*hit_prim\);\s*\n\s*float\s+dist\s*=\s*distance\(@P,\s*hit_pos\);',
            r'int hit_prim;\nvector hit_uv;\nfloat dist = xyzdist(1, @P, hit_prim, hit_uv);\nvector hit_pos = primuv(1, "P", hit_prim, hit_uv);',
            c
        )

    # Auto-repair @P in detail wrangles when iterating over points with nearpoint
    if "npoints(0)" in c and "@P" in c and "for (int i" in c:
        c = re.sub(r'nearpoint\s*\(\s*0\s*,\s*@P\s*,\s*([^,]+)\s*,\s*i\s*\)', r'nearpoint(0, vector(point(0, "P", i)), \1)', c)
        c = re.sub(r'distance\s*\(\s*@P\s*,', r'distance(vector(point(0, "P", i)),', c)

    # Auto-repair ambiguous polymorphic calls: distance(point(...), ...) -> distance(vector(point(...)), ...)
    c = re.sub(r'distance\s*\(\s*(point\s*\([^)]+\))\s*,', r'distance(vector(\1),', c)
    c = re.sub(r'distance\s*\(\s*([^,()]+)\s*,\s*(point\s*\([^)]+\))\s*\)', r'distance(\1, vector(\2))', c)

    # Auto-repair nearpoint self-exclusion bug in detail loop:
    if "nearpoint(0," in c and ("pt != i" in c or "pt == i" in c):
        c = re.sub(
            r'int\s+([a-zA-Z0-9_]+)\s*=\s*nearpoint\s*\(\s*0\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\);\s*\n\s*if\s*\(\s*\1\s*!=\s*-1\s*&&\s*\1\s*!=\s*([a-zA-Z0-9_]+)\s*\)',
            r'int _nb[] = nearpoints(0, \2, \3, 2);\n    int \1 = (len(_nb) > 1) ? _nb[1] : -1;\n    if (\1 != -1)',
            c
        )

    # Auto-repair hallucinated clip(...) SOP pseudo-function to removepoint()
    c = re.sub(
        r'\bclip\s*\(\s*(?:set)?\s*\(\s*1(?:\.0)?\s*,\s*0(?:\.0)?\s*,\s*0(?:\.0)?\s*\)\s*,\s*([0-9.]+)\s*\);?',
        r'if (@P.x > \1) removepoint(0, @ptnum);',
        c
    )
    c = re.sub(
        r'\bclip\s*\(\s*(?:set)?\s*\(\s*0(?:\.0)?\s*,\s*1(?:\.0)?\s*,\s*0(?:\.0)?\s*\)\s*,\s*([0-9.]+)\s*\);?',
        r'if (@P.y > \1) removepoint(0, @ptnum);',
        c
    )
    c = re.sub(
        r'\bclip\s*\(\s*(?:set)?\s*\(\s*0(?:\.0)?\s*,\s*0(?:\.0)?\s*,\s*1(?:\.0)?\s*\)\s*,\s*([0-9.]+)\s*\);?',
        r'if (@P.z > \1) removepoint(0, @ptnum);',
        c
    )
    c = re.sub(
        r'\bclip\s*\(\s*set\s*\(([^)]+)\)\s*,\s*([^)]+)\s*\);?',
        r'if (dot(@P, normalize(set(\1))) > \2) removepoint(0, @ptnum);',
        c
    )

    # Auto-repair 3-argument neighbours(geo, pt, radius) -> nearpoints(geo, @P, radius)
    c = re.sub(
        r'\bneighbours\s*\(\s*([^,]+)\s*,\s*@?ptnum\s*,\s*([^)]+)\s*\)',
        r'nearpoints(\1, @P, \2)',
        c
    )

    # Auto-repair hallucinated @numptnbr attribute -> neighbourcount(0, @ptnum)
    c = re.sub(r'(@numptnbr|numptnbr)\b', 'neighbourcount(0, @ptnum)', c)

    # Auto-repair hallucinated intersect_plane(pos, normal, dist) to hyperplane orthogonal projection
    c = re.sub(
        r'\bintersect_plane\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)',
        r'(\1 - \2 * (dot(\1, \2) - \3))',
        c
    )

    # Auto-repair dynamic array expressions in curly braces {expr, expr} -> array(expr, expr)
    def _fix_dynamic_array(m):
        t, name, inner = m.group(1), m.group(2), m.group(3)
        if any(op in inner for op in ['(', ')', '*', '/', '+', '-', '[', ']', '@', 'phi', 'sqrt']) and not re.match(r'^\s*[-0-9.,\s]+\s*$', inner):
            return f"{t} {name}[] = array({inner});"
        return m.group(0)
    c = re.sub(r'\b(int|float|vector|vector4|string)\s+([a-zA-Z0-9_]+)\[\s*\]\s*=\s*\{([\s\S]+?)\};', _fix_dynamic_array, c)

    # Auto-repair uninitialized point mass attribute divisions in physics: 1.0 / point(..., "mass", ...)
    c = re.sub(
        r'/\s*point\s*\(\s*([^,]+)\s*,\s*["\']mass["\']\s*,\s*([^)]+)\s*\)',
        r'/ max(0.001, float(point(\1, "mass", \2)))',
        c
    )

    # Auto-repair illegal l-value point() write in detail wrangles: point(0, "P", pt) += ... -> setpointattrib(...)
    c = re.sub(
        r'point\s*\(\s*([^,]+)\s*,\s*["\']([^"\']+)["\']\s*,\s*([^)]+)\s*\)\s*\+=\s*([^;]+);',
        r'setpointattrib(\1, "\2", \3, point(\1, "\2", \3) + (\4), "set");',
        c
    )

    # Clean previously corrupted do-while safety iterators
    c = re.sub(r'\}\s*int\s+__safety_iter_\d+\s*=\s*0;\s*\n\s*while\s*\(\(+([\s\S]*?)\s*&&\s*\(__safety_iter_\d+\+\+\s*<\s*10000\)\)+;', r'} while (\1);', c)

    # Auto-repair halfedge pointhedgeotherpoint & point("primitive", ...)
    c = re.sub(r'\bpoint\s*\(\s*0\s*,\s*["\']primitive["\']\s*,\s*pointhedgeotherpoint\s*\(\s*0\s*,\s*([a-zA-Z0-9_]+)\s*\)\s*\)', r'hedge_prim(0, \1)', c)
    c = re.sub(r'\bpointhedgeotherpoint\s*\(', 'hedge_dstpoint(', c)

    # Guard halfedge circulation loop boundary termination
    c = re.sub(r'\bwhile\s*\(\s*([a-zA-Z0-9_]+)\s*!=\s*pointhedge\s*\(\s*0\s*,\s*@ptnum\s*\)\s*\)', r'while (\1 != -1 && \1 != pointhedge(0, @ptnum))', c)

    # Auto-repair xyzdist with vector hit_p instead of int hit_prim
    c = re.sub(r'\bxyzdist\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*hit_p\s*,\s*([a-zA-Z0-9_]+)\s*\)', r'xyzdist(\1, \2, hit_prim, \3)', c)
    if "hit_prim" in c and not re.search(r'\bint\s+hit_prim\b', c):
        c = "int hit_prim = -1;\n" + c

    # Auto-repair pts[] sequential empty indexing
    if len(re.findall(r'(?<!int\s)(?<!float\s)(?<!vector\s)(?<!vector4\s)(?<!matrix\s)(?<!string\s)\b([a-zA-Z0-9_]+)\[\s*\](?!\s*@)', c)) >= 2:
        _counter_pts = [0]
        def _repl_pts(m):
            var = m.group(1)
            res = f"{var}[{_counter_pts[0]}]"
            _counter_pts[0] += 1
            return res
        c = re.sub(r'(?<!int\s)(?<!float\s)(?<!vector\s)(?<!vector4\s)(?<!matrix\s)(?<!string\s)\b([a-zA-Z0-9_]+)\[\s*\](?!\s*@)', _repl_pts, c)

    # Auto-repair primvertexs typo to primvertices
    c = re.sub(r'\bprimvertexs\b', 'primvertices', c)

    # Auto-repair volumegradient assigned to float dpx or finite-difference hallucination
    c = re.sub(
        r'int\s+dx\[\s*\]\s*=\s*set\(1,\s*0,\s*0\);[\s\S]*?@N\s*=\s*normalize\(grad\);',
        r'vector grad = volumegradient(1, "density", @P);\n@N = normalize(grad);',
        c
    )
    c = re.sub(r'\bfloat\s+([a-zA-Z0-9_]+)\s*=\s*(volumegradient\s*\([^;]+\));', r'vector \1 = \2;', c)

    # Auto-repair point(1, "P", minpos(...)) -> minpos(...)
    c = re.sub(r'point\s*\(\s*([^,]+)\s*,\s*["\']P["\']\s*,\s*(minpos\s*\([^)]+\))\s*\)', r'\2', c)

    # Auto-repair matrix rotation with qrotate / m[] *= rot_m[]
    if "4@localtransform" in c and ("qrotate" in c or "rot_m" in c):
        c = re.sub(
            r'matrix\s+([a-zA-Z0-9_]+)\s*=\s*4@localtransform;[\s\S]*?4@localtransform\s*=\s*\1\s*;',
            r'matrix \1 = 4@localtransform;\nfloat angle = chf("angle");\nvector axis = set(0, 1, 0);\nrotate(\1, radians(angle), axis);\n4@localtransform = \1;',
            c
        )

    # Auto-repair pcfind 4-argument missing "P"
    c = re.sub(r'\bpcfind\s*\(\s*([^,]+)\s*,\s*(@?[a-zA-Z0-9_]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)', r'pcfind(\1, "P", \2, \3, \4)', c)

    # Auto-repair divide by zero in len(...)
    c = re.sub(r'/\s*len\s*\(\s*([a-zA-Z0-9_]+)\s*\)', r'/ max(1, len(\1))', c)

    # Auto-repair volumenoi -> snoise
    c = re.sub(r'\bvolumenoi\s*\(\s*[^,]+\s*,\s*[^,]+\s*,\s*([^)]+)\s*\)', r'snoise(\1)', c)
    c = re.sub(r'\bvolumenoi\b', 'snoise', c)

    # Safe fallback for chi/chf iterations
    if "chi(\"max_iterations\")" in c and "if (max_iter" not in c:
        c = re.sub(r'(int\s+max_iter\s*=\s*chi\s*\(\s*["\']max_iterations["\']\s*\)\s*;)', r'\1\nif (max_iter <= 0) max_iter = 1;', c)

    # Auto-repair channel denominators in mathematical expressions: guard chf() against 0.0 default
    channels = re.findall(r'float\s+([a-zA-Z0-9_]+)\s*=\s*chf\s*\(\s*["\']([^"\']+)["\']\s*\)\s*;', c)
    for var, ch_name in channels:
        if re.search(rf'/\s*\(?[^;]*\b{var}\b', c):
            if f"if ({var} ==" not in c and f"if ({var} <=" not in c and f"if (abs({var})" not in c:
                c = re.sub(
                    rf'(float\s+{var}\s*=\s*chf\s*\(\s*["\']{ch_name}["\']\s*\)\s*;)',
                    rf'\1\nif (abs({var}) < 1e-4) {var} = 1.0;',
                    c
                )

    # Heal any truncation from token limit exhaustion (unclosed braces, trailing cutoffs)
    c = _heal_truncated_vex(c)

    # Protect against infinite while loops that can freeze Houdini evaluation
    c = _protect_infinite_loops(c)

    return c.strip()


_LOOP_GUARD_LIMIT = 1000000  # per loop entry; high enough for legitimate loops, still ends runaway ones


def _code_mask(code: str) -> list[bool]:
    """True for characters inside string literals or comments (skipped by the loop scanner)."""
    mask = [False] * len(code)
    i, n = 0, len(code)
    while i < n:
        ch = code[i]
        if code.startswith("//", i):
            j = code.find("\n", i)
            j = n if j < 0 else j
        elif code.startswith("/*", i):
            j = code.find("*/", i + 2)
            j = n if j < 0 else j + 2
        elif ch in "\"'":
            j = i + 1
            while j < n and code[j] != ch:
                j += 2 if code[j] == "\\" else 1
            j = min(j + 1, n)
        else:
            i += 1
            continue
        for k in range(i, j):
            mask[k] = True
        i = j
    return mask


def _matching_paren(code: str, open_idx: int, mask: list[bool]) -> int:
    depth = 0
    for k in range(open_idx, len(code)):
        if mask[k]:
            continue
        if code[k] == "(":
            depth += 1
        elif code[k] == ")":
            depth -= 1
            if depth == 0:
                return k
    return -1


def _protect_infinite_loops(code: str) -> str:
    """Guard while / do-while loops against runaway iteration (a VEX infinite loop hangs the cook).

    'while (C) body'        -> 'for (int __safety_iter_k = 0; (C) && __safety_iter_k < L; __safety_iter_k++) body'
    'do body while (C);'    -> 'do body while ((C) && (__safety_iter_k++ < L));' with the counter declared
                               in a block that wraps the whole do statement.
    Both forms are exact rewrites for loops that finish within L iterations, keep the original scope
    (safe after a braceless if), and handle conditions with nested parentheses.
    """
    if not code or "while" not in code or "__safety_iter" in code:
        return code
    mask = _code_mask(code)
    edits = []  # (start, end, replacement) on the original string
    counter = 0
    for m in re.finditer(r"\bwhile\s*\(", code):
        if mask[m.start()]:
            continue
        open_idx = m.end() - 1
        close_idx = _matching_paren(code, open_idx, mask)
        if close_idx < 0:
            continue
        cond = code[open_idx + 1:close_idx].strip()
        if "pciterate" in cond or "pcunshadow" in cond:
            continue
        k = counter
        counter += 1
        var = f"__safety_iter_{k}"
        prev = code[:m.start()].rstrip()
        if prev.endswith("}") and _is_do_while_tail(code, m.start(), mask):
            # do { ... } while (C);  -> bounded tail, counter declared before the matching 'do'
            do_idx = _find_do_for_tail(code, m.start(), mask)
            if do_idx < 0:
                continue
            semi = code.find(";", close_idx)
            if semi < 0:
                continue
            edits.append((do_idx, do_idx, f"{{ int {var} = 0; "))
            edits.append((m.start(), semi + 1, f"while (({cond}) && ({var}++ < {_LOOP_GUARD_LIMIT})); }}"))
        else:
            edits.append((m.start(), close_idx + 1,
                          f"for (int {var} = 0; ({cond}) && {var} < {_LOOP_GUARD_LIMIT}; {var}++)"))
    for start, end, rep in sorted(edits, key=lambda e: e[0], reverse=True):
        code = code[:start] + rep + code[end:]
    return code


def _is_do_while_tail(code: str, while_idx: int, mask: list[bool]) -> bool:
    return _find_do_for_tail(code, while_idx, mask) >= 0


def _find_do_for_tail(code: str, while_idx: int, mask: list[bool]) -> int:
    """For 'do { ... } while', return the index of 'do'; -1 if the '}' does not close a do-block."""
    close = code[:while_idx].rstrip()
    if not close.endswith("}"):
        return -1
    depth = 0
    for k in range(len(close) - 1, -1, -1):
        if mask[k]:
            continue
        if close[k] == "}":
            depth += 1
        elif close[k] == "{":
            depth -= 1
            if depth == 0:
                before = close[:k].rstrip()
                if before.endswith("do") and (len(before) == 2 or not (before[-3].isalnum() or before[-3] == "_")):
                    return len(before) - 2
                return -1
    return -1




def _light_vex_cleanup(code: str) -> str:
    """Minimal, semantics-preserving preparation of model output: strip stray think tags, heal a
    token-limit truncation, and guard loops against runaway iteration."""
    c = re.sub(r"</?think>", "", code or "").strip()
    return _protect_infinite_loops(_heal_truncated_vex(c)).strip()


def _apply_generated_vex(node, task_text: str, context_str: str, vex_code: str, geo_context: str,
                         max_repairs: int = 2) -> tuple[str, bool, str | None]:
    """Compile-first application of generated VEX.

    1. The model's code with only light cleanup is tried first: correct code is never rewritten.
    2. Only if Houdini rejects it are the aggressive regex repairs (sanitize_vex_syntax) tried.
    3. Then up to `max_repairs` compiler-feedback repair passes, each again light-first.
    Returns (applied_or_last_code, success, last_error).
    """
    def attempt(code):
        light = _light_vex_cleanup(code)
        if not re.search(r"[;{}]", light):
            # Nothing that looks like VEX survived (prose, refusal, cut-off answer). Never apply an
            # empty snippet: it "compiles" and would silently wipe the user's working code.
            return (code or "").strip(), False, "Model output contains no VEX statements."
        ok, err = try_apply_snippet(node, light)
        if ok:
            return light, True, None
        heavy = sanitize_vex_syntax(code)
        if heavy and heavy != light:
            ok2, err2 = try_apply_snippet(node, heavy)
            if ok2:
                return heavy, True, None
            return heavy, False, err2 or err
        return light, False, err

    code, ok, err = attempt(vex_code)
    for i in range(max_repairs):
        if ok or not err:
            break
        if hou.isUIAvailable():
            hou.ui.setStatusMessage(f"Auto-repairing VEX (attempt {i + 1}/{max_repairs})...", severity=hou.severityType.Message)
        try:
            _, repaired = repair_vex(task_text, context_str, code, err, geo_context=geo_context)
        except GenerationCancelled:
            # Esc during the auto-repair: stop, and say so in front of the compile error of the code we have
            err = f"Auto-repair cancelled by user. {err or ''}".strip()
            break
        except Exception as exc:
            # an engine hiccup or an empty answer: stop repairing and report the compile error of the code we
            # have (with the reason the repair stopped), instead of losing the attempt to an exception
            err = f"{err or ''} (auto-repair stopped: {exc})".strip()
            break
        if not repaired:
            break
        code, ok, err = attempt(repaired)
    return code, ok, (None if ok else err)

def _heal_truncated_vex(code: str) -> str:
    """Detects and repairs truncated VEX code from token limit cutoffs."""
    if not code:
        return ""
    lines = code.splitlines()
    if not lines:
        return code

    # Strip trailing incomplete statement cut off mid-token (e.g. "float pscale")
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if last.endswith((';', '}', '{', '*/')):
            break
        lines.pop()

    healed = "\n".join(lines).strip()

    # Balance unclosed curly braces
    open_braces = healed.count('{')
    close_braces = healed.count('}')
    if open_braces > close_braces:
        healed += "\n" + ("}\n" * (open_braces - close_braces))

    return healed


def _resolve_chramp_polymorphic_ambiguity(code: str) -> str:
    """Rewrites inline chramp() calls inside set*attrib() to use typed local variables.
    Handles arbitrarily nested expressions inside chramp() like clamp(length(v)/40.0, 0, 1).
    """
    func_re = re.compile(r'\b(set(?:point|prim|vertex|detail)attrib)\s*\(')
    result = []
    i = 0
    counter = 0

    while i < len(code):
        m = func_re.search(code, i)
        if not m:
            result.append(code[i:])
            break

        start_pos = m.start()
        open_pos = m.end() - 1  # '('
        result.append(code[i:start_pos])

        # Find matching ')' for set*attrib(...)
        depth = 1
        j = open_pos + 1
        while j < len(code) and depth > 0:
            if code[j] == '(': depth += 1
            elif code[j] == ')': depth -= 1
            j += 1

        if depth != 0:
            result.append(code[start_pos:j])
            i = j
            continue

        inner_args_str = code[open_pos + 1:j - 1]

        # Check if chramp is inside arguments
        if 'chramp' in inner_args_str:
            ch_match = re.search(r'\bchramp\s*\(', inner_args_str)
            if ch_match:
                ch_open = ch_match.end() - 1
                ch_depth = 1
                k = ch_open + 1
                while k < len(inner_args_str) and ch_depth > 0:
                    if inner_args_str[k] == '(': ch_depth += 1
                    elif inner_args_str[k] == ')': ch_depth -= 1
                    k += 1

                if ch_depth == 0:
                    full_chramp_call = inner_args_str[ch_match.start():k]
                    is_color = bool(re.search(r'["\'](?:Cd|cd|color|colour)["\']', inner_args_str))
                    counter += 1
                    var_name = f"__chramp_col_{counter}" if is_color else f"__chramp_val_{counter}"
                    var_type = "vector" if is_color else "float"

                    decl = f"{var_type} {var_name} = {full_chramp_call};\n"
                    new_inner = inner_args_str[:ch_match.start()] + var_name + inner_args_str[k:]
                    result.append(f"{decl}{m.group(1)}({new_inner})")
                    i = j
                    continue

        result.append(code[start_pos:j])
        i = j

    return ''.join(result)


class GenerationCancelled(RuntimeError):
    """The user pressed Esc / Cancel while the model was generating."""


class EmptyModelResponse(RuntimeError):
    """The engine answered, but with neither text nor thinking (not an engine failure)."""


def _post_json_interruptible(url: str, data: bytes, headers: dict, timeout: float, label: str) -> dict:
    """POST JSON on a worker thread while Houdini's main thread shows an interruptible progress
    dialog: the UI stays responsive and Esc / Cancel aborts instead of freezing Houdini."""
    import threading

    box = {}

    def worker():
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=timeout) as resp:
                box["result"] = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # re-raised on the main thread
            box["error"] = exc

    t = threading.Thread(target=worker, name="ai_wrangle_llm", daemon=True)
    t.start()
    try:
        with hou.InterruptableOperation(label, open_interrupt_dialog=True) as op:
            while t.is_alive():
                t.join(0.1)
                op.updateProgress(-1.0)  # raises hou.OperationInterrupted when the user cancels
    except hou.OperationInterrupted:
        raise GenerationCancelled("Generation cancelled by user.")
    if "error" in box:
        raise box["error"]
    return box.get("result", {})


def query_llm(prompt_text: str, max_tokens: int | None = None, reasoning_mode: bool = False,
              temperature: float | None = None, seed: int | None = None,
              system_prompt: str | None = None, template_kwargs: dict | None = None) -> tuple[str, str]:
    """
    Queries AI inference engine.
    Priority 1: Embedded Standalone Engine (127.0.0.1:58421 - Zero Dependencies)
    Priority 2: Local Ollama Endpoint (127.0.0.1:11434)
    Returns (thought_trace, pure_vex_code).
    """
    global _engine_error
    if system_prompt is None:
        system_prompt = REASONING_SYSTEM_PROMPT if reasoning_mode else TURBO_SYSTEM_PROMPT

    # 1. Start and query the bundled standalone engine (llama-server).
    engine_ready = ensure_embedded_engine()
    port = _engine_port()
    chat_url = f"http://127.0.0.1:{port}/v1/chat/completions"
    
    if max_tokens is not None:
        pred_tokens = max_tokens
    else:
        pred_tokens = 3072 if reasoning_mode else 1536

    chat_payload = {
        "model": "default",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": temperature if temperature is not None else (0.6 if reasoning_mode else 0.1),
        "top_p": 0.95,
        "max_tokens": pred_tokens,
    }
    # template_kwargs={} sends none, i.e. the chat template's own defaults (how the model was trained)
    tk = {"enable_thinking": reasoning_mode} if template_kwargs is None else template_kwargs
    if tk:
        chat_payload["chat_template_kwargs"] = tk
    if seed is not None:
        chat_payload["seed"] = int(seed)
    
    if engine_ready:
        try:
            api_key = getattr(_engine_singleton, "api_key", None) if _engine_singleton else None
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            def ask(payload):
                """(answer text, separately returned thinking) of one chat request"""
                res_data = _post_json_interruptible(chat_url, json.dumps(payload).encode("utf-8"), headers, timeout=300,
                                                    label="AI VEX Copilot: generating (Esc / Cancel to stop)")
                message = (res_data.get("choices") or [{}])[0].get("message") or {}
                # llama-server may return the thinking as message.reasoning_content instead of inline <think> tags
                return (message.get("content") or ""), (message.get("reasoning_content") or "").strip()

            raw, thinking = ask(chat_payload)
            thought, code = extract_thought_and_code(raw) if raw.strip() else ("", "")
            if not code.strip() and tk.get("enable_thinking") is True:
                # Thinking was asked for, the token budget went into it and no answer followed: ask once more for
                # the answer alone. (Not for template_kwargs={}: that request is the training-format candidate
                # and has to stay in its format; an empty answer there simply drops the candidate.) If the second
                # request fails, the thinking of the first is still returned.
                try:
                    raw, _ = ask(dict(chat_payload, chat_template_kwargs={"enable_thinking": False}))
                    more_thought, code = extract_thought_and_code(raw) if raw.strip() else ("", "")
                    thought = thought or more_thought
                except GenerationCancelled:
                    raise
                except Exception:
                    code = ""
            thought = thought or thinking
            if code.strip() or thought:
                return thought, code  # code can be "" (thinking only): callers report "no code"
            raise EmptyModelResponse("The model returned an empty answer. Try again or rephrase the request.")
        except (GenerationCancelled, EmptyModelResponse):
            raise
        except Exception as exc:
            _engine_error = f"Bundled inference request failed: {exc}"

    if os.getenv("AI_WRANGLE_ALLOW_OLLAMA_FALLBACK", "0") != "1":
        raise RuntimeError(
            "Bundled AI engine is unavailable. "
            f"{_engine_error or 'Check the model vault, GPU driver, and system requirements.'} "
            "Set AI_WRANGLE_ALLOW_OLLAMA_FALLBACK=1 only for developer troubleshooting."
        )

    # 2. Optional developer fallback to Local Ollama API (11434)
    model_name = resolve_model_name()
    ollama_payload = {
        "model": model_name,
        "prompt": prompt_text,
        "system": system_prompt,
        "stream": False,
        "options": {
            "num_predict": pred_tokens,
            "num_ctx": 4096,
            "temperature": 0.2 if reasoning_mode else 0.1,
            "top_p": 0.95
        }
    }
    data = json.dumps(ollama_payload).encode("utf-8")
    req = urllib.request.Request(
        LOCAL_API_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=120) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        raw = res_data.get("response", "")
        return extract_thought_and_code(raw)


# ---------------------------------------------------------------------------
# Production FX Preset Cookbook (Verified VEX Algorithms)
# ---------------------------------------------------------------------------

_FX_PRESETS = {
    "pbd_cloth": {
        "label": "🎪 [Sim] PBD Cloth Distance Constraints",
        "context": "point",
        "prompt": "Apply Position Based Dynamics (PBD) distance constraints to relax mesh edges",
        "code": """// PBD Distance Constraints
vector target_p = point(0, "P", @ptnum);
int nbrs[] = neighbours(0, @ptnum);
float rest_len = chf("rest_length");
float stiffness = chf("stiffness");

vector dP = set(0, 0, 0);
int count = 0;
foreach (int n; nbrs) {
    vector np = point(0, "P", n);
    vector dir = @P - np;
    float dist = length(dir);
    if (dist > 1e-6) {
        float C = dist - rest_len;
        dP += -stiffness * 0.5 * (C / dist) * dir;
        count++;
    }
}
if (count > 0) {
    @P += dP / float(count);
}"""
    },
    "rk4_flow": {
        "label": "🌊 [Sim] Runge-Kutta 4th Order (RK4) Advection",
        "context": "point",
        "prompt": "Advect particles along a 3D curlnoise flow field using RK4 numerical integration",
        "code": """// Runge-Kutta 4th Order (RK4) Advection
float dt = chf("time_step");
float speed = chf("flow_speed");
float freq = chf("curl_freq");

vector v1 = curlnoise(@P * freq) * speed;
vector p2 = @P + 0.5 * dt * v1;
vector v2 = curlnoise(p2 * freq) * speed;
vector p3 = @P + 0.5 * dt * v2;
vector v3 = curlnoise(p3 * freq) * speed;
vector p4 = @P + dt * v3;
vector v4 = curlnoise(p4 * freq) * speed;

vector v_final = (v1 + 2.0 * v2 + 2.0 * v3 + v4) / 6.0;
@P += v_final * dt;
v@v = v_final;"""
    },
    "verlet_particles": {
        "label": "⚡ [Sim] Verlet Particle Step + Ground Bounce",
        "context": "point",
        "prompt": "Step particle positions using Verlet integration with gravity, air drag, and ground bounce",
        "code": """// Verlet Particle Step with Ground Collision & Drag
vector old_p = hasattrib(0, "point", "prev_P") ? v@prev_P : @P;
v@prev_P = @P;

vector gravity = set(0.0, -9.81 * chf("gravity_scale"), 0.0);
float drag = chf("air_drag");
float bounce = chf("restitution");
float dt = chf("time_step");

vector vel = (@P - old_p) * (1.0 - drag);
vel += gravity * dt * dt;

@P += vel;

float ground_y = chf("ground_y");
if (@P.y < ground_y) {
    @P.y = ground_y;
    vel.y = -vel.y * bounce;
    v@prev_P = @P - vel;
}
v@v = vel / max(dt, 1e-5);"""
    },
    "curl_noise_smoke": {
        "label": "💨 [Sim] 4D Divergence-Free Curlnoise Velocity",
        "context": "point",
        "prompt": "Inject 4D curl noise velocity turbulence with time evolution and smooth blending",
        "code": """// 4D Divergence-Free Curlnoise Velocity
float freq = chf("noise_freq");
float amp = chf("noise_amp");
float speed = chf("time_speed");
float blend = chf("vel_blend");

vector4 p4 = set(@P.x * freq, @P.y * freq, @P.z * freq, @Time * speed);
vector curl = curlnoise(p4) * amp;

v@v = lerp(v@v, curl, blend);
@P += v@v * @TimeInc;"""
    },
    "diff_growth": {
        "label": "🌱 [Model] Differential Surface Mesh Growth",
        "context": "point",
        "prompt": "Relax and expand mesh surface vertices using tangential differential growth",
        "code": """// Differential Surface Mesh Growth & Relaxation
float max_dist = chf("search_radius");
int max_pts = chi("max_neighbors");
float push_force = chf("push_strength");

int nbrs[] = nearpoints(0, @P, max_dist, max_pts);
vector push = set(0, 0, 0);
int count = 0;

foreach (int n; nbrs) {
    if (n == @ptnum) continue;
    vector np = point(0, "P", n);
    vector diff = @P - np;
    float dist = length(diff);
    if (dist < max_dist && dist > 1e-6) {
        push += normalize(diff) * (1.0 - dist / max_dist);
        count++;
    }
}
if (count > 0) {
    push = (push / float(count)) * push_force;
    if (hasattrib(0, "point", "N")) {
        push -= dot(push, normalize(@N)) * normalize(@N);
    }
    @P += push;
}"""
    },
    "log_spiral": {
        "label": "🌀 [Model] 3D Logarithmic Golden Spiral Curve",
        "context": "detail",
        "prompt": "Generate a 3D logarithmic golden spiral polyline curve with height and color gradient",
        "code": """// Logarithmic Spiral Curve (Detail Wrangle)
int total_pts = chi("point_count");
float a = chf("scale_a");
float b = chf("growth_rate_b");
float height_scale = chf("height_factor");
float turns = chf("total_turns");

int prim = addprim(0, "polyline");
float max_theta = turns * 6.283185307;

for (int i = 0; i < total_pts; i++) {
    float t = float(i) / float(max(total_pts - 1, 1));
    float theta = t * max_theta;
    float r = a * exp(b * theta);
    float x = r * cos(theta);
    float z = r * sin(theta);
    float y = t * height_scale;
    int pt = addpoint(0, set(x, y, z));
    addvertex(0, prim, pt);
    setpointattrib(0, "Cd", pt, lerp(set(0.1, 0.4, 1.0), set(1.0, 0.8, 0.2), t), "set");
}"""
    },
    "quat_lookat": {
        "label": "🎯 [Math] Quaternion Lookat with Up Constraint",
        "context": "point",
        "prompt": "Align point orientation quaternion @orient to look at target position with up-vector",
        "code": """// Quaternion Lookat with Up-Vector Constraint
vector target = chv("target_position");
vector up = chv("up_vector");
vector forward = normalize(target - @P);

if (length2(forward) > 1e-6) {
    matrix3 m = maketransform(forward, normalize(up));
    p@orient = quaternion(m);
    @N = forward;
}"""
    },
    "fabrik_ik": {
        "label": "🦴 [Math] FABRIK Multi-Bone IK Solver",
        "context": "detail",
        "prompt": "Solve inverse kinematics for multi-joint bone chain using the FABRIK algorithm",
        "code": """// FABRIK Multi-Bone Chain IK Solver (Detail Wrangle)
int count = npoints(0);
if (count < 2) return;

vector target = chv("ik_target");
float tol = chf("tolerance");
int max_iter = chi("max_iterations");

vector pos[];
float d[];
resize(pos, count);
resize(d, count - 1);

float total_len = 0.0;
for (int i = 0; i < count; i++) {
    pos[i] = point(0, "P", i);
    if (i > 0) {
        d[i - 1] = distance(pos[i - 1], pos[i]);
        total_len += d[i - 1];
    }
}

vector root = pos[0];
float dist_to_target = distance(root, target);

if (dist_to_target > total_len) {
    vector dir = normalize(target - root);
    for (int i = 1; i < count; i++) {
        pos[i] = pos[i - 1] + dir * d[i - 1];
    }
} else {
    for (int iter = 0; iter < max_iter; iter++) {
        if (distance(pos[count - 1], target) < tol) break;
        pos[count - 1] = target;
        for (int i = count - 2; i >= 0; i--) {
            vector dir = normalize(pos[i] - pos[i + 1]);
            pos[i] = pos[i + 1] + dir * d[i];
        }
        pos[0] = root;
        for (int i = 0; i < count - 1; i++) {
            vector dir = normalize(pos[i + 1] - pos[i]);
            pos[i + 1] = pos[i] + dir * d[i];
        }
    }
}

for (int i = 0; i < count; i++) {
    setpointattrib(0, "P", i, pos[i], "set");
}"""
    },
    "ripple_interference": {
        "label": "🌊 [Deform] Multi-Source Ripple Interference",
        "context": "point",
        "prompt": "Create dual-source concentric wave ripple interference deformation with color mapping",
        "code": """// Multi-Source Ripple Interference
vector s1 = chv("source1_pos");
vector s2 = chv("source2_pos");
float freq = chf("wave_frequency");
float speed = chf("wave_speed");
float amp = chf("wave_amplitude");

float d1 = distance(@P, s1);
float d2 = distance(@P, s2);

float w1 = sin(d1 * freq - @Time * speed);
float w2 = sin(d2 * freq - @Time * speed);
float height = (w1 + w2) * amp * 0.5;

@P.y += height;
f@wave_height = height;
v@Cd = chramp("wave_ramp", fit(height, -amp, amp, 0.0, 1.0));"""
    },
    "reaction_diffusion": {
        "label": "🧪 [Deform] Gray-Scott Reaction-Diffusion Step",
        "context": "point",
        "prompt": "Simulate one Gray-Scott reaction-diffusion step across surface vertices",
        "code": """// Gray-Scott Reaction-Diffusion Step
float feed = chf("feed_rate");
float kill = chf("kill_rate");
float diff_a = chf("diff_a");
float diff_b = chf("diff_b");
float dt = chf("time_step");

float a = hasattrib(0, "point", "chem_a") ? f@chem_a : 1.0;
float b = hasattrib(0, "point", "chem_b") ? f@chem_b : 0.0;

int nbrs[] = neighbours(0, @ptnum);
float lap_a = 0.0;
float lap_b = 0.0;
if (len(nbrs) > 0) {
    foreach (int n; nbrs) {
        lap_a += point(0, "chem_a", n);
        lap_b += point(0, "chem_b", n);
    }
    lap_a = (lap_a / float(len(nbrs))) - a;
    lap_b = (lap_b / float(len(nbrs))) - b;
}

float abb = a * b * b;
float new_a = a + (diff_a * lap_a - abb + feed * (1.0 - a)) * dt;
float new_b = b + (diff_b * lap_b + abb - (kill + feed) * b) * dt;

f@chem_a = clamp(new_a, 0.0, 1.0);
f@chem_b = clamp(new_b, 0.0, 1.0);

v@Cd = chramp("chemical_ramp", f@chem_b);"""
    },
    "normal_displace": {
        "label": "🏔️ [Deform] Fractal Noise Normal Displacement",
        "context": "point",
        "prompt": "Displace points along normals using multi-octave 3D fractal simplex noise",
        "code": """// Multi-Octave Fractal Noise Normal Displacement
float freq = chf("base_frequency");
float amp = chf("displacement_scale");
float rough = chf("roughness");
int octaves = chi("octaves");

vector pos = @P * freq;
float n = 0.0;
float curr_amp = 1.0;
float max_amp = 0.0;

for (int i = 0; i < octaves; i++) {
    n += snoise(pos) * curr_amp;
    max_amp += curr_amp;
    curr_amp *= rough;
    pos *= 2.0;
}
n /= max(max_amp, 1e-4);

vector normal = hasattrib(0, "point", "N") ? normalize(@N) : set(0, 1, 0);
@P += normal * n * amp;
f@disp = n;
v@Cd = chramp("displacement_color", fit(n, -1.0, 1.0, 0.0, 1.0));"""
    }
}

# Well-known Houdini attribute semantic roles (Phase 2: #11)
_ATTRIB_SEMANTICS = {
    "P": "position", "N": "normal", "Cd": "color (RGB)", "Alpha": "opacity",
    "v": "velocity", "orient": "quaternion rotation", "pscale": "uniform scale",
    "scale": "non-uniform scale (vec3)", "rest": "rest position (stable noise ref)",
    "up": "up vector (secondary orient axis)", "id": "persistent element ID",
    "age": "particle age", "life": "particle lifetime", "width": "curve width",
    "tangentu": "curve tangent", "curveu": "curve parameter 0..1",
    "uv": "texture coordinates", "shop_materialpath": "material path (string)",
    "name": "piece name (string)", "class": "connectivity class ID",
    "piece": "fracture piece ID", "transform": "4x4 transform matrix",
    "accel": "acceleration", "force": "force vector", "torque": "torque vector",
    "density": "density (float)", "viscosity": "viscosity (float)",
}

# Upstream node type → workflow hint (Phase 2: #3)
_UPSTREAM_HINTS = {
    "scatter":         "Points were scattered — point cloud workflow.",
    "scatter::2.0":    "Points were scattered — point cloud workflow.",
    "vdbfrompolygons": "Input is a VDB/SDF. Use volumesample(), volumegradient().",
    "copytopoints":    "Geometry instanced via Copy to Points.",
    "copytopoints::2.0": "Geometry instanced via Copy to Points.",
    "solver":          "Data from a SOP Solver — time-stepping simulation context.",
    "solver::2.0":     "Data from a SOP Solver — time-stepping simulation context.",
    "dopimport":       "DOP Import — simulation data from DOPs.",
    "dopimportfield":  "DOP field import — volume simulation data.",
    "filecache":       "Cached geometry from disk.",
    "filecache::2.0":  "Cached geometry from disk.",
    "remesh":          "Remeshed geometry — expect uniform polygon sizes.",
    "remesh::2.0":     "Remeshed geometry — expect uniform polygon sizes.",
    "trail":           "Trail SOP — velocity (@v) attribute available.",
    "trail::2.0":      "Trail SOP — velocity (@v) attribute available.",
    "attribfrommap":   "Texture attributes baked from UV maps.",
    "heightfield":     "Heightfield volumes (height, mask, etc.).",
    "polyreduce":      "Poly-reduced geometry — simplified topology.",
    "vdbsmooth":       "Smoothed VDB field.",
    "pack":            "Packed geometry (use intrinsics, not point attribs on prims).",
    "assemble":        "Assembled pieces — @name attribute identifies pieces.",
    "voronoifracture": "Voronoi-fractured pieces — use @name or @class for pieces.",
}


def _volume_count(geo) -> int:
    try:
        return geo.countPrimType(hou.primType.Volume) + geo.countPrimType(hou.primType.VDB)
    except Exception:
        return 0


def _volume_prims(geo, limit: int = 2000) -> list:
    """Volume/VDB primitives without walking huge polygon meshes when there are none."""
    if _volume_count(geo) == 0:
        return []
    out = []
    for p in geo.iterPrims():
        if p.type() in (hou.primType.Volume, hou.primType.VDB):
            out.append(p)
            if len(out) >= limit:
                break
    return out


def _classify_geo_type(geo, npts: int, nprims: int) -> str:
    """Classify geometry type accurately from primitive types and bounding dimensions."""
    if nprims == 0:
        return "Point Cloud (no primitives)" if npts > 0 else "Empty Geometry"

    # Sample up to first 50 prims for classification
    sample = _sample_prims(geo, 50)
    prim_types = set(p.type() for p in sample)

    if hou.primType.Volume in prim_types or hou.primType.VDB in prim_types:
        return "Volume/VDB"
    if hou.primType.PackedGeometry in prim_types:
        return "Packed Geometry"
    if prim_types & {hou.primType.NURBSCurve, hou.primType.BezierCurve}:
        return "NURBS/Bezier Curves"

    # All polygon — distinguish 3D solid mesh vs 2D planar grid vs open/closed polylines
    if all(p.type() == hou.primType.Polygon for p in sample):
        has_open = any(not p.isClosed() for p in sample)
        has_closed = any(p.isClosed() for p in sample)

        if has_open and not has_closed:
            return "Open Polyline Curve / Guide Path"

        bsz = None
        try:
            bbox = geo.boundingBox()
            bsz = bbox.sizevec()
        except Exception:
            pass

        if has_closed and not has_open:
            if nprims == 1 and len(sample[0].vertices()) > 4:
                return "Closed Polyline Curve / Ring"
            if bsz is not None and min(bsz[0], bsz[1], bsz[2]) < 1e-4:
                return "2D Planar Surface / Grid / Plane"
            return "3D Polygon Mesh (Closed Surface)"

        return "Mixed Polygon (Mesh + Curves)"

    return "Mixed Geometry"


def _format_attrib_typed(attrib) -> str:
    """Return 'name (type, semantic)' string for an attribute (Phase 1: #2 + Phase 2: #11)."""
    a_name = attrib.name()
    sz = attrib.size()
    dt = attrib.dataType()
    if dt == hou.attribData.String:
        type_label = "string"
    elif dt == hou.attribData.Int:
        type_label = "int" if sz == 1 else f"int[{sz}]"
    else:
        type_label = {1: "float", 2: "float2", 3: "vector", 4: "vector4",
                      9: "matrix3", 16: "matrix"}.get(sz, f"float[{sz}]")
    semantic = _ATTRIB_SEMANTICS.get(a_name)
    if semantic:
        return f"{a_name} ({type_label}, {semantic})"
    return f"{a_name} ({type_label})"


def _detect_solver_context(node: hou.Node) -> bool:
    """Walk parent chain to detect if wrangle is inside a SOP Solver/DOP (Phase 1: #5)."""
    parent = node.parent()
    depth = 0
    while parent and depth < 8:
        ptype = parent.type().name()
        if ptype in ("solver", "solver::2.0", "dopnet", "dopnet::2.0"):
            return True
        parent = parent.parent()
        depth += 1
    return False


def _get_upstream_hints(node: hou.Node) -> list:
    """Inspect upstream node types for workflow context (Phase 2: #3)."""
    hints = []
    for i in range(4):
        inp = node.input(i)
        if inp is None:
            continue
        ntype = inp.type().name()
        hint = _UPSTREAM_HINTS.get(ntype)
        if hint:
            hints.append(f"Input {i} (from '{ntype}'): {hint}")
    return hints


def _perf_hint(total_pts: int) -> str:
    """Point-count-aware performance guidance (Phase 2: #7)."""
    if total_pts < 1000:
        return ""
    if total_pts < 50000:
        return f"Moderate geometry (~{total_pts:,} pts). Prefer pcfind()/nearpoints() over O(N^2) loops."
    if total_pts < 500000:
        return f"Large geometry (~{total_pts:,} pts). ALWAYS use spatial acceleration (pcfind/pcopen). Hoist chf() outside loops."
    return f"Very large geometry ({total_pts:,} pts). Minimize per-point function calls. Use pcfind with small maxpts. Avoid nested loops."


def _introspect_node_parameters(node: hou.Node) -> list:
    """Discovers user-created spare parameters and UI controls on this wrangle."""
    lines = []
    if not node:
        return lines
    try:
        spare_entries = []
        base_ignore = {
            "snippet", "group", "grouptype", "class", "exportlist", "autobind", "bindings",
            "groupautobind", "groupbindings", "vex_cwdpath", "vex_outputmask", "vex_updatenmls",
            "vex_matchattrib", "vex_inplace", "vex_selectiongroup", "vex_precision", "vex_numcount",
            "vex_threadjobsize", "vex_strict", "vex_strictvariables", "ai_spare_parms"
        }
        for p in node.parms():
            name = p.name()
            if name.startswith("ai_") or name.startswith("sep_") or name in base_ignore:
                continue
            template = p.parmTemplate()
            t_type = template.type()
            val_str = ""
            try:
                val = p.eval()
                val_str = f" [current={round(val, 3) if isinstance(val, float) else val}]"
            except Exception:
                pass
            if t_type == hou.parmTemplateType.Float:
                spare_entries.append(f"float chf('{name}'){val_str}")
            elif t_type == hou.parmTemplateType.Int:
                spare_entries.append(f"int chi('{name}'){val_str}")
            elif t_type == hou.parmTemplateType.String:
                spare_entries.append(f"string chs('{name}')")
            elif t_type == hou.parmTemplateType.Ramp:
                spare_entries.append(f"ramp chramp('{name}', val)")
        if spare_entries:
            lines.append("Existing UI Parameters on this Wrangle (bind your logic to these where applicable):")
            lines.append("  " + ", ".join(spare_entries))
    except Exception:
        pass
    return lines


def introspect_geometry(node: hou.Node) -> str:
    """Extracts rich sensory context from all 4 inputs: geo type, typed attributes, bbox, groups, volumes,
    upstream node hints, solver context, existing parameters, and multi-input operational patterns."""
    lines = []
    connected_inputs = []
    empty_inputs = []
    input_summaries = {}
    total_pts = 0

    for i in range(4):
        in_node = node.input(i)
        if in_node is None:
            empty_inputs.append(i)
            continue
        try:
            geo = in_node.geometry()
            if not geo:
                empty_inputs.append(i)
                continue

            if i not in connected_inputs:
                connected_inputs.append(i)

            npts = _point_count(geo)
            nprims = _prim_count(geo)
            total_pts += npts

            node_name = in_node.name()
            node_type = in_node.type().name()
            node_desc = in_node.type().description()

            # --- Geometry type classification ---
            geo_type = _classify_geo_type(geo, npts, nprims)
            input_summaries[i] = geo_type

            # --- Volume / VDB Primitive Handling ---
            vol_prims = _volume_prims(geo)
            if vol_prims:
                name_attrib = geo.findPrimAttrib("name")
                field_names = []
                for vp in vol_prims:
                    fn = ""
                    if name_attrib:
                        try:
                            fn = vp.attribValue(name_attrib)
                        except Exception:
                            fn = ""
                    if not fn:
                        try:
                            fn = vp.volumeName()
                        except Exception:
                            fn = ""
                    if fn and fn not in field_names:
                        field_names.append(fn)
                if not field_names:
                    field_names = ["density"]

                vol_flavor = "VDB" if any(p.type() == hou.primType.VDB for p in vol_prims) else "Standard Volume"
                desc = f"Input {i}: Connected from '{node_name}' ({node_desc} SOP, type '{node_type}') -> {vol_flavor} Field ({len(vol_prims)} field primitives)."
                desc += f"\n  Fields: {', '.join(field_names)}."

                try:
                    bbox = geo.boundingBox()
                    bsz = bbox.sizevec()
                    bctr = bbox.center()
                    desc += f"\n  Bounding Box: size=({bsz[0]:.2f}, {bsz[1]:.2f}, {bsz[2]:.2f}), center=({bctr[0]:.2f}, {bctr[1]:.2f}, {bctr[2]:.2f})."
                except Exception:
                    pass

                desc += f"\n  Role: Volumetric Field (Input {i})."
                if any(fn in ("surface", "sdf", "collision") for fn in field_names):
                    sdf_field = next(fn for fn in field_names if fn in ("surface", "sdf", "collision"))
                    desc += f"\n  SDF Sampling Pattern: float dist = volumesample({i}, '{sdf_field}', @P); vector grad = volumegradient({i}, '{sdf_field}', @P);"
                    desc += f"\n  SDF Collision Resolution: if (dist < chf('collision_margin')) {{ @P += normalize(grad) * (chf('collision_margin') - dist); }}"
                elif any("vel" in fn or fn == "v" for fn in field_names):
                    v_field = next(fn for fn in field_names if "vel" in fn or fn == "v")
                    desc += f"\n  Velocity Field Sampling Pattern: vector v_field = volumesamplev({i}, '{v_field}', @P);"
                else:
                    primary_f = field_names[0]
                    desc += f"\n  Density Sampling Pattern: float d = volumesample({i}, '{primary_f}', @P); vector grad = volumegradient({i}, '{primary_f}', @P);"

                lines.append(desc)
                continue

            # --- Regular Surface / Curve / Point Cloud Geometry ---
            pt_typed = [_format_attrib_typed(a) for a in geo.pointAttribs()[:12]]
            pr_typed = [_format_attrib_typed(a) for a in geo.primAttribs()[:8]]
            groups = [g.name() for g in geo.pointGroups()[:6]] + [g.name() for g in geo.primGroups()[:6]]

            desc = f"Input {i}: Connected from '{node_name}' ({node_desc} SOP, type '{node_type}') -> {geo_type}. {npts:,} points, {nprims:,} primitives."

            # Bounding box
            bsz = None
            bctr = None
            try:
                bbox = geo.boundingBox()
                bsz = bbox.sizevec()
                bctr = bbox.center()
                desc += f"\n  Bounding Box: size=({bsz[0]:.2f}, {bsz[1]:.2f}, {bsz[2]:.2f}), center=({bctr[0]:.2f}, {bctr[1]:.2f}, {bctr[2]:.2f})."
            except Exception:
                pass

            # --- Input 0 (Self Geometry Being Modified) ---
            if i == 0:
                is_3d_mesh = (nprims > 0 and "3D Polygon Mesh" in geo_type and bsz is not None and bsz.length() > 0.001)
                is_point_cloud = (nprims == 0 and npts > 0)
                is_planar_surface = ("Planar" in geo_type or (nprims > 0 and bsz is not None and min(bsz[0], bsz[1], bsz[2]) < 1e-4))
                is_curve = ("Curve" in geo_type or "Path" in geo_type)

                if is_3d_mesh:
                    desc += f"\n  Role: Primary input is a 3D {geo_type} ({npts:,} points, {nprims:,} primitives)."
                    desc += "\n  CRITICAL SPATIAL MESH RULE: In Point Wrangle, code runs in parallel per-point (@ptnum)."
                    desc += f"\n  NEVER assign an absolute single-point position like '@P = target_pos;' — that will collapse all {npts:,} vertices into a single degenerate point and destroy the 3D mesh volume!"
                    desc += "\n  To move, animate, or follow a path with this mesh, ALWAYS apply relative translation: vector _c = getbbox_center(0); @P += (target_pos - _c);"
                elif is_point_cloud:
                    desc += f"\n  Role: Primary input is a Point Cloud ({npts:,} points, 0 primitives)."
                    desc += "\n  Point Processing Rule: Points are independent samples/particles. Each point can be directly projected, moved, or advected independently (@P = target_pos; or @P += force * dt;)."
                elif is_planar_surface:
                    desc += f"\n  Role: Primary input is a 2D Planar Surface / Grid ({npts:,} points, {nprims:,} primitives)."
                    desc += "\n  Planar Mesh Rule: Displace points along normal (@N) or Y axis, or apply relative translation to preserve grid layout."
                elif is_curve:
                    desc += f"\n  Role: Primary input is an Open Polyline Curve ({npts:,} points, {nprims:,} primitives)."
                    desc += "\n  Curve Processing Rule: Points form a sequential path. Deform or project points preserving polyline order."
                else:
                    desc += f"\n  Role: Primary input geometry being processed in this wrangle ({npts:,} points, {nprims:,} primitives)."

                if any(a.name() == "v" for a in geo.pointAttribs()):
                    desc += "\n  Dynamics hint: Velocity (v@v) exists on Input 0. For simulation integration: @P += v@v * @TimeInc;"
                if any(a.name() == "orient" for a in geo.pointAttribs()):
                    desc += "\n  Orientation hint: Quaternion (p@orient) exists. Rotate via qmultiply() or qrotate()."
                if any(a.name() == "rest" for a in geo.pointAttribs()):
                    desc += "\n  Rest position hint: @rest exists. Sample procedural noise from @rest to avoid swimming textures."

            # --- Inputs 1, 2, 3 (Secondary External Reference / Guide / Collider) ---
            else:
                if "Curve" in geo_type or "Path" in geo_type or (nprims == 1 and npts > 1 and (bsz is not None and min(bsz[0], bsz[1], bsz[2]) < 0.001)):
                    desc += f"\n  Role: Guide curve / path trajectory (Input {i}) with {npts:,} points."
                    desc += f"\n  Path Following Pattern: float speed = chf('speed'); if (speed == 0.0) speed = 0.5; float u = frac(@Time * speed); vector path_pos = primuv({i}, 'P', 0, set(u, 0, 0));"
                    desc += f"\n  Preserve Volume Mesh Translation: @P += (path_pos - getbbox_center(0));"
                elif "Surface" in geo_type or "Mesh" in geo_type or nprims > 0:
                    desc += f"\n  Role: Target surface geometry / collider (Input {i}) with {npts:,} points, {nprims:,} primitives."
                    desc += f"\n  Closest Surface Query Pattern: int hit_prim; vector hit_uv; float dist = xyzdist({i}, @P, hit_prim, hit_uv); vector hit_P = primuv({i}, 'P', hit_prim, hit_uv); vector hit_N = primuv({i}, 'N', hit_prim, hit_uv);"
                    desc += f"\n  Directional Raycast Pattern: vector hit_P, hit_uv; int hit_prim = intersect({i}, @P, ray_dir * max_dist, hit_P, hit_uv);"
                else:
                    desc += f"\n  Role: Reference point cloud (Input {i}) with {npts:,} points."
                    desc += f"\n  Nearest Point Pattern: int near_pt = nearpoint({i}, @P); vector near_P = point({i}, 'P', near_pt);"
                    desc += f"\n  Radius Filter Pattern: int handle = pcopen({i}, 'P', @P, chf('radius'), chi('maxpts'));"

                # Attributes on secondary inputs
                transferrable = [a.name() for a in geo.pointAttribs() if a.name() not in ("P",)]
                if transferrable:
                    sample_attr = transferrable[0]
                    desc += f"\n  Attribute Transfer from Input {i}: int pt = nearpoint({i}, @P); if (pt != -1) @{sample_attr} = point({i}, '{sample_attr}', pt);"

            if pt_typed:
                desc += f"\n  Point Attribs: {', '.join(pt_typed)}."
            if pr_typed:
                desc += f"\n  Prim Attribs: {', '.join(pr_typed)}."
            if groups:
                desc += f"\n  Groups: {', '.join(groups)}."

            lines.append(desc)
        except Exception:
            if i not in connected_inputs:
                connected_inputs.append(i)

    # Introspect existing UI parameters on this wrangle
    param_lines = _introspect_node_parameters(node)
    if param_lines:
        lines.extend(param_lines)

    if not lines and not connected_inputs:
        return ""

    # --- Multi-Input Executive Header ---
    header_lines = [
        "Live Node & Geometry Context:",
        "Connected Inputs: " + ", ".join(f"Input {x} ({input_summaries.get(x, 'Geo')})" for x in connected_inputs) + ".",
    ]
    if empty_inputs:
        header_lines.append(f"Disconnected Inputs: {', '.join(f'Input {x}' for x in empty_inputs)} (Do NOT query in VEX).")
    header_lines.append("VEX Input Mapping: 0 = Self geometry being modified. 1, 2, 3 = External inputs (e.g. point(1, ...), xyzdist(1, ...)).")

    # --- Input connection rules ---
    rule_lines = []
    if 0 in connected_inputs and not (set(connected_inputs) - {0}):
        rule_lines.append("IMPORTANT: ONLY Input 0 is connected! Do NOT query or reference inputs 1, 2, or 3 (e.g. use nearpoints(0, ...), point(0, ...)).")

    rule_lines.append("Do NOT check or depend on non-existent attributes in if-statements unless they are listed above or you explicitly initialize them first.")

    # Upstream node type hints
    upstream = _get_upstream_hints(node)
    if upstream:
        rule_lines.extend(upstream)

    # Solver context detection
    if _detect_solver_context(node):
        rule_lines.append("This wrangle is INSIDE a SOP Solver. Use @Time/@TimeInc for time-stepping. Accumulate values (e.g., @P += v@vel * @TimeInc) instead of setting absolute values.")

    # Performance hints
    perf = _perf_hint(total_pts)
    if perf:
        rule_lines.append(perf)

    return "\n".join(header_lines) + "\n\n" + "\n".join(lines + rule_lines)


def auto_detect_context(prompt: str, node: hou.Node = None) -> tuple[int, str]:
    """Intelligently determines wrangle class from prompt intent and input geometry presence."""
    p = prompt.lower()
    
    # Check if input 0 has valid incoming geometry
    has_input_0_geo = False
    if node is not None:
        try:
            in0 = node.input(0)
            if in0 is not None:
                g0 = in0.geometry()
                if g0:
                    npts = _point_count(g0)
                    nprims = _prim_count(g0)
                    vols = _volume_count(g0) > 0
                    if npts > 0 or nprims > 0 or vols:
                        has_input_0_geo = True
        except Exception:
            has_input_0_geo = False

    # 1. Detail wrangle checks (curves from scratch, attractors, mesh generation, global aggregation)
    is_detail_generation = any(re.search(rf"\b{re.escape(k)}\b", p) for k in [
        "detail wrangle", "detail context", "from scratch", "create mesh", "generate curve", "create curve",
        "lorenz", "attractor", "spiral", "knot", "helix", "polyline", "mobius", "minimal surface",
        "global attribute", "whole geometry", "global calculation", "create points", "generate points",
        "stitch points", "connect points into", "synthesize", "spawn", "build from scratch", "make curve"
    ])
    
    # If input 0 has geometry and prompt explicitly describes deforming/displacing existing points,
    # do NOT treat it as detail generation from scratch unless "detail" or "from scratch" is explicitly requested.
    is_point_deformation_on_existing = has_input_0_geo and any(k in p for k in [
        "displace", "deform", "offset", "distort", "move points", "displace points", "deform points"
    ]) and not any(k in p for k in ["detail wrangle", "detail context", "from scratch", "create curve", "generate curve", "create mesh"])

    if is_detail_generation and not is_point_deformation_on_existing:
        return 0, "detail wrangle"

    # 2. If input 0 has NO geometry, a point/prim wrangle CANNOT run in Houdini!
    # Point wrangles execute 0 times on 0 input points. Therefore, any generative task MUST be detail!
    if not has_input_0_geo:
        # Respect explicit class overrides in prompt
        if any(re.search(rf"\b{re.escape(k)}\b", p) for k in ["primitive wrangle", "prim wrangle"]):
            return 1, "primitive wrangle"
        if any(re.search(rf"\b{re.escape(k)}\b", p) for k in ["vertex wrangle"]):
            return 3, "vertex wrangle"
        if any(re.search(rf"\b{re.escape(k)}\b", p) for k in ["point wrangle"]):
            return 2, "point wrangle"
        
        # When input 0 is empty/disconnected, default to detail wrangle so VEX runs and produces geometry!
        return 0, "detail wrangle"

    # --- When input geometry exists, detect context from prompt keywords ---
    # 3. Vertex wrangle checks — MUST be checked BEFORE primitive to prevent
    #    "vertex normals weighted by face angle" from matching "face" in primitive keywords.
    _VERTEX_KEYWORDS = [
        "vertex wrangle", "vertex normal", "vertex normals",
        "texture coordinate", "texture coordinates",
        "uv coordinate", "uv coordinates", "planar uv", "uv mapping",
        "run over vertices", "vertex uv", "vertex uvs", "per vertex", "each vertex",
        "vertex color", "vertex attribute", "vertex tangent", "uv seam", "uv island"
    ]
    if any(re.search(rf"\b{re.escape(k)}\b", p) for k in _VERTEX_KEYWORDS):
        if not ("point" in p and "vertex attribute" in p):
            return 3, "vertex wrangle"

    # 4. Primitive wrangle checks — exclude point-level sampling queries
    _PRIM_EXCLUDE_CONTEXTS = {"xyzdist", "primuv", "project points", "sample surface", "closest surface"}
    if not any(k in p for k in _PRIM_EXCLUDE_CONTEXTS):
        _PRIM_KEYWORDS = [
            "primitive wrangle", "prim wrangle",
            "set primitive", "primitive color", "primitive attribute",
            "each primitive", "every primitive", "per primitive",
            "primitive", "primitives", "prims",
            "face", "faces", "polygon", "polygons", "poly", "polys",
            "quad", "quads", "triangle", "triangles", "tris", "facet", "facets",
            "removeprim", "primpoints", "primvertexcount",
            "perimeter", "face area", "prim area", "polygon area",
            "neighbor face", "polygon face", "polygon normal",
            "checkerboard face", "delete small faces", "small faces",
            "delete face", "delete faces", "remove face", "remove faces",
            "delete prim", "delete prims", "remove prim", "remove prims",
            "based on area"
        ]
        if any(re.search(rf"\b{re.escape(k)}\b", p) for k in _PRIM_KEYWORDS):
            return 1, "primitive wrangle"

    # 5. Point operations (when input geometry exists)
    is_point_operation = any(k in p for k in [
        "each point", "every point", "per point", "all points", "particles",
        "point normal", "point position", "point color", "point velocity", "displace each point",
        "project each point", "sample the gradient", "scatter", "nearpoints", "pcopen", "pcfind",
        "deform", "advect", "relax", "smooth", "displace", "color", "noise"
    ])

    if is_point_operation:
        return 2, "point wrangle"

    return 2, "point wrangle"


# ---------------------------------------------------------------------------
# Generation, Refinement & 1-Shot CITL Self-Repair
# ---------------------------------------------------------------------------

# Semantic verb → VEX pattern hints (Phase 3: #6)
_VERB_PATTERNS = {
    # Geometry modification
    "smooth":      "Use neighbour()/nearpoints() averaging loop to smooth positions.",
    "blur":        "Average attribute values using pcfilter() or neighbour iteration.",
    "extrude":     "Move points along @N: @P += @N * chf('amount');",
    "twist":       "Apply rotation matrix around Y axis based on @P.y height.",
    "bend":        "Apply curvature deformation using matrix rotation varying along an axis.",
    "taper":       "Scale @P.xz based on @P.y position using fit().",
    "inflate":     "Push points along normals: @P += @N * chf('amount');",
    "erode":       "Pull points inward along -@N: @P -= @N * chf('amount');",
    "wave":        "Use sin(@P.x * freq + @Time * speed) for wave deformation.",
    "ripple":      "Use sin(length(@P - center) * freq) for concentric ripple.",
    "jitter":      "Add controlled randomness: @P += (rand(@ptnum) - 0.5) * chf('amount');",

    # Attribute operations
    "normalize":   "Use normalize() on the target vector attribute.",
    "randomize":   "Use rand(@ptnum) or random_shash() for per-element randomization.",
    "remap":       "Use fit() or chramp() to remap values between ranges.",
    "clamp":       "Use clamp(value, min, max) to restrict range.",
    "transfer":    "Use point()/prim() to read from another input, or nearpoints averaging.",
    "fit":         "Use fit(value, oldmin, oldmax, newmin, newmax) for range mapping.",

    # Spatial
    "project":     "Use xyzdist() + primuv() to project points onto a surface.",
    "snap":        "Use nearpoint(1, @P) + point(1, 'P', nearest) to snap to closest.",
    "attract":     "Move toward target: @P = lerp(@P, target, chf('strength'));",
    "repel":       "Push away: dir = normalize(@P - target); @P += dir * force;",
    "scatter":     "Use addpoint() in a detail wrangle with random distributions.",
    "relax":       "Use nearpoints averaging to push points apart (blue noise relaxation).",
    "intersection": "Compute surface distance to input 1: float d = xyzdist(1, @P, prim, uv); mask = clamp(1.0 - (d / chf('intersection_width')), 0, 1); set contact color at d=0.",
    "follow":      "To move geometry along a guide curve (input 1) preserving shape: float speed = chf('speed'); if (speed == 0.0) speed = 0.5; float u = frac(@Time * speed); vector path_pos = primuv(1, 'P', 0, set(u, 0, 0)); @P += (path_pos - getbbox_center(0));",
    "track":       "To track along a curve (input 1): float speed = chf('speed'); if (speed == 0.0) speed = 0.5; float u = frac(@Time * speed); vector path_pos = primuv(1, 'P', 0, set(u, 0, 0)); @P += (path_pos - getbbox_center(0));",
    "path":        "To animate geometry along a path curve (input 1) preserving shape: float speed = chf('speed'); if (speed == 0.0) speed = 0.5; float u = frac(@Time * speed); vector path_pos = primuv(1, 'P', 0, set(u, 0, 0)); @P += (path_pos - getbbox_center(0));",
    "stick":       "Sample target surface position using minpos(1, @P) or xyzdist(1, @P, close_prim, close_uv);",
    "attach":      "Sample target surface position using minpos(1, @P) or xyzdist(1, @P, close_prim, close_uv);",
    "intersect":   "Compute surface distance to input 1: float d = xyzdist(1, @P, prim, uv); mask = clamp(1.0 - (d / chf('intersection_width')), 0, 1); set contact color at d=0.",
    "contact":     "Compute surface distance to input 1: float d = xyzdist(1, @P, prim, uv); mask = clamp(1.0 - (d / chf('intersection_width')), 0, 1); set contact color at d=0.",

    # Topology
    "boundary":    "To detect open mesh boundaries/borders: int h = pointhedge(0, @ptnum); int is_b = 0; while (h != -1) { if (hedge_nextequiv(0, h) == h) { is_b = 1; break; } h = pointhedgenext(0, h); } if (is_b) { setpointgroup(0, 'boundary', @ptnum, 1); @Cd = set(1, 0, 0); }",
    "boundaries":  "To detect open mesh boundaries/borders: int h = pointhedge(0, @ptnum); int is_b = 0; while (h != -1) { if (hedge_nextequiv(0, h) == h) { is_b = 1; break; } h = pointhedgenext(0, h); } if (is_b) { setpointgroup(0, 'boundary', @ptnum, 1); @Cd = set(1, 0, 0); }",
    "boundries":   "To detect open mesh boundaries/borders: int h = pointhedge(0, @ptnum); int is_b = 0; while (h != -1) { if (hedge_nextequiv(0, h) == h) { is_b = 1; break; } h = pointhedgenext(0, h); } if (is_b) { setpointgroup(0, 'boundary', @ptnum, 1); @Cd = set(1, 0, 0); }",
    "border":      "To detect open mesh boundaries/borders: int h = pointhedge(0, @ptnum); int is_b = 0; while (h != -1) { if (hedge_nextequiv(0, h) == h) { is_b = 1; break; } h = pointhedgenext(0, h); } if (is_b) { setpointgroup(0, 'boundary', @ptnum, 1); @Cd = set(1, 0, 0); }",
    "perimeter":   "To detect perimeter/boundary edges: int h = pointhedge(0, @ptnum); int is_b = 0; while (h != -1) { if (hedge_nextequiv(0, h) == h) { is_b = 1; break; } h = pointhedgenext(0, h); } if (is_b) setpointgroup(0, 'boundary', @ptnum, 1);",
    "cull":        "Remove elements failing a condition via removepoint/removeprim.",
    "remove":      "Use removepoint(0, @ptnum) or removeprim(0, @primnum, 1).",
    "delete":      "Use removepoint(0, @ptnum) or removeprim(0, @primnum, 1).",
    "clip":        "In VEX, clip geometry or cull points along an axis or plane using removepoint(0, @ptnum) (e.g. if (@P.x > chf('clip_x')) removepoint(0, @ptnum);). Note: clip() is a SOP node, not a VEX geometry function.",
    "slice":       "To slice or cut geometry along an axis/plane in VEX: if (@P.x > chf('slice_pos')) removepoint(0, @ptnum); (or assign to groups i@group_slice = @P.x > 0;).",
    "lonely":      "To detect and remove lonely/isolated points with no connected primitives or neighbors: if (neighbourcount(0, @ptnum) == 0) removepoint(0, @ptnum);",
    "isolated":    "To remove isolated/unshared points with no neighbors: if (neighbourcount(0, @ptnum) == 0) removepoint(0, @ptnum);",
    "unshared":    "To remove unshared points: if (neighbourcount(0, @ptnum) == 0 || len(pointprims(0, @ptnum)) == 0) removepoint(0, @ptnum);",
    "split":       "Assign to groups, then use removeprim()/removepoint() per group.",
    "merge":       "In detail wrangle: loop over points from input sources.",

    # Color/Visual
    "color":       "Set @Cd = set(r, g, b); for per-point coloring.",
    "gradient":    "Use fit(@P.y, bottom, top, 0, 1) to create height-based color gradients.",
    "checkerboard": "Alternate colors using modular arithmetic on indices.",

    # Physics/Simulation
    "gravity":     "v@vel += {0, -9.81, 0} * @TimeInc; @P += v@vel * @TimeInc;",
    "bounce":      "Reflect velocity: v@vel = reflect(v@vel, hit_normal);",
    "friction":    "Dampen velocity: v@vel *= (1.0 - chf('friction'));",
    "collide":     "Use intersect() to detect surface collision, then resolve.",
    "orbit":       "Compute tangential velocity perpendicular to radius vector.",
    "spring":      "Use Hooke's law: force = -k * (length - rest_length) * dir;",

    # Mathematical & Algorithmic
    "prime":       "For primality test: numbers <= 1 are composite, 2 is prime, evens > 2 are composite. In trial division, use d * d <= n (not <) or d <= sqrt(n) so perfect squares like 4 and 9 are correctly marked composite.",
    "fibonacci":   "Generate Fibonacci sequence iteratively: int a = 0, b = 1; for (int i = 0; i < n; i++) { int c = a + b; a = b; b = c; }",
    "modulo":      "Use % operator for modular arithmetic: if (n % d == 0)",
}


def _build_verb_hints(task: str) -> str:
    """Match action verbs in the task to VEX pattern hints (Phase 3: #6)."""
    t = task.lower()
    hints = []
    for verb, hint in _VERB_PATTERNS.items():
        if re.search(rf"\b{re.escape(verb)}\b", t):
            hints.append(f"Hint ({verb}): {hint}")
    return "\n".join(hints[:3])  # cap at 3 to avoid bloating the prompt


def _build_init_guards(task: str, geo_context: str) -> str:
    """Detect attributes mentioned in the task that don't exist in geo_context and warn (Phase 3: #9 + #12)."""
    # Common attribute keywords users might reference
    ATTR_KEYWORDS = {
        "velocity": "v@vel", "vel": "v@vel", "color": "v@Cd", "normal": "v@N",
        "orient": "p@orient", "scale": "f@pscale", "pscale": "f@pscale",
        "rest": "v@rest", "age": "f@age", "life": "f@life", "id": "i@id",
        "density": "f@density", "mass": "f@mass", "width": "f@width",
    }
    t = task.lower()
    guards = []
    seen_attrs = set()
    for keyword, vex_attr in ATTR_KEYWORDS.items():
        if keyword in t and vex_attr not in seen_attrs:
            # Check if this attribute is already listed in geo_context
            attr_base = vex_attr.split("@")[1]  # e.g. "vel" from "v@vel"
            if geo_context and attr_base in geo_context:
                continue  # Already exists upstream
            guards.append(f"Attribute {vex_attr} may not exist yet. Initialize it before use if needed (e.g. {vex_attr} = {{0,0,0}};).")
            seen_attrs.add(vex_attr)
    return "\n".join(guards[:3])


def generate_vex(task: str, context: str = "point wrangle", geo_context: str = "", reasoning_mode: bool = False,
                 enable_rag: bool | None = None, temperature: float | None = None, seed: int | None = None) -> tuple[str, str]:
    """Generates pure VEX code with optional Deep Reasoning thought trace and RAG Ground Truth."""
    full_prompt = build_generation_prompt(task, context, geo_context, enable_rag)
    return query_llm(full_prompt, reasoning_mode=reasoning_mode, temperature=temperature, seed=seed)


def build_generation_prompt(task: str, context: str = "point wrangle", geo_context: str = "",
                            enable_rag: bool | None = None) -> str:
    """The user message Generate sends (RAG examples, geometry context, hints). Training data for
    the plugin's prompt format is built with this same function."""
    prompt_parts = []
    use_rag = enable_rag if enable_rag is not None else (os.getenv("AI_WRANGLE_ENABLE_RAG", "1") != "0")
    # The reference block (documented signatures of the functions the task probably needs) goes after the examples
    # and the geometry context, directly in front of the task. At the top of the prompt the models mostly ignored
    # it (open dev prompts, v53b: 52 -> 56 of 84 when moved; the listed function was used more often).
    # AI_WRANGLE_REFERENCE_LAST=0 restores the old position at the top.
    reference_last = os.getenv("AI_WRANGLE_REFERENCE_LAST", "1") != "0"
    rag_block = ""
    if use_rag and get_vex_rag_engine:
        try:
            rag = get_vex_rag_engine()
            rag_block = rag.build_rag_context_block(task, context=context)
            if rag_block and not reference_last:
                prompt_parts.append(rag_block)
        except Exception:
            rag_block = ""

    # Worked examples from the verified card bank (data/vex_card_bank.json): the most similar solved tasks.
    # On by default (sealed suites B-F, full pipeline: 114 -> 126 of 227 with the bank of 339 cards, 132 with 262;
    # open dev prompts 41 -> 46 of 84).
    # AI_WRANGLE_EXAMPLES=0 turns it off,
    # AI_WRANGLE_EXAMPLES_K sets how many (default 2).
    if use_rag and os.getenv("AI_WRANGLE_EXAMPLES", "1") != "0":
        try:
            import vex_example_bank
            # k is validated inside (1..6; anything that is not a number falls back to 2)
            ex_block = vex_example_bank.build_examples_block(task, context=context,
                                                             k=os.getenv("AI_WRANGLE_EXAMPLES_K", "2"))
            if ex_block:
                prompt_parts.append(ex_block)
        except Exception:
            pass

    if geo_context:
        prompt_parts.append(geo_context)
    if rag_block and reference_last:
        prompt_parts.append(rag_block)
    prompt_parts.append(f"Context: {context}")

    # --- Verb pattern hints (Phase 3: #6) ---
    verb_hints = _build_verb_hints(task)

    # --- Attribute initialization guards (Phase 3: #9 + #12) ---
    init_guards = _build_init_guards(task, geo_context)

    task_block = f"Task Instruction: {task}"
    if verb_hints:
        task_block += f"\n{verb_hints}"
    if init_guards:
        task_block += f"\n{init_guards}"

    prompt_parts.append(task_block)
    prompt_parts.append("Write pure Houdini VEX code:")

    return "\n\n".join(prompt_parts)


def refine_vex(refinement_task: str, existing_code: str, context: str = "point wrangle", geo_context: str = "", reasoning_mode: bool = False, enable_rag: bool | None = None) -> tuple[str, str]:
    """Performs multi-turn iterative modification on existing VEX code."""
    prompt_parts = []
    use_rag = enable_rag if enable_rag is not None else (os.getenv("AI_WRANGLE_ENABLE_RAG", "1") != "0")
    if use_rag and get_vex_rag_engine:
        try:
            rag = get_vex_rag_engine()
            rag_block = rag.build_rag_context_block(f"{refinement_task} {existing_code}", context=context)
            if rag_block:
                prompt_parts.append(rag_block)
        except Exception:
            pass

    if geo_context:
        prompt_parts.append(geo_context)
    prompt_parts.append(f"Context: {context}")
    prompt_parts.append(f"Existing VEX Code:\n{existing_code}")
    prompt_parts.append(f"Refinement Instruction:\n{refinement_task}")
    prompt_parts.append("Write pure updated Houdini VEX code:")
    
    full_prompt = "\n\n".join(prompt_parts)
    return query_llm(full_prompt, reasoning_mode=reasoning_mode)


def repair_vex(task: str, context: str, faulty_code: str, compiler_error: str, geo_context: str = "") -> tuple[str, str]:
    """Autonomous 1-Shot CITL Self-Repair using live compiler feedback and RAG Ground Truth."""
    full_prompt = build_repair_prompt(task, context, faulty_code, compiler_error, geo_context)
    return query_llm(full_prompt, max_tokens=2048, reasoning_mode=True)


def build_repair_prompt(task: str, context: str, faulty_code: str, compiler_error: str, geo_context: str = "") -> str:
    """The user message of a compiler-feedback repair request (training data uses the same function)."""
    prompt_parts = []
    enable_rag = os.getenv("AI_WRANGLE_ENABLE_RAG", "1") != "0"
    reference_last = os.getenv("AI_WRANGLE_REFERENCE_LAST", "1") != "0"  # same layout as build_generation_prompt
    rag_block = ""
    if enable_rag and get_vex_rag_engine:
        try:
            rag = get_vex_rag_engine()
            # With the function lookup the block is built from the task alone: the words of a compiler message
            # ("error", "undefined function", type names) are not about the task and pulled in error() and other
            # unrelated functions. The function the message is about gets its documented usage in the hint below.
            # (The older keyword matcher keeps its task + message query.)
            lookup_on = os.getenv("AI_WRANGLE_FUNCTION_INDEX", "1") != "0"
            rag_block = rag.build_rag_context_block(task if lookup_on else f"{task} {compiler_error}", context=context)
        except Exception:
            rag_block = ""
    if rag_block and not reference_last:
        prompt_parts.append(rag_block)

    if geo_context:
        prompt_parts.append(geo_context)
    if rag_block and reference_last:
        prompt_parts.append(rag_block)

    # Factual fix-it note for API near-misses (a function that does not exist, an unbound attribute, an
    # ambiguous overload, wrong arguments), from the compiler's function list and the function reference
    # (python/vex_api_hints.py). On by default since 2026-11-11 (open dev prompts: every answer of v53b compiled,
    # v54 46 -> 51 of 84 with no prompt lost); AI_WRANGLE_API_HINTS=0 turns it off.
    hint = ""
    if os.getenv("AI_WRANGLE_API_HINTS", "1") != "0":
        try:
            import vex_api_hints
            hint = vex_api_hints.hints_for_error(compiler_error, task=task)
        except Exception:
            hint = ""
    error_block = compiler_error + (f"\nHint: {hint}" if hint else "")

    prompt_parts.append(
        f"Context: {context}\n"
        f"Task: {task}\n\n"
        f"Faulty VEX Code:\n{faulty_code}\n\n"
        f"Compiler Error from previous attempt:\n{error_block}\n\n"
        f"Write the 100% correct, pure Houdini VEX code from scratch solving the task and avoiding this compiler error:"
    )
    return "\n\n".join(prompt_parts)


# ---------------------------------------------------------------------------
# SIMD Optimizer, Profiler & Explainer
# ---------------------------------------------------------------------------

def _require_vex(code: str) -> str:
    """Optimize and Explain replace the user's snippet with the answer: an answer without a single VEX statement
    (the model returned only thinking, or prose) must never get there, an empty snippet "compiles" and would wipe
    working code."""
    if not re.search(r"[;{}]", code or ""):
        raise EmptyModelResponse("The model returned no VEX code; the snippet was left unchanged.")
    return code


def optimize_vex_code(existing_code: str, context: str = "point wrangle") -> str:
    """Refactors VEX code for SIMD parallelism and execution efficiency."""
    prompt = (
        f"Context: {context}\n\n"
        f"VEX Code to Optimize:\n{existing_code}\n\n"
        f"Optimization Instructions:\n"
        f"- Hoist loop invariants and eliminate repeated function calls (e.g. normalize, distance).\n"
        f"- Replace pow(x, 2.0) with x * x and length(a - b) < r with length2(a - b) < r * r where applicable.\n"
        f"- Vectorize calculations using SIMD operations.\n"
        f"- Retain exact parameter channels (chf, chv, chramp).\n\n"
        f"Write pure optimized Houdini VEX code:"
    )
    _, code = query_llm(prompt, max_tokens=1536, reasoning_mode=False)
    return _require_vex(code)


def profile_node_cook(node: hou.Node) -> tuple[float, int, float]:
    """Measures cook execution time in milliseconds and compute throughput."""
    t0 = time.perf_counter()
    node.cook(force=True)
    cook_time = time.perf_counter() - t0
    cook_ms = cook_time * 1000.0
    
    g = node.geometry()
    npts = _point_count(g) if g else 0
    throughput = (npts / cook_time / 1e6) if cook_time > 0 and npts > 0 else 0.0
    return cook_ms, npts, throughput


def explain_and_document_vex(existing_code: str, context: str = "point wrangle") -> str:
    """Annotates VEX code with clean, educational inline comments and docstrings."""
    prompt = (
        f"Context: {context}\n\n"
        f"VEX Code to Document:\n{existing_code}\n\n"
        f"Instructions:\n"
        f"- Add a header comment explaining what the snippet does.\n"
        f"- Add concise step-by-step inline comments for matrix/quaternion/vector math.\n"
        f"- Document what each UI parameter (chf, chv, chramp) controls.\n"
        f"- Keep the exact same functional code intact and pure VEX.\n\n"
        f"Write the documented VEX code:"
    )
    _, code = query_llm(prompt, max_tokens=1536, reasoning_mode=False)
    return _require_vex(code)


# ---------------------------------------------------------------------------
# History Stack & Time Machine
# ---------------------------------------------------------------------------

def _get_status_parm(node: hou.Node):
    return node.parm("ai_status") or node.parm("last_error") if node else None


def _get_info_parm(node: hou.Node):
    return node.parm("ai_version_info") or node.parm("ai_history_label") if node else None


def _get_history_parm(node: hou.Node):
    return node.parm("ai_history_json") or node.parm("ai_history") if node else None


def get_history_stack(node: hou.Node) -> list[dict]:
    parm = _get_history_parm(node)
    if not parm or not parm.eval().strip():
        return []
    try:
        return json.loads(parm.eval())
    except Exception:
        return []


_HISTORY_LIMIT = 50


def push_to_history_stack(node: hou.Node, prompt: str, code: str, context_str: str, cook_ms: float = 0.0, thought: str = ""):
    parm = _get_history_parm(node)
    info_parm = _get_info_parm(node)
    if not parm:
        return

    history = get_history_stack(node)
    if history and history[-1].get("code", "").strip() == code.strip():
        return

    version_num = (history[-1].get("version", len(history)) + 1) if history else 1
    entry = {
        "version": version_num,
        "timestamp": time.strftime("%H:%M:%S"),
        "prompt": prompt[:40] if prompt else "Optimized/Documented",
        "context": context_str,
        "code": code,
        "cook_ms": cook_ms,
        "thought": (thought or "")[:2000],
    }
    history.append(entry)
    # Bounded: the stack lives in a string parm saved with the .hip and copied into every undo step.
    history = history[-_HISTORY_LIMIT:]
    parm.set(json.dumps(history))

    if info_parm:
        info_parm.set(f"v{version_num} / {len(history)} kept ({entry['timestamp']})")


def navigate_history_version(node: hou.Node, direction: int):
    history = get_history_stack(node)
    if not history:
        if hou.isUIAvailable():
            hou.ui.displayMessage("No history recorded yet.", severity=hou.severityType.Warning)
        return

    # Determine current index from version_info parm (reliable, not content-based)
    info_parm = _get_info_parm(node)
    current_idx = len(history) - 1
    if info_parm:
        ver_str = info_parm.eval()  # e.g. "v5 / 11 (20:10:13)"
        try:
            # Parse "vX / Y (HH:MM:SS)" -> X-1 (0-based)
            current_ver_num = int(ver_str.split("/")[0].strip().lstrip("v"))
            # Find the matching history entry by version number
            for i, item in enumerate(history):
                if item.get("version") == current_ver_num:
                    current_idx = i
                    break
        except (ValueError, IndexError):
            # Fallback: search by content match
            current_code = node.parm("snippet").eval().strip() if node.parm("snippet") else ""
            for i, item in enumerate(history):
                if item.get("code", "").strip() == current_code:
                    current_idx = i
                    break

    target_idx = max(0, min(len(history) - 1, current_idx + direction))
    if target_idx == current_idx:
        if hou.isUIAvailable():
            hou.ui.setStatusMessage(
                "Already at first version." if direction < 0 else "Already at latest version.",
                severity=hou.severityType.Message
            )
        return

    target_entry = history[target_idx]
    target_code = target_entry["code"]

    with hou.undos.group(f"AI VEX History v{target_entry.get('version', target_idx + 1)}"):
        saved = _snapshot_spare_values(node)
        node.parm("snippet").set(target_code)
        sync_spare_parameters(node, target_code)
        _restore_spare_values(node, saved)

    if node.parm("ai_thought_trace") and "thought" in target_entry:
        node.parm("ai_thought_trace").set(target_entry["thought"] or "Turbo mode (direct execution)")

    try:
        node.cook(force=True)
    except Exception:
        pass

    status_parm = _get_status_parm(node)
    if info_parm:
        info_parm.set(f"v{target_entry['version']} / {len(history)} ({target_entry['timestamp']})")
    if status_parm:
        status_parm.set(f"Loaded v{target_entry['version']}: {target_entry['prompt']}")



# ---------------------------------------------------------------------------
# Spare Parameter Synchronization
# ---------------------------------------------------------------------------

def parse_vex_channels(vex_code: str) -> dict[str, str]:
    # Strip comments before parsing to prevent phantom spare parameters from
    # commented-out channel calls like: // float amp = chf("amp");
    stripped = re.sub(r'/\*.*?\*/', '', vex_code, flags=re.DOTALL)
    stripped = re.sub(r'//[^\n]*', '', stripped)

    channels = {}
    for m in re.finditer(r'chramp\s*\(\s*["\']([^"\']+)["\']', stripped):
        channels[m.group(1)] = "ramp"
    for m in re.finditer(r'(?:chv|chp)\s*\(\s*["\']([^"\']+)["\']', stripped):
        name = m.group(1)
        if name not in channels: channels[name] = "vector"
    for m in re.finditer(r'chi\s*\(\s*["\']([^"\']+)["\']', stripped):
        name = m.group(1)
        if name not in channels: channels[name] = "int"
    for m in re.finditer(r'chs\s*\(\s*["\']([^"\']+)["\']', stripped):
        name = m.group(1)
        if name not in channels: channels[name] = "string"
    for m in re.finditer(r'(?:chf|ch)\s*\(\s*["\']([^"\']+)["\']', stripped):
        name = m.group(1)
        if name not in channels: channels[name] = "float"
    return channels


_NUM = r"(-?\d+(?:\.\d*)?(?:[eE]-?\d+)?|-?\.\d+)"


def channel_default_hints(vex_code: str) -> dict:
    """Defaults the code itself asks for. Generated code often reads a slider and falls back when it is
    unset, e.g. `float step = chf("step"); if (step == 0.0) step = 0.1;`. An unset slider would give
    that fallback, so the slider is created with it as its default (a generic 1.0 changed the result).
    Divide-by-zero guards like `if (abs(x) < 1e-4) x = 1.0;` are not intent and are ignored."""
    stripped = re.sub(r'/\*.*?\*/', '', vex_code or "", flags=re.DOTALL)
    stripped = re.sub(r'//[^\n]*', '', stripped)
    hints = {}
    decl = r'\b(?:float|int)\s+(\w+)\s*=\s*(?:chf|chi|ch)\s*\(\s*["\']([^"\']+)["\']\s*\)\s*;'
    for m in re.finditer(decl, stripped):
        var, ch = m.group(1), m.group(2)
        g = re.search(rf'if\s*\(\s*{var}\s*(?:==|<=|<)\s*0(?:\.0*)?\s*\)\s*\{{?\s*{var}\s*=\s*{_NUM}\s*;',
                      stripped[m.end():])
        if g:
            try:
                hints.setdefault(ch, float(g.group(1)))
            except ValueError:
                pass
    return hints


def _compute_scale_calibrated_parm(name: str, p_type: str, bbox_max: float, hint: float | None = None) -> hou.ParmTemplate:
    """Calibrates parameter defaults, minimums, and maximums based on geometry bounding box scale.
    hint: the default the code itself falls back to (see channel_default_hints), used when given."""
    label = name.replace("_", " ").title()
    tooltip = f"Auto-generated interactive {p_type} control for VEX channel '{name}'."
    n_lower = name.lower()
    if hint is not None and p_type in ("float", "int"):
        span = max(abs(hint) * 2.0, 1.0)
        lo = min(0.0, -span) if hint < 0 else 0.0
        if p_type == "int":
            return hou.IntParmTemplate(name, label, 1, default_value=(int(round(hint)),), min=int(lo), max=int(max(span, 10)),
                                       min_is_strict=False, max_is_strict=False, help=tooltip)
        return hou.FloatParmTemplate(name, label, 1, default_value=(hint,), min=lo, max=span,
                                     min_is_strict=False, max_is_strict=False, help=tooltip)

    if p_type == "float":
        if any(k in n_lower for k in ["radius", "dist", "distance", "offset", "maxdist", "thresh", "threshold", "size", "scale"]):
            max_val = max(round(bbox_max, 2), 1.0)
            def_val = round(bbox_max * 0.1, 3)
            return hou.FloatParmTemplate(name, label, 1, default_value=(def_val,), min=0.0, max=max_val, min_is_strict=False, max_is_strict=False, help=tooltip)
        elif any(k in n_lower for k in ["freq", "frequency"]):
            max_val = max(round(50.0 / max(bbox_max, 0.1), 2), 10.0)
            def_val = round(2.0 / max(bbox_max, 0.1), 3)
            return hou.FloatParmTemplate(name, label, 1, default_value=(def_val,), min=0.01, max=max_val, min_is_strict=False, max_is_strict=False, help=tooltip)
        elif any(k in n_lower for k in ["roughness", "contrast", "friction", "blend", "damping", "bias", "gain", "stiffness", "weight", "amount", "mix", "strength"]):
            return hou.FloatParmTemplate(name, label, 1, default_value=(0.5,), min=0.0, max=1.0, min_is_strict=True, max_is_strict=True, help=tooltip)
        elif any(k in n_lower for k in ["angle", "rot", "rotation", "pitch", "yaw", "roll"]):
            return hou.FloatParmTemplate(name, label, 1, default_value=(45.0,), min=0.0, max=360.0, min_is_strict=False, max_is_strict=False, help=tooltip)
        elif any(k in n_lower for k in ["speed", "vel", "velocity", "accel"]):
            max_val = max(round(bbox_max * 5.0, 1), 10.0)
            def_val = round(bbox_max * 0.5, 2)
            return hou.FloatParmTemplate(name, label, 1, default_value=(def_val,), min=0.0, max=max_val, min_is_strict=False, max_is_strict=False, help=tooltip)
        else:
            return hou.FloatParmTemplate(name, label, 1, default_value=(1.0,), min=0.0, max=10.0, min_is_strict=False, max_is_strict=False, help=tooltip)

    elif p_type == "int":
        if any(k in n_lower for k in ["maxpts", "neighbors", "nbrs", "samples", "count", "num"]):
            return hou.IntParmTemplate(name, label, 1, default_value=(16,), min=1, max=100, min_is_strict=False, max_is_strict=False, help=tooltip)
        elif any(k in n_lower for k in ["steps", "iterations", "substeps"]):
            return hou.IntParmTemplate(name, label, 1, default_value=(10,), min=1, max=50, min_is_strict=False, max_is_strict=False, help=tooltip)
        elif any(k in n_lower for k in ["total", "pts", "points"]):
            return hou.IntParmTemplate(name, label, 1, default_value=(200,), min=1, max=1000, min_is_strict=False, max_is_strict=False, help=tooltip)
        else:
            return hou.IntParmTemplate(name, label, 1, default_value=(1,), min=0, max=100, min_is_strict=False, max_is_strict=False, help=tooltip)

    elif p_type == "vector":
        if any(k in n_lower for k in ["color", "cd"]):
            def_vec = (1.0, 0.5, 0.2)
        elif any(k in n_lower for k in ["dir", "axis", "up"]):
            def_vec = (0.0, 1.0, 0.0)
        elif any(k in n_lower for k in ["scale"]):
            def_vec = (1.0, 1.0, 1.0)
        elif any(k in n_lower for k in ["target"]):
            def_vec = (0.0, round(bbox_max * 0.5, 2), 0.0)
        else:
            def_vec = (0.0, 1.0, 0.0)
        return hou.FloatParmTemplate(name, label, 3, default_value=def_vec, look=hou.parmLook.Vector, help=tooltip)

    elif p_type == "string":
        return hou.StringParmTemplate(name, label, 1, default_value=("",), help=tooltip)

    elif p_type == "ramp":
        return hou.RampParmTemplate(name, label, hou.rampParmType.Color, help=tooltip)

    return hou.FloatParmTemplate(name, label, 1, default_value=(1.0,), min=0.0, max=10.0, min_is_strict=False, max_is_strict=False, help=tooltip)


def sync_spare_parameters(node: hou.Node, vex_code: str):
    channels = parse_vex_channels(vex_code)
    ptg = node.parmTemplateGroup()
    folder_name = "ai_spare_parms"
    folder = ptg.find(folder_name)

    if not channels:
        if folder is not None:
            ptg.remove(folder_name)
            node.setParmTemplateGroup(ptg)
        return

    # Extract upstream geometry scale for bounding-box calibration
    bbox_max = 1.0
    try:
        inp = node.input(0)
        if inp and inp.geometry():
            bsz = inp.geometry().boundingBox().sizevec()
            bbox_max = max(bsz.x(), bsz.y(), bsz.z(), 0.01)
    except Exception:
        pass

    hints = channel_default_hints(vex_code)
    reset = {}  # parms whose default changed and whose value was never touched -> new default

    if folder is None:
        folder = hou.FolderParmTemplate(folder_name, "Generated UI Parameters", folder_type=hou.folderType.Simple)
        for name, p_type in channels.items():
            folder.addParmTemplate(_compute_scale_calibrated_parm(name, p_type, bbox_max, hints.get(name)))

        snippet_parm = ptg.find("snippet")
        if snippet_parm:
            ptg.insertAfter(snippet_parm, folder)
        else:
            ptg.append(folder)
    else:
        existing_templates = {pt.name(): pt for pt in folder.parmTemplates()}
        new_folder = hou.FolderParmTemplate(folder_name, "Generated UI Parameters", folder_type=hou.folderType.Simple)
        
        for name, p_type in channels.items():
            old_t = existing_templates.get(name)
            hint = hints.get(name)
            if old_t is not None and hint is not None and _untouched_default(node, old_t, hint):
                new_folder.addParmTemplate(_compute_scale_calibrated_parm(name, p_type, bbox_max, hint))
                reset[name] = hint
            elif old_t is not None:
                new_folder.addParmTemplate(old_t)
            else:
                new_folder.addParmTemplate(_compute_scale_calibrated_parm(name, p_type, bbox_max, hint))

        ptg.replace(folder_name, new_folder)

    node.setParmTemplateGroup(ptg)
    for name, val in reset.items():
        p = node.parm(name)
        if p is not None:
            try:
                p.set(int(round(val)) if p.parmTemplate().type() == hou.parmTemplateType.Int else val)
            except Exception:
                pass


def _untouched_default(node, template, new_default: float) -> bool:
    """True if a 1-component numeric slider still sits at its template default (the artist never moved
    it) and the new code asks for a different default."""
    try:
        if template.numComponents() != 1 or template.type() not in (hou.parmTemplateType.Float, hou.parmTemplateType.Int):
            return False
        old_default = float(template.defaultValue()[0])
        p = node.parm(template.name())
        return (p is not None and abs(float(p.eval()) - old_default) < 1e-9
                and abs(old_default - float(new_default)) > 1e-9)
    except Exception:
        return False


# ---------------------------------------------------------------------------
def force_refresh_wrangle(node: hou.Node) -> None:
    """
    Forces immediate recompilation, parameter evaluation, and viewport redraw.
    Eliminates the need for manual node cut-and-paste refreshes.
    """
    if not node:
        return

    # 1. Force recompile on internal WrangleCore / VOP child nodes if inside an HDA
    for child in node.children():
        fc = child.parm("vop_forcecompile")
        if fc:
            try:
                fc.pressButton()
            except Exception:
                pass
        try:
            child.cook(force=True)
        except Exception:
            pass

    # 2. Force full cook on node geometry
    try:
        node.cook(force=True)
        _ = node.geometry()
    except Exception:
        pass

    # Downstream nodes are dirtied by Houdini automatically; force-cooking them here used to re-run
    # solvers / file caches below the wrangle on every generation attempt.

    # 3. Trigger UI update & force scene viewer viewport redraw
    if hou.isUIAvailable():
        try:
            hou.ui.triggerUpdate()
        except Exception:
            pass
        try:
            for pane in hou.ui.currentPaneTabs():
                if pane.type() == hou.paneTabType.SceneViewer:
                    pane.curViewport().draw()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Compile & Apply Safety Net
# ---------------------------------------------------------------------------

def _point_count(geo) -> int:
    try:
        return int(geo.intrinsicValue("pointcount"))
    except Exception:
        return len(geo.points())


def _prim_count(geo) -> int:
    try:
        return int(geo.intrinsicValue("primitivecount"))
    except Exception:
        return len(geo.prims())


def _sample_points(geo, k: int = 50) -> list:
    """Up to k points spread evenly over the geometry, without materialising all points."""
    n = _point_count(geo)
    if n <= 0:
        return []
    step = max(1, n // k)
    return [geo.point(i) for i in range(0, n, step)][:k]


def _sample_prims(geo, k: int = 50) -> list:
    n = _prim_count(geo)
    if n <= 0:
        return []
    step = max(1, n // k)
    return [geo.prim(i) for i in range(0, n, step)][:k]


def verify_physical_invariants(node: hou.Node) -> tuple[bool, str | None]:
    """Physical & Topological Invariant Verifier.
    
    Evaluates whether the cooked geometry satisfies fundamental physical and topological laws.
    Flags singularities (mesh volume collapse), NaNs, and unexpected element annihilation
    so the CITL loop can prompt the model to self-correct using first-principles logic.
    """
    if not hou or not node:
        return True, None
    try:
        geo = node.geometry()
        if not geo:
            return True, None

        # Check NaN / Infinite Coordinates (sample spread over the whole geometry; never build a
        # Python list of every point: that alone takes seconds on million-point meshes)
        sample_pts = _sample_points(geo, 50)
        for pt in sample_pts:
            pos = pt.position()
            if any(math.isnan(v) or math.isinf(v) for v in pos):
                return False, (
                    "PHYSICAL INVARIANT VIOLATION: Point coordinates evaluate to NaN or Inf! "
                    "Ensure numerical stability: check for division by zero, invalid acos/asin domain (clamp -1 to 1), "
                    "or taking sqrt/log of negative numbers."
                )

        in0 = node.input(0)
        if in0:
            g0 = in0.geometry()
            if g0:
                n_in = _point_count(g0)
                n_out = _point_count(geo)
                b_in = g0.boundingBox()
                b_out = geo.boundingBox()
                sz_in = b_in.sizevec()
                sz_out = b_out.sizevec()

                # Invariant 1: 3D Mesh Volume Collapse / Singularity
                # If Input 0 was a 3D mesh (size > 0.05, >4 points) and output collapsed to 0:
                if n_in > 4 and sz_in.length() > 0.05 and sz_out.length() < 0.0001:
                    prompt_val = ""
                    p_parm = node.parm("ai_prompt")
                    if p_parm:
                        prompt_val = p_parm.eval().lower()
                    if not any(k in prompt_val for k in ["collapse", "singularity", "origin", "merge into one point"]):
                        return False, (
                            "PHYSICAL INVARIANT VIOLATION: 3D mesh collapsed into a zero-radius singularity! "
                            "All points were assigned the identical absolute coordinate (e.g. '@P = target_pos;'). "
                            "In a Point Wrangle, code runs in parallel per-point (@ptnum). "
                            "To move/deform a mesh along a path or target while preserving its 3D volume, "
                            "you MUST apply relative centroid translation: "
                            "@P += (target_pos - getbbox_center(0));"
                        )

                # Invariant 2: Catastrophic Accidental Point Annihilation
                if n_in > 50 and n_out == 0:
                    prompt_val = node.parm("ai_prompt").eval().lower() if node.parm("ai_prompt") else ""
                    if not any(k in prompt_val for k in ["delete", "remove", "clear", "cull", "destroy", "empty"]):
                        return False, (
                            "PHYSICAL INVARIANT VIOLATION: All points were unexpectedly deleted! "
                            "Input had elements, but output geometry is empty. "
                            "Verify removepoint() or point culling condition logic."
                        )

                # Invariant 3: Uncontrolled Coordinate Explosion
                if sz_in.length() > 0.001 and (sz_out.length() / max(sz_in.length(), 0.001)) > 5000.0:
                    prompt_val = node.parm("ai_prompt").eval().lower() if node.parm("ai_prompt") else ""
                    if not any(k in prompt_val for k in ["explode", "huge", "infinite", "expand by 1000"]):
                        return False, (
                            "PHYSICAL INVARIANT VIOLATION: Coordinates exploded by >5000x! "
                            "Check parameter scale multiplier or exponential growth in simulation logic."
                        )

                # Invariant 4: Attribute Numerical Sanity (@v, p@orient, @Cd NaNs)
                for attr_name in ("v", "orient", "Cd"):
                    attr = geo.findPointAttrib(attr_name)
                    if attr:
                        for pt in sample_pts[:20]:
                            val = pt.attribValue(attr_name)
                            if isinstance(val, (list, tuple)) and any(math.isnan(v) or math.isinf(v) for v in val):
                                return False, (
                                    f"PHYSICAL INVARIANT VIOLATION: Point attribute '@{attr_name}' contains NaN or Inf! "
                                    f"Ensure numerical stability in vector/quaternion math operations."
                                )

                # Invariant 5: Normal Vector Degeneracy / Collapse
                n_attr = geo.findPointAttrib("N")
                if n_attr and len(sample_pts) > 0:
                    zero_n_count = 0
                    for pt in sample_pts[:20]:
                        n_val = pt.attribValue("N")
                        if isinstance(n_val, (list, tuple)) and all(abs(v) < 1e-6 for v in n_val):
                            zero_n_count += 1
                    if zero_n_count > 5:
                        prompt_val = node.parm("ai_prompt").eval().lower() if node.parm("ai_prompt") else ""
                        if not any(k in prompt_val for k in ["clear normal", "zero normal", "remove normal", "delete normal"]):
                            return False, (
                                "PHYSICAL INVARIANT VIOLATION: Surface normals collapsed to zero vector (0, 0, 0)! "
                                "Ensure vector normalization normalize(N) and provide non-zero fallback."
                            )
    except Exception:
        pass
    return True, None


def _snapshot_spare_values(node) -> dict:
    """Current values of the generated UI parameters (sliders, ramps), keyed by parm tuple name."""
    out = {}
    folder = node.parmTemplateGroup().find("ai_spare_parms")
    if folder is None:
        return out
    for pt in folder.parmTemplates():
        tup = node.parmTuple(pt.name())
        if tup is not None:
            try:
                out[pt.name()] = tup.eval()
            except Exception:
                pass
    return out


def _restore_spare_values(node, values: dict) -> None:
    for name, val in values.items():
        tup = node.parmTuple(name)
        if tup is None:
            continue
        try:
            if isinstance(val, hou.Ramp):
                tup.set(val)
            else:
                tup.set(val if isinstance(val, (tuple, list)) else (val,))
        except Exception:
            pass


def try_apply_snippet(node: hou.Node, vex_code: str, snippet_parm_name: str = "snippet") -> tuple[bool, str | None]:
    parm = node.parm(snippet_parm_name)
    if parm is None:
        return False, f"Node {node.path()} has no '{snippet_parm_name}' parameter."

    previous_value = parm.eval()
    previous_ptg = node.parmTemplateGroup()
    previous_spare_values = _snapshot_spare_values(node)
    parm.set(vex_code)

    # Synchronize spare parameters first so channel default values exist
    sync_spare_parameters(node, vex_code)

    # Force internal VOP recompile and cook
    force_refresh_wrangle(node)

    vop = node.node("attribvop1") if (node.type().name().startswith("attrib") or node.type().name().startswith("ai_")) else None
    raw_vop_errs = vop.errors() if vop else ()
    raw_node_errs = node.errors()

    try:
        node.cook(force=True)
    except Exception as e:
        raw_node_errs = tuple(list(raw_node_errs) + [str(e)])
    
    # Filter out benign 'invalid source' messages when input 0 is simply not yet wired
    vop_errs = [e for e in raw_vop_errs if "invalid source" not in e.lower()]
    node_errs = [e for e in raw_node_errs if "invalid source" not in e.lower()]

    # Any compile/cook error counts (e.g. "Empty array index", "Invalid assignment", "Error in VOP"
    # used to slip past a keyword whitelist and be reported as success, skipping self-repair).
    has_real_error = bool(node_errs or vop_errs)

    if has_real_error:
        err_msg = "\n".join(list(raw_node_errs) + list(raw_vop_errs) + list(node.warnings()))
        parm.set(previous_value)
        node.setParmTemplateGroup(previous_ptg)
        _restore_spare_values(node, previous_spare_values)
        force_refresh_wrangle(node)
        return False, err_msg

    # Verify physical and topological invariants
    inv_ok, inv_err = verify_physical_invariants(node)
    if not inv_ok:
        parm.set(previous_value)
        node.setParmTemplateGroup(previous_ptg)
        _restore_spare_values(node, previous_spare_values)
        force_refresh_wrangle(node)
        return False, inv_err

    return True, None


# ---------------------------------------------------------------------------
# Production Safety Shield & Diagnostics
# ---------------------------------------------------------------------------

def sanitize_nan_inf_vex(code: str) -> str:
    """Injects defensive mathematical guards against NaN/Inf and division-by-zero.

    Uses balanced parenthesis matching to correctly handle nested function calls
    like acos(dot(normalize(v@N), {0,1,0})).
    """
    def _guard_func(code, func_name, wrapper_fmt):
        """Find all occurrences of func_name(...) and wrap inner arg with wrapper_fmt."""
        result = []
        i = 0
        func_re = re.compile(rf'\b{func_name}\s*\(')
        while i < len(code):
            m = func_re.search(code, i)
            if not m:
                result.append(code[i:])
                break
            result.append(code[i:m.start()])
            open_pos = m.end() - 1
            depth = 1
            j = open_pos + 1
            while j < len(code) and depth > 0:
                if code[j] == '(':
                    depth += 1
                elif code[j] == ')':
                    depth -= 1
                j += 1
            if depth != 0:
                result.append(code[m.start():j])
                i = j
                continue
            inner_arg = code[open_pos + 1:j - 1].strip()
            guarded_arg = wrapper_fmt.format(inner_arg)
            result.append(f"{func_name}({guarded_arg})")
            i = j
        return ''.join(result)

    # 1. acos(x) -> acos(clamp(x, -1.0, 1.0))
    code = _guard_func(code, 'acos', 'clamp({0}, -1.0, 1.0)')
    # 2. asin(x) -> asin(clamp(x, -1.0, 1.0))
    code = _guard_func(code, 'asin', 'clamp({0}, -1.0, 1.0)')
    # 3. sqrt(x) -> sqrt(max(x, 0.0))
    code = _guard_func(code, 'sqrt', 'max({0}, 0.0)')
    # 4. log(x) -> log(max(x, 1e-6))
    code = _guard_func(code, 'log', 'max({0}, 1e-6)')
    return code


def _float_attrib_array(geo, attr):
    """All values of a numeric (non-array) point/prim attribute as an (n, size) float64 array."""
    import numpy as np
    owner = attr.type()
    if attr.isArrayType():
        return None
    if attr.dataType() == hou.attribData.Float:
        raw = (geo.pointFloatAttribValuesAsString(attr.name()) if owner == hou.attribType.Point
               else geo.primFloatAttribValuesAsString(attr.name()))
        arr = np.frombuffer(raw, dtype=np.float32)
    elif attr.dataType() == hou.attribData.Int:
        raw = (geo.pointIntAttribValuesAsString(attr.name()) if owner == hou.attribType.Point
               else geo.primIntAttribValuesAsString(attr.name()))
        arr = np.frombuffer(raw, dtype=np.int32)
    else:
        return None
    size = max(1, attr.size())
    return arr.astype(np.float64).reshape(-1, size) if arr.size else arr.reshape(0, size).astype(np.float64)


def scan_geometry_health(node: hou.Node) -> tuple[bool, str]:
    """Checks every point and primitive float attribute for NaN / Inf (vectorised, all elements)."""
    try:
        import numpy as np
        geo = node.geometry()
        if not geo:
            return True, "No geometry to scan."
        nan_issues, inf_issues = [], []
        for attr in list(geo.pointAttribs()) + list(geo.primAttribs()):
            if attr.dataType() != hou.attribData.Float:
                continue
            vals = _float_attrib_array(geo, attr)
            if vals is None or vals.size == 0:
                continue
            if np.isnan(vals).any():
                nan_issues.append(attr.name())
            elif np.isinf(vals).any():
                inf_issues.append(attr.name())
        total = f" (scanned all {_point_count(geo):,} points, {_prim_count(geo):,} prims)"
        if nan_issues or inf_issues:
            parts = []
            if nan_issues:
                parts.append(f"NaN in @{', @'.join(nan_issues)}")
            if inf_issues:
                parts.append(f"Inf in @{', @'.join(inf_issues)}")
            return False, f"⚠️ Health Alert: Detected {'; '.join(parts)}!{total}"
        return True, f"✅ Geometry Healthy: 0 NaNs / 0 Infs detected.{total}"
    except Exception as e:
        return True, f"Scan skipped: {e}"


def inspect_attribute_statistics(node: hou.Node) -> str:
    """min / max / average (magnitude for vectors) and NaN/Inf counts over all elements."""
    import numpy as np
    geo = node.geometry()
    if not geo:
        return "No geometry available on this node."
    lines = [f"=== Attribute Health & Statistics: {node.path()} ==="]
    lines.append(f"Total Geometry: {_point_count(geo):,} points, {_prim_count(geo):,} primitives.\n")
    for title, attribs in (("Point", geo.pointAttribs()), ("Primitive", geo.primAttribs())):
        if not attribs:
            continue
        lines.append(f"--- {title} Attributes ---")
        for attr in attribs:
            name, sz, dt = attr.name(), attr.size(), attr.dataType()
            if attr.isArrayType():
                lines.append(f"  @{name} ({dt.name().lower()} array)")
                continue
            if dt == hou.attribData.String:
                lines.append(f"  @{name} (string)")
                continue
            vals = _float_attrib_array(geo, attr)
            if vals is None or vals.size == 0:
                lines.append(f"  @{name}: empty")
                continue
            bad_nan = int(np.isnan(vals).any(axis=1).sum())
            bad_inf = int((np.isinf(vals).any(axis=1) & ~np.isnan(vals).any(axis=1)).sum())
            good = vals[np.isfinite(vals).all(axis=1)]
            mags = good[:, 0] if sz == 1 else np.sqrt((good * good).sum(axis=1))
            stats = f"min={mags.min():.3f}, max={mags.max():.3f}, avg={mags.mean():.3f}" if mags.size else "no finite values"
            err = (f" [🚨 {bad_nan} NaNs!]" if bad_nan else "") + (f" [⚠️ {bad_inf} Infs!]" if bad_inf else "")
            kind = ("int" if dt == hou.attribData.Int else "float") if sz == 1 else ("vector" if sz == 3 else f"{dt.name().lower()}[{sz}]")
            label = "magnitude " if sz > 1 else ""
            lines.append(f"  @{name} ({kind}): {label}{stats}{err}")
    return "\n".join(lines)

def toggle_viewport_visualizer(node: hou.Node, vis_type: str, attr_name: str, enable: bool):
    """Configures a Viewport Visualizer for vector or heatmap inspection."""
    try:
        if not hasattr(hou, "viewportVisualizers"):
            return
        category = hou.viewportVisualizerCategory.Node
        vis_list = hou.viewportVisualizers.visualizers(category, node=node)
        target_vis = None
        target_type = "vis_vector" if vis_type == "vector" else "vis_color"
        for v in vis_list:
            if v.type().name() == target_type:
                target_vis = v
                break

        if not target_vis and enable:
            vis_type_obj = hou.viewportVisualizers.type(target_type)
            if vis_type_obj:
                target_vis = hou.viewportVisualizers.createVisualizer(vis_type_obj, category, node=node)

        if target_vis:
            if vis_type == "vector":
                target_vis.setParm("attrib", attr_name)
                target_vis.setParm("length", 0.5)
            else:
                target_vis.setParm("attrib", attr_name)
                target_vis.setParm("class", 0)  # point
            target_vis.setIsActive(enable)
            
        force_refresh_wrangle(node)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Node Parameter Setup (v4.0 — Clean & Focused)
# ---------------------------------------------------------------------------

def setup_ai_parameters(node: hou.Node, force: bool = False) -> bool:
    if not node.type().name().endswith("wrangle"):
        if hou.isUIAvailable():
            hou.ui.displayMessage("Target node must be an Attribute / Volume / POP Wrangle.", severity=hou.severityType.Warning)
        return False

    ptg = node.parmTemplateGroup()
    has_old_layout = (
        ptg.find("ai_refine") is not None or
        ptg.find("ai_vis_vector_toggle") is not None or
        ptg.find("ai_optimize") is not None or
        ptg.find("ai_explain") is not None
    )
    if not force and not has_old_layout and ptg.find("ai_generate") and ptg.find("ai_folder") and ptg.find("ai_use_rag") and ptg.find("ai_model_select"):
        return True

    if has_old_layout or force:
        if ptg.find("ai_folder"):
            try:
                ptg.remove("ai_folder")
                node.setParmTemplateGroup(ptg)
                ptg = node.parmTemplateGroup()
            except Exception:
                pass

    _known_base_parms = {
        "snippet", "group", "grouptype", "class", "exportlist",
        "autobind", "bindings", "groupautobind", "groupbindings",
        "vex_cwdpath", "vex_outputmask", "vex_updatenmls",
        "vex_matchattrib", "vex_inplace", "vex_selectiongroup",
        "vex_precision", "vex_numcount", "vex_threadjobsize",
        "vex_strict", "vex_strictvariables", "ai_spare_parms",
    }

    # Strip stale spare parms and any existing AI folders/parms for a clean rebuild
    for folder_name in (
        "ai_folder", "ai_folder2", "ai_tabs", "ai_history_tab", "ai_tools_tab", "ai_thought_tab",
        "ai_history_folder", "ai_advanced_folder", "ai_thought_folder", "folder_snip_a", "folder_snip_b"
    ):
        existing_folder = ptg.find(folder_name)
        if existing_folder:
            try:
                ptg.remove(existing_folder)
            except Exception:
                pass

    # Only remove stale AI-layout parms (all prefixed "ai_"). Anything else - generated sliders inside
    # ai_spare_parms, the user's own spare parms, the native bindings multiparm - is left untouched.
    spare_folder = ptg.find("ai_spare_parms")
    generated = {pt.name() for pt in spare_folder.parmTemplates()} if spare_folder else set()
    for e in list(ptg.entriesWithoutFolders()):
        name = e.name()
        if name.startswith("ai_") and name != "ai_spare_parms" and name not in generated:
            try:
                ptg.remove(e)
            except Exception:
                pass

    # =========================================================================
    # MAIN PANEL — flat Simple folder (no tabs, no clutter)
    # =========================================================================
    ai_folder = hou.FolderParmTemplate(
        "ai_folder", "AI VEX Copilot",
        folder_type=hou.folderType.Simple
    )

    # ── 1. Prompt ─────────────────────────────────────────────────────────────
    prompt_parm = hou.StringParmTemplate(
        name="ai_prompt",
        label="Prompt",
        num_components=1,
        default_value=[""],
        string_type=hou.stringParmType.Regular,
        help=(
            "Describe what you want in plain English.\n\n"
            "Examples:\n"
            "• 'Displace points along normals using noise'\n"
            "• 'Color points by height with a ramp'\n"
            "• 'Scatter pscale randomly between 0.01 and 0.1'\n\n"
            "Supports VEX attributes (@P, @N, @Cd, @v, @pscale), "
            "UI channels (chf, chv, chramp), and natural language task descriptions."
        )
    )
    prompt_parm.setTags({"multiline": "1"})

    # ── 2. Action Button & Deep Reasoning (unified single row) ────────────────
    gen_btn = hou.ButtonParmTemplate(
        name="ai_generate",
        label="✦ Generate",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_generate_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Generate VEX from your prompt. Automatically generates fresh, refines existing code, optimizes for SIMD, or adds UI sliders based on your prompt."
    )
    gen_btn.setJoinWithNext(True)

    reasoning_parm = hou.ToggleParmTemplate(
        name="ai_reasoning_mode",
        label="Deep Reasoning",
        default_value=False,
        help=(
            "Deep Reasoning Mode: the AI thinks step-by-step before writing code. "
            "Turn on for complex algorithms, custom physics, spatial math, or multi-input transfer. "
            "Turn off (Turbo) for instant interactive generation."
        )
    )

    # ── 3. Status ─────────────────────────────────────────────────────────────
    status_parm = hou.StringParmTemplate(
        name="ai_status",
        label="",
        num_components=1,
        default_value=["Ready — type a prompt and press Generate."],
        string_type=hou.stringParmType.Regular,
        help="Shows the current AI engine status, compile result, and timing."
    )
    status_parm.setTags({"editable": "0"})

    sep_top = hou.SeparatorParmTemplate("sep_top")

    # ── 4. Presets (inline row) ───────────────────────────────────────────────
    preset_items = list(_FX_PRESETS.keys())
    preset_labels = [_FX_PRESETS[k]["label"] for k in preset_items]
    preset_menu_script = (
        "import houdini_ai_wrangle\n"
        "items = []\n"
        "for k, v in houdini_ai_wrangle._FX_PRESETS.items():\n"
        "    items.extend([k, v['label']])\n"
        "return items"
    )
    preset_menu = hou.MenuParmTemplate(
        name="ai_preset_menu",
        label="Preset",
        menu_items=preset_items,
        menu_labels=preset_labels,
        item_generator_script=preset_menu_script,
        item_generator_script_language=hou.scriptLanguage.Python,
        help="Choose a built-in FX recipe to load as your starting point."
    )
    preset_menu.setJoinWithNext(True)

    load_preset_btn = hou.ButtonParmTemplate(
        name="ai_load_preset",
        label="Load",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_load_preset_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Load the selected preset into the VEX snippet and cook immediately."
    )

    sep_pre_hist = hou.SeparatorParmTemplate("sep_pre_hist")

    # ── 5. History & Variants (collapsible folder) ───────────────────────────
    history_folder = hou.FolderParmTemplate(
        name="ai_history_folder",
        label="History",
        folder_type=hou.folderType.Collapsible
    )

    variant_parm = hou.MenuParmTemplate(
        name="ai_variant",
        label="Active Variant",
        menu_items=("0", "1"),
        menu_labels=("Variant A", "Variant B"),
        default_value=0,
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_variant_changed(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Switch active VEX code between Variant A and Variant B."
    )
    variant_parm.setJoinWithNext(True)

    toggle_ab_btn = hou.ButtonParmTemplate(
        name="ai_toggle_ab",
        label="⇄ Swap",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_toggle_variants_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Quickly swap between Variant A and Variant B."
    )

    store_a_btn = hou.ButtonParmTemplate(
        name="ai_store_a",
        label="📌 Set as A",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_store_variant_a_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Save current code into Variant A."
    )
    store_a_btn.setJoinWithNext(True)

    store_b_btn = hou.ButtonParmTemplate(
        name="ai_store_b",
        label="📌 Set as B",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_store_variant_b_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Save current code into Variant B."
    )

    sep_hist_inner = hou.SeparatorParmTemplate("sep_hist_inner")

    prev_btn = hou.ButtonParmTemplate(
        name="ai_prev_version",
        label="◀ Prev",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_prev_version_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Roll back to previous generated VEX version in the history stack."
    )
    prev_btn.setJoinWithNext(True)

    version_info_parm = hou.StringParmTemplate(
        name="ai_version_info",
        label="Version",
        num_components=1,
        default_value=["—"],
        string_type=hou.stringParmType.Regular,
        help="Current version / total versions and timestamp."
    )
    version_info_parm.setTags({"editable": "0"})
    version_info_parm.setJoinWithNext(True)

    next_btn = hou.ButtonParmTemplate(
        name="ai_next_version",
        label="Next ▶",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_next_version_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Step forward to next generated VEX version in the history stack."
    )

    history_folder.addParmTemplate(variant_parm)
    history_folder.addParmTemplate(toggle_ab_btn)
    history_folder.addParmTemplate(store_a_btn)
    history_folder.addParmTemplate(store_b_btn)
    history_folder.addParmTemplate(sep_hist_inner)
    history_folder.addParmTemplate(prev_btn)
    history_folder.addParmTemplate(version_info_parm)
    history_folder.addParmTemplate(next_btn)

    # ── 6. Advanced Options (collapsible folder) ──────────────────────────────
    adv_folder = hou.FolderParmTemplate(
        name="ai_advanced_folder",
        label="Advanced Options",
        folder_type=hou.folderType.Collapsible
    )

    autodetect_parm = hou.ToggleParmTemplate(
        name="ai_autodetect",
        label="Auto-Detect Class",
        default_value=True,
        help="Automatically infers wrangle execution class (Point, Primitive, Detail, Vertex)."
    )

    sep_adv2 = hou.SeparatorParmTemplate("sep_adv2")

    sanitize_btn = hou.ButtonParmTemplate(
        name="ai_sanitize_guards",
        label="🛡 Sanitize",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_sanitize_guards_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Inject safety guards into VEX."
    )
    sanitize_btn.setJoinWithNext(True)

    stats_btn = hou.ButtonParmTemplate(
        name="ai_inspect_stats",
        label="📊 Stats",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_inspect_stats_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Inspect attribute statistics for upstream geometry."
    )
    stats_btn.setJoinWithNext(True)

    help_btn = hou.ButtonParmTemplate(
        name="ai_generate_help",
        label="📝 Help Card",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_generate_help_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Generate SideFX-style documentation and debug card (view, select, and 1-click copy prompt, VEX, parameters, and inputs)."
    )
    help_btn.setJoinWithNext(True)

    export_btn = hou.ButtonParmTemplate(
        name="ai_export_header",
        label="💾 Export .h",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_export_header_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Export VEX code as .h header."
    )

    sep_adv3 = hou.SeparatorParmTemplate("sep_adv3")

    model_menu_script = (
        "import houdini_ai_wrangle\n"
        "return houdini_ai_wrangle.get_available_models_menu_items()\n"
    )
    # String menu: stores the model file name, so adding models later never changes a saved choice.
    model_select_parm = hou.StringParmTemplate(
        "ai_model_select", "AI Model", 1,
        default_value=("auto",),
        menu_type=hou.menuType.Normal,
        item_generator_script=model_menu_script,
        item_generator_script_language=hou.scriptLanguage.Python,
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_model_select_changed(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Model weights file from models/. 'Auto' uses the newest fine-tuned model."
    )
    model_select_parm.setJoinWithNext(True)

    switch_model_btn = hou.ButtonParmTemplate(
        name="ai_switch_model",
        label="Switch Model",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_switch_model_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Switch and reload the embedded local inference engine with the selected model."
    )

    custom_model_parm = hou.StringParmTemplate(
        name="ai_custom_model_path",
        label="Custom Model File",
        num_components=1,
        default_value=[""],
        string_type=hou.stringParmType.FileReference,
        help="Absolute path to a custom .gguf or .dat model weights file on disk."
    )
    custom_model_parm.setConditional(
        hou.parmCondType.HideWhen, "{ ai_model_select != custom }"
    )

    model_info_parm = hou.StringParmTemplate(
        name="ai_model_info",
        label="Active Engine",
        num_components=1,
        default_value=[get_active_ai_model_display_string()],
        string_type=hou.stringParmType.Regular,
        help="Active AI model loaded and serving in embedded inference engine."
    )
    model_info_parm.setTags({"editable": "0"})

    use_rag_parm = hou.ToggleParmTemplate(
        name="ai_use_rag",
        label="SideFX Micro-RAG",
        default_value=True,
        help="When enabled, injects official SideFX VEX function signatures and architectural reference patterns into the prompt. Turn off to test pure neural model weights."
    )

    candidates_parm = hou.IntParmTemplate(
        "ai_num_candidates", "AI Candidates", 1, default_value=(DEFAULT_CANDIDATES,), min=1, max=8,
        min_is_strict=True, max_is_strict=True,
        help="Answers generated for a new snippet; each is cooked on this node and the one most candidates "
             "agree on is kept (1 = fastest).")

    adv_folder.addParmTemplate(autodetect_parm)
    adv_folder.addParmTemplate(use_rag_parm)
    adv_folder.addParmTemplate(candidates_parm)
    adv_folder.addParmTemplate(sep_adv2)
    adv_folder.addParmTemplate(sanitize_btn)
    adv_folder.addParmTemplate(stats_btn)
    adv_folder.addParmTemplate(help_btn)
    adv_folder.addParmTemplate(export_btn)
    adv_folder.addParmTemplate(sep_adv3)
    adv_folder.addParmTemplate(model_select_parm)
    adv_folder.addParmTemplate(switch_model_btn)
    adv_folder.addParmTemplate(custom_model_parm)
    adv_folder.addParmTemplate(model_info_parm)

    # ── 7. Reasoning Trace (collapsible folder) ───────────────────────────────
    thought_folder = hou.FolderParmTemplate(
        name="ai_thought_folder",
        label="Reasoning Trace",
        folder_type=hou.folderType.Collapsible
    )

    thought_parm = hou.StringParmTemplate(
        name="ai_thought_trace",
        label="Trace",
        num_components=1,
        default_value=["No reasoning trace yet. Enable Deep Reasoning and Generate."],
        string_type=hou.stringParmType.Regular,
        tags={"editor": "1", "multiline": "1"},
        help="Chain-of-Thought reasoning from the AI."
    )
    thought_folder.addParmTemplate(thought_parm)

    # ── 8. Hidden background data parms ──────────────────────────────────────
    snip_a = hou.StringParmTemplate(
        name="ai_snippet_a", label="Variant A",
        num_components=1, default_value=[""],
        string_type=hou.stringParmType.Regular,
    )
    snip_a.setTags({"hide": "1"})

    snip_b = hou.StringParmTemplate(
        name="ai_snippet_b", label="Variant B",
        num_components=1, default_value=[""],
        string_type=hou.stringParmType.Regular,
    )
    snip_b.setTags({"hide": "1"})

    history_json_parm = hou.StringParmTemplate(
        name="ai_history_json",
        label="History Data",
        num_components=1,
        default_value=["[]"],
        string_type=hou.stringParmType.Regular,
    )
    history_json_parm.setTags({"hide": "1"})

    perf_parm = hou.StringParmTemplate(
        name="ai_perf",
        label="Cook Benchmark",
        num_components=1,
        default_value=["—"],
        string_type=hou.stringParmType.Regular,
    )
    perf_parm.setTags({"hide": "1"})

    # Assemble panel
    ai_folder.addParmTemplate(prompt_parm)
    ai_folder.addParmTemplate(gen_btn)
    ai_folder.addParmTemplate(reasoning_parm)
    ai_folder.addParmTemplate(status_parm)
    ai_folder.addParmTemplate(sep_top)
    ai_folder.addParmTemplate(preset_menu)
    ai_folder.addParmTemplate(load_preset_btn)
    ai_folder.addParmTemplate(sep_pre_hist)
    ai_folder.addParmTemplate(history_folder)
    ai_folder.addParmTemplate(adv_folder)
    ai_folder.addParmTemplate(thought_folder)
    ai_folder.addParmTemplate(snip_a)
    ai_folder.addParmTemplate(snip_b)
    ai_folder.addParmTemplate(history_json_parm)
    ai_folder.addParmTemplate(perf_parm)

    snippet_parm_tmpl = ptg.find("snippet")
    if snippet_parm_tmpl:
        ptg.insertBefore(snippet_parm_tmpl, ai_folder)
    else:
        ptg.append(ai_folder)

    node.setParmTemplateGroup(ptg)
    return True

# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def _extract_node(kwargs) -> hou.Node | None:
    if isinstance(kwargs, hou.Node):
        return kwargs
    if isinstance(kwargs, dict):
        return kwargs.get("node") or (kwargs.get("parm").node() if kwargs.get("parm") else None)
    if hasattr(hou, "pwd"):
        pwd = hou.pwd()
        if isinstance(pwd, hou.Node):
            return pwd
    return None


DEFAULT_CANDIDATES = 3


def _num_candidates(node=None) -> int:
    """How many answers to generate for a new snippet (AI Candidates parm, else env, else 3)."""
    try:
        p = node.parm("ai_num_candidates") if node is not None else None
        if p is not None:
            return max(1, min(8, int(p.eval())))
    except Exception:
        pass
    try:
        return max(1, min(8, int(os.environ.get("AI_WRANGLE_CANDIDATES", DEFAULT_CANDIDATES))))
    except ValueError:
        return DEFAULT_CANDIDATES


# The exact prompt format the fine-tuned models were trained on (see ai_model_training/ and
# benchmarks/heldout_semantic/run_eval.py). The plugin's long prompt (geometry context, RAG examples, API
# rules) is out of that distribution and can pull a fine-tune back to verbose base-model habits.
TRAINING_SYSTEM_PROMPT = ("You are an expert SideFX Houdini VEX programmer and technical director. "
                          "Write pure VEX code without explanation or markdown formatting.")


def generate_vex_training_format(task: str, context: str = "point wrangle", temperature: float = 0.0,
                                 seed: int = 0) -> tuple[str, str]:
    """One answer in the training prompt format: no geometry context, no RAG, chat-template defaults."""
    ctx = context.strip()
    if ctx.startswith("lop") and "attribute" not in ctx:
        ctx = "lop attribute wrangle"
    if not ctx.endswith("wrangle"):
        ctx += " wrangle"
    return query_llm(f"Context: {ctx}.\nTask: {task}", temperature=temperature, seed=seed,
                     system_prompt=TRAINING_SYSTEM_PROMPT, template_kwargs={})


def _generate_candidates(task: str, context_str: str, geo_context: str, enable_rag, first_code: str, n: int) -> list[str]:
    """first_code (the normal low-temperature answer), then one greedy answer in the training prompt
    format, then sampled alternatives, n in total. Cancelling (Esc) during the extra answers keeps
    whatever was generated so far."""
    out = [first_code]
    for k in range(1, n):
        try:
            if k == 1:
                _, extra = generate_vex_training_format(task, context_str)
            else:
                _, extra = generate_vex(task, context=context_str, geo_context=geo_context, reasoning_mode=False,
                                        enable_rag=enable_rag, temperature=0.7, seed=1000 + k)
        except GenerationCancelled:
            break
        except Exception:
            continue
        if extra and extra.strip():
            out.append(extra)
    return out


def _geometry_fingerprint(geo) -> str:
    """Hash of what a snippet produced: element counts, attribute names/types and (rounded) values."""
    import hashlib
    import numpy as np

    h = hashlib.sha1()
    try:
        nvtx = int(geo.intrinsicValue("vertexcount"))
    except Exception:
        nvtx = -1
    h.update(f"{_point_count(geo)}|{_prim_count(geo)}|{nvtx}".encode())
    for kind, attribs in (("pt", geo.pointAttribs()), ("pr", geo.primAttribs()), ("vx", geo.vertexAttribs()), ("dt", geo.globalAttribs())):
        for a in sorted(attribs, key=lambda x: x.name()):
            h.update(f"{kind}:{a.name()}:{a.dataType()}:{a.size()}:{a.isArrayType()}".encode())
            try:
                if kind in ("pt", "pr") and not a.isArrayType():
                    if a.dataType() == hou.attribData.String:
                        vals = geo.pointStringAttribValues(a.name()) if kind == "pt" else geo.primStringAttribValues(a.name())
                        h.update("|".join(vals).encode("utf-8"))
                    else:
                        arr = _float_attrib_array(geo, a)
                        if arr is not None:
                            h.update(np.round(arr, 3).tobytes())
                elif kind == "dt":
                    h.update(repr(geo.attribValue(a.name())).encode())
            except Exception:
                pass
    for g in sorted(x.name() for x in geo.pointGroups()):
        h.update(f"g:{g}".encode())
    return h.hexdigest()


def _choose_by_execution(node, codes: list[str]) -> tuple[str, str]:
    """Execution-based self-consistency: compile + cook every candidate on this node and return the
    one whose output geometry the most candidates agree on (ties -> earliest, i.e. the low-temperature
    answer). Candidates that do not compile are skipped; if none compile, the first is returned so the
    normal repair path can work on it."""
    groups: dict[str, list[int]] = {}
    compiled = 0
    for i, code in enumerate(codes):
        if not re.search(r"[;{}]", code or ""):
            continue
        ok, _ = try_apply_snippet(node, code)
        if not ok:
            continue
        compiled += 1
        try:
            fp = _geometry_fingerprint(node.geometry())
        except Exception:
            fp = f"unhashable-{i}"
        groups.setdefault(fp, []).append(i)
    if not groups:
        return codes[0], f"0/{len(codes)} candidates compiled"
    best = max(groups.values(), key=lambda idx: (len(idx), -idx[0]))
    return codes[best[0]], f"candidate {best[0] + 1}/{len(codes)}: {compiled} compiled, {len(best)} agreed"


def on_generate_clicked(kwargs):
    """Generate / refine button. Everything it changes (Run Over class, snippet, generated sliders,
    history) is one undo step."""
    node = _extract_node(kwargs)
    prompt = node.parm("ai_prompt").eval().strip()[:30] if node and node.parm("ai_prompt") else ""
    with hou.undos.group(f"AI VEX: {prompt}"):
        _on_generate_impl(kwargs)


def _on_generate_impl(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return

    prompt_parm = node.parm("ai_prompt")
    autodetect_parm = node.parm("ai_autodetect")
    reasoning_parm = node.parm("ai_reasoning_mode")
    rag_parm = node.parm("ai_use_rag")
    enable_rag = bool(rag_parm.eval()) if rag_parm else (os.getenv("AI_WRANGLE_ENABLE_RAG", "1") != "0")
    thought_parm = node.parm("ai_thought_trace")
    status_parm = _get_status_parm(node)
    perf_parm = node.parm("ai_perf")
    model_info_parm = node.parm("ai_model_info")
    class_parm = node.parm("class")
    snippet_parm = node.parm("snippet")

    if prompt_parm is None or not prompt_parm.eval().strip():
        if hou.isUIAvailable():
            hou.ui.setStatusMessage("Please enter an AI prompt description first.", severity=hou.severityType.Warning)
        if status_parm:
            status_parm.set("Enter a prompt first.")
        return

    target_model_path = resolve_selected_model_path(node)
    ensure_embedded_engine(target_model_path)
    if model_info_parm:
        model_info_parm.set(get_active_ai_model_display_string())

    task = prompt_parm.eval().strip()
    is_reasoning = bool(reasoning_parm and reasoning_parm.eval())
    geo_context = introspect_geometry(node)

    CLASS_TOKEN_MAP = {0: "detail", 1: "primitive", 2: "point", 3: "vertex"}

    if autodetect_parm and autodetect_parm.eval() and class_parm:
        detected_idx, detected_str = auto_detect_context(task, node=node)
        token_name = CLASS_TOKEN_MAP.get(detected_idx, "point")
        try:
            class_parm.set(token_name)
        except Exception:
            class_parm.set(detected_idx)
        context_str = detected_str
    else:
        context_val = class_parm.eval() if class_parm else "point"
        if isinstance(context_val, int):
            context_str = CLASS_MAP.get(context_val, "point wrangle")
        else:
            context_str = f"{context_val} wrangle" if not str(context_val).endswith("wrangle") else str(context_val)

    snippet_parm = node.parm("snippet")
    existing_code = snippet_parm.eval().strip() if snippet_parm else ""

    EDIT_KEYWORDS = [
        "fix", "repair", "broken", "bug", "wrong", "doesn't work", "failing",
        "modify", "tweak", "update existing", "instead of", "adjust", "replace existing",
        "refine", "optimize", "speed up", "make faster",
        "document code", "inline comment", "docstring",
        "shield", "zero-division",
    ]
    RESET_KEYWORDS = ["from scratch", "reset", "fresh", "brand new", "replace entirely", "clear existing", "ignore existing", "create", "generate", "build", "align", "displace", "sample"]

    is_edit_intent = bool(existing_code) and (
        bool(kwargs.get("force_refine"))
        or (any(k in task.lower() for k in EDIT_KEYWORDS) and not any(r in task.lower() for r in RESET_KEYWORDS))
    )

    if not is_edit_intent:
        action_label = "Generation"
    elif any(k in task.lower() for k in ["optimize", "optimization", "speed up", "make faster", "simd", "parallel", "hoist"]):
        action_label = "Optimization"
    elif any(k in task.lower() for k in ["document", "explain", "comment"]):
        action_label = "Documentation"
    elif any(k in task.lower() for k in ["parameter", "channel", "slider", "expose", "chf", "chi", "chv", "chramp"]):
        action_label = "Parameterization"
    elif any(k in task.lower() for k in ["fix", "repair", "error", "broken", "bug", "wrong", "doesn't work"]):
        action_label = "Repair"
    else:
        action_label = "Refinement"

    status_msg = "Deep Reasoning (Thinking & Planning)..." if is_reasoning else f"{action_label} VEX..."
    with hou.undos.group(f"AI VEX {action_label}: {task[:30]}"):
        try:
            if hou.isUIAvailable():
                hou.ui.setStatusMessage(status_msg, severity=hou.severityType.Message)
            t0 = time.time()
            if is_edit_intent:
                thought_trace, vex_code = refine_vex(task, existing_code, context=context_str, geo_context=geo_context, reasoning_mode=is_reasoning, enable_rag=enable_rag)
            else:
                thought_trace, vex_code = generate_vex(task, context=context_str, geo_context=geo_context, reasoning_mode=is_reasoning, enable_rag=enable_rag)
            candidates = [vex_code]
            n_cand = _num_candidates(node)
            if vex_code and n_cand > 1 and not is_edit_intent and not is_reasoning:
                candidates = _generate_candidates(task, context_str, geo_context, enable_rag, vex_code, n_cand)
            gen_time = time.time() - t0
        except Exception as e:
            if status_parm:
                status_parm.set(f"{action_label} Failed: {e}")
            if hou.isUIAvailable():
                hou.ui.setStatusMessage(f"AI {action_label} Failed: {e}", severity=hou.severityType.Error)
            return

        if thought_parm:
            thought_parm.set(thought_trace if thought_trace else "Turbo mode: direct execution (no thought trace).")

        if not vex_code:
            if status_parm:
                status_parm.set("Error: Model returned empty VEX code.")
            return

        # 1. Light, semantics-preserving cleanup (heavy regex repairs only run if Houdini rejects the code)
        vex_code = _light_vex_cleanup(vex_code)

        # Context Alignment Guard: if code clearly targets primitives (@primnum/removeprim without pointprimitives),
        # ensure the node runs over primitives so @primnum does not evaluate to 0!
        if class_parm:
            curr_class = class_parm.eval()
            if curr_class == 2 and ("@primnum" in vex_code or "removeprim(" in vex_code) and "pointprimitives" not in vex_code:
                try:
                    class_parm.set("primitive")
                except Exception:
                    class_parm.set(1)
            elif curr_class == 1 and ("@ptnum" in vex_code and "@primnum" not in vex_code and "removeprim" not in vex_code):
                if not any(k in task.lower() for k in ["face", "faces", "prim", "prims", "primitive", "primitives", "polygon", "polygons"]):
                    try:
                        class_parm.set("point")
                    except Exception:
                        class_parm.set(2)
            elif curr_class in (0, "detail") and ("@P" in vex_code or "@ptnum" in vex_code or "@N" in vex_code) and "addpoint" not in vex_code and "addprim" not in vex_code and "setdetailattrib" not in vex_code:
                try:
                    in0 = node.input(0)
                    if in0 and in0.geometry() and _point_count(in0.geometry()) > 0:
                        class_parm.set("point")
                except Exception:
                    pass

        # 2. Several candidates: keep the one most candidates agree on when executed
        pick_note = ""
        if len(candidates) > 1:
            vex_code, pick_note = _choose_by_execution(node, [_light_vex_cleanup(c) for c in candidates])

        # 3. Compile-first application + compiler-feedback self-repair
        vex_code, success, error = _apply_generated_vex(node, task, context_str, vex_code, geo_context)
        if success and pick_note and thought_parm:
            thought_parm.set(f"Best-of-{len(candidates)}: {pick_note}\n\n" + (thought_parm.eval() or ""))

        # Re-fetch parm references after try_apply_snippet may have updated the PTG
        status_parm = _get_status_parm(node)
        perf_parm = node.parm("ai_perf")
        snippet_parm = node.parm("snippet")

        if success:
            cook_ms, npts, throughput = profile_node_cook(node)
            push_to_history_stack(node, task, vex_code, context_str, cook_ms=cook_ms, thought=thought_trace)

            # Sync active variant slot
            variant_parm = node.parm("ai_variant")
            if variant_parm:
                slot = "ai_snippet_b" if variant_parm.eval() == 1 else "ai_snippet_a"
                if node.parm(slot):
                    node.parm(slot).set(vex_code)

            # Geometry health scan for NaNs/Infs
            healthy, health_msg = scan_geometry_health(node)

            mode_label = "Deep Reasoning" if is_reasoning else "Turbo"
            if status_parm:
                action_text = f"{action_label} [{mode_label}]" if is_edit_intent else f"Compiled [{mode_label}]"
                if healthy:
                    status_parm.set(f"{action_text} ({gen_time:.2f}s).")
                else:
                    status_parm.set(f"{action_text} ({gen_time:.2f}s). {health_msg}")
            if perf_parm:
                perf_parm.set(f"Cook: {cook_ms:.2f}ms ({npts:,} pts @ {throughput:.1f} Mpts/s)")
            if hou.isUIAvailable():
                hou.ui.setStatusMessage("AI VEX compiled and applied successfully.", severity=hou.severityType.Message)
        else:
            _report_failed_generation(node, vex_code, error, "Generation")


def _report_failed_generation(node, failed_code: str, error: str | None, action: str) -> None:
    """Keep the user's last working snippet; show the error and park the failed attempt in the
    Reasoning Trace so it can still be inspected or copied."""
    lines = [l.strip() for l in (error or "").splitlines() if l.strip() and "invalid source" not in l.lower()]
    first = lines[0] if lines else "the generated code did not compile"
    status = _get_status_parm(node)
    if status:
        status.set(f"{action} failed: {first} (your previous code was kept; failed attempt is in Reasoning Trace)")
    trace = node.parm("ai_thought_trace")
    if trace:
        trace.set(f"--- Failed attempt (not applied) ---\n{failed_code}\n\n--- Houdini error ---\n{error or ''}")
    if hou.isUIAvailable():
        hou.ui.setStatusMessage(f"AI VEX {action.lower()} failed: {first}", severity=hou.severityType.Warning)


def on_refine_clicked(kwargs):
    """Edit the existing snippet with the prompt as a refinement instruction (same pipeline as
    Generate: RAG, compile-first apply, compiler-feedback repair, history, undo group)."""
    on_generate_clicked(dict(kwargs, force_refine=True))


def on_optimize_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    snippet_parm = node.parm("snippet")
    status_parm = _get_status_parm(node)
    perf_parm = node.parm("ai_perf")
    class_parm = node.parm("class")

    existing_code = snippet_parm.eval().strip() if snippet_parm else ""
    if not existing_code:
        if hou.isUIAvailable():
            hou.ui.displayMessage("No VEX code to optimize.", severity=hou.severityType.Warning)
        return

    context_idx = class_parm.eval() if class_parm else 2
    context_str = CLASS_MAP.get(context_idx, "point wrangle")

    with hou.undos.group("AI VEX SIMD Optimization"):
        with hou.InterruptableOperation("Optimizing for SIMD execution...", open_interrupt_dialog=hou.isUIAvailable()):
            try:
                t0 = time.time()
                optimized_code = optimize_vex_code(existing_code, context=context_str)
                gen_time = time.time() - t0
            except Exception as e:
                if hou.isUIAvailable():
                    hou.ui.displayMessage(f"Optimization Failed:\n{e}", severity=hou.severityType.Error)
                return

        success, error = try_apply_snippet(node, optimized_code)
        
        # Re-fetch parm references
        status_parm = _get_status_parm(node)
        perf_parm = node.parm("ai_perf")
        
        if success:
            cook_ms, npts, throughput = profile_node_cook(node)
            push_to_history_stack(node, "SIMD Optimized", optimized_code, context_str, cook_ms=cook_ms)
            
            if status_parm:
                status_parm.set(f"Optimized for SIMD ({gen_time:.2f}s).")
            if perf_parm:
                perf_parm.set(f"Cook: {cook_ms:.2f}ms ({npts:,} pts @ {throughput:.1f} Mpts/s)")
            if hou.isUIAvailable():
                hou.ui.setStatusMessage("VEX code optimized for SIMD parallelism.", severity=hou.severityType.Message)


def on_explain_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    snippet_parm = node.parm("snippet")
    status_parm = _get_status_parm(node)
    class_parm = node.parm("class")

    existing_code = snippet_parm.eval().strip() if snippet_parm else ""
    if not existing_code:
        if hou.isUIAvailable():
            hou.ui.displayMessage("No VEX code to explain.", severity=hou.severityType.Warning)
        return

    context_idx = class_parm.eval() if class_parm else 2
    context_str = CLASS_MAP.get(context_idx, "point wrangle")

    with hou.undos.group("AI VEX Auto-Documentation"):
        with hou.InterruptableOperation("Adding inline math comments...", open_interrupt_dialog=hou.isUIAvailable()):
            try:
                doc_code = explain_and_document_vex(existing_code, context=context_str)
            except Exception as e:
                if hou.isUIAvailable():
                    hou.ui.displayMessage(f"Documentation Failed:\n{e}", severity=hou.severityType.Error)
                return

        success, error = try_apply_snippet(node, doc_code)
        if success:
            push_to_history_stack(node, "Auto-Documented", doc_code, context_str)
            if status_parm:
                status_parm.set("Code documented with inline math comments.")
            if hou.isUIAvailable():
                hou.ui.setStatusMessage("VEX code annotated with educational comments.", severity=hou.severityType.Message)


def on_prev_version_clicked(kwargs):
    node = _extract_node(kwargs)
    if node:
        navigate_history_version(node, direction=-1)


def on_next_version_clicked(kwargs):
    node = _extract_node(kwargs)
    if node:
        navigate_history_version(node, direction=+1)


def on_collapse_history_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    for p in ("ai_thought_folder", "ai_advanced_folder"):
        parm = node.parm(p)
        if parm:
            parm.set(0)


def on_expand_history_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    for p in ("ai_thought_folder", "ai_advanced_folder"):
        parm = node.parm(p)
        if parm:
            parm.set(1)


def on_load_preset_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    menu_parm = node.parm("ai_preset_menu")
    if not menu_parm:
        return
    preset_key = menu_parm.evalAsString()
    if preset_key not in _FX_PRESETS:
        keys = list(_FX_PRESETS.keys())
        idx = menu_parm.eval()
        preset_key = keys[idx] if 0 <= idx < len(keys) else keys[0]

    preset = _FX_PRESETS[preset_key]
    prompt_parm = node.parm("ai_prompt")
    snippet_parm = node.parm("snippet")
    class_parm = node.parm("class")
    status_parm = _get_status_parm(node)

    with hou.undos.group(f"Load AI Preset: {preset['label']}"):
        if prompt_parm:
            prompt_parm.set(preset["prompt"])
        if class_parm:
            try:
                class_parm.set(preset["context"])
            except Exception:
                pass
        if snippet_parm:
            snippet_parm.set(preset["code"])

        success, err = try_apply_snippet(node, preset["code"])
        if success:
            cook_ms, npts, throughput = profile_node_cook(node)
            push_to_history_stack(node, f"Preset: {preset['label']}", preset["code"], f"{preset['context']} wrangle", cook_ms=cook_ms)
            if status_parm:
                status_parm.set(f"Loaded Preset: {preset['label']}.")
            if hou.isUIAvailable():
                hou.ui.setStatusMessage(f"Loaded FX Preset: {preset['label']}.", severity=hou.severityType.Message)
        else:
            if status_parm:
                status_parm.set(f"Preset Warning: {err.splitlines()[0] if err else 'Compile warning'}")


def on_variant_changed(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    variant_parm = node.parm("ai_variant")
    if not variant_parm:
        return
    variant_idx = int(variant_parm.eval())
    snippet_parm = node.parm("snippet")
    if not snippet_parm:
        return

    snip_a = node.parm("ai_snippet_a")
    snip_b = node.parm("ai_snippet_b")
    curr_code = snippet_parm.eval()

    if variant_idx == 1:
        target_code = snip_b.eval() if snip_b else ""
        if not target_code.strip() and curr_code.strip():
            if snip_b:
                snip_b.set(curr_code)
            target_code = curr_code
    else:
        target_code = snip_a.eval() if snip_a else ""
        if not target_code.strip() and curr_code.strip():
            if snip_a:
                snip_a.set(curr_code)
            target_code = curr_code

    if target_code.strip():
        with hou.undos.group(f"AI VEX Variant {'B' if variant_idx == 1 else 'A'}"):
            saved = _snapshot_spare_values(node)
            snippet_parm.set(target_code)
            sync_spare_parameters(node, target_code)
            _restore_spare_values(node, saved)
        force_refresh_wrangle(node)
        status_parm = _get_status_parm(node)
        if status_parm:
            status_parm.set(f"Active Variant: {'Variant B' if variant_idx == 1 else 'Variant A'}.")


def on_store_variant_a_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    snippet_parm = node.parm("snippet")
    snip_a = node.parm("ai_snippet_a")
    if snippet_parm and snip_a:
        code = snippet_parm.eval()
        snip_a.set(code)
        if node.parm("ai_variant"):
            node.parm("ai_variant").set(0)
        status_parm = _get_status_parm(node)
        if status_parm:
            status_parm.set("Current code saved to Variant A ✅")
        if hou.isUIAvailable():
            hou.ui.setStatusMessage("Saved current code to Variant A.", severity=hou.severityType.Message)


def on_store_variant_b_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    snippet_parm = node.parm("snippet")
    snip_b = node.parm("ai_snippet_b")
    if snippet_parm and snip_b:
        code = snippet_parm.eval()
        snip_b.set(code)
        if node.parm("ai_variant"):
            node.parm("ai_variant").set(1)
        status_parm = _get_status_parm(node)
        if status_parm:
            status_parm.set("Current code saved to Variant B ✅")
        if hou.isUIAvailable():
            hou.ui.setStatusMessage("Saved current code to Variant B.", severity=hou.severityType.Message)


def on_toggle_variants_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    variant_parm = node.parm("ai_variant")
    if not variant_parm:
        return
    current_val = int(variant_parm.eval())
    new_val = 1 if current_val == 0 else 0
    variant_parm.set(new_val)
    on_variant_changed(kwargs)


def on_clear_history_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    if hou.isUIAvailable():
        if not hou.ui.displayConfirmation("Are you sure you want to clear all version history for this node?"):
            return
    hist_parm = _get_history_parm(node)
    if hist_parm:
        hist_parm.set("[]")
    info_parm = _get_info_parm(node)
    if info_parm:
        info_parm.set("—")
    status_parm = _get_status_parm(node)
    if status_parm:
        status_parm.set("Version history cleared.")


def on_copy_history_to_a_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    snippet_parm = node.parm("snippet")
    snip_a = node.parm("ai_snippet_a")
    if snippet_parm and snip_a:
        snip_a.set(snippet_parm.eval())
        status_parm = _get_status_parm(node)
        if status_parm:
            status_parm.set("Loaded version copied to Variant A ✅")


def on_copy_history_to_b_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    snippet_parm = node.parm("snippet")
    snip_b = node.parm("ai_snippet_b")
    if snippet_parm and snip_b:
        snip_b.set(snippet_parm.eval())
        status_parm = _get_status_parm(node)
        if status_parm:
            status_parm.set("Loaded version copied to Variant B ✅")


def on_fork_branch_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    parent = node.parent()
    if not parent:
        return

    with hou.undos.group("Fork AI Wrangle Variant"):
        curr_code = node.parm("snippet").eval() if node.parm("snippet") else ""

        # Always capture current snippet as Variant A
        snip_a_parm = node.parm("ai_snippet_a")
        if snip_a_parm and not snip_a_parm.eval().strip():
            snip_a_parm.set(curr_code)

        snip_a = snip_a_parm.eval() if snip_a_parm else curr_code
        snip_b_parm = node.parm("ai_snippet_b")
        snip_b = snip_b_parm.eval() if snip_b_parm else ""

        if not snip_b.strip():
            if hou.isUIAvailable():
                hou.ui.displayMessage(
                    "Variant A has been captured from the current snippet.\n\n"
                    "To complete the A/B fork:\n"
                    "1. Generate or Refine to create the second variant.\n"
                    "2. Press '🌿 Fork to Branch Node & Switch' again.\n\n"
                    "The fork will create a Switch SOP for live A/B comparison.",
                    severity=hou.severityType.Message
                )
            return

        # hou.Node has no copy(); duplicate the node (parms, inputs, spare parms) with copyNodesTo
        fork = hou.copyNodesTo((node,), parent)[0]
        fork.setName(f"{node.name()}_variantB", unique_name=True)
        for i, inp in enumerate(node.inputs()):
            if inp is not None:
                fork.setInput(i, inp)
        fork.parm("snippet").set(snip_b)
        if fork.parm("ai_variant"):
            fork.parm("ai_variant").set(1)
        sync_spare_parameters(fork, snip_b)

        switch = parent.createNode("switch", f"{node.name()}_compare_switch")
        switch.setInput(0, node)
        switch.setInput(1, fork)
        switch.moveToGoodPosition()
        fork.moveToGoodPosition()
        switch.setDisplayFlag(True)
        switch.setRenderFlag(True)

        if hou.isUIAvailable():
            hou.ui.setStatusMessage(f"Forked {node.name()} into {fork_name} with Switch SOP.", severity=hou.severityType.Message)


def on_sanitize_guards_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    snippet_parm = node.parm("snippet")
    status_parm = _get_status_parm(node)
    if not snippet_parm or not snippet_parm.eval().strip():
        if hou.isUIAvailable():
            hou.ui.displayMessage("No VEX code to sanitize.", severity=hou.severityType.Warning)
        return

    curr_code = snippet_parm.eval()
    sanitized = sanitize_nan_inf_vex(curr_code)
    with hou.undos.group("Sanitize VEX NaNs/Infs"):
        success, err = try_apply_snippet(node, sanitized)
        if success:
            push_to_history_stack(node, "Sanitized NaNs & Infs", sanitized, "wrangle")
            if status_parm:
                status_parm.set("🛡️ Applied defensive guards (clamp, sqrt, acos bounds).")
            if hou.isUIAvailable():
                hou.ui.setStatusMessage("VEX code sanitized with defensive math guards.", severity=hou.severityType.Message)
        else:
            if status_parm:
                status_parm.set(f"Sanitize Warning: {err.splitlines()[0] if err else ''}")


def on_inspect_stats_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    stats_text = inspect_attribute_statistics(node)
    if hou.isUIAvailable():
        hou.ui.displayMessage(stats_text, title=f"Attribute Statistics: {node.name()}", severity=hou.severityType.Message)
    else:
        print(stats_text)


def on_vis_vector_toggle(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    toggle_parm = node.parm("ai_vis_vector_toggle")
    attr_parm = node.parm("ai_vis_vector_attr")
    if toggle_parm and attr_parm:
        enable = bool(toggle_parm.eval())
        attr_name = attr_parm.eval().strip() or "v"
        toggle_viewport_visualizer(node, "vector", attr_name, enable)


def on_vis_color_toggle(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    toggle_parm = node.parm("ai_vis_color_toggle")
    attr_parm = node.parm("ai_vis_color_attr")
    if toggle_parm and attr_parm:
        enable = bool(toggle_parm.eval())
        attr_name = attr_parm.eval().strip() or "speed"
        toggle_viewport_visualizer(node, "color", attr_name, enable)


# ---------------------------------------------------------------------------
# Help Card & Debug Window
# ---------------------------------------------------------------------------

_help_card_dialog_singleton = None


class NodeHelpCardDialog(QtWidgets.QDialog if QtWidgets else object):
    """Modern Houdini-native PySide dialog for viewing, selecting, and copying Help Cards."""

    def __init__(self, node_name, doc_text, vex_code="", prompt="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"⚡ Help Card & Debug — {node_name}")
        self.resize(760, 600)
        self.setMinimumSize(540, 400)
        self.doc_text = doc_text
        self.vex_code = vex_code
        self.prompt = prompt

        if QtCore:
            self.setWindowFlags(self.windowFlags() | QtCore.Qt.Window)
        if hasattr(hou, "qt") and hasattr(hou.qt, "styleSheet"):
            self.setStyleSheet(hou.qt.styleSheet())

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Header bar
        hdr_layout = QtWidgets.QHBoxLayout()
        title_lbl = QtWidgets.QLabel(f"<b>📝 Node Documentation & Debug Card:</b> <code style='color:#ff9922;'>{node_name}</code>")
        title_lbl.setStyleSheet("font-size: 13px;")
        hdr_layout.addWidget(title_lbl)
        hdr_layout.addStretch()

        hint_lbl = QtWidgets.QLabel("Select text to copy, or use 1-click copy buttons below")
        hint_lbl.setStyleSheet("color: #888888; font-size: 10px; font-style: italic;")
        hdr_layout.addWidget(hint_lbl)
        layout.addLayout(hdr_layout)

        # Monospace Text Area
        self.editor = QtWidgets.QPlainTextEdit()
        self.editor.setPlainText(doc_text)
        self.editor.setReadOnly(True)
        self.editor.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        if QtGui:
            font = QtGui.QFont("Consolas", 10)
            font.setStyleHint(QtGui.QFont.Monospace)
            self.editor.setFont(font)
        self.editor.setStyleSheet(
            "background-color: #17171c; color: #ececf1; "
            "border: 1px solid #33333e; border-radius: 4px; padding: 8px;"
        )
        layout.addWidget(self.editor, stretch=1)

        # Status feedback line
        self.status_lbl = QtWidgets.QLabel("")
        self.status_lbl.setStyleSheet("color: #00ff88; font-size: 11px; font-weight: bold; min-height: 16px;")
        layout.addWidget(self.status_lbl)

        # Button row
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_copy_all = QtWidgets.QPushButton("📋 Copy Entire Card")
        self.btn_copy_all.setStyleSheet("font-weight: bold; padding: 6px 14px; background-color: #ff7700; color: #ffffff; border-radius: 4px;")
        self.btn_copy_all.clicked.connect(self._copy_all)
        btn_layout.addWidget(self.btn_copy_all)

        if vex_code.strip():
            self.btn_copy_vex = QtWidgets.QPushButton("⚡ Copy VEX Only")
            self.btn_copy_vex.setStyleSheet("padding: 6px 12px; background-color: #2e3846; color: #88ccff; border-radius: 4px;")
            self.btn_copy_vex.clicked.connect(self._copy_vex)
            btn_layout.addWidget(self.btn_copy_vex)

        if prompt.strip():
            self.btn_copy_prompt = QtWidgets.QPushButton("💬 Copy Prompt")
            self.btn_copy_prompt.setStyleSheet("padding: 6px 12px; background-color: #2c3330; color: #88ffaa; border-radius: 4px;")
            self.btn_copy_prompt.clicked.connect(self._copy_prompt)
            btn_layout.addWidget(self.btn_copy_prompt)

        btn_layout.addStretch()

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.setStyleSheet("padding: 6px 16px; border-radius: 4px;")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def update_content(self, node_name, doc_text, vex_code="", prompt=""):
        self.setWindowTitle(f"⚡ Help Card & Debug — {node_name}")
        self.doc_text = doc_text
        self.vex_code = vex_code
        self.prompt = prompt
        self.editor.setPlainText(doc_text)
        self.status_lbl.setText("🔄 Content updated from node.")

    def _copy_all(self):
        hou.ui.copyTextToClipboard(self.doc_text)
        self.status_lbl.setText("✅ Copied entire Help Card to clipboard!")
        hou.ui.setStatusMessage("Help Card copied to clipboard!", severity=hou.severityType.Message)

    def _copy_vex(self):
        if self.vex_code:
            hou.ui.copyTextToClipboard(self.vex_code)
            self.status_lbl.setText("✅ Copied VEX snippet to clipboard!")
            hou.ui.setStatusMessage("VEX snippet copied to clipboard!", severity=hou.severityType.Message)

    def _copy_prompt(self):
        if self.prompt:
            hou.ui.copyTextToClipboard(self.prompt)
            self.status_lbl.setText("✅ Copied Prompt to clipboard!")
            hou.ui.setStatusMessage("Prompt copied to clipboard!", severity=hou.severityType.Message)


def show_help_card_dialog(node_name, doc_text, vex_code="", prompt="") -> bool:
    """Displays or refreshes the non-modal NodeHelpCardDialog window."""
    global _help_card_dialog_singleton
    if not QtWidgets:
        return False
    try:
        parent = hou.qt.mainWindow() if hasattr(hou, "qt") and hasattr(hou.qt, "mainWindow") else None
        if _help_card_dialog_singleton is None or not _help_card_dialog_singleton.isVisible():
            _help_card_dialog_singleton = NodeHelpCardDialog(node_name, doc_text, vex_code, prompt, parent=parent)
        else:
            _help_card_dialog_singleton.update_content(node_name, doc_text, vex_code, prompt)
        _help_card_dialog_singleton.show()
        _help_card_dialog_singleton.raise_()
        _help_card_dialog_singleton.activateWindow()
        return True
    except Exception:
        return False


def on_generate_help_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    prompt = node.parm("ai_prompt").eval() if node.parm("ai_prompt") else "Procedural VEX Node"
    snippet = node.parm("snippet").eval() if node.parm("snippet") else ""
    class_name = node.parm("class").evalAsString() if node.parm("class") else "point"
    active_model = get_active_ai_model_display_string()
    channels = parse_vex_channels(snippet)

    # Inspect upstream inputs
    input_descs = []
    for i in range(4):
        inp = node.input(i)
        if inp:
            desc = f"Input {i}: Connected to `{inp.name()}` ({inp.type().description() or inp.type().name()})"
            try:
                geo = inp.geometry()
                if geo:
                    pt_count = _point_count(geo)
                    prim_count = _prim_count(geo)
                    attribs = [a.name() for a in geo.pointAttribs()]
                    geo_info = f" — [{pt_count} pts, {prim_count} prims"
                    if attribs:
                        geo_info += f", attribs: {', '.join(attribs[:6])}{'...' if len(attribs) > 6 else ''}"
                    geo_info += "]"
                    desc += geo_info
            except Exception:
                pass
            input_descs.append(desc)
        else:
            input_descs.append(f"Input {i}: (Not connected)")

    # Inspect interactive parameters and current evaluated values
    param_descs = []
    for ch_name, ch_type in channels.items():
        parm_tuple = node.parmTuple(ch_name)
        parm = node.parm(ch_name)
        val_str = ""
        if parm_tuple and len(parm_tuple) > 1:
            vals = tuple(round(v, 4) if isinstance(v, float) else v for v in parm_tuple.eval())
            val_str = f" = {vals}"
        elif parm:
            val = parm.eval()
            if isinstance(val, float):
                val_str = f" = {val:.4g}"
            else:
                val_str = f" = {val}"
        param_descs.append(f"  • {ch_name} ({ch_type}){val_str}")

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    doc_text = f"""================================================================================
⚡ AI ATTRIBUTE WRANGLE — NODE DEBUG & HELP CARD
================================================================================
Node:            {node.name()} ({node.path()})
Execution Class: {class_name.capitalize()} Wrangle
AI Model:        {active_model}
Timestamp:       {timestamp}

--------------------------------------------------------------------------------
📌 USER PROMPT
--------------------------------------------------------------------------------
{prompt}

--------------------------------------------------------------------------------
🔌 UPSTREAM INPUTS (0-3)
--------------------------------------------------------------------------------
{chr(10).join('  • ' + d for d in input_descs)}

--------------------------------------------------------------------------------
🎛️ INTERACTIVE PARAMETERS & VALUES
--------------------------------------------------------------------------------
{chr(10).join(param_descs) if param_descs else '  • No interactive channel parameters detected.'}

--------------------------------------------------------------------------------
📜 VEX SNIPPET
--------------------------------------------------------------------------------
{snippet if snippet.strip() else '// (Empty snippet)'}
================================================================================
"""

    if hou.isUIAvailable():
        shown = show_help_card_dialog(node.name(), doc_text, vex_code=snippet, prompt=prompt)
        if not shown:
            btn_idx = hou.ui.displayMessage(
                f"Help Card for {node.name()}:\n\n{doc_text}",
                buttons=("📋 Copy to Clipboard", "Close"),
                default_choice=0,
                close_choice=1,
                details=doc_text,
                details_label="Select / Copy Details",
                details_expanded=True,
                title=f"Documentation: {node.name()}",
                severity=hou.severityType.Message
            )
            if btn_idx == 0:
                hou.ui.copyTextToClipboard(doc_text)
                hou.ui.setStatusMessage("Help Card copied to clipboard!", severity=hou.severityType.Message)
    else:
        print(doc_text)


def on_export_header_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    snippet = node.parm("snippet").eval().strip() if node.parm("snippet") else ""
    if not snippet:
        if hou.isUIAvailable():
            hou.ui.displayMessage("No VEX code to export.", severity=hou.severityType.Warning)
        return

    if not hou.isUIAvailable() and not hasattr(hou, "ui"):
        return
    try:
        snippet_to_vex_function(snippet, "FUNC_PLACEHOLDER")
    except ValueError as exc:
        hou.ui.displayMessage(f"Cannot export this snippet as a function:\n{exc}", severity=hou.severityType.Warning)
        return

    default_name = re.sub(r'[^a-zA-Z0-9_]', '_', node.name().lower())
    button_idx, func_name = hou.ui.readInput(
        "Enter VEX Library Function Name (without .h):",
        buttons=("Export Header", "Cancel"),
        default_choice=0,
        initial_contents=f"ansv_{default_name}",
        title="Export to VEX Header"
    )
    if button_idx != 0 or not func_name.strip():
        return

    func_name = re.sub(r'[^a-zA-Z0-9_]', '_', func_name.strip())
    include_dir = os.path.join(hou.homeHoudiniDirectory(), "vex", "include")
    os.makedirs(include_dir, exist_ok=True)
    header_path = os.path.join(include_dir, f"{func_name}.h")
    if os.path.exists(header_path):
        if hou.ui.displayMessage(f"{header_path} already exists. Overwrite it?",
                                 buttons=("Overwrite", "Cancel"), default_choice=1,
                                 severity=hou.severityType.Warning) != 0:
            return

    header_body, call_line = snippet_to_vex_function(snippet, func_name)
    guard_name = f"__{func_name.upper()}_H__"
    header_content = (
        f"#ifndef {guard_name}\n#define {guard_name}\n\n"
        f"// Houdini AI VEX Library: {func_name}\n"
        f"// Generated from: {node.path()} on {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"// Attributes are passed in as arguments (VEX passes arguments by reference, so writes\n"
        f"// go back to the attributes). Use in any wrangle:\n"
        f"//     #include <{func_name}.h>\n"
        f"//     {call_line}\n\n"
        f"{header_body}\n\n#endif // {guard_name}\n"
    )
    try:
        with open(header_path, "w", encoding="utf-8") as f:
            f.write(header_content)
        include_code = f"#include <{func_name}.h>\n{call_line}"
        try:
            hou.ui.copyTextToClipboard(include_code)
        except Exception:
            pass
        hou.ui.displayMessage(
            f"Header exported:\n{header_path}\n\nUsage in any wrangle (copied to clipboard):\n{include_code}",
            title="VEX Header Exported", severity=hou.severityType.Message)
    except Exception as e:
        hou.ui.displayMessage(f"Failed to export header:\n{e}", severity=hou.severityType.Error)


_BINDING_TYPES = {"f": "float", "i": "int", "v": "vector", "s": "string", "p": "vector4", "u": "vector2",
                  "2": "matrix2", "3": "matrix3", "4": "matrix", "d": "dict"}
_KNOWN_BINDINGS = {
    "vector": {"P", "N", "v", "Cd", "up", "uv", "rest", "force", "accel", "w", "scale", "trans", "pivot", "center"},
    "vector4": {"orient", "rot"},
    "int": {"ptnum", "primnum", "vtxnum", "numpt", "numprim", "numvtx", "elemnum", "numelem", "id", "Frame"},
    "string": {"name", "path", "group", "class", "OpInput1", "OpInput2", "OpInput3", "OpInput4"},
    "float": {"Time", "TimeInc", "pscale", "Alpha", "width", "mass", "age", "life", "density", "SimTime", "SimFrame"},
}
_READ_ONLY_BINDINGS = {"ptnum", "primnum", "vtxnum", "numpt", "numprim", "numvtx", "elemnum", "numelem",
                       "Time", "TimeInc", "Frame", "SimTime", "SimFrame", "OpInput1", "OpInput2", "OpInput3", "OpInput4"}
_BINDING_RE = re.compile(r"(?<![A-Za-z0-9_])((?:[fivspu234d](?:\[\])?)?)@([A-Za-z_][A-Za-z0-9_]*)")
_FUNC_DEF_RE = re.compile(r"^\s*(?:void|int|float|vector[24]?|matrix[23]?|string|dict|function)\b[^;=]*\)\s*\{", re.M)


def snippet_to_vex_function(snippet: str, func_name: str) -> tuple[str, str]:
    """Turn a wrangle snippet into a reusable VEX function plus the call line for a wrangle.

    '@' bindings are not expanded inside #include files, so every binding becomes a function
    argument (VEX passes by reference, so writes still land on the attribute) and the call line
    passes the bindings in.
    """
    if _FUNC_DEF_RE.search(snippet):
        raise ValueError("the snippet defines its own functions; move them into the header by hand.")
    params = {}  # binding name -> (declaration, call expression)
    for m in _BINDING_RE.finditer(snippet):
        prefix, name = m.group(1), m.group(2)
        if name in params:
            continue
        is_array = prefix.endswith("[]")
        base = _BINDING_TYPES.get(prefix[:1]) if prefix else None
        if base is None:
            base = next((t for t, names in _KNOWN_BINDINGS.items() if name in names), "float")
        const = "const " if name in _READ_ONLY_BINDINGS else ""
        params[name] = (f"{const}{base}{'[]' if is_array else ''} _a_{name}", f"{prefix}@{name}")
    body = _BINDING_RE.sub(lambda m: f"_a_{m.group(2)}", snippet)
    args = "; ".join(d for d, _ in params.values())
    lines = "\n".join("    " + l for l in body.splitlines())
    fn = f"void {func_name}({args})\n{{\n{lines}\n}}"
    call = f"{func_name}({', '.join(c for _, c in params.values())});"
    return fn, call


# ---------------------------------------------------------------------------
# Shelf Tools
# ---------------------------------------------------------------------------

def create_ai_wrangle_tool():
    pane = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    pwd = pane.pwd() if pane else hou.node("/obj")
    
    if pwd.childTypeCategory() != hou.sopNodeTypeCategory():
        geo = pwd.createNode("geo", "ai_geo")
        target_network = geo
    else:
        target_network = pwd

    wrangle = target_network.createNode("attribwrangle", "ai_attribwrangle1")
    setup_ai_parameters(wrangle)
    wrangle.moveToGoodPosition()
    wrangle.setSelected(True, clear_all_selected=True)
    
    if hou.isUIAvailable():
        open_copilot_dialog(wrangle)


def convert_selection_tool():
    selected = hou.selectedNodes()
    if not selected:
        if hou.isUIAvailable():
            hou.ui.displayMessage("Please select one or more Wrangle nodes first.", severity=hou.severityType.Warning)
        return

    count = 0
    for node in selected:
        if node.type().name().endswith("wrangle"):
            if setup_ai_parameters(node):
                count += 1

    if hou.isUIAvailable():
        hou.ui.displayMessage(f"Attached AI Copilot v3.5 interface to {count} node(s).", severity=hou.severityType.Message)


def open_copilot_dialog(node: hou.Node = None):
    if node is None:
        selected = hou.selectedNodes()
        if not selected:
            if hou.isUIAvailable():
                hou.ui.displayMessage("Please select an Attribute Wrangle node first.", severity=hou.severityType.Warning)
            return
        node = selected[0]

    if not node.type().name().endswith("wrangle"):
        if hou.isUIAvailable():
            hou.ui.displayMessage(f"Selected node '{node.name()}' is not a Wrangle node.", severity=hou.severityType.Warning)
        return

    setup_ai_parameters(node)

    class_parm = node.parm("class")
    context_idx = class_parm.eval() if class_parm else 2
    context_str = CLASS_MAP.get(context_idx, "point wrangle")

    init_prompt = node.parm("ai_prompt").eval() if node.parm("ai_prompt") else ""
    existing_code = node.parm("snippet").eval().strip() if node.parm("snippet") else ""

    buttons = ("Generate VEX", "Refine Existing", "Cancel") if existing_code else ("Generate VEX", "Cancel")

    button_idx, task_text = hou.ui.readInput(
        f"Enter procedural instruction for [{context_str.upper()}]:",
        buttons=buttons,
        title=f"AI VEX Copilot v3.5 - {node.name()}",
        initial_contents=init_prompt
    )

    if (existing_code and button_idx == 2) or (not existing_code and button_idx == 1) or not task_text.strip():
        return

    task = task_text.strip()
    if node.parm("ai_prompt"):
        node.parm("ai_prompt").set(task)

    is_refine = (existing_code and button_idx == 1)

    if is_refine:
        on_refine_clicked({"node": node})
    else:
        on_generate_clicked({"node": node})


def check_model_health():
    _eng_port = _engine_port()
    """Checks health status of all available AI inference backends."""
    status_lines = []

    # 1. Check Embedded Standalone Engine (Primary — Port 58421)
    try:
        t0 = time.time()
        api_key = getattr(_engine_singleton, "api_key", None) if _engine_singleton else None
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = urllib.request.Request(f"http://127.0.0.1:{_eng_port}/health", headers=headers)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ping_ms = (time.time() - t0) * 1000
            engine_status = data.get("status", "unknown")
        if engine_status == "ok":
            status_lines.append(f"✅ Embedded AI Engine (port {_eng_port}): ONLINE ({ping_ms:.1f}ms)")
        else:
            status_lines.append(f"⏳ Embedded AI Engine (port {_eng_port}): LOADING ({engine_status})")
    except urllib.error.HTTPError as e:
        if e.code == 503:
            status_lines.append(f"⏳ Embedded AI Engine (port {_eng_port}): LOADING (model warming up)")
        else:
            status_lines.append(f"❌ Embedded AI Engine (port {_eng_port}): HTTP Error {e.code}")
    except Exception:
        status_lines.append(f"❌ Embedded AI Engine (port {_eng_port}): OFFLINE")

    # 2. Check Ollama Fallback Engine (Secondary — Port 11434)
    try:
        t0 = time.time()
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ping_ms = (time.time() - t0) * 1000
        models = [m["name"] for m in data.get("models", [])]
        is_vex_installed = any("qwen3-vex" in m for m in models)
        status_lines.append(
            f"✅ Ollama Fallback (port 11434): ONLINE ({ping_ms:.1f}ms)\n"
            f"   Active Model: {resolve_model_name()}\n"
            f"   qwen3-vex Installed: {'YES ✅' if is_vex_installed else 'NO ❌'}\n"
            f"   Available Models: {', '.join(models)}"
        )
    except Exception:
        status_lines.append("⚠️ Ollama Fallback (port 11434): OFFLINE (not required if embedded engine is active)")

    msg = "\n\n".join(status_lines)
    if hou.isUIAvailable():
        hou.ui.displayMessage(msg, title="Houdini AI System Health", severity=hou.severityType.Message)
    else:
        print(msg)
