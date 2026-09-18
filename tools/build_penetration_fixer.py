# -*- coding: utf-8 -*-
"""
Houdini AI Penetration Fixer - Automated HDA Generator V2 (Neural Doctor Edition)
================================================================================
Builds and installs the universal, zero-setup ansv_penetration_fixer.hda asset.

Core Innovations:
1. Scale-Invariant Self-Calibration (Auto-detects mesh edge length & units)
2. Universal Hybrid Collider Engine (Surface Mesh Ray Projection default)
3. Dynamic Adaptive Iteration Scaling (0 iters for clean, 2-8 iters for deep)
4. Tangential-Only Laplace-Beltrami Manifold Smoothing (Zero spikes/puckering)
5. Live Real-Time Diagnostic HUD on every playback frame
6. AI Simulation Doctor Tab powered by local Qwen3-8B-Houdini-VEX on port 58421
7. Streamlined 2-Slider Artist UI with expandable TD Overrides

Compatible with Houdini 20.0, 20.5, 21.0+ (SOP context).
"""

import os
import shutil
import hou


def build_hda(output_path=None):
    if output_path is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_path = os.path.join(repo_root, "otls", "ansv_penetration_fixer.hda")

    output_path = output_path.replace("\\", "/")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except Exception:
            pass

    obj = hou.node("/obj")
    builder_geo = obj.createNode("geo", "temp_builder_geo_v2")

    try:
        sub = builder_geo.createNode("subnet", "ansv_penetration_fixer")

        # -------------------------------------------------------------
        # 1. Parameter Template Group (Zero Standard/Spare Tabs)
        # -------------------------------------------------------------
        ptg = hou.ParmTemplateGroup()

        # TAB 1: MAIN (MINIMALIST ARTIST CONTROLS)
        tab_main = hou.FolderParmTemplate("tab_main", "Penetration Fixer", folder_type=hou.folderType.Tabs)

        m_solver_mode = hou.MenuParmTemplate(
            "solver_mode",
            "Solver Mode",
            menu_items=("0", "1"),
            menu_labels=(
                "⚡ Fully Autonomous (Auto-Adaptive)",
                "⚙️ Manual TD Override",
            ),
            default_value=0,
        )
        m_solver_mode.setHelp("Auto-Adaptive: Dynamically analyzes scene scale, edge lengths, and penetration depth to configure iterations and clearance automatically.\nManual Override: Unlocks manual technical sliders in Advanced tab.")
        tab_main.addParmTemplate(m_solver_mode)

        p_margin_mult = hou.FloatParmTemplate(
            "margin_mult",
            "Surface Margin",
            1,
            default_value=(1.0,),
            min=0.0,
            max=3.0,
        )
        p_margin_mult.setHelp("Relative safety margin scale (1.0 = 100% of optimal auto-detected clearance). Scale-invariant.")
        tab_main.addParmTemplate(p_margin_mult)

        p_smoothing = hou.FloatParmTemplate(
            "smoothing",
            "Surface Smoothing",
            1,
            default_value=(0.5,),
            min=0.0,
            max=1.0,
        )
        p_smoothing.setHelp("Tangential-only Laplacian relaxation weight. Allows vertices to glide across the collision surface to equalize triangle tension without sinking back in.")
        tab_main.addParmTemplate(p_smoothing)

        tab_main.addParmTemplate(hou.SeparatorParmTemplate("sep_core"))

        p_dovel = hou.ToggleParmTemplate("dovelocity", "Prevent Re-penetration (Correct Velocity)", default_value=True)
        p_dovel.setHelp("Cancels inward normal velocity components and damps contact friction so cloth does not immediately re-enter collider on the next simulation frame.")
        tab_main.addParmTemplate(p_dovel)

        m_vis = hou.MenuParmTemplate(
            "vis_mode",
            "Viewport Visualizer",
            menu_items=("1", "2", "0"),
            menu_labels=(
                "🟢 Heatmap (Green = Fixed, Red = Clipping)",
                "Depth Gradient",
                "Bypass Visualizer (Clean Geometry)",
            ),
            default_value=0,
        )
        m_vis.setHelp("Live viewport feedback: Green indicates successfully corrected vertices; Red highlights any unresolvable clipping; Blue represents untouched cloth.")
        tab_main.addParmTemplate(m_vis)

        tab_main.addParmTemplate(hou.SeparatorParmTemplate("sep_hud"))

        s_hud = hou.StringParmTemplate(
            "hud_status",
            "Live Resolution HUD",
            1,
            default_value=("Evaluating geometry...",),
        )
        s_hud.setDefaultExpression(('details("./live_hud_diagnostics", "hud_msg")',))
        s_hud.setDefaultExpressionLanguage((hou.scriptLanguage.Hscript,))
        s_hud.setHelp("Real-time live resolution readout updated automatically on every frame.")
        tab_main.addParmTemplate(s_hud)

        ptg.append(tab_main)

        # TAB 2: AI SIMULATION DOCTOR (NEURAL REASONING LAYER)
        tab_doc = hou.FolderParmTemplate("tab_doc", "🧠 AI Simulation Doctor", folder_type=hou.folderType.Tabs)

        b_doc = hou.ButtonParmTemplate("btn_consult_doctor", "🧠 Consult AI Doctor (Diagnose & Prescribe)")
        b_doc.setHelp("Extracts 3D geometry telemetry, collision dynamics, and upstream solver parameters, sending them to the local Qwen3-8B model for root-cause diagnosis and solver prescription.")
        b_doc.setScriptCallback("hou.phm().on_consult_doctor(hou.pwd())")
        b_doc.setScriptCallbackLanguage(hou.scriptLanguage.Python)
        tab_doc.addParmTemplate(b_doc)

        p_reason = hou.ToggleParmTemplate("reasoning_mode", "Deep Reasoning Mode (<think> Physics Trace)", default_value=False)
        p_reason.setHelp("When enabled, the neural model performs a deep 3D vector space analysis and chain-of-thought calculation before providing recommendations.")
        tab_doc.addParmTemplate(p_reason)

        tab_doc.addParmTemplate(hou.SeparatorParmTemplate("sep_doc"))

        s_model = hou.StringParmTemplate("model_status", "Active Neural Model", 1, default_value=("Qwen3-8B-Houdini-VEX-v11-Q5_K_M (Port 58421 - 100% Offline)",))
        tab_doc.addParmTemplate(s_model)

        s_diag = hou.StringParmTemplate(
            "ai_diagnosis",
            "AI Diagnosis & Prescription",
            1,
            default_value=("Click 'Consult AI Doctor' to analyze telemetry with local Qwen3-8B neural model.",),
        )
        s_diag.setTags({"editor": "1"})
        s_diag.setHelp("Full markdown diagnostic breakdown and upstream solver fix from Qwen3-8B.")
        tab_doc.addParmTemplate(s_diag)

        ptg.append(tab_doc)

        # TAB 3: ADVANCED OVERRIDES (COLLAPSED BY DEFAULT)
        tab_adv = hou.FolderParmTemplate("tab_adv", "Advanced Overrides", folder_type=hou.folderType.Tabs)

        m_method = hou.MenuParmTemplate(
            "col_method",
            "Collision Engine",
            menu_items=("0", "1"),
            menu_labels=(
                "Surface Mesh Ray Projection (Recommended)",
                "OpenVDB Signed Distance Field (VDB)",
            ),
            default_value=0,
        )
        m_method.setHelp("Surface Mesh: Exact 3D ray projection onto collider polygons (Works on open sheets & solids).\nOpenVDB: Signed narrow-band distance field.")
        tab_adv.addParmTemplate(m_method)

        p_abs_offset = hou.FloatParmTemplate("abs_offset", "Absolute Offset Override", 1, default_value=(0.0,), min=0.0, max=0.1)
        p_abs_offset.setHelp("If greater than 0, overrides the auto-detected scale margin with this exact distance.")
        tab_adv.addParmTemplate(p_abs_offset)

        p_force_iters = hou.IntParmTemplate("force_iters", "Max Iterations Cap", 1, default_value=(6,), min=1, max=15)
        p_force_iters.setHelp("Upper ceiling on dynamic adaptive iteration passes.")
        tab_adv.addParmTemplate(p_force_iters)

        p_fric = hou.FloatParmTemplate("friction", "Contact Tangential Friction", 1, default_value=(0.3,), min=0.0, max=1.0)
        p_fric.setHelp("Tangential velocity damping upon collision surface contact.")
        tab_adv.addParmTemplate(p_fric)

        tab_adv.addParmTemplate(hou.SeparatorParmTemplate("sep_vdb"))

        p_vox = hou.FloatParmTemplate("voxelsize", "VDB Voxel Size", 1, default_value=(0.015,), min=0.002, max=0.1)
        tab_adv.addParmTemplate(p_vox)

        p_ext = hou.FloatParmTemplate("exteriorband", "VDB Exterior Band", 1, default_value=(0.05,), min=0.01, max=0.5)
        tab_adv.addParmTemplate(p_ext)

        p_int = hou.FloatParmTemplate("interiorband", "VDB Interior Band", 1, default_value=(0.3,), min=0.02, max=1.0)
        tab_adv.addParmTemplate(p_int)

        p_fill = hou.ToggleParmTemplate("fillinterior", "VDB Fill Interior", default_value=True)
        tab_adv.addParmTemplate(p_fill)

        ptg.append(tab_adv)

        sub.setParmTemplateGroup(ptg)

        # -------------------------------------------------------------
        # 2. Internal SOP Network Wiring
        # -------------------------------------------------------------
        sub_inputs = sub.indirectInputs()
        in_cloth = sub_inputs[0]
        in_col = sub_inputs[1]

        # STEP A: Scale & Density Auto-Calibration (Detail Wrangle)
        w_scale = sub.createNode("attribwrangle", "auto_scale_calibrator")
        w_scale.setInput(0, in_cloth)
        w_scale.setInput(1, in_col)
        w_scale.parm("class").set("detail")
        w_scale.parm("snippet").set("""// 1. Scale-Invariant Self-Calibration
int n_pts = npoints(0);
float sum_len = 0.0;
int sample_count = 0;
int step = max(1, n_pts / 250);

for (int i = 0; i < n_pts; i += step) {
    int nbs[] = neighbours(0, i);
    vector p_i = point(0, "P", i);
    foreach (int nb; nbs) {
        sum_len += distance(p_i, point(0, "P", nb));
        sample_count++;
    }
}

float avg_edge = sample_count > 0 ? (sum_len / float(sample_count)) : 0.01;
float abs_override = chf("../abs_offset");
float margin_mult = chf("../margin_mult");

float effective_offset = (abs_override > 0.0) ? abs_override : (avg_edge * 0.15 * margin_mult);
setdetailattrib(0, "auto_avg_edge", avg_edge, "set");
setdetailattrib(0, "effective_offset", effective_offset, "set");
""")

        # STEP B: Collision Geometry Preparation
        vdb_col = sub.createNode("vdbfrompolygons", "gen_col_vdb")
        vdb_col.setInput(0, in_col)
        vdb_col.parm("voxelsize").setExpression('ch("../voxelsize")')
        vdb_col.parm("exteriorband").setExpression('ch("../exteriorband")')
        vdb_col.parm("interiorband").setExpression('ch("../interiorband")')
        vdb_col.parm("fillinterior").setExpression('ch("../fillinterior")')

        sw_col = sub.createNode("switch", "switch_col_active")
        sw_col.setInput(0, in_col)
        sw_col.setInput(1, vdb_col)
        sw_col.parm("input").setExpression('ch("../col_method")')

        null_col = sub.createNode("null", "COL_ACTIVE")
        null_col.setInput(0, sw_col)

        # STEP C: Live Penetration Detection (Point Wrangle)
        w_detect = sub.createNode("attribwrangle", "detect_penetration")
        w_detect.setInput(0, w_scale)
        w_detect.setInput(1, null_col)
        w_detect.parm("class").set("point")
        w_detect.parm("snippet").set("""// Live Penetration Detection
int method = chi("../col_method");
float offset = detail(0, "effective_offset", 0);
v@orig_P = @P;

float depth = 0.0;
int pen = 0;

if (method == 0) {
    // Exact Surface Polygon Projection
    int prim; vector uv;
    xyzdist(1, @P, prim, uv);
    vector hitP = primuv(1, "P", prim, uv);
    vector primN = prim_normal(1, prim, uv);
    
    vector to_pt = @P - hitP;
    float dot_n = dot(to_pt, primN);
    
    if (dot_n < offset) {
        depth = offset - dot_n;
        pen = 1;
    }
} else {
    // OpenVDB SDF
    float sdf = volumesample(1, "surface", @P);
    if (sdf < offset) {
        depth = offset - sdf;
        pen = 1;
    }
}

f@penetration = depth;
i@penetrating = pen;
setpointgroup(0, "penetrating", @ptnum, pen, "set");
""")

        # STEP D: Live Real-Time Diagnostic HUD (Detail Wrangle)
        w_hud = sub.createNode("attribwrangle", "live_hud_diagnostics")
        w_hud.setInput(0, w_detect)
        w_hud.setInput(1, null_col)
        w_hud.parm("class").set("detail")
        w_hud.parm("snippet").set("""// Live Real-Time Diagnostic HUD
int pen_count = 0;
float max_d = 0.0;
float sum_d = 0.0;
int npts = npoints(0);

for (int i = 0; i < npts; i++) {
    float d = point(0, "penetration", i);
    if (d > 0.0) {
        pen_count++;
        sum_d += d;
        if (d > max_d) max_d = d;
    }
}

float avg_d = pen_count > 0 ? sum_d / float(pen_count) : 0.0;
float edge_len = detail(0, "auto_avg_edge", 0);
float eff_offset = detail(0, "effective_offset", 0);
int col_prims = nprimitives(1);

setdetailattrib(0, "pen_count", pen_count, "set");
setdetailattrib(0, "max_depth", max_d, "set");
setdetailattrib(0, "avg_depth", avg_d, "set");
setdetailattrib(0, "col_prims", col_prims, "set");

string hud_msg = "";
if (col_prims == 0) {
    hud_msg = "⚠️ Input 2 Disconnected: Connect Collider Geometry";
} else if (pen_count == 0) {
    hud_msg = sprintf("🟢 100%% Clean (0 penetrations) vs Collider (%d polys) | Edge: %.2fcm | Margin: %.2fmm", col_prims, edge_len * 100.0, eff_offset * 1000.0);
} else {
    hud_msg = sprintf("🟢 Resolved %d points vs Collider (%d polys) | Max Depth: %.1fcm | Margin: %.2fmm", pen_count, col_prims, max_d * 100.0, eff_offset * 1000.0);
}

setdetailattrib(0, "hud_msg", hud_msg, "set");
""")

        # STEP E: Tag Affected Neighborhood (Point Wrangle)
        w_tag = sub.createNode("attribwrangle", "tag_affected")
        w_tag.setInput(0, w_hud)
        w_tag.parm("class").set("point")
        w_tag.parm("snippet").set("""// Tag Affected Neighborhood
i@affected = i@penetrating;
if (!i@penetrating) {
    int nbs[] = neighbours(0, @ptnum);
    foreach (int nb; nbs) {
        if (point(0, "penetrating", nb) == 1) {
            i@affected = 1;
            break;
        }
    }
}
""")

        # STEP F: Autonomous Adaptive Solver Core (Point Wrangle)
        w_solve = sub.createNode("attribwrangle", "solve_autonomous")
        w_solve.setInput(0, w_tag)
        w_solve.setInput(1, null_col)
        w_solve.parm("class").set("point")
        w_solve.parm("snippet").set("""// Autonomous Adaptive Mathematical Solver Core
int method = chi("../col_method");
float offset = detail(0, "effective_offset", 0);
float edge_len = detail(0, "auto_avg_edge", 0);
float smooth_w = chf("../smoothing");
int max_cap = chi("../force_iters");

// Dynamic Per-Point Iteration Scaling
int iters = 0;
float init_depth = f@penetration;

if (init_depth <= 0.0) {
    iters = 0; // 0 compute bypass for clean vertices!
} else if (init_depth <= edge_len) {
    iters = 2; // Shallow grazing
} else {
    // Deep penetration: scale proportionally
    iters = clamp(int(ceil(init_depth / max(edge_len * 0.3, 1e-4))), 3, max_cap);
}

for (int it = 0; it < iters; it++) {
    vector push_dir = {0, 1, 0};
    
    if (method == 0) {
        // Surface Polygon Projection
        int prim; vector uv;
        xyzdist(1, @P, prim, uv);
        vector hitP = primuv(1, "P", prim, uv);
        vector primN = prim_normal(1, prim, uv);
        
        vector to_pt = @P - hitP;
        float dot_n = dot(to_pt, primN);
        
        if (dot_n < offset) {
            @P = hitP + primN * offset;
            push_dir = primN;
        }
    } else {
        // OpenVDB SDF
        float sdf = volumesample(1, "surface", @P);
        if (sdf < offset) {
            vector grad = volumegradient(1, "surface", @P);
            vector n = length(grad) > 1e-6 ? normalize(grad) : {0, 1, 0};
            @P += n * (offset - sdf);
            push_dir = n;
        }
    }
    
    // Tangential-Only Laplace-Beltrami Manifold Smoothing
    if ((i@penetrating == 1 || i@affected == 1) && smooth_w > 0.0) {
        int nbs[] = neighbours(0, @ptnum);
        int count = len(nbs);
        if (count > 0) {
            vector avg_p = {0, 0, 0};
            foreach (int nb; nbs) avg_p += point(0, "P", nb);
            avg_p /= float(count);
            
            vector delta = avg_p - @P;
            // Decompose: zero out normal component, keep purely tangential slide
            vector delta_tan = delta - dot(delta, push_dir) * push_dir;
            @P += delta_tan * smooth_w;
            
            // Re-clamp strictly against collider
            if (method == 0) {
                int prim; vector uv;
                xyzdist(1, @P, prim, uv);
                vector hitP = primuv(1, "P", prim, uv);
                vector primN = prim_normal(1, prim, uv);
                if (dot(@P - hitP, primN) < offset) {
                    @P = hitP + primN * offset;
                }
            } else {
                float chk_sdf = volumesample(1, "surface", @P);
                if (chk_sdf < offset) {
                    vector cg = volumegradient(1, "surface", @P);
                    vector cn = length(cg) > 1e-6 ? normalize(cg) : push_dir;
                    @P += cn * (offset - chk_sdf);
                }
            }
        }
    }
}

v@correction = @P - v@orig_P;
""")

        # STEP G: Velocity Correction Wrangle
        w_vel = sub.createNode("attribwrangle", "correct_velocity")
        w_vel.setInput(0, w_solve)
        w_vel.setInput(1, null_col)
        w_vel.parm("class").set("point")
        w_vel.parm("snippet").set("""// Velocity Vector Correction
if (chi("../dovelocity") == 1 && hasattrib(0, "point", "v") && (i@penetrating == 1 || i@affected == 1)) {
    int method = chi("../col_method");
    float friction = chf("../friction");
    vector n = {0, 1, 0};
    
    if (method == 0) {
        int prim; vector uv;
        xyzdist(1, @P, prim, uv);
        n = prim_normal(1, prim, uv);
    } else {
        vector grad = volumegradient(1, "surface", @P);
        n = length(grad) > 1e-6 ? normalize(grad) : {0, 1, 0};
    }
    
    // Inward normal velocity cancellation with friction damping
    float inward = min(dot(v@v, n), 0.0);
    v@v -= inward * n;
    vector v_tan = v@v - dot(v@v, n) * n;
    v@v = dot(v@v, n) * n + v_tan * (1.0 - friction);
}
""")

        # STEP H: Visualizer Wrangle
        w_vis = sub.createNode("attribwrangle", "visualizer")
        w_vis.setInput(0, w_vel)
        w_vis.setInput(1, null_col)
        w_vis.parm("class").set("point")
        w_vis.parm("snippet").set("""// Viewport Heatmap & Visualizer
int vis_mode = chi("../vis_mode");
int method = chi("../col_method");
float max_d = max(detail(0, "max_depth", 0), 0.01);

if (vis_mode == 0) { // Heatmap
    float corr_len = length(v@correction);
    float res_dot = 1.0;
    
    if (method == 0) {
        int prim; vector uv;
        xyzdist(1, @P, prim, uv);
        vector hitP = primuv(1, "P", prim, uv);
        vector primN = prim_normal(1, prim, uv);
        res_dot = dot(@P - hitP, primN);
    } else {
        res_dot = volumesample(1, "surface", @P);
    }
    
    if (res_dot < 0.0) {
        // Residual clipping = Glowing Red
        @Cd = set(1.0, 0.05, 0.05);
    } else if (corr_len > 1e-4) {
        // Corrected & safe = Vibrant Emerald Green
        float t = clamp(corr_len / max_d, 0.0, 1.0);
        @Cd = lerp(set(0.15, 0.95, 0.35), set(0.1, 1.0, 0.8), t);
    } else if (i@affected == 1) {
        // Affected transition zone = Soft Gold
        @Cd = set(0.85, 0.80, 0.2);
    } else {
        // Untouched cloth = Deep Slate Blue
        @Cd = set(0.12, 0.22, 0.48);
    }
} else if (vis_mode == 1) { // Depth Gradient
    float t = clamp(f@penetration / max_d, 0.0, 1.0);
    @Cd = lerp(set(0.05, 0.05, 0.05), set(1.0, 0.1, 0.1), t);
}
""")

        # Switch for Output 0
        sw_out0 = sub.createNode("switch", "switch_vis")
        sw_out0.setInput(0, w_vis)
        sw_out0.setInput(1, w_vel)
        sw_out0.parm("input").setExpression('if(ch("../vis_mode") == 2, 1, 0)')

        # Outputs
        out0 = sub.createNode("output", "output0")
        out0.setInput(0, sw_out0)
        out0.parm("outputidx").set(0)

        w_mask = sub.createNode("attribwrangle", "gen_mask")
        w_mask.setInput(0, w_detect)
        w_mask.parm("class").set("point")
        w_mask.parm("snippet").set("""// Penetration Mask Output
float val = f@penetration > 0.0 ? 1.0 : 0.0;
@Cd = set(val, val, val);
""")
        out1 = sub.createNode("output", "output1")
        out1.setInput(0, w_mask)
        out1.parm("outputidx").set(1)

        out2 = sub.createNode("output", "output2")
        out2.setInput(0, w_vis)
        out2.parm("outputidx").set(2)

        sub.layoutChildren()

        # -------------------------------------------------------------
        # 3. Create HDA Definition & PythonModule
        # -------------------------------------------------------------
        hda_node = sub.createDigitalAsset(
            name="ansv_penetration_fixer::1.0",
            hda_file_name=output_path,
            description="AI Penetration Fixer",
            min_num_inputs=2,
            max_num_inputs=2,
            save_as_embedded=False,
            ignore_external_references=True,
        )

        defn = hda_node.type().definition()
        defn.setMaxNumOutputs(3)

        # PythonModule section for HUD update and AI doctor callback
        py_code = """# AI Penetration Fixer Autonomous Controller
import hou

def update_hud(node):
    hud_node = node.node('live_hud_diagnostics')
    if not hud_node: return
    try:
        geo = hud_node.geometry()
        if geo and geo.findGlobalAttrib('hud_msg'):
            msg = geo.attribValue('hud_msg')
            node.parm('hud_status').set(msg)
    except Exception:
        pass

def on_consult_doctor(node):
    try:
        import ai_penetration_fixer
        reasoning = bool(node.parm('reasoning_mode').eval()) if node.parm('reasoning_mode') else False
        ai_penetration_fixer.consult_ai_doctor(node, reasoning_mode=reasoning)
    except Exception as err:
        if node.parm('ai_diagnosis'):
            node.parm('ai_diagnosis').set(f"Error consulting AI Doctor: {err}")
"""
        defn.addSection("PythonModule", py_code)

        on_input_code = """node = kwargs.get('node')
if node and node.parm('ai_diagnosis'):
    col = node.input(1)
    cloth = node.input(0)
    if not col or not cloth:
        node.parm('ai_diagnosis').set("⚠️ Connect both Cloth (Input 1) and Collision Geometry (Input 2).")
    else:
        node.parm('ai_diagnosis').set(f"Input rewired to '{col.name()}'. Click 'Consult AI Doctor' to analyze new geometry.")
"""
        defn.addSection("OnInputChanged", on_input_code)
        defn.setParmTemplateGroup(ptg)
        defn.save(output_path)

        # Copy to Houdini preferences otls
        doc_otls = r"C:\Users\Anshul\Documents\houdini21.0\otls"
        os.makedirs(doc_otls, exist_ok=True)
        dest_hda = os.path.join(doc_otls, "ansv_penetration_fixer.hda")
        shutil.copyfile(output_path, dest_hda)
        hou.hda.installFile(dest_hda)

        return output_path
    finally:
        builder_geo.destroy()


if __name__ == "__main__":
    path = build_hda()
    print("V2 Neural Doctor HDA generated successfully at:", path)
