"""
Ground-truth, verified SideFX Houdini 21 VEX function signatures with accurate C++ argument types.
Replaces the noisy '<type> func(...)' placeholders in vex_1115_compact.json.
"""

VEX_GROUND_TRUTH_SIGNATURES = {
    # ── Geometry Queries & Proximity ──
    "xyzdist": [
        "float xyzdist(int geohandle, vector pos, int &prim, vector &uv)",
        "float xyzdist(int geohandle, vector pos, int &prim, vector &uv, float maxdist)",
        "float xyzdist(int geohandle, string primgroup, vector pos, int &prim, vector &uv)",
        "// Computes the distance to the closest point on geometry, outputting hit prim and parametric uv."
    ],
    "primuv": [
        "<type> primuv(int geohandle, string attribname, int primnum, vector uv)",
        "// Interpolates attribute value at the given parametric UV coordinates on a primitive."
    ],
    "minpos": [
        "vector minpos(int geohandle, vector pos)",
        "vector minpos(int geohandle, vector pos, float maxdist)",
        "vector minpos(int geohandle, string primgroup, vector pos)",
        "// Returns the closest position on a surface geometry."
    ],
    "nearpoints": [
        "int[] nearpoints(int geohandle, vector pos, float maxdist)",
        "int[] nearpoints(int geohandle, vector pos, float maxdist, int maxpts)",
        "int[] nearpoints(int geohandle, string ptgroup, vector pos, float maxdist, int maxpts)",
        "// Finds array of point numbers within maxdist from position, ordered from closest to farthest."
    ],
    "nearpoint": [
        "int nearpoint(int geohandle, vector pos)",
        "int nearpoint(int geohandle, vector pos, float maxdist)",
        "int nearpoint(int geohandle, string ptgroup, vector pos)",
        "// Finds the single closest point number in geometry to position."
    ],
    "neighbours": [
        "int[] neighbours(int geohandle, int ptnum)",
        "// Returns array of point numbers connected to ptnum by a polygon or polyline edge. (Strictly 2 arguments)."
    ],
    "neighbourcount": [
        "int neighbourcount(int geohandle, int ptnum)",
        "// Returns number of connected topological neighbors for ptnum. (0 indicates isolated/lonely point)."
    ],
    "pointprims": [
        "int[] pointprims(int geohandle, int ptnum)",
        "// Returns array of primitive numbers referencing ptnum. (Empty array indicates unmeshed point)."
    ],
    "pointvertices": [
        "int[] pointvertices(int geohandle, int ptnum)",
        "// Returns array of linear vertex numbers referencing ptnum."
    ],
    "surfacedist": [
        "float surfacedist(int geohandle, string ptgroup, string P_attrib, int ptnum, int &closest_pt, string distance_metric)",
        "float surfacedist(int geohandle, string ptgroup, string P_attrib, int ptnum, float max_radius, int &closest_pt, string distance_metric)",
        "// Computes approximate surface geodesic distance from ptnum to ptgroup across polygon edges."
    ],

    # ── Element Creation & Culling ──
    "removepoint": [
        "int removepoint(int geohandle, int ptnum)",
        "int removepoint(int geohandle, int ptnum, int and_prims)",
        "// Removes a point from geometry. If and_prims=1, also removes primitives that become degenerate."
    ],
    "removeprim": [
        "int removeprim(int geohandle, int primnum, int and_points)",
        "// Removes a primitive from geometry. If and_points=1, also removes unused unshared points."
    ],
    "removevertex": [
        "int removevertex(int geohandle, int linear_vertex_index)",
        "// Removes a vertex, given its LINEAR vertex number (see vertexindex(geohandle, primnum, vertex_of_prim))."
    ],
    "addpoint": [
        "int addpoint(int geohandle, vector pos)",
        "// Adds a point with position pos to geometry and returns the new point number."
    ],
    "addprim": [
        "int addprim(int geohandle, string type)",
        "int addprim(int geohandle, string type, int pt0, int pt1)",
        "// Adds a primitive (e.g. 'polyline', 'poly', 'sphere') to geometry."
    ],
    "addvertex": [
        "int addvertex(int geohandle, int primnum, int ptnum)",
        "// Adds a vertex referencing ptnum to the end of primitive primnum."
    ],

    # ── Attribute Access & Modification ──
    "point": [
        "<type> point(int geohandle, string attribname, int ptnum)",
        "// Reads a point attribute value from geometry. Cast to typed variable (e.g. vector p = point(...))."
    ],
    "prim": [
        "<type> prim(int geohandle, string attribname, int primnum)",
        "// Reads a primitive attribute value from geometry."
    ],
    "vertex": [
        "<type> vertex(int geohandle, string attribname, int linearvtx)",
        "// Reads a vertex attribute value from geometry."
    ],
    "detail": [
        "<type> detail(int geohandle, string attribname)",
        "// Reads a detail attribute value from geometry."
    ],
    "setpointattrib": [
        "int setpointattrib(int geohandle, string name, int ptnum, <type> val, string mode='set')",
        "// Sets a point attribute value. Mode can be 'set', 'add', 'multiply', 'min', 'max'."
    ],
    "setprimattrib": [
        "int setprimattrib(int geohandle, string name, int primnum, <type> val, string mode='set')",
        "// Sets a primitive attribute value."
    ],
    "setvertexattrib": [
        "int setvertexattrib(int geohandle, string name, int linearvtx, <type> val, string mode='set')",
        "// Sets a vertex attribute value."
    ],
    "setdetailattrib": [
        "int setdetailattrib(int geohandle, string name, <type> val, string mode='set')",
        "// Sets a detail attribute value."
    ],
    "hasattrib": [
        "int hasattrib(int geohandle, string type, string name)",
        "// Returns 1 if attribute exists on class ('point', 'prim', 'vertex', 'detail'), 0 otherwise."
    ],
    "addattrib": [
        "int addattrib(int geohandle, string type, string name, <type> defaultval)",
        "// Creates a new attribute on geometry with the given default value."
    ],

    # ── Ray Intersection ──
    "intersect": [
        "int intersect(int geohandle, vector orig, vector dir, vector &pos, float &u, float &v)",
        "int intersect(int geohandle, vector orig, vector dir, vector &pos, vector &uvw)",
        "int intersect(int geohandle, string primgroup, vector orig, vector dir, vector &pos, vector &uvw)",
        "// Intersects a ray with geometry. RETURNS the primitive number hit, or -1 on a miss. The ray is only as long as dir: scale a unit direction by the maximum distance."
    ],
    "intersect_all": [
        "int intersect_all(int geohandle, vector orig, vector dir, vector &positions[], int &prims[], vector &uvws[])",
        "int intersect_all(int geohandle, vector orig, vector dir, vector &positions[], int &prims[], vector &uvws[], float tol, float ttol)",
        "// Intersects ray with geometry finding all intersection points along ray path."
    ],

    # ── Volumes & OpenVDB ──
    "volumesample": [
        "float volumesample(int geohandle, int primnum, vector pos)",
        "float volumesample(int geohandle, string volumename, vector pos)",
        "// Samples a scalar volume field (or SDF) at world space position."
    ],
    "volumesamplev": [
        "vector volumesamplev(int geohandle, int primnum, vector pos)",
        "vector volumesamplev(int geohandle, string volumename, vector pos)",
        "// Samples a 3D vector volume field (e.g. velocity) at world space position."
    ],
    "volumegradient": [
        "vector volumegradient(int geohandle, int primnum, vector pos)",
        "vector volumegradient(int geohandle, string volumename, vector pos)",
        "// Computes the spatial gradient vector of a volume field at position pos."
    ],
    "volumeindex": [
        "float volumeindex(int geohandle, int primnum, vector voxel_ijk)",
        "// Samples a volume voxel directly by integer (i, j, k) coordinates."
    ],
    "volumeres": [
        "vector volumeres(int geohandle, int primnum)",
        "// Returns the (rx, ry, rz) voxel resolution of volume primitive."
    ],
    "volumevoxeldiameter": [
        "float volumevoxeldiameter(int geohandle, int primnum)",
        "float volumevoxeldiameter(int geohandle, string volumename)",
        "// Returns the approximate diameter (diagonal) of a single voxel in world space."
    ],

    # ── Point Clouds (KD-Tree) ──
    "pcopen": [
        "int pcopen(int geohandle, string Pchannel, vector pos, float maxdist, int maxpts)",
        "// Opens a point cloud query returning a handle for iteration."
    ],
    "pciterate": [
        "int pciterate(int handle)",
        "// Advances point cloud iterator to next point in queue. Returns 1 if valid, 0 when exhausted."
    ],
    "pcimport": [
        "int pcimport(int handle, string channel_name, <type> &val)",
        "// Reads an attribute from the current point in pciterate loop."
    ],
    "pcfilter": [
        "<type> pcfilter(int handle, string channel_name)",
        "// Filters attribute over all points found in pcopen query using smooth inverse-distance weighting."
    ],
    "pcclose": [
        "void pcclose(int handle)",
        "// Closes an open point cloud query handle and frees resources."
    ],
    "pcfind": [
        "int[] pcfind(int geohandle, string Pchannel, vector pos, float maxdist, int maxpts)",
        "// Finds array of point numbers matching spatial query without needing iteration handle."
    ],

    # ── Half-Edge Topology ──
    "pointhedge": [
        "int pointhedge(int geohandle, int ptnum)",
        "// Returns the first half-edge originating from ptnum, or -1."
    ],
    "pointhedgenext": [
        "int pointhedgenext(int geohandle, int hedge)",
        "// Returns next half-edge originating from the same point."
    ],
    "hedge_nextequiv": [
        "int hedge_nextequiv(int geohandle, int hedge)",
        "// Returns opposing half-edge across face. Returns hedge itself if on open boundary border."
    ],
    "hedge_dstpoint": [
        "int hedge_dstpoint(int geohandle, int hedge)",
        "// Returns destination point of half-edge."
    ],
    "hedge_srcpoint": [
        "int hedge_srcpoint(int geohandle, int hedge)",
        "// Returns source point of half-edge."
    ],
    "hedge_prim": [
        "int hedge_prim(int geohandle, int hedge)",
        "// Returns primitive number owning half-edge."
    ],

    # ── Quaternions & Rotations ──
    "quaternion": [
        "vector4 quaternion(float angle_rad, vector axis)",
        "vector4 quaternion(vector angle_axis)",
        "vector4 quaternion(matrix3 rot_matrix)",
        "// Creates a 4D quaternion vector4 representing a 3D rotation."
    ],
    "qrotate": [
        "vector qrotate(vector4 q, vector v)",
        "// Rotates a 3D vector v by quaternion q."
    ],
    "qmultiply": [
        "vector4 qmultiply(vector4 q1, vector4 q2)",
        "// Multiplies two quaternions (combines rotations q1 then q2)."
    ],
    "slerp": [
        "vector4 slerp(vector4 q0, vector4 q1, float t)",
        "// Spherical linear interpolation between two quaternions."
    ],
    "dihedral": [
        "vector4 dihedral(vector v0, vector v1)",
        "// Returns quaternion that rotates vector v0 to align with vector v1."
    ],
    "lookat": [
        "matrix3 lookat(vector from, vector to)",
        "matrix3 lookat(vector from, vector to, vector up)",
        "// Constructs 3x3 rotation matrix looking from 'from' toward 'to'."
    ],
    "maketransform": [
        "matrix maketransform(int trs, int xyz, vector trans, vector rot_degrees)",
        "matrix maketransform(int trs, int xyz, vector trans, vector rot_degrees, vector scale)",
        "matrix maketransform(int trs, int xyz, vector trans, vector rot_degrees, vector scale, vector pivot)",
        "matrix3 maketransform(vector zaxis, vector yaxis)",
        "// Builds a 4x4 transform from translate / rotate (degrees) / scale with the given orders (e.g. XFORM_SRT, XFORM_XYZ), or a 3x3 rotation from a forward (z) and up (y) axis."
    ],

    # ── Math, Linear Algebra & Matrix ──
    "svddecomp": [
        "void svddecomp(matrix3 m, matrix3 &u, vector &singular_values, matrix3 &v)",
        "// Computes singular value decomposition M = U * diag(S) * V^T."
    ],
    "polardecomp": [
        "void polardecomp(matrix3 m, matrix3 &r, matrix3 &s)",
        "// Polar decomposition M = R * S where R is orthogonal rotation and S is symmetric stretch."
    ],
    "eigenvalues": [
        "void eigenvalues(int &nroot, matrix3 m, vector &real, vector &imaginary)",
        "// Computes the eigenvalues of a 3x3 matrix: nroot = number of real roots, values returned in real / imaginary."
    ],
    "invert": [
        "matrix invert(matrix m)",
        "matrix3 invert(matrix3 m)",
        "// Inverts a square matrix."
    ],
    "determinant": [
        "float determinant(matrix m)",
        "float determinant(matrix3 m)",
        "// Computes the determinant of a matrix."
    ],
    "ident": [
        "matrix ident()",
        "matrix3 ident()",
        "// Returns identity matrix."
    ],

    # ── Bounding Boxes ──
    "getbbox": [
        "void getbbox(int geohandle, vector &bmin, vector &bmax)",
        "void getbbox(int geohandle, string group, vector &bmin, vector &bmax)",
        "// Computes the axis-aligned bounding box min and max vectors."
    ],
    "getbbox_min": [
        "vector getbbox_min(int geohandle)",
        "// Returns bounding box minimum position."
    ],
    "getbbox_max": [
        "vector getbbox_max(int geohandle)",
        "// Returns bounding box maximum position."
    ],
    "getbbox_size": [
        "vector getbbox_size(int geohandle)",
        "// Returns bounding box size vector (max - min)."
    ],
    "getbbox_center": [
        "vector getbbox_center(int geohandle)",
        "// Returns bounding box center vector (min + max) * 0.5."
    ],
    "relbbox": [
        "vector relbbox(int geohandle, vector pos)",
        "// Returns normalized [0, 1] relative coordinates of pos within bounding box."
    ],

    # ── UI Channels & Ramps ──
    "chf": ["float chf(string channel_name)", "// Reads float parameter from UI."],
    "chi": ["int chi(string channel_name)", "// Reads integer parameter from UI."],
    "chv": ["vector chv(string channel_name)", "// Reads 3D vector parameter from UI."],
    "chs": ["string chs(string channel_name)", "// Reads string parameter from UI."],
    "chp": ["vector4 chp(string channel_name)", "// Reads 4D vector / quaternion parameter from UI."],
    "chramp": [
        "vector chramp(string ramp_name, float pos)",
        "float chramp(string ramp_name, float pos)",
        "// Evaluates a spline ramp parameter at position pos in [0, 1]."
    ],

    # ── Groups ──
    "setpointgroup": [
        "int setpointgroup(int geohandle, string group, int ptnum, int value, string mode='set')",
        "// Adds (value=1) or removes (value=0) point from group."
    ],
    "setprimgroup": [
        "int setprimgroup(int geohandle, string group, int primnum, int value, string mode='set')",
        "// Adds (value=1) or removes (value=0) primitive from group."
    ],
    "inpointgroup": [
        "int inpointgroup(int geohandle, string group, int ptnum)",
        "// Returns 1 if ptnum is in point group, 0 otherwise."
    ],
    "inprimgroup": [
        "int inprimgroup(int geohandle, string group, int primnum)",
        "// Returns 1 if primnum is in primitive group, 0 otherwise."
    ],

    # ── Noise ──
    "curlnoise": [
        "vector curlnoise(vector pos)",
        "vector curlnoise(vector4 pos)",
        "// Evaluates divergence-free 3D/4D curl noise."
    ],
    "snoise": [
        "float snoise(vector pos)",
        "vector snoise(vector pos)",
        "// Simplex noise in range [-1, 1]."
    ],
    "anoise": [
        "float anoise(vector pos)",
        "vector anoise(vector pos)",
        "// Alligator noise (Voronoi cellular based)."
    ]
}
