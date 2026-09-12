"""
=============================================================================
 Houdini VEX Micro-RAG Engine v4.0 (40 Master Architectural Blueprints + 1,115 Functions)
 Complete in-memory retrieval of 1,115 SideFX VEX function signatures PLUS
 40 battle-tested procedural architectural scaffolds spanning every major
 production domain: differential curves, RK4 flows, Turing morphogenesis,
 KD-tree Blue Noise, SPH fluids, Boids, PBD cloth, SDF raymarching, half-edge
 topology, quaternions, catenaries, strange attractors, PCA, Gerstner ocean
 waves, Dijkstra geodesics, Physarum slime mold, L-systems, minimal surfaces,
 space colonization, Voronoi shatters, MikkTSpace TBN, and procedural grooming.
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
        os.path.join(pkg_dir, "scripts", "data", "vex_1115_compact.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "vex_1115_compact.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "data", "vex_1115_compact.json"),
        os.path.join(os.getcwd(), "data", "vex_1115_compact.json"),
        r"C:\Users\Anshul\Documents\houdini21.0\scripts\data\vex_1115_compact.json",
        r"E:\#AI#\Houdini Attribute Wrangle\data\vex_1115_compact.json",
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

# ---------------------------------------------------------------------------
# 40 Master Architectural Blueprints (Production Scaffolds for Houdini VEX)
# ---------------------------------------------------------------------------
VEX_MASTER_RECIPES = {
    # ── 1. Parametric Geometry & Space Curves ──
    "curve_bishop_frame": {
        "triggers": ("curve", "spiral", "knot", "helix", "polyline", "tendril", "vortex", "addpoint", "addprim", "from scratch", "synthesize", "torus knot", "braid"),
        "title": "Procedural Discrete Curve with Orthonormal Bishop Frame (Detail Wrangle)",
        "context": "detail wrangle",
        "blueprint": """// -- Blueprint: Procedural Curve & Bishop Parallel Transport Frame --
int count = chi("point_count");
if (count <= 0) count = 250;
int prim = addprim(0, "polyline");

vector prev_P = {0, 0, 0};
vector prev_T = {0, 1, 0};
vector prev_N = {1, 0, 0};

for (int i = 0; i < count; i++) {
    float u = float(i) / float(count - 1);
    float theta = u * 6.2831853 * chf("turns");
    float r = lerp(chf("r_start"), chf("r_end"), u);
    vector base_P = set(r * cos(theta), chf("height") * u, r * sin(theta));
    vector P = base_P + curlnoise(base_P * chf("noise_freq") + set(0, @Time * 0.2, 0)) * chf("noise_amp");

    vector T = {0, 1, 0};
    if (i > 0) {
        T = normalize(P - prev_P);
        vector cross_axis = cross(prev_T, T);
        float sin_angle = length(cross_axis);
        if (sin_angle > 1e-5) {
            vector axis = cross_axis / sin_angle;
            float cos_angle = clamp(dot(prev_T, T), -1.0, 1.0);
            matrix3 m_rot = ident();
            rotate(m_rot, atan2(sin_angle, cos_angle), axis);
            prev_N = normalize(prev_N * m_rot);
        }
    }
    vector N = prev_N;
    vector B = normalize(cross(T, N));
    matrix3 m_orient = set(N, B, T);
    vector4 orient = quaternion(m_orient);

    int pt = addpoint(0, P);
    addvertex(0, prim, pt);
    
    setpointattrib(0, "P", pt, P, "set");
    setpointattrib(0, "N", pt, N, "set");
    setpointattrib(0, "orient", pt, orient, "set");
    setpointattrib(0, "curveu", pt, u, "set");
    setpointattrib(0, "pscale", pt, lerp(chf("pscale_start"), chf("pscale_end"), pow(u, 1.5)), "set");
    setpointattrib(0, "Cd", pt, chramp("color_ramp", u), "set");

    prev_P = P;
    prev_T = T;
}"""
    },

    # ── 2. Vector Integration & Fluid Mechanics ──
    "rk4_numerical_advection": {
        "triggers": ("rk4", "runge-kutta", "streamline", "advect", "flow field", "vorticity", "field flow", "particle trail"),
        "title": "4th-Order Runge-Kutta (RK4) Vector Field Advection (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: 4th-Order Runge-Kutta (RK4) Numerical Integration --
float dt = chf("time_step");
if (dt <= 0.0) dt = 0.05;
float speed = chf("flow_speed");
float freq = chf("field_frequency");

vector p = @P;
vector v1 = curlnoise(p * freq) * speed;
vector v2 = curlnoise((p + 0.5 * dt * v1) * freq) * speed;
vector v3 = curlnoise((p + 0.5 * dt * v2) * freq) * speed;
vector v4 = curlnoise((p + dt * v3) * freq) * speed;

vector v_rk4 = (v1 + 2.0 * v2 + 2.0 * v3 + v4) / 6.0;
@P += v_rk4 * dt;
v@vel = v_rk4;
float speed_norm = length(v_rk4);
f@speed = speed_norm;
@pscale = fit(speed_norm, 0.0, speed * 1.5, 0.02, 0.2);
@Cd = chramp("energy_speed_ramp", clamp(speed_norm / (speed * 1.5 + 1e-5), 0.0, 1.0));"""
    },

    # ── 3. Reaction-Diffusion & Morphogenesis ──
    "gray_scott_reaction_diffusion": {
        "triggers": ("reaction diffusion", "gray-scott", "gray scott", "chemical", "activator", "turing pattern", "laplacian"),
        "title": "Gray-Scott Reaction-Diffusion Surface Solver (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Gray-Scott Reaction-Diffusion with Surface Laplacian --
float feed = chf("feed_rate");
float kill = chf("kill_rate");
float diff_a = chf("diff_a");
float diff_b = chf("diff_b");
float dt = chf("time_step");

float a = hasattrib(0, "point", "chem_a") ? f@chem_a : 1.0;
float b = hasattrib(0, "point", "chem_b") ? f@chem_b : 0.0;
if (!hasattrib(0, "point", "chem_b")) {
    b = (curlnoise(@P * 2.5).x > 0.15) ? 1.0 : 0.0;
}

int nbrs[] = neighbours(0, @ptnum);
float lap_a = 0.0;
float lap_b = 0.0;
int count = len(nbrs);
if (count > 0) {
    foreach (int n; nbrs) {
        lap_a += point(0, "chem_a", n);
        lap_b += point(0, "chem_b", n);
    }
    lap_a = (lap_a / float(count)) - a;
    lap_b = (lap_b / float(count)) - b;
}

float uvv = a * b * b;
float da = (diff_a * lap_a - uvv + feed * (1.0 - a)) * dt;
float db = (diff_b * lap_b + uvv - (kill + feed) * b) * dt;

f@chem_a = clamp(a + da, 0.0, 1.0);
f@chem_b = clamp(b + db, 0.0, 1.0);

float disp_scale = chf("disp_scale");
if (disp_scale != 0.0) {
    @P += normalize(@N) * f@chem_b * disp_scale;
}
@Cd = chramp("reaction_ramp", f@chem_b);
f@pscale = fit01(f@chem_b, 0.02, 0.1);"""
    },

    # ── 4. Conformal Surface Projections ──
    "surface_projection_primuv": {
        "triggers": ("xyzdist", "primuv", "project to surface", "conform", "shrinkwrap", "stick to surface", "nearest surface", "surface snap"),
        "title": "Conformal Surface Projection & Attribute Interpolation (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Conformal Surface Projection & Attribute Interpolation --
int hit_prim;
vector hit_uv;
float d = xyzdist(1, @P, hit_prim, hit_uv);

if (hit_prim != -1) {
    vector target_P = primuv(1, "P", hit_prim, hit_uv);
    vector target_N = primuv(1, "N", hit_prim, hit_uv);
    
    float blend = clamp(chf("blend_weight"), 0.0, 1.0);
    @P = lerp(@P, target_P, blend);
    v@N = normalize(lerp(v@N, target_N, blend));
    f@dist = d;
    @Cd = chramp("distance_ramp", fit(d, 0.0, chf("max_dist"), 0.0, 1.0));
}"""
    },

    # ── 5. Spatial Cloud Relaxation ──
    "blue_noise_spatial_relaxation": {
        "triggers": ("blue noise", "relax", "relaxation", "repulsion", "distribute", "sph", "density", "pcfind", "nearpoints", "spacing"),
        "title": "KD-Tree Blue Noise Spatial Point Relaxation (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: KD-Tree Blue Noise Spatial Relaxation (pcfind) --
int max_pts = chi("max_neighbors");
if (max_pts <= 0) max_pts = 16;
float search_rad = chf("search_radius");
if (search_rad <= 0.0) search_rad = 0.5;
float push_weight = chf("push_weight");
if (push_weight <= 0.0) push_weight = 0.3;

int close_pts[] = pcfind(0, "P", @P, search_rad, max_pts);
vector disp = {0, 0, 0};
int n_found = 0;

foreach (int pt; close_pts) {
    if (pt == @ptnum) continue;
    vector other_P = point(0, "P", pt);
    vector diff = @P - other_P;
    float dist = length(diff);
    if (dist > 1e-5 && dist < search_rad) {
        float falloff = pow(1.0 - (dist / search_rad), 2.0);
        disp += normalize(diff) * falloff;
        n_found++;
    }
}

if (n_found > 0) {
    @P += disp * (push_weight / float(n_found));
}
f@density = float(n_found);
@pscale = max(0.005, search_rad * 0.25);
@Cd = chramp("density_ramp", fit(float(n_found), 0.0, float(max_pts), 0.0, 1.0));"""
    },

    # ── 6. Orthonormal Orientation Frames ──
    "quaternion_orientation_frames": {
        "triggers": ("orient", "quaternion", "rotation", "tangent", "normal", "dihedral", "lookat", "aim", "instance orient"),
        "title": "Orthonormal Orientation Quaternions (@orient) (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Orthonormal Orientation Quaternions (@orient) --
vector T = normalize(v@v);
vector up = set(0, 1, 0);
if (abs(dot(T, up)) > 0.99) up = set(1, 0, 0);

vector N = normalize(cross(up, T));
vector B = normalize(cross(T, N));
matrix3 m_orient = set(N, up, T);
p@orient = quaternion(m_orient);"""
    },

    # ── 7. Level-Set Volume SDFs ──
    "volume_sdf_projection": {
        "triggers": ("sdf", "collision", "volumesample", "volumegradient", "penetration", "project out", "containment", "level set"),
        "title": "Volume Signed Distance Field (SDF) Collision & Projection (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Volume SDF Sampling, Collision & Gradient Projection --
float dist = volumesample(1, "surface", @P);
float margin = chf("collision_margin");
if (margin <= 0.0) margin = 0.02;

if (dist < margin) {
    vector grad = volumegradient(1, "surface", @P);
    float grad_len = length(grad);
    if (grad_len > 1e-5) {
        vector nml = normalize(grad);
        @P += nml * (margin - dist);
        
        float v_norm = dot(v@v, nml);
        if (v_norm < 0.0) {
            vector tangent = normalize(v@v - nml * v_norm);
            float bounce = chf("bounce"); if (bounce <= 0.0) bounce = 0.5;
            float friction = clamp(chf("friction"), 0.0, 1.0);
            v@v = tangent * (1.0 - friction) - nml * (v_norm * bounce);
        }
        @Cd = set(1.2, 0.65, 0.1);
    }
}"""
    },

    # ── 8. Procedural Point Cloud Synthesis ──
    "particle_point_cloud_synthesis": {
        "triggers": ("particle", "particles", "points from scratch", "ring of particles", "swarm", "sparks", "stars", "cloud of points", "spawn particles", "sphere of points"),
        "title": "Procedural Point Cloud Synthesis (Detail Wrangle)",
        "context": "detail wrangle",
        "blueprint": """// -- Blueprint: Procedural Point Cloud Synthesis (Detail Wrangle) --
int total = chi("total_points");
if (total <= 0) total = 300;
float radius = chf("cloud_radius");
if (radius <= 0.0) radius = 2.0;

for (int i = 0; i < total; i++) {
    float theta = rand(i * 17 + 3) * 6.2831853;
    float phi = acos(2.0 * rand(i * 31 + 7) - 1.0);
    float r = radius * pow(rand(i * 13 + 5), 0.5);
    vector pos = set(r * sin(phi) * cos(theta), r * cos(phi), r * sin(phi) * sin(theta));
    
    int pt = addpoint(0, pos);
    vector vel = normalize(pos) * chf("speed") + curlnoise(pos * 2.0) * chf("turb_amp");
    setpointattrib(0, "v", pt, vel, "set");
    setpointattrib(0, "pscale", pt, fit01(rand(i * 37 + 11), 0.01, 0.05), "set");
    
    float norm_r = clamp(r / radius, 0.0, 1.0);
    vector col = chramp("radial_color_ramp", norm_r);
    setpointattrib(0, "Cd", pt, col, "set");
}"""
    },

    # ── 9. Catenary Hanging Cables ──
    "catenary_hanging_cable": {
        "triggers": ("catenary", "cable", "hanging wire", "rope", "sag", "cables", "power lines", "suspension", "hanging curve"),
        "title": "Catenary Hanging Cable / Wire Curve (Detail Wrangle)",
        "context": "detail wrangle",
        "blueprint": """// -- Blueprint: Catenary Hanging Cable / Wire (Detail Wrangle) --
vector p0 = chv("start_point");
vector p1 = chv("end_point");
float sag = chf("cable_sag");
if (sag <= 0.0) sag = 0.5;
int num_pts = chi("cable_resolution");
if (num_pts <= 2) num_pts = 64;

int prim = addprim(0, "polyline");
float chord_len = distance(p0, p1);

for (int i = 0; i < num_pts; i++) {
    float u = float(i) / float(num_pts - 1);
    vector p_linear = lerp(p0, p1, u);
    float x_norm = (u - 0.5) * 2.0;
    float catenary_y = -(cosh(x_norm * sag) - 1.0) / (cosh(sag) - 1.0 + 1e-5) * chord_len * 0.25;
    
    vector p_catenary = p_linear + set(0.0, catenary_y, 0.0);
    int pt = addpoint(0, p_catenary);
    addvertex(0, prim, pt);
    
    setpointattrib(0, "curveu", pt, u, "set");
    setpointattrib(0, "pscale", pt, chf("wire_radius"), "set");
    setpointattrib(0, "Cd", pt, chramp("cable_ramp", u), "set");
}"""
    },

    # ── 10. Chaotic Strange Attractors ──
    "strange_attractors_lorenz_aizawa": {
        "triggers": ("attractor", "lorenz", "aizawa", "clifford", "rossler", "chaos", "strange attractor", "phase space", "dynamical system"),
        "title": "Lorenz / Chaotic Strange Attractor Orbit (Detail Wrangle)",
        "context": "detail wrangle",
        "blueprint": """// -- Blueprint: Lorenz / Strange Attractor Orbit (Detail Wrangle) --
int total_steps = chi("simulation_steps");
if (total_steps <= 0) total_steps = 2500;
float dt = chf("time_step");
if (dt <= 0.0) dt = 0.008;

float s = chf("sigma"); if (s <= 0.0) s = 10.0;
float r = chf("rho");   if (r <= 0.0) r = 28.0;
float b = chf("beta");  if (b <= 0.0) b = 8.0 / 3.0;

vector p = set(0.1, 0.0, 0.0);
int prim = addprim(0, "polyline");

for (int step = 0; step < total_steps; step++) {
    float dx = s * (p.y - p.x);
    float dy = p.x * (r - p.z) - p.y;
    float dz = p.x * p.y - b * p.z;
    vector v = set(dx, dy, dz);
    p += v * dt;
    
    int pt = addpoint(0, p * chf("scale_factor"));
    addvertex(0, prim, pt);
    
    float u = float(step) / float(total_steps - 1);
    setpointattrib(0, "curveu", pt, u, "set");
    setpointattrib(0, "v", pt, v, "set");
    setpointattrib(0, "speed", pt, length(v), "set");
    setpointattrib(0, "Cd", pt, chramp("velocity_ramp", clamp(length(v) / 40.0, 0.0, 1.0)), "set");
    setpointattrib(0, "pscale", pt, fit01(u, 0.04, 0.01), "set");
}"""
    },

    # ── 11. Spherical Fibonacci Lattice ──
    "spherical_fibonacci_lattice": {
        "triggers": ("fibonacci sphere", "fibonacci", "spherical distribution", "even distribution", "equi-area", "sphere points", "uniform sphere", "sunflower"),
        "title": "Spherical Fibonacci Lattice Equal-Area Sampling (Detail Wrangle)",
        "context": "detail wrangle",
        "blueprint": """// -- Blueprint: Spherical Fibonacci Lattice Equal-Area Sampling (Detail Wrangle) --
int total_points = chi("point_count");
if (total_points <= 0) total_points = 500;
float radius = chf("sphere_radius");
if (radius <= 0.0) radius = 2.0;

float phi_golden = 3.14159265 * (3.0 - sqrt(5.0));

for (int i = 0; i < total_points; i++) {
    float y = 1.0 - (float(i) / float(total_points - 1)) * 2.0;
    float r_ring = sqrt(max(0.0, 1.0 - y * y));
    float theta = phi_golden * float(i);
    
    float x = cos(theta) * r_ring;
    float z = sin(theta) * r_ring;
    vector nml = set(x, y, z);
    vector pos = nml * radius;
    
    int pt = addpoint(0, pos);
    setpointattrib(0, "N", pt, nml, "set");
    setpointattrib(0, "pscale", pt, chf("particle_radius"), "set");
    setpointattrib(0, "Cd", pt, chramp("latitude_ramp", fit(y, -1.0, 1.0, 0.0, 1.0)), "set");
}"""
    },

    # ── 12. Vogel Phyllotaxis Spiral ──
    "phyllotaxis_vogel_spiral": {
        "triggers": ("phyllotaxis", "vogel", "sunflower spiral", "flower", "succulent", "disk distribution", "golden angle", "spiral distribution"),
        "title": "Vogel Phyllotaxis Spiral Distribution (Detail Wrangle)",
        "context": "detail wrangle",
        "blueprint": """// -- Blueprint: Vogel Phyllotaxis Spiral Distribution (Detail Wrangle) --
int count = chi("total_seeds");
if (count <= 0) count = 400;
float spread = chf("spread_factor");
if (spread <= 0.0) spread = 0.15;
float golden_angle = 2.3999632;

for (int i = 0; i < count; i++) {
    float r = spread * sqrt(float(i));
    float theta = float(i) * golden_angle;
    
    float x = r * cos(theta);
    float z = r * sin(theta);
    float y = exp(-r * 0.4) * chf("dome_height");
    
    vector pos = set(x, y, z);
    int pt = addpoint(0, pos);
    
    float u = float(i) / float(count - 1);
    vector nml = normalize(set(x * 0.2, 1.0, z * 0.2));
    setpointattrib(0, "N", pt, nml, "set");
    setpointattrib(0, "pscale", pt, fit01(sqrt(u), 0.02, 0.06), "set");
    setpointattrib(0, "Cd", pt, chramp("botanical_ramp", u), "set");
}"""
    },

    # ── 13. Reynolds Boids Flocking ──
    "flocking_boids_simulation": {
        "triggers": ("boids", "flocking", "swarm", "separation", "alignment", "cohesion", "bird flock", "fish school", "crowd"),
        "title": "Reynolds Boids Swarm Intelligence Solver (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Reynolds Boids Swarm Intelligence Solver (Point Wrangle) --
float r_sep = chf("separation_radius"); if (r_sep <= 0.0) r_sep = 0.4;
float r_nbr = chf("neighbor_radius");   if (r_nbr <= 0.0) r_nbr = 1.5;
float w_sep = chf("weight_separation");  if (w_sep <= 0.0) w_sep = 1.5;
float w_ali = chf("weight_alignment");   if (w_ali <= 0.0) w_ali = 1.0;
float w_coh = chf("weight_cohesion");    if (w_coh <= 0.0) w_coh = 0.8;
float max_speed = chf("max_speed");      if (max_speed <= 0.0) max_speed = 3.0;

int near_pts[] = pcfind(0, "P", @P, r_nbr, 24);
vector f_sep = {0, 0, 0};
vector f_ali = {0, 0, 0};
vector center_coh = {0, 0, 0};
int n_nbrs = 0;

foreach (int pt; near_pts) {
    if (pt == @ptnum) continue;
    vector other_P = point(0, "P", pt);
    vector diff = @P - other_P;
    float dist = length(diff);
    if (dist > 1e-5) {
        if (dist < r_sep) f_sep += normalize(diff) * (1.0 - (dist / r_sep));
        f_ali += point(0, "v", pt);
        center_coh += other_P;
        n_nbrs++;
    }
}

vector steer = {0, 0, 0};
if (n_nbrs > 0) {
    f_ali = normalize(f_ali / float(n_nbrs)) * max_speed - v@v;
    center_coh = (center_coh / float(n_nbrs)) - @P;
    steer = f_sep * w_sep + f_ali * w_ali + normalize(center_coh) * w_coh;
}

v@v = clamp_length(v@v + steer * @TimeInc, 0.1, max_speed);
@P += v@v * @TimeInc;
p@orient = quaternion(maketransform(normalize(v@v), set(0, 1, 0)));"""
    },

    # ── 14. Position-Based Dynamics Cloth ──
    "position_based_dynamics_pbd_cloth": {
        "triggers": ("pbd", "verlet", "distance constraint", "cloth constraint", "stretch constraint", "structural spring", "relaxation step", "position based"),
        "title": "Position-Based Dynamics (PBD) Distance Constraints (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Position-Based Dynamics (PBD) Distance Constraints (Point Wrangle) --
int nbrs[] = neighbours(0, @ptnum);
float stiffness = clamp(chf("constraint_stiffness"), 0.0, 1.0);
if (stiffness <= 0.0) stiffness = 0.5;

vector p1 = @P;
vector delta_P = {0, 0, 0};
int count = 0;

foreach (int n; nbrs) {
    vector p2 = point(0, "P", n);
    vector dir = p1 - p2;
    float current_dist = length(dir);
    float rest_dist = hasattrib(0, "point", "rest_len") ? f@rest_len : chf("default_rest_length");
    if (rest_dist <= 0.0) rest_dist = 0.1;
    
    if (current_dist > 1e-5) {
        float diff = (current_dist - rest_dist) / current_dist;
        delta_P -= 0.5 * stiffness * diff * dir;
        count++;
    }
}

if (count > 0 && !hasattrib(0, "point", "pinned")) {
    @P += delta_P / float(count);
}"""
    },

    # ── 15. Half-Edge Boundary Topology ──
    "halfedge_boundary_topology": {
        "triggers": ("halfedge", "half-edge", "boundary edge", "open edge", "border", "mesh boundary", "seam", "manifold", "edge loop", "unshared edge"),
        "title": "Half-Edge Topological Boundary & Seam Detection (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Half-Edge Topological Boundary & Seam Detection (Point Wrangle) --
int hedge = pointhedge(0, @ptnum);
int is_boundary = 0;

while (hedge != -1) {
    int opposite = hedge_equivelem(0, hedge);
    if (opposite == -1) {
        is_boundary = 1;
        break;
    }
    hedge = pointhedgenext(0, hedge);
}

i@is_boundary = is_boundary;
if (is_boundary) {
    @Cd = set(1.0, 0.1, 0.0);
    @pscale = chf("boundary_pscale");
} else {
    @Cd = set(0.2, 0.6, 0.9);
}"""
    },

    # ── 16. Cosine Harmonic Color Palettes ──
    "cosine_color_palette_harmonics": {
        "triggers": ("palette", "cosine palette", "inigo quilez", "gradient color", "color ramp", "spectral color", "color harmonics", "procedural color"),
        "title": "Inigo Quilez Cosine Harmonic Color Palettes (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Inigo Quilez Cosine Harmonic Color Palettes (Point Wrangle) --
float t = chf("color_phase") + (hasattrib(0, "point", "curveu") ? f@curveu : (@P.y * chf("freq")));

vector a = chv("palette_a"); if (length(a) == 0.0) a = set(0.5, 0.5, 0.5);
vector b = chv("palette_b"); if (length(b) == 0.0) b = set(0.5, 0.5, 0.5);
vector c = chv("palette_c"); if (length(c) == 0.0) c = set(1.0, 1.0, 1.0);
vector d = chv("palette_d"); if (length(d) == 0.0) d = set(0.00, 0.33, 0.67);

vector col = a + b * cos(6.2831853 * (c * t + d));
@Cd = clamp(col, 0.0, 1.0);"""
    },

    # ── 17. Analytical SDF Raymarching ──
    "raymarch_sphere_trace_sdf": {
        "triggers": ("raymarch", "sphere tracing", "sdf raymarch", "analytical sdf", "smooth minimum", "smin", "isosurface", "distance function"),
        "title": "Analytical SDF Raymarching & Sphere Tracing (Detail Wrangle)",
        "context": "detail wrangle",
        "blueprint": """// -- Blueprint: Analytical SDF Raymarching & Sphere Tracing (Detail Wrangle) --
int max_steps = chi("max_steps"); if (max_steps <= 0) max_steps = 64;
float max_dist = chf("max_distance"); if (max_dist <= 0.0) max_dist = 15.0;
float hit_eps = 0.001;

vector ro = set(0.0, 1.5, 4.0);
vector target = set(0.0, 0.0, 0.0);
vector cam_fwd = normalize(target - ro);
vector cam_right = normalize(cross(cam_fwd, set(0, 1, 0)));
vector cam_up = cross(cam_right, cam_fwd);

int res = chi("ray_grid_res"); if (res <= 0) res = 40;

for (int y = 0; y < res; y++) {
    for (int x = 0; x < res; x++) {
        float u = (float(x) / float(res - 1) - 0.5) * 2.0;
        float v = (float(y) / float(res - 1) - 0.5) * 2.0;
        vector rd = normalize(cam_fwd + cam_right * u + cam_up * v);
        
        float t = 0.0;
        for (int step = 0; step < max_steps; step++) {
            vector p_curr = ro + rd * t;
            float d_sphere = length(p_curr) - 1.2;
            float d_gyroid = (abs(dot(sin(p_curr * 3.0), cos(p_curr.zxy * 3.0))) - 0.2) * 0.3;
            float d = max(d_sphere, d_gyroid);
            
            if (abs(d) < hit_eps) {
                int pt = addpoint(0, p_curr);
                setpointattrib(0, "Cd", pt, normalize(p_curr) * 0.5 + 0.5, "set");
                break;
            }
            t += d;
            if (t > max_dist) break;
        }
    }
}"""
    },

    # ── 18. Ray-Mesh Intersection & Reflection ──
    "ray_mesh_intersection_reflect": {
        "triggers": ("intersect", "raycast", "reflection", "refraction", "snell", "fresnel", "bounce ray", "surface hit", "ray trace"),
        "title": "Ray-Mesh Intersection & Surface Reflection (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Ray-Mesh Intersection & Surface Reflection (Point Wrangle) --
vector ray_origin = @P;
vector ray_dir = normalize(v@v);
float max_ray_dist = chf("max_distance"); if (max_ray_dist <= 0.0) max_ray_dist = 50.0;

vector hit_P;
vector hit_uv;
int hit_prim = intersect(1, ray_origin + ray_dir * 0.001, ray_dir * max_ray_dist, hit_P, hit_uv);

if (hit_prim != -1) {
    vector hit_N = normalize(primuv(1, "N", hit_prim, hit_uv));
    vector reflected_dir = reflect(ray_dir, hit_N);
    float bounce = chf("restitution"); if (bounce <= 0.0) bounce = 0.8;
    
    @P = hit_P;
    v@v = reflected_dir * length(v@v) * bounce;
    v@N = hit_N;
    i@hit = 1;
    @Cd = set(1.0, 0.4, 0.1);
} else {
    i@hit = 0;
}"""
    },

    # ── 19. Principal Component Analysis (PCA) ──
    "pca_oriented_bounding_box": {
        "triggers": ("pca", "oriented bounding box", "obb", "eigenvalue", "covariance", "principal component", "fit box", "tight bounding box"),
        "title": "Principal Component Analysis (PCA) Minimum OBB (Detail Wrangle)",
        "context": "detail wrangle",
        "blueprint": """// -- Blueprint: Principal Component Analysis (PCA) Minimum OBB (Detail Wrangle) --
int npts = npoints(0);
if (npts < 3) return;

vector center = {0, 0, 0};
for (int i = 0; i < npts; i++) center += point(0, "P", i);
center /= float(npts);

matrix3 cov = 0;
for (int i = 0; i < npts; i++) {
    vector d = point(0, "P", i) - center;
    cov += set(d.x*d.x, d.x*d.y, d.x*d.z, d.y*d.x, d.y*d.y, d.y*d.z, d.z*d.x, d.z*d.y, d.z*d.z);
}
cov /= float(npts);

vector v1 = set(1.0, 1.0, 1.0);
for (int iter = 0; iter < 16; iter++) v1 = normalize(v1 * cov);

vector v2_seed = cross(v1, set(0, 1, 0));
if (length(v2_seed) < 0.1) v2_seed = cross(v1, set(1, 0, 0));
vector v2 = normalize(v2_seed * cov);
v2 = normalize(v2 - dot(v2, v1) * v1);
vector v3 = normalize(cross(v1, v2));

setdetailattrib(0, "pca_center", center, "set");
setdetailattrib(0, "pca_axis_x", v1, "set");
setdetailattrib(0, "pca_axis_y", v2, "set");
setdetailattrib(0, "pca_axis_z", v3, "set");
setdetailattrib(0, "pca_orient", quaternion(set(v1, v2, v3)), "set");"""
    },

    # ── 20. Point Cloud Spatial Repulsion ──
    "spatial_relaxation": {
        "triggers": ("relax points", "repel points", "distribute points", "point relaxation", "spatial repulsion"),
        "title": "Point Cloud KD-Tree Spatial Relaxation (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: KD-Tree Spatial Repulsive Relaxation --
int max_neighbors = chi("max_neighbors"); if (max_neighbors <= 0) max_neighbors = 16;
float max_radius = chf("search_radius"); if (max_radius <= 0.0) max_radius = 0.5;
float push_strength = chf("push_strength"); if (push_strength <= 0.0) push_strength = 0.2;

int near_pts[] = pcfind(0, "P", @P, max_radius, max_neighbors);
vector push = {0, 0, 0};
int count = 0;

foreach (int pt; near_pts) {
    if (pt == @ptnum) continue;
    vector other_P = point(0, "P", pt);
    vector delta = @P - other_P;
    float d = length(delta);
    if (d > 1e-5 && d < max_radius) {
        float falloff = 1.0 - (d / max_radius);
        push += normalize(delta) * (falloff * falloff);
        count++;
    }
}

if (count > 0) {
    push = (push / float(count)) * push_strength;
    if (hasattrib(0, "point", "N")) {
        push -= dot(push, normalize(@N)) * normalize(@N);
    }
    @P += push;
}"""
    },

    # ── 21. Gerstner Ocean Wave Superposition ──
    "gerstner_ocean_waves": {
        "triggers": ("gerstner", "ocean wave", "waves", "ocean", "sea", "trochoidal", "crest", "water surface", "foam", "jacobian"),
        "title": "Gerstner Ocean Wave Superposition & Whitecap Foam (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Gerstner Ocean Wave Superposition & Whitecap Foam --
int num_waves = chi("num_wave_components"); if (num_waves <= 0) num_waves = 4;
float time_scale = chf("time_speed"); if (time_scale <= 0.0) time_scale = 1.5;
float gravity = 9.81;

vector p_orig = @P;
vector disp = {0, 0, 0};
vector normal_accum = {0, 1, 0};
float jacobian_accum = 0.0;

for (int w = 0; w < num_waves; w++) {
    float angle = rand(w * 31 + 7) * 6.2831853;
    vector2 dir = normalize(set(cos(angle), sin(angle)));
    float wavelength = lerp(1.5, 12.0, rand(w * 17 + 3));
    float k = 6.2831853 / wavelength;
    float w_freq = sqrt(gravity * k);
    float amp = (1.0 / k) * chf("steepness") / float(num_waves);
    
    float phase = k * dot(dir, set(p_orig.x, p_orig.z)) - w_freq * @Time * time_scale;
    float cos_p = cos(phase);
    float sin_p = sin(phase);
    
    // Horizontal trochoidal displacement
    disp.x += dir.x * (amp * cos_p);
    disp.z += dir.y * (amp * cos_p);
    disp.y += amp * sin_p;
    
    // Wave normal accumulation
    normal_accum.x -= dir.x * (k * amp * cos_p);
    normal_accum.z -= dir.y * (k * amp * cos_p);
    
    // Jacobian determinant component for crest pinching / whitecap foam
    jacobian_accum += k * amp * sin_p;
}

@P = p_orig + disp;
v@N = normalize(normal_accum);
f@foam = clamp(fit(jacobian_accum, 0.4, 1.2, 0.0, 1.0), 0.0, 1.0);
vector deep_col = set(0.01, 0.08, 0.2);
vector crest_col = set(0.1, 0.4, 0.6);
vector foam_col = set(0.9, 0.95, 1.0);
@Cd = lerp(lerp(deep_col, crest_col, fit(@P.y, -1.0, 1.0, 0.0, 1.0)), foam_col, f@foam);"""
    },

    # ── 22. SPH Fluid Density & Pressure Forces ──
    "sph_fluid_density_pressure": {
        "triggers": ("sph", "smoothed particle", "fluid density", "tait equation", "pressure force", "fluid particle", "navier-stokes", "density gradient"),
        "title": "SPH Fluid Density & Tait Pressure Gradient Solver (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: SPH Fluid Density & Tait Pressure Gradient Solver --
float h = chf("smoothing_radius"); if (h <= 0.0) h = 0.3;
float h2 = h * h;
float rest_density = chf("rest_density"); if (rest_density <= 0.0) rest_density = 1000.0;
float stiffness = chf("gas_stiffness"); if (stiffness <= 0.0) stiffness = 50.0;

int nbrs[] = pcfind(0, "P", @P, h, 32);
float density = 0.0;
// Poly6 smoothing kernel constant: 315 / (64 * PI * h^9)
float poly6_coeff = 315.0 / (64.0 * 3.14159265 * pow(h, 9.0));

foreach (int pt; nbrs) {
    float r2 = distance2(@P, point(0, "P", pt));
    if (r2 < h2) {
        density += poly6_coeff * pow(h2 - r2, 3.0);
    }
}
density = max(density, 10.0);
f@density = density;

// Tait equation of state for weakly compressible SPH: P = B * ((rho/rho_0)^7 - 1)
float pressure = stiffness * (pow(density / rest_density, 7.0) - 1.0);
f@pressure = max(0.0, pressure);

// Spiky pressure gradient force: -45 / (PI * h^6) * (h - r)^2 * dir
float spiky_coeff = -45.0 / (3.14159265 * pow(h, 6.0));
vector f_pressure = {0, 0, 0};

foreach (int pt; nbrs) {
    if (pt == @ptnum) continue;
    vector diff = @P - point(0, "P", pt);
    float r = length(diff);
    if (r > 1e-5 && r < h) {
        float p_other = point(0, "pressure", pt);
        float p_term = (pressure + p_other) / (2.0 * density * max(point(0, "density", pt), 10.0));
        f_pressure += normalize(diff) * (spiky_coeff * pow(h - r, 2.0) * p_term);
    }
}

v@v += (f_pressure + set(0, -9.81, 0)) * @TimeInc;
@P += v@v * @TimeInc;
@Cd = chramp("density_ramp", clamp(density / (rest_density * 1.5), 0.0, 1.0));"""
    },

    # ── 23. Dijkstra Geodesic Surface Propagation ──
    "dijkstra_geodesic_propagation": {
        "triggers": ("geodesic", "dijkstra", "shortest path", "surface distance", "heat method", "pathfinding", "distance along surface", "geodesic distance"),
        "title": "Dijkstra Geodesic Surface Distance Propagation (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Dijkstra Geodesic Surface Distance Propagation --
float current_dist = hasattrib(0, "point", "geodist") ? f@geodist : 1e9;

// Seed points have geodist initialized to 0.0 (e.g. in group 'seeds')
if (inpointgroup(0, "seeds", @ptnum)) {
    current_dist = 0.0;
}

int nbrs[] = neighbours(0, @ptnum);
foreach (int n; nbrs) {
    if (hasattrib(0, "point", "geodist")) {
        float n_dist = point(0, "geodist", n);
        float edge_len = distance(@P, point(0, "P", n));
        if (n_dist + edge_len < current_dist) {
            current_dist = n_dist + edge_len;
        }
    }
}

f@geodist = current_dist;
@Cd = chramp("geodesic_contour_ramp", frac(current_dist * chf("contour_frequency")));"""
    },

    # ── 24. Differential Curve Growth ──
    "differential_curve_growth": {
        "triggers": ("differential growth", "meandering", "curve growth", "resample growth", "colonization", "wrinkle", "brain coral", "tendril branching"),
        "title": "Differential Curve Growth & Meandering Morphology (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Differential Curve Growth & Meandering Morphology --
float search_r = chf("repulsion_radius"); if (search_r <= 0.0) search_r = 0.25;
float push_force = chf("repulsion_force"); if (push_force <= 0.0) push_force = 0.15;
float smooth_weight = chf("smooth_weight"); if (smooth_weight <= 0.0) smooth_weight = 0.3;

// 1. Repulsion from nearby non-adjacent points on curve
int near_pts[] = pcfind(0, "P", @P, search_r, 20);
vector push = {0, 0, 0};
int count = 0;

foreach (int pt; near_pts) {
    // Ignore direct topological neighbors in curve
    if (abs(pt - @ptnum) <= 1) continue;
    vector diff = @P - point(0, "P", pt);
    float d = length(diff);
    if (d > 1e-5 && d < search_r) {
        push += normalize(diff) * (1.0 - (d / search_r));
        count++;
    }
}
if (count > 0) push = (push / float(count)) * push_force;

// 2. Laplacian curvature smoothing between adjacent neighbors
vector prev_P = (@ptnum > 0) ? point(0, "P", @ptnum - 1) : @P;
vector next_P = (@ptnum < npoints(0) - 1) ? point(0, "P", @ptnum + 1) : @P;
vector mid = (prev_P + next_P) * 0.5;
vector smooth_disp = (mid - @P) * smooth_weight;

@P += push + smooth_disp;
f@growth_stress = length(push);
@Cd = chramp("stress_ramp", clamp(length(push) * 5.0, 0.0, 1.0));"""
    },

    # ── 25. Procedural L-System Fractal Tree ──
    "lsystem_fractal_tree_stack": {
        "triggers": ("lsystem", "l-system", "tree", "branching", "fractal tree", "turtle graphics", "plant", "foliage", "branches", "procedural tree"),
        "title": "Procedural L-System Fractal Tree with Transform Stack (Detail Wrangle)",
        "context": "detail wrangle",
        "blueprint": """// -- Blueprint: Procedural L-System Fractal Tree with Transform Stack --
int max_depth = chi("tree_depth"); if (max_depth <= 0) max_depth = 4;
float base_len = chf("branch_length"); if (base_len <= 0.0) base_len = 1.2;
float branch_angle = radians(chf("branch_angle_deg")); if (branch_angle == 0.0) branch_angle = radians(28.0);
float ratio = chf("length_decay"); if (ratio <= 0.0) ratio = 0.72;

// Recursive stack emulation arrays
vector stack_P[];
vector stack_T[];
vector stack_N[];
float stack_len[];
int stack_depth[];
int stack_parent[];

// Push root trunk
append(stack_P, set(0, 0, 0));
append(stack_T, set(0, 1, 0));
append(stack_N, set(1, 0, 0));
append(stack_len, base_len);
append(stack_depth, 0);
append(stack_parent, -1);

while (len(stack_P) > 0) {
    int last = len(stack_P) - 1;
    vector curr_P = stack_P[last];
    vector curr_T = stack_T[last];
    vector curr_N = stack_N[last];
    float curr_len = stack_len[last];
    int depth = stack_depth[last];
    int parent_pt = stack_parent[last];
    
    // Pop
    removeindex(stack_P, last);
    removeindex(stack_T, last);
    removeindex(stack_N, last);
    removeindex(stack_len, last);
    removeindex(stack_depth, last);
    removeindex(stack_parent, last);
    
    vector next_P = curr_P + curr_T * curr_len;
    int pt0 = (parent_pt != -1) ? parent_pt : addpoint(0, curr_P);
    int pt1 = addpoint(0, next_P);
    
    int prim = addprim(0, "polyline");
    addvertex(0, prim, pt0);
    addvertex(0, prim, pt1);
    
    float u = float(depth) / float(max_depth);
    setpointattrib(0, "pscale", pt1, lerp(chf("trunk_pscale"), 0.01, u), "set");
    setpointattrib(0, "Cd", pt1, chramp("bark_leaf_ramp", u), "set");
    
    if (depth < max_depth) {
        // Spawn bifurcating branches
        vector B = normalize(cross(curr_T, curr_N));
        for (int b = -1; b <= 1; b += 2) {
            matrix3 m = ident();
            rotate(m, float(b) * branch_angle, B);
            rotate(m, rand(depth * 37 + b) * 1.5 - 0.75, curr_T);
            
            append(stack_P, next_P);
            append(stack_T, normalize(curr_T * m));
            append(stack_N, normalize(curr_N * m));
            append(stack_len, curr_len * ratio);
            append(stack_depth, depth + 1);
            append(stack_parent, pt1);
        }
    }
}"""
    },

    # ── 26. Dual Mesh Polygonization ──
    "dual_mesh_subdivision": {
        "triggers": ("dual mesh", "hexagonal", "dual graph", "voronoi dual", "centroid dual", "tessellation", "polygon dual"),
        "title": "Centroid Dual Mesh Graph Subdivision (Detail Wrangle)",
        "context": "detail wrangle",
        "blueprint": """// -- Blueprint: Centroid Dual Mesh Graph Subdivision --
int num_in_prims = nprimitives(0);
if (num_in_prims == 0) return;

// 1. Calculate centroid points for each input primitive
int dual_pts[];
for (int i = 0; i < num_in_prims; i++) {
    vector center = {0, 0, 0};
    int pts[] = primpoints(0, i);
    foreach (int p; pts) center += point(0, "P", p);
    center /= float(max(1, len(pts)));
    
    int dpt = addpoint(0, center);
    setpointattrib(0, "P", dpt, center, "set");
    setpointattrib(0, "orig_prim", dpt, i, "set");
    append(dual_pts, dpt);
}

// 2. Loop over interior vertices and connect adjacent face centroids into dual faces
for (int i = 0; i < npoints(0); i++) {
    int adj_prims[] = pointprims(0, i);
    if (len(adj_prims) >= 3) {
        int dual_poly = addprim(0, "poly");
        foreach (int pr; adj_prims) {
            addvertex(0, dual_poly, dual_pts[pr]);
        }
    }
}"""
    },

    # ── 27. Mean Curvature Flow & Minimal Surface ──
    "mean_curvature_flow_minimal_surface": {
        "triggers": ("minimal surface", "catenoid", "helicoid", "mean curvature", "soap film", "laplace beltrami", "cotangent weights", "surface tension"),
        "title": "Mean Curvature Flow & Minimal Surface Relaxation (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Mean Curvature Flow & Minimal Surface Relaxation --
// Pin boundary points to preserve open border topology
int hedge = pointhedge(0, @ptnum);
int is_border = 0;
while (hedge != -1) {
    if (hedge_equivelem(0, hedge) == -1) { is_border = 1; break; }
    hedge = pointhedgenext(0, hedge);
}

if (!is_border) {
    int nbrs[] = neighbours(0, @ptnum);
    vector laplacian = {0, 0, 0};
    float total_weight = 0.0;
    
    foreach (int n; nbrs) {
        vector diff = point(0, "P", n) - @P;
        float d = length(diff);
        if (d > 1e-5) {
            float w = 1.0 / d; // Cotangent weight approximation
            laplacian += diff * w;
            total_weight += w;
        }
    }
    
    if (total_weight > 0.0) {
        vector mean_curvature_disp = laplacian / total_weight;
        float step = chf("flow_step"); if (step <= 0.0) step = 0.25;
        @P += mean_curvature_disp * step;
        f@mean_curvature = length(mean_curvature_disp);
        @Cd = chramp("curvature_ramp", clamp(f@mean_curvature * 10.0, 0.0, 1.0));
    }
}"""
    },

    # ── 28. Dual Quaternion Blending ──
    "dual_quaternion_skinning_blend": {
        "triggers": ("dual quaternion", "dqs", "skinning", "rigid blend", "candy wrapper", "twist blend", "quaternion blend", "screw motion"),
        "title": "Dual Quaternion Rigid Transform Blending (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Dual Quaternion Rigid Transform Blending --
// Real quaternion q0 (rotation) and dual quaternion qd (translation: 0.5 * t * q0)
vector4 q_rot1 = chv4("rot_quat_1"); if (length(q_rot1) == 0.0) q_rot1 = set(0, 0, 0, 1);
vector t1 = chv("trans_1");
vector4 q_dual1 = 0.5 * qmultiply(set(t1.x, t1.y, t1.z, 0.0), q_rot1);

vector4 q_rot2 = chv4("rot_quat_2"); if (length(q_rot2) == 0.0) q_rot2 = set(0, 0, 0, 1);
vector t2 = chv("trans_2");
vector4 q_dual2 = 0.5 * qmultiply(set(t2.x, t2.y, t2.z, 0.0), q_rot2);

float weight = clamp(chf("blend_weight"), 0.0, 1.0);
if (dot(q_rot1, q_rot2) < 0.0) { q_rot2 = -q_rot2; q_dual2 = -q_dual2; }

// Dual quaternion linear blend (DLB)
vector4 q_r_blend = lerp(q_rot1, q_rot2, weight);
vector4 q_d_blend = lerp(q_dual1, q_dual2, weight);
float norm_r = length(q_r_blend);
q_r_blend /= norm_r;
q_d_blend /= norm_r;

// Extract blended rigid transformation
vector blended_t = 2.0 * qmultiply(q_d_blend, set(-q_r_blend.x, -q_r_blend.y, -q_r_blend.z, q_r_blend.w)).xyz;
@P = qrotate(q_r_blend, @P) + blended_t;
p@orient = q_r_blend;"""
    },

    # ── 29. Physarum Slime Mold Network ──
    "physarum_slime_mold_network": {
        "triggers": ("physarum", "slime mold", "transport network", "agent simulation", "chemoattractant", "mold trail", "sensor angle", "foraging"),
        "title": "Physarum Slime Mold Multi-Agent Transport Network (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Physarum Slime Mold Multi-Agent Transport Network --
float sensor_angle = radians(chf("sensor_angle_deg")); if (sensor_angle == 0.0) sensor_angle = radians(35.0);
float sensor_dist = chf("sensor_distance"); if (sensor_dist <= 0.0) sensor_dist = 0.4;
float step_size = chf("agent_speed"); if (step_size <= 0.0) step_size = 0.08;

vector dir = normalize(v@v);
if (length(dir) < 0.1) dir = set(cos(rand(@ptnum)*6.28), 0, sin(rand(@ptnum)*6.28));

// 3 Forward sensing antennas: Center, Left, Right
vector pos_c = @P + dir * sensor_dist;
matrix3 m_l = ident(); rotate(m_l, sensor_angle, set(0, 1, 0));
vector pos_l = @P + normalize(dir * m_l) * sensor_dist;
matrix3 m_r = ident(); rotate(m_r, -sensor_angle, set(0, 1, 0));
vector pos_r = @P + normalize(dir * m_r) * sensor_dist;

// Sample chemoattractant trail from input 1
float val_c = volumesample(1, "trail", pos_c);
float val_l = volumesample(1, "trail", pos_l);
float val_r = volumesample(1, "trail", pos_r);

matrix3 steer_rot = ident();
if (val_c > val_l && val_c > val_r) {
    // Continue forward
} else if (val_l > val_r) {
    rotate(steer_rot, sensor_angle, set(0, 1, 0));
} else if (val_r > val_l) {
    rotate(steer_rot, -sensor_angle, set(0, 1, 0));
} else {
    rotate(steer_rot, (rand(@ptnum + @Time) - 0.5) * sensor_angle, set(0, 1, 0));
}

v@v = normalize(dir * steer_rot) * step_size;
@P += v@v;
p@orient = quaternion(maketransform(normalize(v@v), set(0, 1, 0)));
f@trail_deposit = 1.0;
@Cd = set(1.0, 0.8, 0.2);"""
    },

    # ── 30. Space Colonization Leaf Venation ──
    "space_colonization_veins": {
        "triggers": ("space colonization", "venation", "veins", "vascular", "attractor points", "branch growth", "leaf veins", "root system"),
        "title": "Space Colonization Vascular Growth & Venation (Detail Wrangle)",
        "context": "detail wrangle",
        "blueprint": """// -- Blueprint: Space Colonization Vascular Growth & Venation --
float r_kill = chf("kill_distance"); if (r_kill <= 0.0) r_kill = 0.15;
float r_search = chf("search_radius"); if (r_search <= 0.0) r_search = 1.2;
float growth_step = chf("growth_step"); if (growth_step <= 0.0) growth_step = 0.2;

int n_attractors = npoints(1);
int n_tree_pts = npoints(0);
if (n_attractors == 0 || n_tree_pts == 0) return;

// For each tree node, accumulate attraction vectors
vector avg_growth[];
int count_attract[];
resize(avg_growth, n_tree_pts);
resize(count_attract, n_tree_pts);

for (int a = 0; a < n_attractors; a++) {
    vector p_att = point(1, "P", a);
    int nearest_node = -1;
    float min_dist = r_search;
    
    for (int t = 0; t < n_tree_pts; t++) {
        float d = distance(p_att, point(0, "P", t));
        if (d < min_dist) { min_dist = d; nearest_node = t; }
    }
    
    if (nearest_node != -1) {
        avg_growth[nearest_node] += normalize(p_att - point(0, "P", nearest_node));
        count_attract[nearest_node]++;
    }
}

// Spawn daughter branches
for (int t = 0; t < n_tree_pts; t++) {
    if (count_attract[t] > 0) {
        vector growth_dir = normalize(avg_growth[t] / float(count_attract[t]));
        vector new_P = point(0, "P", t) + growth_dir * growth_step;
        int new_pt = addpoint(0, new_P);
        int prim = addprim(0, "polyline");
        addvertex(0, prim, t);
        addvertex(0, prim, new_pt);
    }
}"""
    },

    # ── 31. Voronoi Hyperplane Shatter ──
    "voronoi_hyperplane_shatter": {
        "triggers": ("shatter", "voronoi fracture", "cutting plane", "hyperplane", "fracture", "destruction", "cell fragment", "boolean cut"),
        "title": "Voronoi Hyperplane Shatter & Distance Clustering (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Voronoi Hyperplane Shatter & Distance Clustering --
int num_seeds = npoints(1);
if (num_seeds == 0) return;

// Find closest seed (Voronoi cell cluster)
int closest_seed = -1;
float min_d = 1e9;

for (int s = 0; s < num_seeds; s++) {
    float d = distance(@P, point(1, "P", s));
    if (d < min_d) {
        min_d = d;
        closest_seed = s;
    }
}

i@class = closest_seed;
i@piece = closest_seed;
f@center_dist = min_d;

// Cell crack edge visualization
float second_min_d = 1e9;
for (int s = 0; s < num_seeds; s++) {
    if (s == closest_seed) continue;
    float d = distance(@P, point(1, "P", s));
    if (d < second_min_d) second_min_d = d;
}

f@crack_border = second_min_d - min_d;
if (f@crack_border < chf("crack_width")) {
    @Cd = set(1.0, 0.2, 0.05); // Highlight fracture seams
} else {
    @Cd = rand(closest_seed * 47 + 13);
}"""
    },

    # ── 32. Marching Cubes Implicit Voxel Polygonizer ──
    "marching_cubes_implicit_iso": {
        "triggers": ("marching cubes", "isosurface", "polygonize", "metaball", "implicit surface", "field to mesh", "scalar field mesh"),
        "title": "Marching Cubes Implicit Isosurface Polygonizer (Detail Wrangle)",
        "context": "detail wrangle",
        "blueprint": """// -- Blueprint: Marching Cubes Implicit Isosurface Polygonizer --
int res = chi("voxel_resolution"); if (res <= 0) res = 20;
float bound = chf("domain_bound"); if (bound <= 0.0) bound = 2.0;
float iso_val = chf("isovalue");
float step = (bound * 2.0) / float(res);

for (int z = 0; z < res; z++) {
    for (int y = 0; y < res; y++) {
        for (int x = 0; x < res; x++) {
            vector p0 = set(-bound + float(x)*step, -bound + float(y)*step, -bound + float(z)*step);
            // Scalar field evaluation (e.g. metaballs or gyroid)
            float v0 = length(p0) - 1.2;
            vector p1 = p0 + set(step, 0, 0); float v1 = length(p1) - 1.2;
            vector p2 = p0 + set(0, step, 0); float v2 = length(p2) - 1.2;
            vector p3 = p0 + set(0, 0, step); float v3 = length(p3) - 1.2;
            
            if ((v0 < iso_val && v1 >= iso_val) || (v0 >= iso_val && v1 < iso_val)) {
                float t = (iso_val - v0) / (v1 - v0 + 1e-5);
                int pt = addpoint(0, lerp(p0, p1, t));
                setpointattrib(0, "N", pt, normalize(lerp(p0, p1, t)), "set");
                setpointattrib(0, "Cd", pt, set(0.2, 0.7, 1.0), "set");
            }
        }
    }
}"""
    },

    # ── 33. Curved Spline Arc-Length Parameterization ──
    "curved_spline_resample_arc_length": {
        "triggers": ("arc length", "resample curve", "equal distance", "parameterize", "curve tangent", "spline sample", "motion path"),
        "title": "Curved Spline Arc-Length Uniform Resampling (Detail Wrangle)",
        "context": "detail wrangle",
        "blueprint": """// -- Blueprint: Curved Spline Arc-Length Uniform Resampling --
int n_in = npoints(0);
if (n_in < 2) return;

// 1. Calculate cumulative chord lengths
float cum_lengths[];
float total_len = 0.0;
append(cum_lengths, 0.0);

for (int i = 1; i < n_in; i++) {
    total_len += distance(point(0, "P", i - 1), point(0, "P", i));
    append(cum_lengths, total_len);
}

// 2. Sample uniform distances along curve
int num_samples = chi("target_samples"); if (num_samples <= 0) num_samples = 100;
int prim = addprim(0, "polyline");

for (int s = 0; s < num_samples; s++) {
    float target_d = (float(s) / float(num_samples - 1)) * total_len;
    
    // Find segment containing target_d
    int seg = 0;
    while (seg < n_in - 2 && cum_lengths[seg + 1] < target_d) seg++;
    
    float seg_len = cum_lengths[seg + 1] - cum_lengths[seg];
    float u = (seg_len > 1e-5) ? (target_d - cum_lengths[seg]) / seg_len : 0.0;
    
    vector P_new = lerp(point(0, "P", seg), point(0, "P", seg + 1), u);
    int pt = addpoint(0, P_new);
    addvertex(0, prim, pt);
    setpointattrib(0, "curveu", pt, float(s) / float(num_samples - 1), "set");
}"""
    },

    # ── 34. MacCormack BFECC Fluid Advection ──
    "maccormack_bfecc_advection": {
        "triggers": ("maccormack", "bfecc", "fluid advection", "error correction", "back and forth", "velocity advect", "unconditionally stable"),
        "title": "MacCormack BFECC High-Order Volume Advection (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: MacCormack BFECC High-Order Volume Advection --
float dt = chf("time_step"); if (dt <= 0.0) dt = 0.05;
vector v = v@v;

// 1. Forward step: P_star = P - dt * v
vector p_star = @P - v * dt;
float phi_star = volumesample(0, "density", p_star);

// 2. Backward step: P_dagger = P_star + dt * v(P_star)
vector v_star = volumesamplev(1, "vel", p_star);
vector p_dagger = p_star + v_star * dt;
float phi_dagger = volumesample(0, "density", p_dagger);

// 3. Error compensation: phi_bar = phi_star + 0.5 * (phi_orig - phi_dagger)
float phi_orig = volumesample(0, "density", @P);
float phi_corrected = phi_star + 0.5 * (phi_orig - phi_dagger);

// Monotonic limiter: clamp to neighborhood bounds to prevent overshoot oscillations
float min_phi = min(phi_orig, phi_star);
float max_phi = max(phi_orig, phi_star);
f@density = clamp(phi_corrected, min_phi, max_phi);
@Cd = chramp("density_ramp", f@density);"""
    },

    # ── 35. Laplacian ARAP Mesh Deformation ──
    "laplacian_mesh_deformation_arap": {
        "triggers": ("arap", "as rigid as possible", "laplacian deform", "mesh morph", "handle deformation", "surface editing", "preserve details"),
        "title": "Laplacian ARAP Surface Differential Editing (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Laplacian ARAP Surface Differential Editing --
int nbrs[] = neighbours(0, @ptnum);
int count = len(nbrs);
if (count == 0) return;

// Compute uniform discrete Laplacian differential coordinate
vector avg_neighbor = {0, 0, 0};
foreach (int n; nbrs) avg_neighbor += point(0, "P", n);
avg_neighbor /= float(count);

vector delta = @P - avg_neighbor;
v@laplacian_delta = delta;

// Preserve high-frequency detail under handle deformation
if (hasattrib(0, "point", "handle_disp")) {
    @P += v@handle_disp;
} else {
    float relax = chf("detail_preservation"); if (relax <= 0.0) relax = 0.5;
    @P = avg_neighbor + delta * relax;
}
@Cd = chramp("strain_ramp", clamp(length(delta) * 10.0, 0.0, 1.0));"""
    },

    # ── 36. MikkTSpace Tangent Space UV Derivatives ──
    "tangent_space_uv_derivatives": {
        "triggers": ("tangent space", "bitangent", "tbn", "normal map", "uv derivatives", "cotangent frame", "surface tangent"),
        "title": "MikkTSpace Orthonormal TBN Basis Construction (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: MikkTSpace Orthonormal TBN Basis Construction --
int prims[] = pointprims(0, @ptnum);
if (len(prims) == 0) return;

int pr = prims[0];
int pts[] = primpoints(0, pr);
if (len(pts) < 3) return;

vector p0 = point(0, "P", pts[0]);
vector p1 = point(0, "P", pts[1]);
vector p2 = point(0, "P", pts[2]);

vector uv0 = point(0, "uv", pts[0]);
vector uv1 = point(0, "uv", pts[1]);
vector uv2 = point(0, "uv", pts[2]);

vector dp1 = p1 - p0;
vector dp2 = p2 - p0;
vector2 duv1 = set(uv1.x - uv0.x, uv1.y - uv0.y);
vector2 duv2 = set(uv2.x - uv0.x, uv2.y - uv0.y);

float r = 1.0 / (duv1.x * duv2.y - duv1.y * duv2.x + 1e-6);
vector tangent = normalize((dp1 * duv2.y - dp2 * duv1.y) * r);
vector N = normalize(@N);

// Gram-Schmidt orthogonalize
tangent = normalize(tangent - N * dot(N, tangent));
vector bitangent = cross(N, tangent);

v@tangent = tangent;
v@bitangent = bitangent;
p@orient = quaternion(set(tangent, bitangent, N));"""
    },

    # ── 37. Harmonic Spring-Mass Lattice Jiggle ──
    "harmonic_spring_mass_lattice": {
        "triggers": ("spring mass", "spring", "hooke", "jiggle", "soft body", "elastic", "damping", "lattice spring", "structural vibration"),
        "title": "Harmonic Spring-Mass Elastic Lattice Solver (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Harmonic Spring-Mass Elastic Lattice Solver --
float k_stiff = chf("spring_stiffness"); if (k_stiff <= 0.0) k_stiff = 120.0;
float damping = chf("damping_coeff"); if (damping <= 0.0) damping = 2.5;

int nbrs[] = neighbours(0, @ptnum);
vector f_spring = {0, 0, 0};

foreach (int n; nbrs) {
    vector diff = point(0, "P", n) - @P;
    float dist = length(diff);
    float rest_len = distance(point(0, "rest", @ptnum), point(0, "rest", n));
    if (dist > 1e-5) {
        vector dir = diff / dist;
        float stretch = dist - rest_len;
        vector v_rel = point(0, "v", n) - v@v;
        // Hooke force + relative velocity viscous damping
        f_spring += (dir * (stretch * k_stiff)) + (dir * (dot(v_rel, dir) * damping));
    }
}

v@v += (f_spring + set(0, -9.81, 0)) * @TimeInc;
v@v *= (1.0 - chf("drag") * @TimeInc);
@P += v@v * @TimeInc;"""
    },

    # ── 38. Procedural Feather & Fur Grooming ──
    "procedural_feather_grooming": {
        "triggers": ("feather", "rachis", "barbs", "groom", "fur", "quill", "vane", "hair", "clumping", "strand"),
        "title": "Procedural Feather Rachis & Aerodynamic Barbs (Detail Wrangle)",
        "context": "detail wrangle",
        "blueprint": """// -- Blueprint: Procedural Feather Rachis & Aerodynamic Barbs --
int num_barbs = chi("num_barb_pairs"); if (num_barbs <= 0) num_barbs = 80;
float rachis_len = chf("feather_length"); if (rachis_len <= 0.0) rachis_len = 3.0;
float max_vane_w = chf("vane_width"); if (max_vane_w <= 0.0) max_vane_w = 0.8;

// Central Rachis spine
int rachis_prim = addprim(0, "polyline");
for (int i = 0; i <= 30; i++) {
    float u = float(i) / 30.0;
    vector P = set(0.0, u * rachis_len, pow(u, 2.0) * chf("camber"));
    int pt = addpoint(0, P);
    addvertex(0, rachis_prim, pt);
}

// Lateral Barbs (Left & Right)
for (int side = -1; side <= 1; side += 2) {
    for (int b = 1; b < num_barbs; b++) {
        float u = float(b) / float(num_barbs);
        vector root_P = set(0.0, u * rachis_len, pow(u, 2.0) * chf("camber"));
        float vane_w = sin(u * 3.14159265) * max_vane_w;
        
        int barb_prim = addprim(0, "polyline");
        int pt_root = addpoint(0, root_P);
        addvertex(0, barb_prim, pt_root);
        
        for (int seg = 1; seg <= 6; seg++) {
            float v_frac = float(seg) / 6.0;
            vector barb_P = root_P + set(float(side) * v_frac * vane_w, v_frac * 0.2, -pow(v_frac, 2.0) * 0.1);
            int pt_seg = addpoint(0, barb_P);
            addvertex(0, barb_prim, pt_seg);
            setpointattrib(0, "Cd", pt_seg, chramp("feather_iridescence", u), "set");
        }
    }
}"""
    },

    # ── 39. Discrete Gaussian & Mean Curvatures ──
    "discrete_curvatures_principal_gaussian": {
        "triggers": ("gaussian curvature", "mean curvature", "principal curvature", "shape operator", "weingarten", "ridge", "valley", "umbilic"),
        "title": "Discrete Gaussian & Mean Curvature Differential Geometry (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Discrete Gaussian & Mean Curvature Differential Geometry --
int nbrs[] = neighbours(0, @ptnum);
int count = len(nbrs);
if (count < 3) return;

// 1. Gauss-Bonnet angular defect for Gaussian curvature K = (2*PI - sum(angles)) / Area
float angle_sum = 0.0;
for (int i = 0; i < count; i++) {
    vector v1 = normalize(point(0, "P", nbrs[i]) - @P);
    vector v2 = normalize(point(0, "P", nbrs[(i + 1) % count]) - @P);
    angle_sum += acos(clamp(dot(v1, v2), -1.0, 1.0));
}
float K = (6.2831853 - angle_sum);
f@gaussian_curvature = K;

// 2. Mean curvature vector H
vector lap = {0, 0, 0};
foreach (int n; nbrs) lap += (point(0, "P", n) - @P);
lap /= float(count);
float H = 0.5 * dot(lap, normalize(@N));
f@mean_curvature = H;

// Color: Blue = elliptic (K > 0), Red = hyperbolic/saddle (K < 0), White = parabolic/flat
@Cd = (K > 0.0) ? lerp(set(1,1,1), set(0.1, 0.4, 1.0), clamp(K * 5.0, 0.0, 1.0))
                : lerp(set(1,1,1), set(1.0, 0.2, 0.1), clamp(-K * 5.0, 0.0, 1.0));"""
    },

    # ── 40. Rigid Body Impulse Manifold Contact ──
    "rigid_body_impulse_manifold": {
        "triggers": ("impulse", "rigid body", "contact resolution", "restitution impulse", "torque impulse", "angular momentum", "rbd collision"),
        "title": "Rigid Body Dynamics Impulse Collision Resolution (Point Wrangle)",
        "context": "point wrangle",
        "blueprint": """// -- Blueprint: Rigid Body Dynamics Impulse Collision Resolution --
float dist = volumesample(1, "surface", @P);
float margin = chf("contact_threshold"); if (margin <= 0.0) margin = 0.02;

if (dist < margin) {
    vector nml = normalize(volumegradient(1, "surface", @P));
    vector vel = v@v;
    vector omega = hasattrib(0, "point", "w") ? v@w : {0, 0, 0};
    vector r = @P - (hasattrib(0, "point", "com") ? v@com : @P);
    
    // Contact point velocity: v_contact = v + omega x r
    vector v_contact = vel + cross(omega, r);
    float v_rel_norm = dot(v_contact, nml);
    
    if (v_rel_norm < 0.0) {
        float restitution = chf("restitution"); if (restitution <= 0.0) restitution = 0.6;
        float mass = hasattrib(0, "point", "mass") ? f@mass : 1.0;
        
        // Impulse magnitude: J = -(1 + e) * v_rel_norm / (1/m + (r x n)^2 / I)
        float impulse_mag = -(1.0 + restitution) * v_rel_norm * mass;
        vector impulse = nml * impulse_mag;
        
        v@v += impulse / mass;
        if (hasattrib(0, "point", "w")) {
            v@w += cross(r, impulse) * chf("inv_inertia");
        }
        @P += nml * (margin - dist);
        @Cd = set(1.2, 0.3, 0.1);
    }
}"""
    }
}

class VEXRAGEngine:
    def __init__(self):
        self.catalog = load_1115_catalog()
        self.recipes = VEX_MASTER_RECIPES

    def reload(self):
        self.catalog = load_1115_catalog()

    def retrieve_recipes_for_task(self, prompt: str) -> list:
        p_lower = prompt.lower()
        matched = []
        for key, rec in self.recipes.items():
            score = 0
            for trig in rec["triggers"]:
                if trig in p_lower:
                    score += 1
            if score > 0:
                matched.append((rec, score))
        matched.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matched[:2]]

    def retrieve_signatures_for_task(self, prompt: str, max_results: int = 8) -> list:
        p_lower = prompt.lower()
        matched_funcs = []

        # 1. Exact function name keyword matching
        for func_name in self.catalog.keys():
            pattern = rf"\b{re.escape(func_name)}\b"
            if re.search(pattern, p_lower):
                matched_funcs.append((func_name, 20))

        # 2. Semantic topic matching across all 40 domains
        topic_triggers = {
            ("set attribute", "setpointattrib", "setprimattrib", "setdetailattrib", "set point", "set prim", "accumulate attribute", "write attribute"): 
                ["setpointattrib", "setprimattrib", "setdetailattrib", "addattrib", "setattribtypeinfo"],
            ("closest", "projection", "surface query", "distance to surface", "nearest surface", "snap to surface"): 
                ["xyzdist", "primuv", "minpos", "surfacedist"],
            ("point cloud", "pc filter", "pc filter color", "pc import", "pointcloud"): 
                ["pcopen", "pciterate", "pcimport", "pcfilter", "pcclose", "pcfind", "pcfind_radius"],
            ("neighbors", "neighbor points", "k nearest", "nearpoints", "nearpoint"): 
                ["nearpoints", "nearpoint", "neighbours", "neighbourcount", "neighbour"],
            ("half edge", "halfedge", "boundary", "open mesh", "edge loop", "crease", "boundary edge", "seam"): 
                ["pointhedge", "pointhedgenext", "hedge_nextequiv", "hedge_dstpoint", "hedge_isprimary", "hedge_prim", "hedge_srcpoint", "hedge_equivelem"],
            ("quaternion", "orient", "rotation", "rotate", "lookat", "slerp", "dihedral", "aim"): 
                ["quaternion", "qrotate", "qmultiply", "slerp", "dihedral", "lookat", "maketransform", "eulertoquaternion"],
            ("eigen", "eigenvalues", "covariance", "decomposition", "svd", "polar", "pca"): 
                ["svd", "polardecomp", "eigenvalues", "diagonal", "trace"],
            ("volume", "sdf", "vdb", "gradient", "density", "sample volume", "curl", "vorticity", "divergence", "rk4", "viscosity", "bfecc"): 
                ["volumesample", "volumesamplev", "volumegradient", "volumeindex", "volumeindexv", "nametoprim", "volumeres", "volumevoxelsize"],
            ("ray", "raycast", "intersect", "reflection", "refraction", "fresnel", "bounce", "snell"): 
                ["intersect", "intersect_all", "reflect", "refract", "fresnel"],
            ("array", "sort", "reverse", "resize", "insert", "append", "push", "pop"): 
                ["append", "sort", "reverse", "resize", "insert", "find", "push", "pop", "len", "slice"],
            ("create points", "generate curve", "add points", "spiral", "knot", "polygon", "mesh", "ribbon", "tendril", "catenary", "feather"): 
                ["addpoint", "addprim", "addvertex", "removeprim", "setprimintrinsic"],
            ("group", "point group", "prim group", "in group", "add to group"): 
                ["setpointgroup", "setprimgroup", "inpointgroup", "inprimgroup", "pointgroup", "primgroup"],
            ("matrix", "transform", "invert", "transpose", "determinant", "affine"): 
                ["ident", "invert", "transpose", "determinant", "scale", "translate", "rotate"],
            ("string", "format", "sprintf", "concat", "regex"): 
                ["sprintf", "concat", "split", "startswith", "endswith", "strip", "match"],
            ("color", "palette", "rgb", "hsv", "harmonics", "gradient"): 
                ["rgbtohsv", "hsvtorgb", "chramp", "chrampeval"],
            ("bounding box", "bbox", "relbbox", "normalize coordinates"): 
                ["relbbox", "getbbox_min", "getbbox_max", "getbbox_size", "getbbox_center"],
            ("channel", "chf", "chi", "chv", "chramp", "ramp", "parameter"): 
                ["chf", "chi", "chv", "chramp", "chs", "chrampeval"],
            ("noise", "perlin", "simplex", "worley", "curl noise", "anoise"): 
                ["noise", "curlnoise", "anoise", "snoise", "wnoise", "pnoise", "flownoise"],
            ("math", "trig", "fit", "clamp", "smooth", "lerp", "cross", "dot", "distance", "length", "cosh", "sinh"): 
                ["fit", "clamp", "lerp", "cross", "dot", "normalize", "distance", "smooth", "asin", "acos", "atan2", "cosh", "sinh"]
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
        blocks = []
        recipes = self.retrieve_recipes_for_task(prompt)
        if recipes:
            for rec in recipes:
                blocks.append(
                    f"Master Architectural Reference Pattern ({rec['title']}):\n"
                    f"```c\n{rec['blueprint']}\n```\n"
                    "Note: Use the structural architecture above as a blueprint. Adapt equations and channels to the user's specific prompt."
                )
            
        sigs = self.retrieve_signatures_for_task(prompt)
        if sigs:
            lines = ["Official SideFX VEX Function Signatures (Ground Truth Reference):"]
            for s in sigs:
                lines.append(f"  - {s}")
            blocks.append("\n".join(lines))
            
        return "\n\n".join(blocks)

_rag_engine = VEXRAGEngine()

def get_vex_rag_engine() -> VEXRAGEngine:
    return _rag_engine
