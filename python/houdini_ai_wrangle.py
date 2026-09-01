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

import os
import json
import re
import time
import urllib.request
import urllib.error
import hou

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
    "You are an expert Houdini VEX programmer. "
    "Write pure, high-performance Houdini VEX code to solve the user's task in the specified context.\n"
    "Rules:\n"
    "  1. Output pure VEX code without markdown formatting or conversational text.\n"
    "  2. Use standard Houdini VEX functions and constructors: set(x, y, z) or {x, y, z}.\n"
    "  3. In detail wrangles with loops, always hoist parameter channel calls (chf, chi, chv, chramp) outside the loop.\n"
    "  4. Array functions like sort(), reverse(), and resize() operate in place and do not return values.\n"
    "  5. In while or half-edge loops, always use bounded for-loops (e.g. for (int step=0; step<64 && h!=-1; step++)) to prevent infinite cycles.\n"
    "  6. Always declare vector4 for quaternions (vector4 q = quaternion(matrix3_m) or vector4 q = dihedral(from_v, to_v)).\n"
    "  7. Always access geometry attributes with the '@' prefix (e.g. @P, @N, @v, @Cd, @ptnum, @primnum).\n"
    "  8. nearpoints() and pcfind() on input 0 ALWAYS include the query point itself (@ptnum). An isolated/lonely point with zero other neighbors has len(nearpoints(0, @P, radius)) <= 1 (count <= 1). To delete lonely particles, use: if (len(nearpoints(0, @P, radius, 2)) <= 1) removepoint(0, @ptnum);\n"
    "  9. Surface projection: vector p = minpos(1, @P); To sample attributes at closest point: int prim; vector uv; float d = xyzdist(1, @P, prim, uv); vector p = primuv(1, 'P', prim, uv);\n"
    "  10. To close a polyline curve in a Detail Wrangle: setprimintrinsic(0, 'closed', poly, 1);\n"
    "  11. To align orientation quaternion @orient from velocity @v: vector4 q = dihedral(set(0, 0, 1), normalize(@v)); or matrix3 m = set(side, up, normalize(@v)); vector4 q = quaternion(m); @orient = q;\n"
    "  12. In loops over point/prim counts (npoints/nprims), always use standard C-style loops: for (int i = 0; i < npoints(0); i++)."
)

REASONING_SYSTEM_PROMPT = (
    "You are a senior Houdini FX Technical Director and computational geometry mathematician.\n"
    "When presented with a task, FIRST think through the problem in an explicit <think>...</think> block:\n"
    "  1. Analyze input geometry, vector spaces, and physical/mathematical equations.\n"
    "  2. Outline algorithmic steps and procedural logic (loops, spatial lookups, matrix transforms).\n"
    "  3. Check edge cases: division by zero, normalization of zero vectors, channel hoisting outside loops, nearpoints/pcfind self-indexing where lonely points have count <= 1, surface projection functions (minpos vs xyzdist/primuv), and only using valid SideFX VEX standard functions (no hallucinated functions like isprime).\n"
    "AFTER the </think> tag, output ONLY the 100% verified, pure Houdini VEX code."
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


def ensure_embedded_engine() -> bool:
    """Start and verify the bundled engine when it is first needed.

    Importing this module must not decrypt an 8+ GB model or launch a process.
    This makes Houdini startup predictable and lets the caller show a useful
    failure message when the engine cannot start.
    """
    global _engine_singleton, _engine_error
    if _engine_singleton and _engine_singleton.is_healthy():
        return True
    try:
        pkg_root = _package_root()
        import sys
        for p in [pkg_root, os.path.join(pkg_root, "python"), os.path.join(pkg_root, "commercial_build")]:
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

        engine_bin = os.path.join(pkg_root, "bin", "llama-server.exe")
        model_path = os.path.join(pkg_root, "models", "qwen3-vex.gguf")

        if not os.path.exists(model_path):
            model_path = os.path.join(pkg_root, "models", "vex_brain.dat")
        if not os.path.exists(model_path):
            model_path = os.path.join(pkg_root, "models", "vex_brain.gguf")
        if not os.path.exists(model_path):
            model_path = os.path.join(pkg_root, "qwen3-vex.gguf")

        if not os.path.exists(engine_bin):
            _engine_error = f"Bundled inference executable is missing: {engine_bin}"
            return False
        if not os.path.exists(model_path):
            _engine_error = f"Bundled model vault is missing: {model_path}"
            return False

        mgr = EngineManager()
        if mgr.start_embedded_engine(engine_bin, model_path):
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
            # Think tag unclosed: if VEX code is present, extract it safely
            content_after = raw.replace("<think>", "").strip()
            # If content contains VEX statements (semicolons, attribute bindings, assignments)
            if ";" in content_after or "@" in content_after:
                code = content_after
                thought_trace = ""
            else:
                thought_trace = content_after
                code = ""

    # Extract from markdown code fences if present
    if "```" in code:
        m = re.search(r"```(?:vex)?\s*([\s\S]*?)\s*```", code)
        if m:
            code = m.group(1).strip()
        else:
            lines = [l for l in code.splitlines() if not l.strip().startswith("```")]
            code = "\n".join(lines).strip()

    return thought_trace, code


def sanitize_vex_syntax(code: str) -> str:
    """
    Automated pre-compilation AST & regex sanitizer.
    Corrects common syntax traps before the compiler ever sees them.
    """
    if not code:
        return code

    c = code

    # 1. Type normalization: vector3 -> vector
    c = re.sub(r"\bvector3\b", "vector", c)

    # 2. Quaternion declaration & argument order
    c = re.sub(r"\bquaternion\s+([a-zA-Z0-9_]+)\s*=", r"vector4 \1 =", c)
    c = re.sub(r"\bquaternion\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\)", r"set(\1, \2, \3, \4)", c)
    c = re.sub(r"quaternion\s*\(\s*([a-zA-Z0-9_@]+)\s*,\s*([0-9.]+)\s*\)", r"quaternion(\2, \1)", c)

    # 3. In-place array assignments: arr = sort(arr); -> sort(arr);
    c = re.sub(r"([a-zA-Z0-9_@]+)\s*=\s*sort\(\s*\1\s*\)\s*;", r"sort(\1);", c)
    c = re.sub(r"([a-zA-Z0-9_@]+)\s*=\s*reverse\(\s*\1\s*\)\s*;", r"reverse(\1);", c)
    c = re.sub(r"([a-zA-Z0-9_@]+)\s*=\s*resize\(\s*\1\s*,([^)]+)\)\s*;", r"resize(\1, \2);", c)
    c = re.sub(r"([a-zA-Z0-9_@]+)\s*=\s*insert\(\s*\1\s*,([^)]+)\)\s*;", r"insert(\1, \2);", c)
    c = re.sub(r"([a-zA-Z0-9_@]+)\s*=\s*removeindex\(\s*\1\s*,([^)]+)\)\s*;", r"removeindex(\1, \2);", c)

    # 4. Matrix row/col methods: m.row(i) -> component indexing
    c = re.sub(r"([a-zA-Z0-9_@]+)\.row\(([0-9]+)\)", r"set(\1.xx, \1.xy, \1.xz)", c)

    # 5. Array reduction overloads: min(arr, 0) -> min(arr)
    c = re.sub(r"\bmin\(([a-zA-Z0-9_@]+\[\]|\b[a-zA-Z0-9_@]+)\s*,\s*0\)", r"min(\1)", c)
    c = re.sub(r"\bmax\(([a-zA-Z0-9_@]+\[\]|\b[a-zA-Z0-9_@]+)\s*,\s*0\)", r"max(\1)", c)

    # 6. Replace undefined diagonal(m) with native set(m.xx, m.yy, m.zz)
    c = re.sub(r"\bdiagonal\(\s*([a-zA-Z0-9_@]+)\s*\)", r"set(\1.xx, \1.yy, \1.zz)", c)

    # 7. Lonely/isolated particle check: nearpoints/pcfind always includes @ptnum (self), so count == 0 is impossible
    if ("nearpoints" in c or "pcfind" in c) and "removepoint" in c:
        c = re.sub(r"if\s*\(\s*([a-zA-Z0-9_]+)\s*==\s*0\s*\)\s*(\{\s*removepoint)", r"if (\1 <= 1) \2", c)
        c = re.sub(r"if\s*\(\s*([a-zA-Z0-9_]+)\s*<=\s*0\s*\)\s*(\{\s*removepoint)", r"if (\1 <= 1) \2", c)
        c = re.sub(r"if\s*\(\s*([a-zA-Z0-9_]+)\s*<\s*1\s*\)\s*(\{\s*removepoint)", r"if (\1 <= 1) \2", c)
        c = re.sub(r"if\s*\(\s*len\s*\(\s*([a-zA-Z0-9_]+)\s*\)\s*==\s*0\s*\)\s*(\{\s*removepoint)", r"if (len(\1) <= 1) \2", c)
        c = re.sub(r"if\s*\(\s*len\s*\(\s*([a-zA-Z0-9_]+)\s*\)\s*<=\s*0\s*\)\s*(\{\s*removepoint)", r"if (len(\1) <= 1) \2", c)
        c = re.sub(r"if\s*\(\s*len\s*\(\s*([a-zA-Z0-9_]+)\s*\)\s*<\s*1\s*\)\s*(\{\s*removepoint)", r"if (len(\1) <= 1) \2", c)
        c = re.sub(r"if\s*\(\s*([a-zA-Z0-9_]+)\s*==\s*0\s*\)\s*removepoint", r"if (\1 <= 1) removepoint", c)
        c = re.sub(r"if\s*\(\s*([a-zA-Z0-9_]+)\s*<=\s*0\s*\)\s*removepoint", r"if (\1 <= 1) removepoint", c)
        c = re.sub(r"if\s*\(\s*len\s*\(\s*([a-zA-Z0-9_]+)\s*\)\s*==\s*0\s*\)\s*removepoint", r"if (len(\1) <= 1) removepoint", c)
        c = re.sub(r"if\s*\(\s*len\s*\(\s*([a-zA-Z0-9_]+)\s*\)\s*<=\s*0\s*\)\s*removepoint", r"if (len(\1) <= 1) removepoint", c)

    # 8. Modernize legacy and foreign array length calls: arraylength(a) / sizeof(a) -> len(a)
    c = re.sub(r"\b(?:arraylength|sizeof)\s*\(", "len(", c)

    # 9. Math shortcuts: sqr(x) -> pow(x, 2) or (x * x)
    c = re.sub(r"\bsqr\s*\(\s*([^)]+)\s*\)", r"((\1) * (\1))", c)

    # 10. pcfind signature normalization: pcfind(0, @P, radius, maxpts) -> pcfind(0, "P", @P, radius, maxpts)
    c = re.sub(r'\bpcfind\s*\(\s*([0-9]+)\s*,\s*(@?P|[a-zA-Z0-9_]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\)', r'pcfind(\1, "P", \2, \3, \4)', c)

    # 11. Range loop normalization: foreach (int i; 0..n-1) -> for (int i = 0; i <= n-1; i++)
    c = re.sub(r'\bforeach\s*\(\s*(?:int\s+)?([a-zA-Z0-9_]+)\s*;\s*([0-9]+)\s*\.\.\s*([^)]+)\s*\)', r'for (int \1 = \2; \1 <= \3; \1++)', c)

    # 12. Pseudo-container loop normalization: foreach (pt; points(0)) -> for (int pt = 0; pt < npoints(0); pt++)
    c = re.sub(r'\bforeach\s*\(\s*(?:int\s+)?([a-zA-Z0-9_]+)\s*;\s*points\s*\(\s*([0-9]+)\s*\)\s*\)', r'for (int \1 = 0; \1 < npoints(\2); \1++)', c)
    c = re.sub(r'\bforeach\s*\(\s*(?:int\s+)?([a-zA-Z0-9_]+)\s*;\s*prims\s*\(\s*([0-9]+)\s*\)\s*\)', r'for (int \1 = 0; \1 < nprimitives(\2); \1++)', c)

    # 13. Geometry count function normalization: nprims() -> nprimitives(), npts() -> npoints()
    c = re.sub(r'\bnprims\s*\(', 'nprimitives(', c)
    c = re.sub(r'\bnpts\s*\(', 'npoints(', c)
    c = re.sub(r'\bnvtxs\s*\(', 'nvertices(', c)

    return c


def query_llm(prompt_text: str, max_tokens: int = 800, reasoning_mode: bool = False) -> tuple[str, str]:
    """
    Queries AI inference engine.
    Priority 1: Embedded Standalone Engine (127.0.0.1:58421 - Zero Dependencies)
    Priority 2: Local Ollama Endpoint (127.0.0.1:11434)
    Returns (thought_trace, pure_vex_code).
    """
    global _engine_error
    system_prompt = REASONING_SYSTEM_PROMPT if reasoning_mode else TURBO_SYSTEM_PROMPT
    
    # 1. Start and query the bundled standalone engine (llama-server on 58421).
    # It is the supported commercial runtime.  Ollama is an opt-in developer
    # fallback, never an undeclared customer dependency.
    engine_ready = ensure_embedded_engine()
    embedded_url = "http://127.0.0.1:58421/completion"
    embedded_payload = {
        "prompt": f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{prompt_text}<|im_end|>\n<|im_start|>assistant\n",
        "n_predict": 512 if not reasoning_mode else 1024,
        "temperature": 0.2 if reasoning_mode else 0.1,
        "top_p": 0.95,
        "stop": ["<|im_end|>", "<|endoftext|>"]
    }
    
    if engine_ready:
        try:
            api_key = getattr(_engine_singleton, "api_key", None) if _engine_singleton else None
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            data = json.dumps(embedded_payload).encode("utf-8")
            req = urllib.request.Request(embedded_url, data=data, headers=headers)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=120) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                raw = res_data.get("content", "")
                if raw:
                    return extract_thought_and_code(raw)
                raise RuntimeError("Bundled inference engine returned an empty response.")
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
            "num_predict": 512 if not reasoning_mode else 1024,
            "num_ctx": 2048,
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
# Geometry Introspection & Context Detection
# ---------------------------------------------------------------------------

def introspect_geometry(node: hou.Node) -> str:
    """Extracts schema, attributes, groups, and volumes from connected inputs."""
    lines = []
    in0 = node.input(0)
    if in0:
        try:
            g0 = in0.geometry()
            if g0:
                npts = len(g0.points())
                nprims = len(g0.prims())
                pt_attribs = [f"@{a.name()} ({a.dataType().name()})" for a in g0.pointAttribs()]
                prim_attribs = [f"@{a.name()} ({a.dataType().name()})" for a in g0.primAttribs()]
                groups = [g.name() for g in g0.pointGroups() + g0.primGroups()]
                size_vec = g0.boundingBox().sizevec()
                
                lines.append(f"Input 0 (Primary Mesh): {npts:,} points, {nprims:,} primitives.")
                if pt_attribs:
                    lines.append(f"  Existing Point Attributes: {', '.join(pt_attribs[:8])}")
                if prim_attribs:
                    lines.append(f"  Existing Prim Attributes: {', '.join(prim_attribs[:6])}")
                if groups:
                    lines.append(f"  Existing Groups: {', '.join(groups[:6])}")
                lines.append(f"  Bounding Box Size: ({size_vec[0]:.2f}, {size_vec[1]:.2f}, {size_vec[2]:.2f})")
        except Exception:
            pass

    in1 = node.input(1)
    if in1:
        try:
            g1 = in1.geometry()
            if g1:
                vol_prims = [p for p in g1.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)]
                if vol_prims:
                    vol_names = list(set([p.attribValue("name") for p in vol_prims if p.findAttrib("name")] or ["density"]))
                    lines.append(f"Input 1: Volume/VDB Fields: {', '.join(vol_names)}")
                else:
                    npts1 = len(g1.points())
                    nprims1 = len(g1.prims())
                    pt_attribs1 = [f"@{a.name()}" for a in g1.pointAttribs()]
                    if nprims1 > 0:
                        lines.append(f"Input 1 (Surface Geometry): Polygon Surface with {nprims1:,} primitives, {npts1:,} points.")
                    else:
                        lines.append(f"Input 1 (Point Cloud): {npts1:,} points.")
        except Exception:
            pass

    if not lines:
        return ""
    return "Upstream Geometry Context:\n" + "\n".join(lines)


def auto_detect_context(prompt: str) -> tuple[int, str]:
    """Intelligently determines wrangle class from prompt keywords using strict word boundaries."""
    p = prompt.lower()
    
    # Detail wrangle checks
    if any(re.search(rf"\b{re.escape(k)}\b", p) for k in [
        "detail", "detail wrangle", "spiral", "addpoint", "addprim", "addvertex",
        "bounding box", "bbox", "across all", "global attribute", "whole geometry"
    ]) or "create points" in p or "generate curve" in p:
        return 0, "detail wrangle"

    # Primitive wrangle checks (strictly exclude point-level queries like xyzdist, primuv, primattrib)
    if not ("xyzdist" in p or "primuv" in p or "surface query" in p or "mesh surface" in p):
        if any(re.search(rf"\b{re.escape(k)}\b", p) for k in [
            "primitive", "primitives", "prim", "prims", "face", "faces", "polygon", "polygons",
            "removeprim", "primpoints", "primvertexcount", "perimeter", "face area", "neighbor face"
        ]):
            return 1, "primitive wrangle"

    # Vertex wrangle checks (strictly vertex wrangles or vertex UVs, not vertex normal math on point meshes)
    if any(re.search(rf"\b{re.escape(k)}\b", p) for k in [
        "vertex wrangle", "texture coordinate", "run over vertices", "vertex uv"
    ]) or ("vertex attribute" in p and "point" not in p):
        return 3, "vertex wrangle"

    return 2, "point wrangle"


# ---------------------------------------------------------------------------
# Generation, Refinement & 1-Shot CITL Self-Repair
# ---------------------------------------------------------------------------

def generate_vex(task: str, context: str = "point wrangle", geo_context: str = "", reasoning_mode: bool = False) -> tuple[str, str]:
    """Generates pure VEX code with optional Deep Reasoning thought trace and RAG Ground Truth."""
    prompt_parts = []
    if get_vex_rag_engine:
        try:
            rag = get_vex_rag_engine()
            rag_block = rag.build_rag_context_block(task)
            if rag_block:
                prompt_parts.append(rag_block)
        except Exception:
            pass

    if geo_context:
        prompt_parts.append(geo_context)
    prompt_parts.append(f"Context: {context}")
    prompt_parts.append(f"Task: {task}")
    prompt_parts.append("Write pure Houdini VEX code:")
    
    full_prompt = "\n\n".join(prompt_parts)
    return query_llm(full_prompt, reasoning_mode=reasoning_mode)


def refine_vex(refinement_task: str, existing_code: str, context: str = "point wrangle", geo_context: str = "", reasoning_mode: bool = False) -> tuple[str, str]:
    """Performs multi-turn iterative modification on existing VEX code."""
    prompt_parts = []
    if get_vex_rag_engine:
        try:
            rag = get_vex_rag_engine()
            rag_block = rag.build_rag_context_block(f"{refinement_task} {existing_code}")
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


def repair_vex(task: str, context: str, faulty_code: str, compiler_error: str) -> tuple[str, str]:
    """Autonomous 1-Shot CITL Self-Repair using live compiler feedback and RAG Ground Truth."""
    prompt_parts = []
    if get_vex_rag_engine:
        try:
            rag = get_vex_rag_engine()
            rag_block = rag.build_rag_context_block(f"{task} {compiler_error}")
            if rag_block:
                prompt_parts.append(rag_block)
        except Exception:
            pass

    prompt_parts.append(
        f"Context: {context}\n"
        f"Task: {task}\n\n"
        f"Faulty VEX Code:\n{faulty_code}\n\n"
        f"Compiler Error from previous attempt:\n{compiler_error}\n\n"
        f"Write the 100% correct, pure Houdini VEX code from scratch solving the task and avoiding this compiler error:"
    )
    full_prompt = "\n\n".join(prompt_parts)
    return query_llm(full_prompt, reasoning_mode=False)


# ---------------------------------------------------------------------------
# SIMD Optimizer, Profiler & Explainer
# ---------------------------------------------------------------------------

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
    _, code = query_llm(prompt, max_tokens=600, reasoning_mode=False)
    return code


def profile_node_cook(node: hou.Node) -> tuple[float, int, float]:
    """Measures cook execution time in milliseconds and compute throughput."""
    t0 = time.perf_counter()
    node.cook(force=True)
    cook_time = time.perf_counter() - t0
    cook_ms = cook_time * 1000.0
    
    g = node.geometry()
    npts = len(g.points()) if g else 0
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
    _, code = query_llm(prompt, max_tokens=800, reasoning_mode=False)
    return code


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


def push_to_history_stack(node: hou.Node, prompt: str, code: str, context_str: str, cook_ms: float = 0.0, thought: str = ""):
    parm = _get_history_parm(node)
    info_parm = _get_info_parm(node)
    if not parm:
        return

    history = get_history_stack(node)
    if history and history[-1].get("code", "").strip() == code.strip():
        return

    version_num = len(history) + 1
    entry = {
        "version": version_num,
        "timestamp": time.strftime("%H:%M:%S"),
        "prompt": prompt[:40] if prompt else "Optimized/Documented",
        "context": context_str,
        "code": code,
        "cook_ms": cook_ms,
        "thought": thought
    }
    history.append(entry)
    parm.set(json.dumps(history))
    
    if info_parm:
        info_parm.set(f"v{version_num} / {version_num} ({entry['timestamp']})")


def navigate_history_version(node: hou.Node, direction: int):
    history = get_history_stack(node)
    if not history:
        if hou.isUIAvailable():
            hou.ui.displayMessage("No history recorded yet.", severity=hou.severityType.Warning)
        return

    current_code = node.parm("snippet").eval().strip() if node.parm("snippet") else ""
    current_idx = len(history) - 1
    
    for i, item in enumerate(history):
        if item.get("code", "").strip() == current_code:
            current_idx = i
            break

    target_idx = max(0, min(len(history) - 1, current_idx + direction))
    if target_idx == current_idx:
        return

    target_entry = history[target_idx]
    target_code = target_entry["code"]

    node.parm("snippet").set(target_code)
    sync_spare_parameters(node, target_code)
    
    if node.parm("ai_thought_trace") and "thought" in target_entry:
        node.parm("ai_thought_trace").set(target_entry["thought"] or "Turbo mode (direct execution)")

    try:
        node.cook(force=True)
    except Exception:
        pass

    info_parm = _get_info_parm(node)
    status_parm = _get_status_parm(node)
    if info_parm:
        info_parm.set(f"v{target_entry['version']} / {len(history)} ({target_entry['timestamp']})")
    if status_parm:
        status_parm.set(f"Loaded {target_entry['prompt']}")


# ---------------------------------------------------------------------------
# Spare Parameter Synchronization
# ---------------------------------------------------------------------------

def parse_vex_channels(vex_code: str) -> dict[str, str]:
    channels = {}
    for m in re.finditer(r'chramp\s*\(\s*["\']([^"\']+)["\']', vex_code):
        channels[m.group(1)] = "ramp"
    for m in re.finditer(r'(?:chv|chp)\s*\(\s*["\']([^"\']+)["\']', vex_code):
        name = m.group(1)
        if name not in channels: channels[name] = "vector"
    for m in re.finditer(r'chi\s*\(\s*["\']([^"\']+)["\']', vex_code):
        name = m.group(1)
        if name not in channels: channels[name] = "int"
    for m in re.finditer(r'chs\s*\(\s*["\']([^"\']+)["\']', vex_code):
        name = m.group(1)
        if name not in channels: channels[name] = "string"
    for m in re.finditer(r'(?:chf|ch)\s*\(\s*["\']([^"\']+)["\']', vex_code):
        name = m.group(1)
        if name not in channels: channels[name] = "float"
    return channels


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

    if folder is None:
        folder = hou.FolderParmTemplate(folder_name, "Generated UI Parameters", folder_type=hou.folderType.Simple)
        for name, p_type in channels.items():
            label = name.replace("_", " ").title()
            tooltip = f"Auto-generated interactive {p_type} control for VEX channel '{name}'."
            if p_type == "float":
                folder.addParmTemplate(hou.FloatParmTemplate(name, label, 1, default_value=(1.0,), min=0.0, max=10.0, min_is_strict=False, max_is_strict=False, help=tooltip))
            elif p_type == "int":
                folder.addParmTemplate(hou.IntParmTemplate(name, label, 1, default_value=(1,), min=0, max=100, min_is_strict=False, max_is_strict=False, help=tooltip))
            elif p_type == "vector":
                folder.addParmTemplate(hou.FloatParmTemplate(name, label, 3, default_value=(0.0, 1.0, 0.0), look=hou.parmLook.Vector, help=tooltip))
            elif p_type == "string":
                folder.addParmTemplate(hou.StringParmTemplate(name, label, 1, default_value=("",), help=tooltip))
            elif p_type == "ramp":
                folder.addParmTemplate(hou.RampParmTemplate(name, label, hou.rampParmType.Color, help=tooltip))

        snippet_parm = ptg.find("snippet")
        if snippet_parm:
            ptg.insertAfter(snippet_parm, folder)
        else:
            ptg.append(folder)
    else:
        existing_templates = {pt.name(): pt for pt in folder.parmTemplates()}
        new_folder = hou.FolderParmTemplate(folder_name, "Generated UI Parameters", folder_type=hou.folderType.Simple)
        
        for name, p_type in channels.items():
            if name in existing_templates:
                new_folder.addParmTemplate(existing_templates[name])
            else:
                label = name.replace("_", " ").title()
                tooltip = f"Auto-generated interactive {p_type} control for VEX channel '{name}'."
                if p_type == "float":
                    new_parm = hou.FloatParmTemplate(name, label, 1, default_value=(1.0,), min=0.0, max=10.0, min_is_strict=False, max_is_strict=False, help=tooltip)
                elif p_type == "int":
                    new_parm = hou.IntParmTemplate(name, label, 1, default_value=(1,), min=0, max=100, min_is_strict=False, max_is_strict=False, help=tooltip)
                elif p_type == "vector":
                    new_parm = hou.FloatParmTemplate(name, label, 3, default_value=(0.0, 1.0, 0.0), look=hou.parmLook.Vector, help=tooltip)
                elif p_type == "string":
                    new_parm = hou.StringParmTemplate(name, label, 1, default_value=("",), help=tooltip)
                elif p_type == "ramp":
                    new_parm = hou.RampParmTemplate(name, label, hou.rampParmType.Color, help=tooltip)
                else:
                    new_parm = hou.FloatParmTemplate(name, label, 1, default_value=(1.0,), min=0.0, max=10.0, min_is_strict=False, max_is_strict=False, help=tooltip)
                new_folder.addParmTemplate(new_parm)
        
        ptg.replace(folder_name, new_folder)

    node.setParmTemplateGroup(ptg)
    
    # Initialize slider values to defaults if they were just created
    for name, p_type in channels.items():
        parm = node.parm(name)
        if parm:
            val = parm.eval()
            if p_type == "float" and val == 0.0:
                if any(k in name.lower() for k in ["freq", "frequency"]):
                    parm.set(1.5)
                elif any(k in name.lower() for k in ["amp", "amplitude", "height", "radius", "turns", "spread", "dome"]):
                    parm.set(1.0)
                elif any(k in name.lower() for k in ["blend", "contrast", "stiffness"]):
                    parm.set(0.5)
            elif p_type == "int" and (val == 0 or val == 1):
                if any(k in name.lower() for k in ["total", "count", "num", "pts", "points", "samples"]):
                    parm.set(200)
                elif any(k in name.lower() for k in ["sides", "segments", "iterations", "steps"]):
                    parm.set(16)
                elif "p_" in name.lower() or name.lower().startswith("p"):
                    parm.set(3)
                elif "q_" in name.lower() or name.lower().startswith("q"):
                    parm.set(7)


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

    # 3. Propagate dirty state downstream to direct outputs (e.g. switch, null, render nodes)
    for out_node in node.outputs():
        try:
            out_node.cook(force=True)
            _ = out_node.geometry()
        except Exception:
            pass

    # 4. Trigger UI update & force scene viewer viewport redraw
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

def try_apply_snippet(node: hou.Node, vex_code: str, snippet_parm_name: str = "snippet") -> tuple[bool, str | None]:
    parm = node.parm(snippet_parm_name)
    if parm is None:
        return False, f"Node {node.path()} has no '{snippet_parm_name}' parameter."

    previous_value = parm.eval()
    previous_ptg = node.parmTemplateGroup()
    parm.set(vex_code)

    # Synchronize spare parameters first so channel default values exist
    sync_spare_parameters(node, vex_code)

    # Force internal VOP recompile and cook
    force_refresh_wrangle(node)

    vop = node.node("attribvop1") if (node.type().name().startswith("attrib") or node.type().name().startswith("ai_")) else None
    raw_vop_errs = vop.errors() if vop else ()
    raw_node_errs = node.errors()
    
    # Filter out benign 'invalid source' messages when input 0 is simply not yet wired
    vop_errs = [e for e in raw_vop_errs if "invalid source" not in e.lower()]
    node_errs = [e for e in raw_node_errs if "invalid source" not in e.lower()]

    has_real_error = False
    for e in list(raw_node_errs) + list(raw_vop_errs):
        if any(k in e.lower() for k in ["syntax error", "undefined", "no matching function", "ambiguous", "cannot convert", "type mismatch", "undeclared", "call to undefined"]):
            has_real_error = True
            break

    if has_real_error:
        err_msg = "\n".join(list(raw_node_errs) + list(raw_vop_errs) + list(node.warnings()))
        parm.set(previous_value)
        node.setParmTemplateGroup(previous_ptg)
        force_refresh_wrangle(node)
        return False, err_msg

    return True, None


# ---------------------------------------------------------------------------
# Node Parameter Setup (v3.5 Layout)
# ---------------------------------------------------------------------------

def setup_ai_parameters(node: hou.Node) -> bool:
    if not node.type().name().endswith("wrangle"):
        if hou.isUIAvailable():
            hou.ui.displayMessage("Target node must be an Attribute / Volume / POP Wrangle.", severity=hou.severityType.Warning)
        return False

    ptg = node.parmTemplateGroup()
    if ptg.find("ai_folder"):
        return True

    ai_folder = hou.FolderParmTemplate("ai_folder", "AI VEX Copilot v3.5", folder_type=hou.folderType.Simple)

    prompt_parm = hou.StringParmTemplate(
        name="ai_prompt",
        label="AI Prompt",
        num_components=1,
        default_value=([""]),
        string_type=hou.stringParmType.Regular,
        help="Type your natural language procedural or FX task here.\nExample: 'Displace points along @N using curlnoise with frequency slider and color ramp'\nSupports attributes (@P, @v, @Cd, @N, @pscale) and UI channels (chf, chv, chramp)."
    )

    autodetect_parm = hou.ToggleParmTemplate(
        name="ai_autodetect",
        label="Auto-Detect Context & Schema",
        default_value=True,
        help="When enabled, automatically inspects upstream geometry schema (attributes, groups, bounding box, volume fields) and determines the target execution class (Point, Primitive, Detail, or Vertex)."
    )

    reasoning_parm = hou.ToggleParmTemplate(
        name="ai_reasoning_mode",
        label="🧠 Deep Reasoning Mode (CoT Math Blueprint)",
        default_value=False,
        help="🧠 Deep Reasoning Mode (CoT):\nWhen enabled, the AI generates a step-by-step mathematical reasoning blueprint (<think> trace) before writing code. Ideal for complex multi-pass algorithms, spatial packing, and custom physics solvers.\nWhen disabled, Turbo Mode generates pure VEX in 1-2s."
    )

    # Action Buttons
    gen_btn = hou.ButtonParmTemplate(
        name="ai_generate",
        label="🪄 Generate VEX",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_generate_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="🪄 Generate VEX:\nQueries qwen3-vex, compiles the code with live CITL error checking, and automatically creates interactive UI parameter sliders (chf, chv, chramp) on this node."
    )

    refine_btn = hou.ButtonParmTemplate(
        name="ai_refine",
        label="🔄 Refine / Iterate",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_refine_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="🔄 Refine / Iterate:\nModifies existing VEX code conversationally based on your new prompt instructions without losing prior functionality.\nExample: 'Make it faster and add velocity drag'."
    )

    optimize_btn = hou.ButtonParmTemplate(
        name="ai_optimize",
        label="⚡ Optimize SIMD",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_optimize_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="⚡ Optimize SIMD:\nAutomatically refactors the VEX snippet for high-throughput SIMD parallel performance on multi-million point meshes (hoists loop invariants, vectorizes calculations, eliminates redundant functions)."
    )

    explain_btn = hou.ButtonParmTemplate(
        name="ai_explain",
        label="💡 Explain & Document",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_explain_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="💡 Explain & Document:\nAnnotates the VEX code with clean, educational inline comments and parameter docstrings without modifying executable logic."
    )

    # Thought Trace Folder
    thought_folder = hou.FolderParmTemplate("ai_thought_folder", "🧠 Chain of Thought Trace", folder_type=hou.folderType.Collapsible)
    thought_parm = hou.StringParmTemplate(
        name="ai_thought_trace",
        label="Reasoning Monologue",
        num_components=1,
        default_value=(["No thought trace recorded yet."]),
        string_type=hou.stringParmType.Regular,
        tags={"editor": "1", "multiline": "1"},
        help="Displays the AI's internal Chain-of-Thought reasoning monologue, vector space analysis, and mathematical blueprint generated during Deep Reasoning Mode."
    )
    thought_folder.addParmTemplate(thought_parm)

    # Time Machine Folder
    history_folder = hou.FolderParmTemplate("ai_history_folder", "⏳ VEX Time Machine", folder_type=hou.folderType.Collapsible)
    prev_btn = hou.ButtonParmTemplate(
        name="ai_prev_version",
        label="◀ Prev Version",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_prev_version_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="◀ Prev Version:\nRolls back non-destructively to the previous working VEX iteration in the Time Machine history stack."
    )
    next_btn = hou.ButtonParmTemplate(
        name="ai_next_version",
        label="▶ Next Version",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_next_version_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="▶ Next Version:\nNavigates forward to the next recorded VEX iteration in the Time Machine history stack."
    )
    version_info_parm = hou.StringParmTemplate(
        name="ai_version_info",
        label="Current Version",
        num_components=1,
        default_value=(["v1 / 1 (Initial)"]),
        string_type=hou.stringParmType.Regular,
        help="Displays current active version number, total recorded versions, and timestamp."
    )
    history_json_parm = hou.StringParmTemplate(
        name="ai_history_json",
        label="History Data",
        num_components=1,
        default_value=(["[]"]),
        string_type=hou.stringParmType.Regular
    )
    history_json_parm.setTags({"hide": "1"})

    history_folder.addParmTemplate(prev_btn)
    history_folder.addParmTemplate(next_btn)
    history_folder.addParmTemplate(version_info_parm)
    history_folder.addParmTemplate(history_json_parm)

    status_parm = hou.StringParmTemplate(
        name="ai_status",
        label="Status",
        num_components=1,
        default_value=(["Ready"]),
        string_type=hou.stringParmType.Regular,
        help="Displays real-time compilation status, 1-shot CITL repair feedback, or generation errors."
    )

    perf_parm = hou.StringParmTemplate(
        name="ai_perf",
        label="Performance",
        num_components=1,
        default_value=(["Cook: --"]),
        string_type=hou.stringParmType.Regular,
        help="Displays live cook execution duration (in milliseconds), processed point count, and compute throughput (Million points / sec)."
    )

    ai_folder.addParmTemplate(prompt_parm)
    ai_folder.addParmTemplate(autodetect_parm)
    ai_folder.addParmTemplate(reasoning_parm)
    ai_folder.addParmTemplate(gen_btn)
    ai_folder.addParmTemplate(refine_btn)
    ai_folder.addParmTemplate(optimize_btn)
    ai_folder.addParmTemplate(explain_btn)
    ai_folder.addParmTemplate(thought_folder)
    ai_folder.addParmTemplate(history_folder)
    ai_folder.addParmTemplate(status_parm)
    ai_folder.addParmTemplate(perf_parm)

    snippet_parm = ptg.find("snippet")
    if snippet_parm:
        ptg.insertBefore(snippet_parm, ai_folder)
    else:
        ptg.append(ai_folder)

    node.setParmTemplateGroup(ptg)
    return True


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def on_generate_clicked(kwargs):
    node = None
    if isinstance(kwargs, dict):
        node = kwargs.get("node") or (kwargs.get("parm").node() if kwargs.get("parm") else None)
    if not node and hasattr(hou, "pwd"):
        node = hou.pwd()
    if not node:
        return

    prompt_parm = node.parm("ai_prompt")
    autodetect_parm = node.parm("ai_autodetect")
    reasoning_parm = node.parm("ai_reasoning_mode")
    thought_parm = node.parm("ai_thought_trace")
    status_parm = _get_status_parm(node)
    perf_parm = node.parm("ai_perf")
    class_parm = node.parm("class")
    snippet_parm = node.parm("snippet")

    if prompt_parm is None or not prompt_parm.eval().strip():
        if hou.isUIAvailable():
            hou.ui.setStatusMessage("Please enter an AI prompt description first.", severity=hou.severityType.Warning)
        return

    task = prompt_parm.eval().strip()
    is_reasoning = bool(reasoning_parm and reasoning_parm.eval())
    geo_context = introspect_geometry(node) if (autodetect_parm and autodetect_parm.eval()) else ""

    CLASS_TOKEN_MAP = {0: "detail", 1: "primitive", 2: "point", 3: "vertex"}

    if autodetect_parm and autodetect_parm.eval() and class_parm:
        detected_idx, detected_str = auto_detect_context(task)
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

    status_msg = "Deep Reasoning (Thinking & Planning)..." if is_reasoning else "Generating VEX..."
    with hou.undos.group(f"AI VEX Generation: {task[:30]}"):
        try:
            if hou.isUIAvailable():
                hou.ui.setStatusMessage(status_msg, severity=hou.severityType.Message)
            t0 = time.time()
            thought_trace, vex_code = generate_vex(task, context=context_str, geo_context=geo_context, reasoning_mode=is_reasoning)
            gen_time = time.time() - t0
        except Exception as e:
            if status_parm:
                status_parm.set(f"Generation Failed: {e}")
            if hou.isUIAvailable():
                hou.ui.setStatusMessage(f"AI Generation Failed: {e}", severity=hou.severityType.Error)
            return

        if thought_parm:
            thought_parm.set(thought_trace if thought_trace else "Turbo mode: direct execution (no thought trace).")

        if not vex_code:
            if status_parm:
                status_parm.set("Error: Model returned empty VEX code.")
            return

        # 1. Automated pre-compilation AST & regex sanitization
        vex_code = sanitize_vex_syntax(vex_code)

        # 2. Multi-Pass Autonomous CITL Self-Healing Loop (Up to 3 Retries)
        max_citl_retries = 3
        success = False
        error = None

        for attempt in range(max_citl_retries):
            success, error = try_apply_snippet(node, vex_code)
            if success:
                error = None
                break

            # If compilation failed, attempt autonomous 1-shot repair with compiler feedback
            if attempt < max_citl_retries - 1 and error:
                if hou.isUIAvailable():
                    hou.ui.setStatusMessage(f"Auto-repairing VEX syntax (Attempt {attempt+2}/{max_citl_retries})...", severity=hou.severityType.Message)
                _, repaired_code = repair_vex(task, context_str, vex_code, error)
                if repaired_code:
                    vex_code = sanitize_vex_syntax(repaired_code)

        # Re-fetch parm references after try_apply_snippet may have updated the PTG
        status_parm = _get_status_parm(node)
        perf_parm = node.parm("ai_perf")
        snippet_parm = node.parm("snippet")

        if success:
            cook_ms, npts, throughput = profile_node_cook(node)
            push_to_history_stack(node, task, vex_code, context_str, cook_ms=cook_ms, thought=thought_trace)
            
            mode_label = "Deep Reasoning" if is_reasoning else "Turbo"
            if status_parm:
                status_parm.set(f"Compiled [{mode_label}] ({gen_time:.2f}s).")
            if perf_parm:
                perf_parm.set(f"Cook: {cook_ms:.2f}ms ({npts:,} pts @ {throughput:.1f} Mpts/s)")
            if hou.isUIAvailable():
                hou.ui.setStatusMessage("AI VEX compiled and applied successfully.", severity=hou.severityType.Message)
        else:
            # Non-blocking status reporting (never spam modal dialogs)
            if snippet_parm:
                snippet_parm.set(vex_code)
            if status_parm:
                first_line_err = error.splitlines()[0] if error else 'Syntax warning'
                status_parm.set(f"Compile Warning: {first_line_err}")
            if hou.isUIAvailable():
                hou.ui.setStatusMessage(f"AI VEX Warning: {error.splitlines()[0] if error else ''}", severity=hou.severityType.Warning)


def on_refine_clicked(kwargs):
    node = kwargs["node"]
    prompt_parm = node.parm("ai_prompt")
    autodetect_parm = node.parm("ai_autodetect")
    reasoning_parm = node.parm("ai_reasoning_mode")
    thought_parm = node.parm("ai_thought_trace")
    status_parm = _get_status_parm(node)
    perf_parm = node.parm("ai_perf")
    class_parm = node.parm("class")
    snippet_parm = node.parm("snippet")

    if prompt_parm is None or not prompt_parm.eval().strip():
        if hou.isUIAvailable():
            hou.ui.setStatusMessage("Please enter a refinement instruction in AI Prompt.", severity=hou.severityType.Warning)
        return

    existing_code = snippet_parm.eval().strip() if snippet_parm else ""
    if not existing_code:
        on_generate_clicked(kwargs)
        return

    refinement_task = prompt_parm.eval().strip()
    is_reasoning = bool(reasoning_parm and reasoning_parm.eval())
    geo_context = introspect_geometry(node) if (autodetect_parm and autodetect_parm.eval()) else ""
    context_idx = class_parm.eval() if class_parm else 2
    context_str = CLASS_MAP.get(context_idx, "point wrangle")

    with hou.undos.group(f"AI VEX Refinement: {refinement_task[:30]}"):
        try:
            if hou.isUIAvailable():
                hou.ui.setStatusMessage("Refining VEX code...", severity=hou.severityType.Message)
            t0 = time.time()
            thought_trace, vex_code = refine_vex(refinement_task, existing_code, context=context_str, geo_context=geo_context, reasoning_mode=is_reasoning)
            gen_time = time.time() - t0
        except Exception as e:
            if status_parm:
                status_parm.set(f"Refinement Failed: {e}")
            if hou.isUIAvailable():
                hou.ui.setStatusMessage(f"AI Refinement Failed: {e}", severity=hou.severityType.Error)
            return

        if thought_parm:
            thought_parm.set(thought_trace if thought_trace else "Refinement applied.")

        # 1. Automated pre-compilation AST & regex sanitization
        vex_code = sanitize_vex_syntax(vex_code)

        # 2. Multi-Pass Autonomous CITL Self-Healing Loop (Up to 3 Retries)
        max_citl_retries = 3
        success = False
        error = None

        for attempt in range(max_citl_retries):
            success, error = try_apply_snippet(node, vex_code)
            if success:
                error = None
                break

            if attempt < max_citl_retries - 1 and error:
                if hou.isUIAvailable():
                    hou.ui.setStatusMessage(f"Auto-repairing VEX syntax (Attempt {attempt+2}/{max_citl_retries})...", severity=hou.severityType.Message)
                _, repaired_code = repair_vex(refinement_task, context_str, vex_code, error)
                if repaired_code:
                    vex_code = sanitize_vex_syntax(repaired_code)

        # Re-fetch parm references after try_apply_snippet may have updated the PTG
        status_parm = _get_status_parm(node)
        perf_parm = node.parm("ai_perf")
        snippet_parm = node.parm("snippet")

        if success:
            cook_ms, npts, throughput = profile_node_cook(node)
            push_to_history_stack(node, refinement_task, vex_code, context_str, cook_ms=cook_ms, thought=thought_trace)
            
            if status_parm:
                status_parm.set(f"Refined ({gen_time:.2f}s).")
            if perf_parm:
                perf_parm.set(f"Cook: {cook_ms:.2f}ms ({npts:,} pts @ {throughput:.1f} Mpts/s)")
            if hou.isUIAvailable():
                hou.ui.setStatusMessage("AI VEX refined successfully.", severity=hou.severityType.Message)
        else:
            if snippet_parm:
                snippet_parm.set(vex_code)
            if status_parm:
                status_parm.set(f"Refine Warning: {error.splitlines()[0] if error else 'Unknown'}")
            if hou.isUIAvailable():
                hou.ui.setStatusMessage(f"AI VEX Warning: {error.splitlines()[0] if error else ''}", severity=hou.severityType.Warning)


def on_optimize_clicked(kwargs):
    node = kwargs["node"]
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
    node = kwargs["node"]
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
    navigate_history_version(kwargs["node"], direction=-1)


def on_next_version_clicked(kwargs):
    navigate_history_version(kwargs["node"], direction=+1)


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
    """Checks health status of all available AI inference backends."""
    status_lines = []

    # 1. Check Embedded Standalone Engine (Primary — Port 58421)
    try:
        t0 = time.time()
        api_key = getattr(_engine_singleton, "api_key", None) if _engine_singleton else None
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = urllib.request.Request("http://127.0.0.1:58421/health", headers=headers)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ping_ms = (time.time() - t0) * 1000
            engine_status = data.get("status", "unknown")
        if engine_status == "ok":
            status_lines.append(f"✅ Embedded AI Engine (port 58421): ONLINE ({ping_ms:.1f}ms)")
        else:
            status_lines.append(f"⏳ Embedded AI Engine (port 58421): LOADING ({engine_status})")
    except urllib.error.HTTPError as e:
        if e.code == 503:
            status_lines.append("⏳ Embedded AI Engine (port 58421): LOADING (model warming up)")
        else:
            status_lines.append(f"❌ Embedded AI Engine (port 58421): HTTP Error {e.code}")
    except Exception:
        status_lines.append("❌ Embedded AI Engine (port 58421): OFFLINE")

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
