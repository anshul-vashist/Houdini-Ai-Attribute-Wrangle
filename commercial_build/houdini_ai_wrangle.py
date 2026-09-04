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
import math
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
    "You are Houdini VEX Copilot, an expert AI programming assistant fine-tuned and created by Anshul Vashist.\n"
    "Write pure, high-performance Houdini VEX code to solve the user's task in the specified context.\n"
    "Rules:\n"
    "  1. Output pure VEX code without markdown formatting or conversational text.\n"
    "  2. Use standard Houdini VEX types and constructors: vector, vector4, matrix3, matrix, set(x, y, z).\n"
    "  3. In detail wrangles with loops, always hoist parameter channel calls (chf, chi, chv, chramp) outside the loop."
)

REASONING_SYSTEM_PROMPT = (
    "You are Houdini VEX Copilot, an expert AI programming assistant fine-tuned and created by Anshul Vashist.\n"
    "When presented with a task, FIRST think through the problem in an explicit <think>...</think> block:\n"
    "  1. Analyze input geometry, vector spaces, and physical/mathematical equations.\n"
    "  2. Outline algorithmic steps and procedural logic (loops, spatial lookups, matrix transforms).\n"
    "AFTER the </think> tag, output ONLY the pure, verified Houdini VEX code.\n"
    "Rules for VEX Code:\n"
    "  - Use standard Houdini VEX types and constructors: vector, vector4, matrix3, matrix, set(x, y, z).\n"
    "  - Use standard Houdini VEX functions: curlnoise, snoise, length, normalize, distance, npoints, nprimitives.\n"
    "  - In detail wrangles with loops, always hoist parameter channel calls (chf, chi, chv, chramp) outside the loop."
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
        base_candidates = [
            os.path.join(pkg_root, "models", "Qwen3-8B-Houdini-VEX-v10-Q5_K_M.gguf"),
            os.path.join(pkg_root, "models", "Qwen3-8B-Q5_K_M.gguf"),
            os.path.join(pkg_root, "models", "qwen3-vex.gguf"),
            os.path.join(pkg_root, "models", "vex_brain.dat"),
            os.path.join(pkg_root, "models", "vex_brain.gguf"),
            os.path.join(pkg_root, "qwen3-vex.gguf"),
        ]
        model_path = next((p for p in base_candidates if os.path.exists(p)), base_candidates[0])

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

def get_active_ai_model_display_string() -> str:
    """Returns human-readable active base model and fine-tuned LoRA adapter name."""
    global _engine_singleton
    if _engine_singleton and hasattr(_engine_singleton, "get_model_info_string"):
        try:
            return _engine_singleton.get_model_info_string()
        except Exception:
            pass

    pkg_root = _package_root()
    model_dir = os.path.join(pkg_root, "models")
    if os.path.isfile(os.path.join(model_dir, "Qwen3-8B-Houdini-VEX-v10-Q5_K_M.gguf")):
        return "Qwen3-8B-Houdini-VEX-v10-Q5_K_M.gguf (Standalone Merged)"
    base_name = "Qwen3-8B-Q5_K_M.gguf" if os.path.isfile(os.path.join(model_dir, "Qwen3-8B-Q5_K_M.gguf")) else "qwen3-vex.gguf"
    lora_candidates = [
        "qwen3-vex-v10-lora.gguf",
        "lora.gguf",
    ]
    active_lora = None
    if os.path.isdir(model_dir):
        for lora in lora_candidates:
            if os.path.isfile(os.path.join(model_dir, lora)):
                active_lora = lora
                break
    if active_lora:
        return f"{base_name} + LoRA: {active_lora}"
    return f"{base_name} (Base)"


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
            content_after = raw.replace("<think>", "").strip()
            if ";" in content_after or "@" in content_after:
                code = content_after
                thought_trace = ""
            else:
                thought_trace = content_after
                code = ""
    elif "</think>" in raw:
        parts = raw.split("</think>", 1)
        thought_trace = parts[0].strip()
        code = parts[1].strip()

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
    """Pass-through for pure neural model generation with safety alias normalization."""
    if not code:
        return ""
    c = code.strip()
    c = re.sub(r'\bcurlnoise(?:2d|3d|4d)\b', 'curlnoise', c)
    c = re.sub(r'\bsnoise(?:2d|3d|4d)\b', 'snoise', c)
    c = re.sub(r'\bpnoise(?:2d|3d|4d)\b', 'pnoise', c)
    c = re.sub(r'\bxnoise(?:2d|3d|4d)\b', 'xnoise', c)
    c = re.sub(r'\bprimcenter\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)', r'primuv(\1, "P", \2, set(0.5, 0.5, 0.0))', c)
    c = re.sub(r'\b(?:dist|pointdistance)\s*\(', 'distance(', c)
    c = re.sub(r'\bmag\s*\(', 'length(', c)
    c = re.sub(r'\bnorm\s*\(', 'normalize(', c)
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
    
    asst_prefix = "<|im_start|>assistant\n<think>\n" if reasoning_mode else "<|im_start|>assistant\n"
    embedded_payload = {
        "prompt": f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{prompt_text}<|im_end|>\n{asst_prefix}",
        "n_predict": 512 if not reasoning_mode else 1024,
        "temperature": 0.2 if reasoning_mode else 0.1,
        "top_p": 0.95,
        "repeat_penalty": 1.15,
        "stop": ["<|im_end|>", "<|endoftext|>", "###"]
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


def _classify_geo_type(geo, npts: int, nprims: int) -> str:
    """Classify geometry type from primitive types (Phase 1: #1)."""
    if nprims == 0:
        return "Point Cloud (no primitives)" if npts > 0 else "Empty Geometry"

    # Sample up to first 50 prims for classification
    sample = geo.prims()[:50]
    prim_types = set(p.type() for p in sample)

    if hou.primType.Volume in prim_types or hou.primType.VDB in prim_types:
        return "Volume/VDB"
    if hou.primType.PackedGeometry in prim_types:
        return "Packed Geometry"
    if prim_types & {hou.primType.NURBSCurve, hou.primType.BezierCurve}:
        return "NURBS/Bezier Curves"

    # All polygon — distinguish mesh vs polyline vs mixed
    if all(p.type() == hou.primType.Polygon for p in sample):
        vert_counts = [len(p.vertices()) for p in sample]
        if all(v == 2 for v in vert_counts):
            return "Polyline / Curve"
        if all(v >= 3 for v in vert_counts):
            return "Polygon Mesh"
        return "Mixed Polygon (mesh + lines)"

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


def introspect_geometry(node: hou.Node) -> str:
    """Extracts rich context from all 4 inputs: geo type, typed attributes, bbox, groups, volumes,
    upstream node hints, solver context, and performance guidance."""
    lines = []
    connected_inputs = []
    empty_inputs = []
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

            connected_inputs.append(i)
            npts = len(geo.points())
            nprims = len(geo.prims())
            total_pts += npts

            # --- Geometry type classification (Phase 1: #1) ---
            geo_type = _classify_geo_type(geo, npts, nprims)

            # --- Volume/VDB shortcut ---
            vol_prims = [p for p in geo.prims() if p.type() in (hou.primType.Volume, hou.primType.VDB)]
            if vol_prims:
                vol_names = list(set(
                    [p.attribValue("name") for p in vol_prims if p.findAttrib("name")] or ["density"]
                ))
                lines.append(f"Input {i}: {geo_type}. Fields: {', '.join(vol_names)}. {npts:,} pts, {nprims:,} prims.")
                continue

            # --- Typed attribute listing (Phase 1: #2) ---
            pt_typed = [_format_attrib_typed(a) for a in geo.pointAttribs()[:12]]
            pr_typed = [_format_attrib_typed(a) for a in geo.primAttribs()[:8]]
            groups = [g.name() for g in geo.pointGroups()] + [g.name() for g in geo.primGroups()]

            desc = f"Input {i}: {geo_type}. {npts:,} points, {nprims:,} primitives."
            if pt_typed:
                desc += f"\n  Point Attribs: {', '.join(pt_typed)}."
            if pr_typed:
                desc += f"\n  Prim Attribs: {', '.join(pr_typed)}."
            if groups:
                desc += f"\n  Groups: {', '.join(groups[:6])}."

            # --- Bounding box (Phase 1: #4) ---
            try:
                bbox = geo.boundingBox()
                bsz = bbox.sizevec()
                bctr = bbox.center()
                desc += f"\n  Bounding Box: size=({bsz[0]:.2f}, {bsz[1]:.2f}, {bsz[2]:.2f}), center=({bctr[0]:.2f}, {bctr[1]:.2f}, {bctr[2]:.2f})."
            except Exception:
                pass

            lines.append(desc)
        except Exception:
            connected_inputs.append(i)

    if not lines and not connected_inputs:
        return ""

    # --- Input connection rules ---
    rule_lines = []
    if 0 in connected_inputs and not (set(connected_inputs) - {0}):
        rule_lines.append("IMPORTANT: ONLY Input 0 is connected! Do NOT query or reference inputs 1, 2, or 3 (e.g. use nearpoints(0, ...), point(0, ...)).")
    elif connected_inputs:
        rule_lines.append(f"Connected Inputs: {', '.join(str(x) for x in connected_inputs)}. Empty / Disconnected Inputs: {', '.join(str(x) for x in empty_inputs)}.")
        rule_lines.append("Do NOT query any disconnected inputs.")

    rule_lines.append("Do NOT check or depend on non-existent attributes in if-statements unless they are listed above or you explicitly initialize them first.")

    # --- Upstream node type hints (Phase 2: #3) ---
    upstream = _get_upstream_hints(node)
    if upstream:
        rule_lines.extend(upstream)

    # --- Solver context detection (Phase 1: #5) ---
    if _detect_solver_context(node):
        rule_lines.append("This wrangle is INSIDE a SOP Solver. Use @Time/@TimeInc for time-stepping. Accumulate values (e.g., @P += v@vel * @TimeInc) instead of setting absolute values.")

    # --- Performance hints (Phase 2: #7) ---
    perf = _perf_hint(total_pts)
    if perf:
        rule_lines.append(perf)

    return "Live Node & Geometry Context:\n" + "\n".join(lines + rule_lines)


def auto_detect_context(prompt: str) -> tuple[int, str]:
    """Intelligently determines wrangle class from prompt intent."""
    p = prompt.lower()
    
    # 1. Detail wrangle checks (curves from scratch, attractors, mesh generation, global aggregation)
    is_detail_generation = any(re.search(rf"\b{re.escape(k)}\b", p) for k in [
        "detail wrangle", "detail context", "from scratch", "create mesh", "generate curve", "create curve",
        "lorenz", "attractor", "spiral", "knot", "helix", "polyline", "mobius", "minimal surface",
        "global attribute", "whole geometry", "global calculation"
    ]) or ("create points" in p) or ("generate points" in p) or ("stitch points" in p) or ("connect points into" in p)
    
    if is_detail_generation:
        return 0, "detail wrangle"
        
    # 2. Point operations
    is_point_operation = any(k in p for k in [
        "each point", "every point", "per point", "all points", "particles",
        "point normal", "point position", "point color", "point velocity", "displace each point",
        "project each point", "sample the gradient", "scatter", "nearpoints", "pcopen", "pcfind"
    ])

    # If it is clearly an operation iterating over points, return point wrangle
    if is_point_operation:
        return 2, "point wrangle"

    # 3. Primitive wrangle checks (face operations, polygon culling, perimeter/area calculation)
    if not ("xyzdist" in p or "primuv" in p or "surface query" in p or "closest surface" in p or "polygon mesh" in p):
        if any(re.search(rf"\b{re.escape(k)}\b", p) for k in [
            "primitive wrangle", "primitive", "primitives", "prim", "prims", "face", "faces",
            "removeprim", "primpoints", "primvertexcount", "perimeter", "face area", "neighbor face",
            "polygon face", "polygon normal", "checkerboard face"
        ]):
            return 1, "primitive wrangle"

    # 4. Vertex wrangle checks (vertex UVs, texture coordinates, vertex attributes)
    if any(re.search(rf"\b{re.escape(k)}\b", p) for k in [
        "vertex wrangle", "texture coordinate", "run over vertices", "vertex uv"
    ]) or ("vertex attribute" in p and "point" not in p):
        return 3, "vertex wrangle"

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

    # Topology
    "cull":        "Remove elements failing a condition via removepoint/removeprim.",
    "remove":      "Use removepoint(0, @ptnum) or removeprim(0, @primnum, 1).",
    "delete":      "Use removepoint(0, @ptnum) or removeprim(0, @primnum, 1).",
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


def _compute_scale_calibrated_parm(name: str, p_type: str, bbox_max: float) -> hou.ParmTemplate:
    """Calibrates parameter defaults, minimums, and maximums based on geometry bounding box scale."""
    label = name.replace("_", " ").title()
    tooltip = f"Auto-generated interactive {p_type} control for VEX channel '{name}'."
    n_lower = name.lower()

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

    if folder is None:
        folder = hou.FolderParmTemplate(folder_name, "Generated UI Parameters", folder_type=hou.folderType.Simple)
        for name, p_type in channels.items():
            folder.addParmTemplate(_compute_scale_calibrated_parm(name, p_type, bbox_max))

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
                new_folder.addParmTemplate(_compute_scale_calibrated_parm(name, p_type, bbox_max))
        
        ptg.replace(folder_name, new_folder)

    node.setParmTemplateGroup(ptg)


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
# Production Safety Shield & Diagnostics
# ---------------------------------------------------------------------------

def sanitize_nan_inf_vex(code: str) -> str:
    """Injects defensive mathematical guards against NaN/Inf and division-by-zero."""
    # 1. acos(x) -> acos(clamp(x, -1.0, 1.0))
    code = re.sub(r'\bacos\s*\(\s*([^()]+)\s*\)', r'acos(clamp(\1, -1.0, 1.0))', code)
    # 2. asin(x) -> asin(clamp(x, -1.0, 1.0))
    code = re.sub(r'\basin\s*\(\s*([^()]+)\s*\)', r'asin(clamp(\1, -1.0, 1.0))', code)
    # 3. sqrt(x) -> sqrt(max(x, 0.0))
    code = re.sub(r'\bsqrt\s*\(\s*([^()]+)\s*\)', r'sqrt(max(\1, 0.0))', code)
    # 4. log(x) -> log(max(x, 1e-6))
    code = re.sub(r'\blog\s*\(\s*([^()]+)\s*\)', r'log(max(\1, 1e-6))', code)
    return code


def scan_geometry_health(node: hou.Node) -> tuple[bool, str]:
    """Inspects cooked geometry for any NaN or Inf floats in point/primitive attributes."""
    try:
        geo = node.geometry()
        if not geo:
            return True, "No geometry to scan."
        
        nan_issues = []
        inf_issues = []

        # Check point attributes
        for attr in geo.pointAttribs():
            dt = attr.dataType()
            if dt != hou.attribData.Float:
                continue
            for pt in geo.points()[:2000]:  # sample up to 2000 points
                vals = pt.attribValue(attr)
                v_list = vals if isinstance(vals, (tuple, list)) else [vals]
                has_nan = any(math.isnan(v) for v in v_list)
                has_inf = any(math.isinf(v) for v in v_list)
                if has_nan:
                    if attr.name() not in nan_issues: nan_issues.append(attr.name())
                    break
                if has_inf:
                    if attr.name() not in inf_issues: inf_issues.append(attr.name())
                    break

        if nan_issues or inf_issues:
            msg_parts = []
            if nan_issues:
                msg_parts.append(f"NaN in @{', @'.join(nan_issues)}")
            if inf_issues:
                msg_parts.append(f"Inf in @{', @'.join(inf_issues)}")
            return False, f"⚠️ Health Alert: Detected {'; '.join(msg_parts)}!"

        return True, "✅ Geometry Healthy: 0 NaNs / 0 Infs detected."
    except Exception as e:
        return True, f"Scan skipped: {e}"


def inspect_attribute_statistics(node: hou.Node) -> str:
    """Computes comprehensive min, max, average, and NaN/Inf stats for all attributes."""
    geo = node.geometry()
    if not geo:
        return "No geometry available on this node."

    lines = [f"=== Attribute Health & Statistics: {node.path()} ==="]
    npts = len(geo.points())
    nprims = len(geo.prims())
    lines.append(f"Total Geometry: {npts:,} points, {nprims:,} primitives.\n")

    lines.append("--- Point Attributes ---")
    for attr in geo.pointAttribs():
        dt = attr.dataType()
        sz = attr.size()
        name = attr.name()
        if dt == hou.attribData.Float:
            sample_pts = geo.points()[:5000]
            nan_count = 0
            inf_count = 0
            magnitudes = []
            for pt in sample_pts:
                v = pt.attribValue(attr)
                if sz == 1:
                    if math.isnan(v): nan_count += 1
                    elif math.isinf(v): inf_count += 1
                    else: magnitudes.append(v)
                else:
                    if any(math.isnan(x) for x in v): nan_count += 1
                    elif any(math.isinf(x) for x in v): inf_count += 1
                    else:
                        mag = math.sqrt(sum(x*x for x in v))
                        magnitudes.append(mag)
            
            if magnitudes:
                min_v = min(magnitudes)
                max_v = max(magnitudes)
                avg_v = sum(magnitudes) / len(magnitudes)
                status_str = f"min={min_v:.3f}, max={max_v:.3f}, avg={avg_v:.3f}"
            else:
                status_str = "empty"
            
            err_str = ""
            if nan_count > 0: err_str += f" [🚨 {nan_count} NaNs!]"
            if inf_count > 0: err_str += f" [⚠️ {inf_count} Infs!]"
            type_lbl = "vector" if sz == 3 else "float" if sz == 1 else f"float[{sz}]"
            lines.append(f"  @{name} ({type_lbl}): {status_str}{err_str}")
        elif dt == hou.attribData.Int:
            lines.append(f"  @{name} (int)")
        else:
            lines.append(f"  @{name} (string)")

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

    # Main Tabbed Container
    ai_tabs = hou.FolderParmTemplate("ai_folder", "AI VEX Copilot v3.5", folder_type=hou.folderType.Tabs)

    # =========================================================================
    # TAB 1: 🪄 Generate (Daily Workflow & Core Engine)
    # =========================================================================
    tab_gen = hou.FolderParmTemplate("tab_generate", "🪄 Generate", folder_type=hou.folderType.Simple)

    prompt_parm = hou.StringParmTemplate(
        name="ai_prompt",
        label="Task Prompt",
        num_components=1,
        default_value=([""]),
        string_type=hou.stringParmType.Regular,
        help="Type your natural language procedural or FX task here.\nExample: 'Displace points along @N using curlnoise with frequency slider and color ramp'\nSupports attributes (@P, @v, @Cd, @N, @pscale) and UI channels (chf, chv, chramp)."
    )
    prompt_parm.setTags({"multiline": "1", "editor": "1"})

    # Context & Reasoning Toggles Row
    autodetect_parm = hou.ToggleParmTemplate(
        name="ai_autodetect",
        label="Auto-Detect Schema & Class",
        default_value=True,
        help="When enabled, automatically inspects upstream geometry schema (attributes, groups, bounding box, volume fields) and determines the target execution class (Point, Primitive, Detail, or Vertex)."
    )
    autodetect_parm.setJoinWithNext(True)

    reasoning_parm = hou.ToggleParmTemplate(
        name="ai_reasoning_mode",
        label="🧠 Deep Reasoning Mode (CoT)",
        default_value=False,
        help="🧠 Deep Reasoning Mode (CoT):\nWhen enabled, the AI generates a step-by-step mathematical reasoning blueprint (<think> trace) before writing code. Ideal for complex multi-pass algorithms, spatial packing, and custom physics solvers.\nWhen disabled, Turbo Mode generates pure VEX in 1-2s."
    )
    reasoning_parm.setJoinWithNext(True)

    compact_parm = hou.ToggleParmTemplate(
        name="ai_compact_mode",
        label="🗕 Compact View",
        default_value=False,
        help="🗕 Compact View:\nWhen enabled, minimizes the interface into a sleek, focused workspace by hiding secondary panels (FX Presets, Diagnostics, History, and Studio Tools)."
    )

    # Action Toolbar Row (Joined horizontally)
    gen_btn = hou.ButtonParmTemplate(
        name="ai_generate",
        label="🪄 Generate VEX",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_generate_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="🪄 Generate VEX:\nQueries qwen3-vex, compiles the code with live CITL error checking, and automatically creates scale-calibrated interactive UI parameter sliders on this node."
    )
    gen_btn.setJoinWithNext(True)

    refine_btn = hou.ButtonParmTemplate(
        name="ai_refine",
        label="🔄 Refine",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_refine_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="🔄 Refine / Iterate:\nModifies existing VEX code conversationally based on your new prompt instructions without losing prior functionality.\nExample: 'Make it faster and add velocity drag'."
    )
    refine_btn.setJoinWithNext(True)

    optimize_btn = hou.ButtonParmTemplate(
        name="ai_optimize",
        label="⚡ SIMD Optimize",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_optimize_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="⚡ Optimize SIMD:\nAutomatically refactors the VEX snippet for high-throughput SIMD parallel performance on multi-million point meshes (hoists loop invariants, vectorizes calculations, eliminates redundant functions)."
    )
    optimize_btn.setJoinWithNext(True)

    explain_btn = hou.ButtonParmTemplate(
        name="ai_explain",
        label="💡 Document",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_explain_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="💡 Explain & Document:\nAnnotates the VEX code with clean, educational inline comments and parameter docstrings without modifying executable logic."
    )

    sep_gen = hou.SeparatorParmTemplate("sep_gen")

    # Status & Benchmark Banner Row
    status_parm = hou.StringParmTemplate(
        name="ai_status",
        label="Status",
        num_components=1,
        default_value=(["Ready"]),
        string_type=hou.stringParmType.Regular,
        help="Displays real-time compilation status, 1-shot CITL repair feedback, or generation errors."
    )
    status_parm.setJoinWithNext(True)

    perf_parm = hou.StringParmTemplate(
        name="ai_perf",
        label="Cook Benchmark",
        num_components=1,
        default_value=(["Cook: --"]),
        string_type=hou.stringParmType.Regular,
        help="Displays live cook execution duration (in milliseconds), processed point count, and compute throughput (Million points / sec)."
    )

    tab_gen.addParmTemplate(prompt_parm)
    tab_gen.addParmTemplate(autodetect_parm)
    tab_gen.addParmTemplate(reasoning_parm)
    tab_gen.addParmTemplate(compact_parm)
    tab_gen.addParmTemplate(gen_btn)
    tab_gen.addParmTemplate(refine_btn)
    tab_gen.addParmTemplate(optimize_btn)
    tab_gen.addParmTemplate(explain_btn)
    tab_gen.addParmTemplate(sep_gen)
    tab_gen.addParmTemplate(status_parm)
    tab_gen.addParmTemplate(perf_parm)

    # =========================================================================
    # TAB 2: 📚 FX Presets & Variants
    # =========================================================================
    tab_presets = hou.FolderParmTemplate("tab_presets", "📚 FX Presets", folder_type=hou.folderType.Simple)
    tab_presets.setConditional(hou.parmCondType.HideWhen, "{ ai_compact_mode == 1 }")

    preset_items = list(_FX_PRESETS.keys())
    preset_labels = [_FX_PRESETS[k]["label"] for k in preset_items]
    preset_menu = hou.MenuParmTemplate(
        name="ai_preset_menu",
        label="Procedural Recipe",
        menu_items=preset_items,
        menu_labels=preset_labels,
        default_value=0,
        help="Choose from 11 verified mathematical and simulation presets."
    )
    preset_menu.setJoinWithNext(True)

    load_preset_btn = hou.ButtonParmTemplate(
        name="ai_load_preset",
        label="📥 Load Recipe",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_load_preset_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Loads the selected mathematical/FX preset into this wrangle, sets target class, and generates parameters."
    )

    sep_fx = hou.SeparatorParmTemplate("sep_fx")

    # A/B Variant Comparison (Collapsible)
    variant_folder = hou.FolderParmTemplate(
        name="ai_variant_folder",
        label="🌿 A/B Variant Audition & Branching",
        folder_type=hou.folderType.Collapsible
    )

    variant_parm = hou.IntParmTemplate(
        name="ai_variant",
        label="Audition Variant",
        num_components=1,
        default_value=(0,),
        menu_items=("0", "1"),
        menu_labels=("Variant A", "Variant B"),
        item_generator_script="",
        menu_type=hou.menuType.Normal,
        help="Toggle between Variant A and Variant B in real time."
    )
    variant_parm.setScriptCallback("import houdini_ai_wrangle; houdini_ai_wrangle.on_variant_changed(kwargs)")
    variant_parm.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    variant_parm.setJoinWithNext(True)

    fork_btn = hou.ButtonParmTemplate(
        name="ai_fork_branch",
        label="🌿 Fork to Branch Node & Switch",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_fork_branch_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Duplicates this node into a sibling with Variant B, connecting both to a Switch SOP."
    )

    snip_a = hou.StringParmTemplate("ai_snippet_a", "Snippet A", 1, default_value=([""]), tags={"hide": "1"})
    snip_b = hou.StringParmTemplate("ai_snippet_b", "Snippet B", 1, default_value=([""]), tags={"hide": "1"})

    variant_folder.addParmTemplate(variant_parm)
    variant_folder.addParmTemplate(fork_btn)
    variant_folder.addParmTemplate(snip_a)
    variant_folder.addParmTemplate(snip_b)

    tab_presets.addParmTemplate(preset_menu)
    tab_presets.addParmTemplate(load_preset_btn)
    tab_presets.addParmTemplate(sep_fx)
    tab_presets.addParmTemplate(variant_folder)

    # =========================================================================
    # TAB 3: 🛡️ Diagnostics & Viewport
    # =========================================================================
    tab_diag = hou.FolderParmTemplate("tab_diagnostics", "🛡️ Diagnostics", folder_type=hou.folderType.Simple)
    tab_diag.setConditional(hou.parmCondType.HideWhen, "{ ai_compact_mode == 1 }")

    sanitize_btn = hou.ButtonParmTemplate(
        name="ai_sanitize_guards",
        label="🛡️ Sanitize NaNs & Infs",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_sanitize_guards_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Refactors the code to add protective mathematical clamps on trig, division, and sqrt."
    )
    sanitize_btn.setJoinWithNext(True)

    stats_btn = hou.ButtonParmTemplate(
        name="ai_inspect_stats",
        label="📊 Inspect Attrib Stats",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_inspect_stats_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Scans geometry attributes, computing min, max, average, and reporting any corrupt NaN/Inf floats."
    )

    sep_diag = hou.SeparatorParmTemplate("sep_diag")

    # Collapsible Viewport Visualizers
    vis_folder = hou.FolderParmTemplate(
        name="ai_vis_folder",
        label="👁️ Viewport Visualizers (Vectors & Heatmaps)",
        folder_type=hou.folderType.Collapsible
    )

    vis_vec_toggle = hou.ToggleParmTemplate(
        name="ai_vis_vector_toggle",
        label="Show 3D Vectors",
        default_value=False,
        help="Enables 3D vector visualizer in viewport."
    )
    vis_vec_toggle.setScriptCallback("import houdini_ai_wrangle; houdini_ai_wrangle.on_vis_vector_toggle(kwargs)")
    vis_vec_toggle.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    vis_vec_toggle.setJoinWithNext(True)

    vis_vec_attr = hou.StringParmTemplate(
        name="ai_vis_vector_attr",
        label="Vector Attrib",
        num_components=1,
        default_value=(["v"]),
        help="Vector attribute to display (e.g. v, N, tangentu)."
    )

    vis_col_toggle = hou.ToggleParmTemplate(
        name="ai_vis_color_toggle",
        label="Show Heatmap",
        default_value=False,
        help="Colors geometry according to attribute magnitude."
    )
    vis_col_toggle.setScriptCallback("import houdini_ai_wrangle; houdini_ai_wrangle.on_vis_color_toggle(kwargs)")
    vis_col_toggle.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    vis_col_toggle.setJoinWithNext(True)

    vis_col_attr = hou.StringParmTemplate(
        name="ai_vis_color_attr",
        label="Heatmap Attrib",
        num_components=1,
        default_value=(["speed"]),
        help="Float attribute to display as heatmap."
    )

    vis_folder.addParmTemplate(vis_vec_toggle)
    vis_folder.addParmTemplate(vis_vec_attr)
    vis_folder.addParmTemplate(vis_col_toggle)
    vis_folder.addParmTemplate(vis_col_attr)

    tab_diag.addParmTemplate(sanitize_btn)
    tab_diag.addParmTemplate(stats_btn)
    tab_diag.addParmTemplate(sep_diag)
    tab_diag.addParmTemplate(vis_folder)

    # =========================================================================
    # TAB 4: ⏳ History & Reasoning (Collapsible & Minimizable)
    # =========================================================================
    tab_hist = hou.FolderParmTemplate("tab_history", "⏳ History", folder_type=hou.folderType.Simple)
    tab_hist.setConditional(hou.parmCondType.HideWhen, "{ ai_compact_mode == 1 }")

    # Quick Action Toolbar for minimizing / expanding panels
    collapse_btn = hou.ButtonParmTemplate(
        name="ai_collapse_history_all",
        label="🗕 Minimize All",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_collapse_history_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Minimize both the Version History stack and Reasoning Monologue panels into sleek accordion bars."
    )
    collapse_btn.setJoinWithNext(True)

    expand_btn = hou.ButtonParmTemplate(
        name="ai_expand_history_all",
        label="🗖 Expand All",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_expand_history_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Expand both the Version History stack and Reasoning Monologue panels."
    )

    sep_hist_top = hou.SeparatorParmTemplate("sep_hist_top")

    # Collapsible Version History Stack
    hist_folder = hou.FolderParmTemplate(
        name="ai_history_folder",
        label="⏳ Time Machine Version History",
        folder_type=hou.folderType.Collapsible
    )

    prev_btn = hou.ButtonParmTemplate(
        name="ai_prev_version",
        label="◀ Prev Version",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_prev_version_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="◀ Prev Version:\nRolls back non-destructively to the previous working VEX iteration in the Time Machine history stack."
    )
    prev_btn.setJoinWithNext(True)

    version_info_parm = hou.StringParmTemplate(
        name="ai_version_info",
        label="Version",
        num_components=1,
        default_value=(["v1 / 1 (Initial)"]),
        string_type=hou.stringParmType.Regular,
        help="Displays current active version number, total recorded versions, and timestamp."
    )
    version_info_parm.setJoinWithNext(True)

    next_btn = hou.ButtonParmTemplate(
        name="ai_next_version",
        label="▶ Next Version",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_next_version_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="▶ Next Version:\nNavigates forward to the next recorded VEX iteration in the Time Machine history stack."
    )

    history_json_parm = hou.StringParmTemplate(
        name="ai_history_json",
        label="History Data",
        num_components=1,
        default_value=(["[]"]),
        string_type=hou.stringParmType.Regular
    )
    history_json_parm.setTags({"hide": "1"})

    hist_folder.addParmTemplate(prev_btn)
    hist_folder.addParmTemplate(version_info_parm)
    hist_folder.addParmTemplate(next_btn)
    hist_folder.addParmTemplate(history_json_parm)

    # Collapsible Reasoning Monologue (Chain of Thought)
    thought_folder = hou.FolderParmTemplate(
        name="ai_thought_folder",
        label="🧠 Reasoning Monologue (Chain of Thought)",
        folder_type=hou.folderType.Collapsible
    )

    thought_parm = hou.StringParmTemplate(
        name="ai_thought_trace",
        label="Reasoning Trace",
        num_components=1,
        default_value=(["No thought trace recorded yet."]),
        string_type=hou.stringParmType.Regular,
        tags={"editor": "1", "multiline": "1"},
        help="Displays the AI's internal Chain-of-Thought reasoning monologue, vector space analysis, and mathematical blueprint generated during Deep Reasoning Mode."
    )
    thought_folder.addParmTemplate(thought_parm)

    tab_hist.addParmTemplate(collapse_btn)
    tab_hist.addParmTemplate(expand_btn)
    tab_hist.addParmTemplate(sep_hist_top)
    tab_hist.addParmTemplate(hist_folder)
    tab_hist.addParmTemplate(thought_folder)

    # =========================================================================
    # TAB 5: 🛠️ Studio Tools
    # =========================================================================
    tab_tools = hou.FolderParmTemplate("tab_tools", "🛠️ Studio Tools", folder_type=hou.folderType.Simple)
    tab_tools.setConditional(hou.parmCondType.HideWhen, "{ ai_compact_mode == 1 }")

    help_btn = hou.ButtonParmTemplate(
        name="ai_generate_help",
        label="📝 Generate Help Card",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_generate_help_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Generates an official SideFX documentation card explaining inputs, algorithms, and parameters."
    )
    help_btn.setJoinWithNext(True)

    export_btn = hou.ButtonParmTemplate(
        name="ai_export_header",
        label="💾 Export to VEX Library (.h)",
        script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_export_header_clicked(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
        help="Wraps snippet into a clean VEX header and saves to $HOUDINI_USER_PREF_DIR/vex/include/."
    )

    sep_tools = hou.SeparatorParmTemplate("sep_tools")

    model_info_parm = hou.StringParmTemplate(
        name="ai_model_info",
        label="🧠 Active Neural Model",
        num_components=1,
        default_value=([get_active_ai_model_display_string()]),
        string_type=hou.stringParmType.Regular,
        help="Displays the base LLM model and fine-tuned LoRA adapter currently loaded in the AI inference engine."
    )

    tab_tools.addParmTemplate(help_btn)
    tab_tools.addParmTemplate(export_btn)
    tab_tools.addParmTemplate(sep_tools)
    tab_tools.addParmTemplate(model_info_parm)

    # Assemble All 5 Tabs into Main Container
    ai_tabs.addParmTemplate(tab_gen)
    ai_tabs.addParmTemplate(tab_presets)
    ai_tabs.addParmTemplate(tab_diag)
    ai_tabs.addParmTemplate(tab_hist)
    ai_tabs.addParmTemplate(tab_tools)

    snippet_parm = ptg.find("snippet")
    if snippet_parm:
        ptg.insertBefore(snippet_parm, ai_tabs)
    else:
        ptg.append(ai_tabs)

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


def on_generate_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return

    prompt_parm = node.parm("ai_prompt")
    autodetect_parm = node.parm("ai_autodetect")
    reasoning_parm = node.parm("ai_reasoning_mode")
    thought_parm = node.parm("ai_thought_trace")
    status_parm = _get_status_parm(node)
    perf_parm = node.parm("ai_perf")
    model_info_parm = node.parm("ai_model_info")
    class_parm = node.parm("class")
    snippet_parm = node.parm("snippet")

    if model_info_parm:
        model_info_parm.set(get_active_ai_model_display_string())

    if prompt_parm is None or not prompt_parm.eval().strip():
        if hou.isUIAvailable():
            hou.ui.setStatusMessage("Please enter an AI prompt description first.", severity=hou.severityType.Warning)
        return

    task = prompt_parm.eval().strip()
    is_reasoning = bool(reasoning_parm and reasoning_parm.eval())
    geo_context = introspect_geometry(node)

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
                if healthy:
                    status_parm.set(f"Compiled [{mode_label}] ({gen_time:.2f}s).")
                else:
                    status_parm.set(f"Compiled [{mode_label}]. {health_msg}")
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
    node = _extract_node(kwargs)
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

            # Sync active variant slot
            variant_parm = node.parm("ai_variant")
            if variant_parm:
                slot = "ai_snippet_b" if variant_parm.eval() == 1 else "ai_snippet_a"
                if node.parm(slot):
                    node.parm(slot).set(vex_code)

            # Geometry health scan for NaNs/Infs
            healthy, health_msg = scan_geometry_health(node)

            if status_parm:
                if healthy:
                    status_parm.set(f"Refined ({gen_time:.2f}s).")
                else:
                    status_parm.set(f"Refined ({gen_time:.2f}s). {health_msg}")
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
    for p in ("ai_history_folder", "ai_thought_folder"):
        parm = node.parm(p)
        if parm:
            parm.set(0)


def on_expand_history_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    for p in ("ai_history_folder", "ai_thought_folder"):
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
    variant_idx = variant_parm.eval()
    snippet_parm = node.parm("snippet")
    if not snippet_parm:
        return

    snip_a = node.parm("ai_snippet_a")
    snip_b = node.parm("ai_snippet_b")
    curr_code = snippet_parm.eval()

    if variant_idx == 1:
        if snip_a and curr_code:
            snip_a.set(curr_code)
        target_code = snip_b.eval() if snip_b else ""
    else:
        if snip_b and curr_code:
            snip_b.set(curr_code)
        target_code = snip_a.eval() if snip_a else ""

    if target_code:
        snippet_parm.set(target_code)
        sync_spare_parameters(node, target_code)
        force_refresh_wrangle(node)
        status_parm = _get_status_parm(node)
        if status_parm:
            status_parm.set(f"Active: Variant {'B' if variant_idx==1 else 'A'}.")


def on_fork_branch_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    parent = node.parent()
    if not parent:
        return

    with hou.undos.group("Fork AI Wrangle Variant"):
        snip_a = node.parm("ai_snippet_a").eval() if node.parm("ai_snippet_a") and node.parm("ai_snippet_a").eval() else node.parm("snippet").eval()
        snip_b = node.parm("ai_snippet_b").eval() if node.parm("ai_snippet_b") else ""

        if not snip_b:
            if hou.isUIAvailable():
                hou.ui.displayMessage("Variant B is currently empty. Generate or paste code into Variant B first.", severity=hou.severityType.Warning)
            return

        fork_name = f"{node.name()}_variantB"
        fork = parent.createNode(node.type().name(), fork_name)
        fork.copy(node)
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


def on_generate_help_clicked(kwargs):
    node = _extract_node(kwargs)
    if not node:
        return
    prompt = node.parm("ai_prompt").eval() if node.parm("ai_prompt") else "Procedural VEX Node"
    snippet = node.parm("snippet").eval() if node.parm("snippet") else ""
    class_name = node.parm("class").evalAsString() if node.parm("class") else "point"
    channels = parse_vex_channels(snippet)

    input_descs = []
    for i in range(4):
        inp = node.input(i)
        if inp:
            input_descs.append(f"Input {i}: Connected to `{inp.name()}` ({inp.type().name()})")

    doc_text = f"""=== {node.name()} (AI Attribute Wrangle) ===

Overview:
  Prompt: {prompt}
  Execution Class: {class_name} wrangle

Inputs:
{chr(10).join('  - ' + d for d in input_descs) if input_descs else '  - No upstream inputs connected.'}

Interactive Parameters:
"""
    for ch_name, ch_type in channels.items():
        doc_text += f"  - {ch_name} ({ch_type})\n"

    doc_text += f"""
VEX Snippet:
{snippet}
"""
    if hou.isUIAvailable():
        hou.ui.displayMessage(doc_text, title=f"Documentation: {node.name()}", severity=hou.severityType.Message)
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

    guard_name = f"__{func_name.upper()}_H__"
    header_content = f"""#ifndef {guard_name}
#define {guard_name}

// ============================================================================
//  Houdini AI VEX Library: {func_name}
//  Generated from: {node.path()}
//  Date: {time.strftime("%Y-%m-%d %H:%M:%S")}
// ============================================================================

void {func_name}(int input_geo) {{
{chr(10).join('    ' + line for line in snippet.splitlines())}
}}

#endif // {guard_name}
"""

    try:
        with open(header_path, "w", encoding="utf-8") as f:
            f.write(header_content)
        
        include_code = f'#include <{func_name}.h>'
        try:
            hou.ui.copyTextToClipboard(include_code)
        except Exception:
            pass

        msg = (
            f"✅ Header exported successfully!\n\n"
            f"File: {header_path}\n\n"
            f"Usage in any wrangle:\n"
            f"   {include_code}\n"
            f"   {func_name}(0);\n\n"
            f"(Include directive copied to clipboard)"
        )
        if hou.isUIAvailable():
            hou.ui.displayMessage(msg, title="VEX Header Exported", severity=hou.severityType.Message)
    except Exception as e:
        if hou.isUIAvailable():
            hou.ui.displayMessage(f"Failed to export header:\n{e}", severity=hou.severityType.Error)


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
