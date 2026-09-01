"""
=============================================================================
 Houdini VEX Micro-RAG Engine
 Provides ultra-fast (<1ms) in-memory retrieval of official SideFX VEX function
 signatures, argument types, and return types to ground AI generation.
=============================================================================
"""

import os
import re
import json

# Comprehensive SideFX VEX Function Signature Catalog
VEX_SIGNATURES = {
    # Spatial & Point Clouds
    "xyzdist": [
        "float xyzdist(int geohandle, vector pt, int &prim, vector &uv)",
        "float xyzdist(int geohandle, vector pt, int &prim, vector &uv, float maxdist)",
        "float xyzdist(int geohandle, string primgroup, vector pt, int &prim, vector &uv)"
    ],
    "primuv": [
        "vector primuv(int geohandle, string attribute, int prim, vector uv)",
        "float primuv(int geohandle, string attribute, int prim, vector uv)",
        "int primuv(int geohandle, string attribute, int prim, vector uv)",
        "vector4 primuv(int geohandle, string attribute, int prim, vector uv)"
    ],
    "pcopen": [
        "int pcopen(int geohandle, string Pchannel, vector P, float radius, int maxpts)",
        "int pcopen(int geohandle, string ptgroup, string Pchannel, vector P, float radius, int maxpts)"
    ],
    "pciterate": [
        "int pciterate(int handle)"
    ],
    "pcimport": [
        "int pcimport(int handle, string channel_name, vector &value)",
        "int pcimport(int handle, string channel_name, float &value)",
        "int pcimport(int handle, string channel_name, int &value)",
        "int pcimport(int handle, string channel_name, string &value)"
    ],
    "pcfilter": [
        "vector pcfilter(int handle, string channel_name)",
        "float pcfilter(int handle, string channel_name)"
    ],
    "pcclose": [
        "void pcclose(int handle)"
    ],
    "nearpoints": [
        "int[] nearpoints(int geohandle, vector pt, float maxdist)",
        "int[] nearpoints(int geohandle, vector pt, float maxdist, int maxpts)",
        "int[] nearpoints(int geohandle, string ptgroup, vector pt, float maxdist, int maxpts)"
    ],
    "nearpoint": [
        "int nearpoint(int geohandle, vector pt)",
        "int nearpoint(int geohandle, vector pt, float maxdist)",
        "int nearpoint(int geohandle, string ptgroup, vector pt)"
    ],
    "pcfind": [
        "int[] pcfind(int geohandle, string Pchannel, vector P, float radius, int maxpts)"
    ],
    "pcfind_radius": [
        "int[] pcfind_radius(int geohandle, string Pchannel, string radius_channel, float radius_scale, vector P, float radius, int maxpts)"
    ],
    "neighbours": [
        "int[] neighbours(int geohandle, int ptnum)"
    ],
    "neighbourcount": [
        "int neighbourcount(int geohandle, int ptnum)"
    ],
    "neighbour": [
        "int neighbour(int geohandle, int ptnum, int neighbour_index)"
    ],

    # Half-Edges & Topology
    "pointhedge": [
        "int pointhedge(int geohandle, int ptnum)",
        "int pointhedge(int geohandle, int ptnum, int index)"
    ],
    "pointhedgenext": [
        "int pointhedgenext(int geohandle, int hedge)"
    ],
    "hedge_dstpoint": [
        "int hedge_dstpoint(int geohandle, int hedge)"
    ],
    "hedge_srcpoint": [
        "int hedge_srcpoint(int geohandle, int hedge)"
    ],
    "hedge_next": [
        "int hedge_next(int geohandle, int hedge)"
    ],
    "hedge_prev": [
        "int hedge_prev(int geohandle, int hedge)"
    ],
    "hedge_nextequiv": [
        "int hedge_nextequiv(int geohandle, int hedge)"
    ],
    "hedge_primary": [
        "int hedge_primary(int geohandle, int hedge)"
    ],
    "hedge_isprimary": [
        "int hedge_isprimary(int geohandle, int hedge)"
    ],
    "hedge_isequiv": [
        "int hedge_isequiv(int geohandle, int hedge1, int hedge2)"
    ],
    "primhedge": [
        "int primhedge(int geohandle, int primnum)"
    ],
    "hedge_prim": [
        "int hedge_prim(int geohandle, int hedge)"
    ],
    "primpoints": [
        "int[] primpoints(int geohandle, int primnum)"
    ],
    "pointprims": [
        "int[] pointprims(int geohandle, int ptnum)"
    ],
    "primvertexcount": [
        "int primvertexcount(int geohandle, int primnum)"
    ],
    "primpoint": [
        "int primpoint(int geohandle, int primnum, int vertex_num)"
    ],

    # Matrix, Transforms & Quaternions
    "svd": [
        "void svd(matrix3 m, matrix3 &u, vector &singular_values, matrix3 &v)",
        "void svd(matrix m, matrix &u, vector4 &singular_values, matrix &v)"
    ],
    "polardecomp": [
        "void polardecomp(matrix3 m, matrix3 &r, matrix3 &s) // access diagonal stretch with set(s.xx, s.yy, s.zz)"
    ],
    "dihedral": [
        "vector4 dihedral(vector v0, vector v1)",
        "matrix3 dihedral(vector v0, vector v1)"
    ],
    "qmultiply": [
        "vector4 qmultiply(vector4 q1, vector4 q2)"
    ],
    "qrotate": [
        "vector qrotate(vector4 q, vector v)"
    ],
    "slerp": [
        "vector4 slerp(vector4 q1, vector4 q2, float blend)"
    ],
    "quaternion": [
        "vector4 quaternion(float angle_in_radians, vector axis)",
        "vector4 quaternion(matrix3 m)",
        "vector4 quaternion(vector euler_in_degrees)"
    ],
    "quaterniontoeuler": [
        "vector quaterniontoeuler(vector4 q, int order)"
    ],
    "eulertoquaternion": [
        "vector4 eulertoquaternion(vector euler_in_degrees, int order)"
    ],
    "maketransform": [
        "matrix maketransform(vector translate, vector4 rotate_quat, vector scale)",
        "matrix maketransform(vector translate, vector rotate_euler, vector scale)",
        "matrix maketransform(int trs_order, int xyz_order, vector translate, vector rotate, vector scale, vector pivot)"
    ],
    "invert": [
        "matrix3 invert(matrix3 m)",
        "matrix invert(matrix m)"
    ],
    "transpose": [
        "matrix3 transpose(matrix3 m)",
        "matrix transpose(matrix m)"
    ],
    "determinant": [
        "float determinant(matrix3 m)",
        "float determinant(matrix m)"
    ],
    "lookat": [
        "matrix3 lookat(vector from, vector to, vector up)",
        "matrix lookat(vector from, vector to, vector up)"
    ],

    # Volumes & Fields
    "volumesample": [
        "float volumesample(int geohandle, string volumename, vector pos)",
        "float volumesample(int geohandle, int primnum, vector pos)"
    ],
    "volumevsample": [
        "vector volumevsample(int geohandle, string volumename, vector pos)",
        "vector volumevsample(int geohandle, int primnum, vector pos)"
    ],
    "volumegradient": [
        "vector volumegradient(int geohandle, string volumename, vector pos)",
        "vector volumegradient(int geohandle, int primnum, vector pos)"
    ],
    "volumeindex": [
        "float volumeindex(int geohandle, string volumename, vector voxel_index)",
        "float volumeindex(int geohandle, int primnum, vector voxel_index)"
    ],
    "volumeindexv": [
        "vector volumeindexv(int geohandle, string volumename, vector voxel_index)"
    ],
    "setvolumeindex": [
        "void setvolumeindex(int geohandle, string volumename, vector voxel_index, float val)",
        "void setvolumeindex(int geohandle, int primnum, vector voxel_index, float val)"
    ],
    "volumecubicsample": [
        "float volumecubicsample(int geohandle, string volumename, vector pos)"
    ],
    "volumevoxelsize": [
        "vector volumevoxelsize(int geohandle, string volumename)",
        "vector volumevoxelsize(int geohandle, int primnum)"
    ],
    "volumeres": [
        "vector volumeres(int geohandle, string volumename)",
        "vector volumeres(int geohandle, int primnum)"
    ],

    # Ray Casting & Occlusion
    "intersect": [
        "int intersect(int geohandle, vector origin, vector ray_dir, vector &hit_p, vector &hit_uv)",
        "int intersect(int geohandle, vector origin, vector ray_dir, int &hit_prim, vector &hit_uv, float &hit_dist)",
        "int intersect(int geohandle, vector origin, vector ray_dir, int &hit_prim, vector &hit_p, vector &hit_uv)"
    ],
    "intersect_all": [
        "int intersect_all(int geohandle, vector origin, vector ray_dir, vector &hit_positions[], int &hit_prims[], vector &hit_uvs[])"
    ],
    "reflect": [
        "vector reflect(vector incident, vector normal)"
    ],
    "refract": [
        "vector refract(vector incident, vector normal, float eta)"
    ],
    "fresnel": [
        "void fresnel(vector incident, vector normal, float eta, float &kr, float &kt)",
        "void fresnel(vector incident, vector normal, float eta, float &kr, float &kt, vector &reflect_dir, vector &refract_dir)"
    ],

    # Geometry Creation & Modification
    "addpoint": [
        "int addpoint(int geohandle, vector pos)",
        "int addpoint(int geohandle, int source_ptnum)"
    ],
    "addprim": [
        "int addprim(int geohandle, string type)",
        "int addprim(int geohandle, string type, int pt0, int pt1)",
        "int addprim(int geohandle, string type, int pt0, int pt1, int pt2)",
        "int addprim(int geohandle, string type, int pt0, int pt1, int pt2, int pt3)"
    ],
    "addvertex": [
        "int addvertex(int geohandle, int primnum, int ptnum)"
    ],
    "removepoint": [
        "int removepoint(int geohandle, int ptnum)"
    ],
    "removeprim": [
        "int removeprim(int geohandle, int primnum, int andpoints)"
    ],
    "setpointattrib": [
        "void setpointattrib(int geohandle, string name, int ptnum, <type> value, string mode='set')"
    ],
    "setprimattrib": [
        "void setprimattrib(int geohandle, string name, int primnum, <type> value, string mode='set')"
    ],
    "setvertexattrib": [
        "void setvertexattrib(int geohandle, string name, int vtxnum, <type> value, string mode='set')"
    ],
    "setdetailattrib": [
        "void setdetailattrib(int geohandle, string name, <type> value, string mode='set')"
    ],

    # Arrays, Lists & Dictionaries
    "insert": [
        "void insert(<type>[] &array, int index, <type> value)"
    ],
    "removeindex": [
        "void removeindex(<type>[] &array, int index)"
    ],
    "removevalue": [
        "void removevalue(<type>[] &array, <type> value)"
    ],
    "sort": [
        "void sort(<type>[] &array)"
    ],
    "reverse": [
        "void reverse(<type>[] &array)"
    ],
    "resize": [
        "void resize(<type>[] &array, int new_size)"
    ],
    "slice": [
        "<type>[] slice(<type>[] array, int start_index, int end_index)"
    ],
    "find": [
        "int find(<type>[] array, <type> value)"
    ],
    "min": [
        "<type> min(<type>[] array)",
        "<type> min(<type> val1, <type> val2)"
    ],
    "max": [
        "<type> max(<type>[] array)",
        "<type> max(<type> val1, <type> val2)"
    ],
    "avg": [
        "float avg(float[] array)",
        "vector avg(vector[] array)"
    ],
    "sum": [
        "float sum(float[] array)",
        "int sum(int[] array)",
        "vector sum(vector[] array)"
    ],
    "isvalidindex": [
        "int isvalidindex(dict d, string key)",
        "int isvalidindex(<type>[] array, int index)"
    ],
    "keys": [
        "string[] keys(dict d)"
    ],

    # Strings & Formatting
    "sprintf": [
        "string sprintf(string format, ...)"
    ],
    "split": [
        "string[] split(string str)",
        "string[] split(string str, string delimiters)"
    ],
    "join": [
        "string join(string[] tokens, string separator)"
    ],
    "match": [
        "int match(string pattern, string subject)"
    ],
    "re_find": [
        "int re_find(string regex, string subject)"
    ],
    "re_replace": [
        "string re_replace(string regex, string replacement, string subject)"
    ]
}


class VEXRAGEngine:
    """
    In-Memory RAG Engine for Houdini VEX.
    Retrieves exact function signatures based on query keywords and compiler errors.
    """
    def __init__(self):
        self.catalog = VEX_SIGNATURES

    def retrieve_signatures_for_task(self, prompt: str, max_results: int = 6) -> list[str]:
        """
        Retrieves relevant official SideFX VEX function signatures for a prompt.
        """
        p_lower = prompt.lower()
        matched_funcs = []

        # 1. Exact function name keyword matching
        for func_name in self.catalog.keys():
            pattern = rf"\b{re.escape(func_name)}\b"
            if re.search(pattern, p_lower):
                matched_funcs.append((func_name, 10))

        # 2. Semantic topic matching
        topic_triggers = {
            ("closest", "projection", "surface query", "distance to surface"): ["xyzdist", "primuv"],
            ("point cloud", "pc filter", "pc filter color", "pc import"): ["pcopen", "pciterate", "pcimport", "pcfilter", "pcclose"],
            ("neighbors", "neighbor points", "k nearest"): ["nearpoints", "nearpoint", "pcfind"],
            ("half edge", "halfedge", "boundary", "open mesh", "edge loop"): ["pointhedge", "pointhedgenext", "hedge_dstpoint", "hedge_isprimary", "hedge_nextequiv"],
            ("quaternion", "orient", "rotation", "rotate", "lookat", "slerp", "dihedral"): ["quaternion", "qrotate", "qmultiply", "slerp", "dihedral", "lookat"],
            ("eigen", "eigenvalues", "covariance", "decomposition", "svd", "polar"): ["svd", "polardecomp", "diagonal"],
            ("volume", "sdf", "vdb", "gradient", "density"): ["volumesample", "volumegradient", "volumevsample", "volumeindex"],
            ("ray", "raycast", "intersect", "reflection", "refraction", "fresnel"): ["intersect", "intersect_all", "reflect", "refract", "fresnel"],
            ("array", "sort", "reverse", "resize", "insert", "dictionary", "dict"): ["sort", "reverse", "resize", "insert", "find", "isvalidindex"],
            ("create points", "generate curve", "add points", "spiral", "knot", "polygon"): ["addpoint", "addprim", "addvertex"],
            ("string", "format", "split", "join", "regex"): ["sprintf", "split", "join", "match", "re_replace"]
        }

        for keywords, funcs in topic_triggers.items():
            if any(k in p_lower for k in keywords):
                for f in funcs:
                    if f in self.catalog and not any(f == mf[0] for mf in matched_funcs):
                        matched_funcs.append((f, 5))

        matched_funcs.sort(key=lambda x: x[1], reverse=True)
        top_funcs = [f[0] for f in matched_funcs[:max_results]]

        retrieved_signatures = []
        for f in top_funcs:
            for sig in self.catalog.get(f, []):
                retrieved_signatures.append(sig)

        return retrieved_signatures[:8]

    def build_rag_context_block(self, prompt: str) -> str:
        """
        Formats retrieved signatures into a compact prompt block.
        """
        sigs = self.retrieve_signatures_for_task(prompt)
        if not sigs:
            return ""

        lines = ["Official SideFX VEX Function Signatures (Ground Truth Reference):"]
        for s in sigs:
            lines.append(f"  - {s}")
        return "\n".join(lines)


# Global Engine Instance
_rag_engine = VEXRAGEngine()


def get_vex_rag_engine() -> VEXRAGEngine:
    return _rag_engine
