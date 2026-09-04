"""
=============================================================================
 Houdini VEX Micro-RAG Engine (1,115 Official Functions)
 Complete in-memory retrieval of every single SideFX VEX function signature,
 parameter types, return types, and context rules.
=============================================================================
"""

import os
import re
import json

_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "vex_1115_compact.json")

def load_1115_catalog():
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate_paths = [
        _DATA_FILE,
        os.path.join(pkg_dir, "data", "vex_1115_compact.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "vex_1115_compact.json"),
        os.path.join(os.getcwd(), "data", "vex_1115_compact.json"),
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

class VEXRAGEngine:
    def __init__(self):
        self.catalog = load_1115_catalog()

    def reload(self):
        self.catalog = load_1115_catalog()

    def retrieve_signatures_for_task(self, prompt: str, max_results: int = 6) -> list:
        p_lower = prompt.lower()
        matched_funcs = []

        # 1. Exact function name keyword matching
        for func_name in self.catalog.keys():
            pattern = rf"\b{re.escape(func_name)}\b"
            if re.search(pattern, p_lower):
                matched_funcs.append((func_name, 20))

        # 2. Semantic topic matching
        topic_triggers = {
            ("set attribute", "setpointattrib", "setprimattrib", "setdetailattrib", "set point", "set prim", "accumulate attribute", "write attribute"): 
                ["setpointattrib", "setprimattrib", "setdetailattrib", "addattrib", "setattribtypeinfo"],
            ("closest", "projection", "surface query", "distance to surface", "nearest surface"): 
                ["xyzdist", "primuv", "minpos", "surfacedist"],
            ("point cloud", "pc filter", "pc filter color", "pc import", "pointcloud"): 
                ["pcopen", "pciterate", "pcimport", "pcfilter", "pcclose", "pcfind", "pcfind_radius"],
            ("neighbors", "neighbor points", "k nearest", "nearpoints", "nearpoint"): 
                ["nearpoints", "nearpoint", "neighbours", "neighbourcount", "neighbour"],
            ("half edge", "halfedge", "boundary", "open mesh", "edge loop", "crease", "boundary edge"): 
                ["pointhedge", "pointhedgenext", "hedge_nextequiv", "hedge_dstpoint", "hedge_isprimary", "hedge_prim", "hedge_srcpoint"],
            ("quaternion", "orient", "rotation", "rotate", "lookat", "slerp", "dihedral"): 
                ["quaternion", "qrotate", "qmultiply", "slerp", "dihedral", "lookat", "maketransform", "eulertoquaternion"],
            ("eigen", "eigenvalues", "covariance", "decomposition", "svd", "polar"): 
                ["svd", "polardecomp", "eigenvalues", "diagonal", "trace"],
            ("volume", "sdf", "vdb", "gradient", "density", "sample volume", "curl", "vorticity", "divergence", "rk4", "viscosity"): 
                ["volumesample", "volumesamplev", "volumegradient", "volumeindex", "volumeindexv", "nametoprim", "volumeres", "volumevoxelsize"],
            ("ray", "raycast", "intersect", "reflection", "refraction", "fresnel", "bounce"): 
                ["intersect", "intersect_all", "reflect", "refract", "fresnel"],
            ("array", "sort", "reverse", "resize", "insert", "append", "push", "pop"): 
                ["append", "sort", "reverse", "resize", "insert", "find", "push", "pop", "len", "slice"],
            ("create points", "generate curve", "add points", "spiral", "knot", "polygon", "mesh", "minimal surface", "ribbon"): 
                ["addpoint", "addprim", "addvertex", "removeprim", "setprimintrinsic"],
            ("bounding box", "bbox", "relbbox", "normalize coordinates"): 
                ["relbbox", "getbbox_min", "getbbox_max", "getbbox_size", "getbbox_center"],
            ("channel", "chf", "chi", "chv", "chramp", "ramp", "parameter"): 
                ["chf", "chi", "chv", "chramp", "chs", "chrampeval"],
            ("noise", "perlin", "simplex", "worley", "curl noise", "anoise"): 
                ["noise", "curlnoise", "anoise", "snoise", "wnoise", "pnoise", "flownoise"],
            ("math", "trig", "fit", "clamp", "smooth", "lerp", "cross", "dot", "distance", "length"): 
                ["fit", "clamp", "lerp", "cross", "dot", "normalize", "distance", "smooth", "asin", "acos"]
        }

        for keywords, funcs in topic_triggers.items():
            if any(k in p_lower for k in keywords):
                for f in funcs:
                    if f in self.catalog and not any(f == mf[0] for mf in matched_funcs):
                        matched_funcs.append((f, 8))

        matched_funcs.sort(key=lambda x: x[1], reverse=True)
        top_funcs = [f[0] for f in matched_funcs[:max_results]]

        retrieved_signatures = []
        for f in top_funcs:
            for sig in self.catalog.get(f, []):
                retrieved_signatures.append(sig)

        return retrieved_signatures[:12]

    def build_rag_context_block(self, prompt: str) -> str:
        sigs = self.retrieve_signatures_for_task(prompt)
        if not sigs:
            return ""
        lines = ["Official SideFX VEX Function Signatures (Ground Truth Reference):"]
        for s in sigs:
            lines.append(f"  - {s}")
        return "\n".join(lines)

_rag_engine = VEXRAGEngine()

def get_vex_rag_engine() -> VEXRAGEngine:
    return _rag_engine
