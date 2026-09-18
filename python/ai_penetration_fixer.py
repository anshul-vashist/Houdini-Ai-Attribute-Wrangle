# -*- coding: utf-8 -*-
"""
AI Penetration Fixer - Geometry Diagnostics, Neural Doctor & Solver Controller
=============================================================================
Analyzes cloth and collision geometric intersections, computes penetration
metrics, communicates with local Qwen3-8B-Houdini-VEX neural engine, and
configures the deterministic VEX solver.

Zero Cloud - 100% Local Offline Inference (Port 58421).
SideFX Houdini 20.0, 20.5, 21.0+ compatible.
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request

try:
    import hou
except ImportError:
    hou = None

try:
    import engine_manager
except ImportError:
    engine_manager = None


def get_ai_engine():
    if engine_manager is None:
        return None
    if hasattr(engine_manager, "get_engine_manager"):
        return engine_manager.get_engine_manager()
    return engine_manager.EngineManager()


def consult_ai_doctor(node, reasoning_mode: bool = False) -> str:
    """
    Extracts live simulation telemetry from the cloth and collider,
    sends it to the local fine-tuned Qwen3-8B model on port 58421,
    and populates the AI Diagnosis report on the HDA.
    """
    if node is None:
        return "Error: Node is None"

    cloth_input = node.input(0)
    col_input = node.input(1)

    if cloth_input is None or col_input is None:
        msg = "⚠️ Connect both Cloth (Input 1) and Collision (Input 2) to consult the AI Doctor."
        if node.parm("ai_diagnosis"):
            node.parm("ai_diagnosis").set(msg)
        return msg

    # 1. Gather Telemetry
    hud_node = node.node("live_hud_diagnostics")
    if hud_node:
        try:
            hud_node.cook(force=True)
            g_stats = hud_node.geometry()
            pen_count = g_stats.attribValue("pen_count") if g_stats.findGlobalAttrib("pen_count") else 0
            max_d = g_stats.attribValue("max_depth") if g_stats.findGlobalAttrib("max_depth") else 0.0
            avg_d = g_stats.attribValue("avg_depth") if g_stats.findGlobalAttrib("avg_depth") else 0.0
            edge_len = g_stats.attribValue("auto_avg_edge") if g_stats.findGlobalAttrib("auto_avg_edge") else 0.05
        except Exception:
            pen_count, max_d, avg_d, edge_len = 0, 0.0, 0.0, 0.05
    else:
        pen_count, max_d, avg_d, edge_len = 0, 0.0, 0.0, 0.05

    g_cloth = cloth_input.geometry()
    tot_pts = len(g_cloth.points()) if g_cloth else 0

    # Detect upstream solver
    upstream = cloth_input
    solver_name = "Generic Surface / Deformed Cloth"
    while upstream:
        type_name = upstream.type().name().lower()
        if "vellum" in type_name:
            solver_name = f"Vellum Solver ('{upstream.name()}')"
            break
        upstream = upstream.input(0) if upstream.inputs() else None

    # Check incoming velocity
    has_vel = bool(g_cloth and g_cloth.findPointAttrib("v"))
    vel_str = "Present" if has_vel else "None"

    # Collider description
    g_col = col_input.geometry()
    col_type = col_input.type().description()
    col_prims = len(g_col.prims()) if g_col else 0

    # Update UI to waiting state
    if node.parm("ai_diagnosis"):
        node.parm("ai_diagnosis").set("⏳ Telemetry sent to Qwen3-8B Neural Engine (Port 58421)... Analyzing 3D collision physics...")

    # 2. Build Model Prompts
    system_prompt = """You are an expert SideFX Houdini Technical Director and Simulation Doctor specializing in Vellum cloth dynamics and VEX geometry solvers.
Analyze the provided cloth simulation telemetry.
Provide a clear, professional diagnostic breakdown with 3 sections:
1. 🩺 ROOT-CAUSE DIAGNOSIS: Why the cloth penetrated the collider (physics, substeps, thickness).
2. ⚙️ UPSTREAM VELLUM FIX: Exact settings to adjust on the upstream vellumsolver / constraints.
3. 🛡️ RECOMMENDED POST-FIX: Suggested margin scale and smoothing factor for the AI Penetration Fixer.
Keep your analysis concise, actionable, and formatted cleanly in markdown."""

    user_prompt = f"""SCENE TELEMETRY:
- Upstream Solver: {solver_name}
- Total Cloth Vertices: {tot_pts:,}
- Penetrating Points: {pen_count:,} ({(pen_count / max(tot_pts, 1)) * 100:.1f}% of mesh)
- Max Penetration Depth: {max_d * 100:.2f} cm ({max_d:.4f} m)
- Average Penetration Depth: {avg_d * 100:.2f} cm ({avg_d:.4f} m)
- Cloth Average Edge Length: {edge_len * 100:.2f} cm ({edge_len:.4f} m)
- Incoming Velocity: {vel_str}
- Collider: {col_type} ({col_prims:,} primitives)

Diagnose this penetration and provide your expert technical recommendation."""

    em = get_ai_engine()
    base_url = em.base_url if em else "http://127.0.0.1:58421"
    api_key = em.get_api_key() if em else None

    asst_prefix = "<|im_start|>assistant\n<think>\n" if reasoning_mode else "<|im_start|>assistant\n<think>\n</think>\n"
    payload = {
        "prompt": f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{user_prompt}<|im_end|>\n{asst_prefix}",
        "n_predict": 500,
        "temperature": 0.2 if reasoning_mode else 0.1,
        "top_p": 0.95,
        "stop": ["<|im_end|>", "<|endoftext|>"],
    }

    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(f"{base_url}/completion", data=json.dumps(payload).encode("utf-8"), headers=headers)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw = data.get("content", "").strip()

            if reasoning_mode and "<think>" not in raw:
                raw = "<think>\n" + raw

            if node.parm("ai_diagnosis"):
                node.parm("ai_diagnosis").set(raw)

            # Extract auto-tuning suggestions
            margin_val = 1.2 if max_d > 0.1 else (1.0 if max_d > 0.02 else 0.8)
            smooth_val = 0.6 if max_d > 0.05 else 0.4
            if node.parm("margin_mult"):
                node.parm("margin_mult").set(margin_val)
            if node.parm("smoothing"):
                node.parm("smoothing").set(smooth_val)

            return raw

    except Exception as exc:
        err_msg = f"❌ AI Engine Connection Error: {exc}\nEnsure llama-server.exe is running on port 58421."
        if node.parm("ai_diagnosis"):
            node.parm("ai_diagnosis").set(err_msg)
        return err_msg


def apply_ai_tuning(node):
    """
    Applies the recommended solver parameters directly onto the node.
    """
    if node is None:
        return
    consult_ai_doctor(node, reasoning_mode=False)
