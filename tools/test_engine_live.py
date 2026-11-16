"""
Live engine test (needs the GPU for ~1 minute). Run with hython:

    hython tools/test_engine_live.py            # phase 1: start, auth, generate, cancel
    hython tools/test_engine_live.py --orphan   # phase 2 helper: start engine, then hard-exit

Phase 1 writes results to tools/test_engine_live.out.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

import hou

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "python"))
os.environ.setdefault("AI_WRANGLE_ROOT", ROOT)
import houdini_ai_wrangle as hw  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_engine_live.out")
lines = []


def check(name, ok, detail=""):
    lines.append(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))


def get(url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, None


if "--orphan" in sys.argv:
    hw.ensure_embedded_engine()
    pid = hw._engine_singleton.process.pid
    open(OUT + ".pid", "w").write(str(pid))
    os._exit(9)  # hard exit: no atexit handlers run (simulates a Houdini crash)

t0 = time.time()
ok = hw.ensure_embedded_engine()
mgr = hw._engine_singleton
check("engine starts with the default (newest) model", ok and mgr and mgr.active_model_name.startswith("Qwen3-8B-Houdini-VEX-v49"),
      getattr(mgr, "active_model_name", hw._engine_error))
lines.append(f"     load time {time.time() - t0:.1f}s on port {getattr(mgr, 'port', None)}")
base = f"http://127.0.0.1:{mgr.port}"
payload = json.dumps({"messages": [{"role": "user", "content": "hi"}], "max_tokens": 4}).encode()
code_noauth, _ = get(base + "/v1/chat/completions", {"Content-Type": "application/json"}, payload)
check("requests without the session key are rejected", code_noauth == 401, str(code_noauth))
thought, code = hw.generate_vex("Store the distance of each point from the origin in a float attribute dist.",
                                context="point wrangle", enable_rag=True)
check("real generation through query_llm", "dist" in code and "length" in code, code[:120])
geo = hou.node("/obj").createNode("geo")
g = geo.createNode("sphere")
n = geo.createNode("ai_attribwrangle")
n.setInput(0, g)
applied, ok2, err = hw._apply_generated_vex(n, "distance from origin", "point wrangle", code, "")
check("generated code compiles on the HDA", ok2 and n.geometry().findPointAttrib("dist") is not None, str(err)[:120])

# cancellation of a model load: callback raises on its first call
hw._shutdown_embedded_engine()
from engine_manager import EngineManager  # noqa: E402
m2 = EngineManager()
calls = {"n": 0}


def cancel_now():
    calls["n"] += 1
    raise hou.OperationInterrupted()


bin_path = os.path.join(ROOT, "bin", "llama-server.exe")
t1 = time.time()
started = m2.start_embedded_engine(bin_path, hw._default_model_path(), wait_callback=cancel_now)
check("model load can be cancelled", (not started) and m2.last_error == "Model loading cancelled." and m2.process is None
      and time.time() - t1 < 10, f"{started} {m2.last_error} {time.time() - t1:.1f}s")
open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
