"""
Turn a VEX compile error into a short, factual hint for the repair prompt.

The model's most common compile failures are API near-misses: a function that does not exist in VEX (round,
capitalize, mean, neighbourpoints, padzero ...), an attribute used without its @ binding, or an overloaded
function whose return type cannot be inferred. The compiler names the problem but not the fix; this module adds
the fix, using the compiler's own list of 951 functions (data/vex_signatures_vcc.json, from `vcc -X cvex`).

    hints_for_error("Call to undefined function 'round'.  (1,8:12)")
    -> "'round' is not a VEX function. Use rint(x) to round to the nearest integer value ..."

Pure Python (no hou), safe to import anywhere; returns "" when it has nothing useful to say.
"""
import difflib
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_SIGS = None

# names the model reaches for -> what VEX actually offers
ALIASES = {
    "round": "Use rint(x) to round to the nearest integer value (also floor, ceil, trunc).",
    "capitalize": "Use titlecase(s) (first letter of each word) or toupper(s).",
    "uppercase": "Use toupper(s).", "upper": "Use toupper(s).",
    "lowercase": "Use tolower(s).", "lower": "Use tolower(s).",
    "mean": "Use avg(array) for the mean of an array.", "average": "Use avg(array) for the mean of an array.",
    "simplex": "Use xnoise(pos) for simplex noise.", "simplexnoise": "Use xnoise(pos) for simplex noise.",
    "perlin": "Use noise(pos) for Perlin noise.", "perlinnoise": "Use noise(pos) for Perlin noise.",
    "nelements": "Use npoints(0), nprimitives(0) or len(array).",
    "neighbourpoints": "Use neighbours(0, ptnum), which returns the connected point numbers.",
    "neighbors": "Use neighbours(0, ptnum) (British spelling).", "neighbor": "Use neighbour(0, ptnum, index) (British spelling).",
    "neighborcount": "Use neighbourcount(0, ptnum) (British spelling).",
    "pointneighbours": "Use neighbours(0, ptnum).", "pointneighbors": "Use neighbours(0, ptnum).",
    "swap": "VEX has no swap(): use a temporary variable (float t = a; a = b; b = t;).",
    "padzero": "padzero is an HScript expression, not VEX: use sprintf(\"%04d\", n).",
    "strcat": "Use concat(a, b, ...) or the + operator on strings.",
    "substr": "Use slicing s[start:end] or slice(s, start, end).", "substring": "Use slicing s[start:end] or slice(s, start, end).",
    "tostring": "Use itoa(int) or sprintf(\"%g\", value).", "str": "Use itoa(int) or sprintf(\"%g\", value).",
    "toint": "Use atoi(string).", "tofloat": "Use atof(string).", "parseint": "Use atoi(string).", "parsefloat": "Use atof(string).",
    "magnitude": "Use length(v).", "norm": "Use length(v).", "normalise": "Use normalize(v).",
    "mix": "Use lerp(a, b, t).", "saturate": "Use clamp(x, 0, 1).", "smoothstep": "Use smooth(min, max, x).",
    "step": "VEX has no step(): write (x >= edge ? 1.0 : 0.0).",
    "mod": "Use the % operator.", "fmod": "Use the % operator.", "sqr": "Use x * x or pow(x, 2).",
    "getattrib": "Read attributes with point(0, name, ptnum), prim(0, name, primnum), vertex(...) or detail(0, name).",
    "getpointattrib": "Use point(0, name, ptnum).", "getprimattrib": "Use prim(0, name, primnum).",
    "addgroup": "Use setpointgroup(0, name, ptnum, 1) or setprimgroup(0, name, primnum, 1).",
    "setgroup": "Use setpointgroup(0, name, ptnum, 1) or setprimgroup(0, name, primnum, 1).",
    "ingroup": "Use inpointgroup(0, name, ptnum) or inprimgroup(0, name, primnum).",
    "removepoints": "Use removepoint(0, ptnum).", "deletepoint": "Use removepoint(0, ptnum).", "deleteprim": "Use removeprim(0, primnum, andpoints).",
    "primcenter": "Average the positions of primpoints(0, primnum), or use primuv(0, \"P\", primnum, {0.5, 0.5, 0}).",
    "primcentroid": "Average the positions of primpoints(0, primnum), or use primuv(0, \"P\", primnum, {0.5, 0.5, 0}).",
    "primarea": "Use primintrinsic(0, \"measuredarea\", primnum).", "primnormal": "Use prim_normal(0, primnum, {0.5, 0.5, 0}).",
    "bbox": "Use getbbox(0, min, max), getbbox_min/max/center/size(0).", "getbounds": "Use getbbox(0, min, max).",
    "randint": "Use int(rand(seed) * n).", "rand01": "Use rand(seed).",
    "size": "Use len(array).", "count": "Use len(array).", "arraylength": "Use len(array).", "length_array": "Use len(array).",
    "contains": "Use find(array_or_string, value) >= 0.", "indexof": "Use find(array_or_string, value).",
    "trim": "Use strip(s).", "format": "Use sprintf(fmt, ...).", "print": "Use printf(fmt, ...).",
    "inverse": "Use invert(m).", "identity": "Use ident().", "transposed": "Use transpose(m).",
    "quatmultiply": "Use qmultiply(a, b).", "qmul": "Use qmultiply(a, b).", "quatrotate": "Use qrotate(q, v).",
    "eulertoquat": "Use eulertoquaternion(radians, order).", "quattoeuler": "Use quaterniontoeuler(q, order).",
    "axisangle": "Use quaternion(angle_radians, axis).", "matrixfromquat": "Use qconvert(q).",
    "closeprim": "Use setprimintrinsic(0, \"closed\", primnum, 1).",
    "connectprim": "Use addprim(0, \"polyline\", pt0, pt1) to connect points.",
    "nearestpoint": "Use nearpoint(0, pos).", "closestpoint": "Use nearpoint(0, pos) (a point) or minpos(0, pos) (a surface position).",
    "closestpoints": "Use nearpoints(0, pos, maxdist, maxpts) or pcfind(0, \"P\", pos, radius, maxpts).",
    "raycast": "Use intersect(0, origin, dir, pos, u, v).", "rayintersect": "Use intersect(0, origin, dir, pos, u, v).",
    "samplevolume": "Use volumesample(0, name, pos).", "volumevalue": "Use volumesample(0, name, pos).",
    "volumenormal": "Use normalize(volumegradient(0, name, pos)).",
    "angle": "VEX has no angle(): the angle between two vectors is acos(dot(normalize(a), normalize(b))) in radians; wrap it in degrees() for degrees.",
    "angle_between": "VEX has no angle_between(): use acos(dot(normalize(a), normalize(b))) (radians); wrap it in degrees() for degrees.",
    "anglebetween": "Use acos(dot(normalize(a), normalize(b))) (radians); wrap it in degrees() for degrees.",
    "strcmp": "Compare strings with == and != (match(pattern, s) tests a wildcard pattern).",
    "det": "Use determinant(m).",
    "remap": "Use fit(value, oldmin, oldmax, newmin, newmax).",
    "map": "Use fit(value, oldmin, oldmax, newmin, newmax).",
    "hash": "Use random_shash(s) for a string, random_ihash(i) for an integer or random_fhash(f) for a float.",
    "argmax": "VEX has no argmax(): int order[] = argsort(values); the last entry of order is the index of the largest value.",
    "argmin": "VEX has no argmin(): int order[] = argsort(values); order[0] is the index of the smallest value.",
    "ptnum": "ptnum is a variable, not a function: write @ptnum.",
    "primnum": "primnum is a variable, not a function: write @primnum.",
    "vtxnum": "vtxnum is a variable, not a function: write @vtxnum.",
    "numpt": "Use the variable @numpt or npoints(0).", "numprim": "Use the variable @numprim or nprimitives(0).",
    "pointgroup": "Use inpointgroup(0, name, ptnum) to test membership and setpointgroup(0, name, ptnum, 1) to add a point.",
    "primgroup": "Use inprimgroup(0, name, primnum) to test membership and setprimgroup(0, name, primnum, 1) to add a primitive.",
    "group": "Use inpointgroup(0, name, ptnum) / inprimgroup(0, name, primnum) to test membership, expandpointgroup(0, name) to list a group.",
    "points": "Use primpoints(0, primnum) for the points of a primitive or expandpointgroup(0, name) for the points of a group.",
    "normal": "The normal is an attribute: use @N, or prim_normal(0, primnum, {0.5, 0.5, 0}) for a face normal.",
    "matrix3": "matrix3 is a type: cast with (matrix3)m, or build one with ident() or set(...).",
    "matrix": "matrix is a type: cast with (matrix)m, or build one with ident() or maketransform(...).",
    "dict": "dict is a type: declare  dict d;  and assign entries with d[\"key\"] = value;",
    "sq": "Use x * x.", "square": "Use x * x.", "cube": "Use x * x * x.",
    "isnull": "Compare with a default instead, or test attributes with haspointattrib(0, name).",
    "exists": "Test attributes with haspointattrib / hasprimattrib / hasdetailattrib(0, name).",
    "median": "VEX has no median(): sort the array with sort() and take the middle entry (the average of the two middle entries for an even count).",
    "stddev": "VEX has no stddev(): compute the mean with avg(array), then the square root of the mean squared difference.",
    "std": "VEX has no std(): compute the mean with avg(array), then the square root of the mean squared difference.",
}

# names that are attributes or globals of a wrangle, with the binding to use when the compiler calls them undefined
BUILTIN_NAMES = {
    "P": "@P (vector position)", "N": "@N (vector normal)", "Cd": "@Cd (vector colour)", "v": "@v (vector velocity)",
    "uv": "@uv (vector)", "up": "v@up (vector)", "orient": "p@orient (quaternion)", "pscale": "@pscale (float)",
    "Alpha": "@Alpha (float)", "id": "@id (int)", "age": "@age (float)", "life": "@life (float)",
    "ptnum": "@ptnum (int, the current point number)", "primnum": "@primnum (int, the current primitive number)",
    "vtxnum": "@vtxnum (int, the current vertex number)", "elemnum": "@elemnum (int, the current element number)",
    "numpt": "@numpt (int, the number of points)", "numprim": "@numprim (int, the number of primitives)",
    "numvtx": "@numvtx (int)", "Time": "@Time (float, seconds)", "Frame": "@Frame (float)", "TimeInc": "@TimeInc (float)",
    "density": "@density (float voxel value in a Volume Wrangle)",
}
# prefixes that say what a function does to its target: a suggestion that swaps them is the opposite function
_VERBS = ("get", "set", "add", "remove", "has", "find", "is", "in", "n")


def _signatures():
    global _SIGS
    if _SIGS is None:
        root = os.environ.get("AI_WRANGLE_ROOT") or os.path.abspath(os.path.join(_HERE, ".."))
        try:
            _SIGS = json.load(open(os.path.join(root, "data", "vex_signatures_vcc.json"), encoding="utf-8"))
        except Exception:
            _SIGS = {}
    return _SIGS


def _pretty(sig):
    return re.sub(r"\s*;\s*", ", ", sig).replace("( ", "(").replace(" )", ")")


def real_signatures(name, limit=3):
    return [_pretty(s) for s in _signatures().get(name, [])[:limit]]


def _documented(fn, max_usage=1):
    """'usage line  // summary' from the function reference, else the compiler's signature, else the bare name."""
    try:
        import vex_function_index
        lines = vex_function_index.signature_lines(fn, max_usage=max_usage)
    except Exception:
        lines = []
    usage = [x for x in lines if not x.startswith("//")]
    note = [x[2:].split(":", 1)[-1].strip() for x in lines if x.startswith("//")]
    if usage:
        text = note[0].split(" Note: ")[0].split(". ")[0].rstrip(".") if note else ""
        try:
            extra = vex_function_index.note_for(fn)  # argument order and special values, when there is a note
        except Exception:
            extra = ""
        return "; ".join(usage) + (f" ({text[:110]})" if text else "") + (f" Note: {extra}" if extra else "")
    s = real_signatures(fn, 1)
    return s[0] if s else fn


def _verb(name):
    """the leading verb of a function name ('set' for setpointattrib, '' if none)"""
    for v in sorted(_VERBS, key=len, reverse=True):
        if name.startswith(v) and len(name) > len(v) + 2:
            return v
    return ""


def similar_functions(name, task="", limit=3):
    """Real VEX functions that a made-up function name probably stands for, most likely first:
      0. the same name in other letter case (VEX is case-sensitive: Rand -> rand), alone;
      1. real names that begin with it (polar -> polardecomp, det -> determinant, svd -> svddecomp);
      2. the functions whose documentation fits the words of the name (polarDecomposition -> 'polar
         decomposition', volumexsize -> 'volume x size': vex_function_index.match_pages);
      3. a real name spelled almost like it (uniqvals -> uniquevals), unless it differs in its leading verb
         (getvertexattrib must not suggest setvertexattrib).
    A candidate found by more than one route comes first."""
    sigs = _signatures()
    low = name.lower()
    if low in sigs and low != name:
        return [low]
    routes = []
    if len(low) >= 3:
        routes.append(sorted((f for f in sigs if f.startswith(low) and f != low), key=len)[:2])
    try:
        import vex_function_index
        words = vex_function_index.split_name(name)
        routes.append([f for f, _ in vex_function_index.match_pages(words, k=3, min_score=0.2, context_text=task)])
    except Exception:
        pass
    if len(low) >= 5:  # short names resemble too many real ones by chance
        routes.append([m for m in difflib.get_close_matches(low, list(sigs), n=2, cutoff=0.74)
                       if not _verb(low) or _verb(m) in ("", _verb(low))])
    count, order = {}, []
    for r in routes:
        for f in r:
            if f in sigs and f != name:
                if f not in count:
                    order.append(f)
                count[f] = count.get(f, 0) + 1
    order.sort(key=lambda f: -count[f])  # stable: ties keep the route order
    return order[:limit]


def hints_for_error(error_text, max_chars=900, task=""):
    """Hint text for a VEX compile error ('' if none). task: the user's request (only used to decide whether
    functions of special topics such as USD may be suggested)."""
    if not error_text:
        return ""
    sigs = _signatures()
    out = []
    for name in dict.fromkeys(re.findall(r"undefined function '(\w+)'", error_text)):
        if name in sigs:
            continue
        line = f"'{name}' is not a VEX function."
        alias = ALIASES.get(name.lower())
        if alias:
            line += " " + alias
        # a hand-written note is the precise answer; the automatic suggestions are for names it does not cover
        close = [] if alias else similar_functions(name, task)
        if close:
            line += " Real functions that may be what you need: " + "; ".join(_documented(f) for f in close) + "."
        if alias or close:
            out.append(line)
    for name in dict.fromkeys(re.findall(r"undefined variable:\s*(\w+)", error_text)):
        if name in BUILTIN_NAMES:
            out.append(f"'{name}' needs its @: write {BUILTIN_NAMES[name]}.")
            continue
        out.append(f"'{name}' is not a declared variable. If it is an attribute, bind it with its type: s@{name} (string), "
                   f"f@{name} (float), v@{name} (vector) or i@{name} (int); if it is a parameter of the node, read it with "
                   f"chf(\"{name}\") (float), chi (int), chs (string) or chv (vector); otherwise declare it before use.")
    for name in dict.fromkeys(re.findall(r"Ambiguous call to function (\w+)\(\)", error_text)):
        out.append(f"{name}() is overloaded and its type cannot be inferred here: store the overloaded value in a typed "
                   f"variable first (for example  vector q = point(0, \"P\", n);  float r = rand(seed);  string names[] = "
                   f"uniquevals(0, \"point\", \"name\");) and use that variable.")
    # wrong arguments for a real function: show how the documentation writes the call, with argument names
    for name in dict.fromkeys(re.findall(r"No matching function for (?:[\w\[\]]+\s+)?(\w+)\(", error_text)):
        if name in sigs:
            shown = _documented(name, max_usage=2)
            if "(" in shown:
                out.append(f"{name}() was called with the wrong arguments. Documented usage: {shown}.")
    text = " ".join(out)
    return text[:max_chars]


if __name__ == "__main__":
    for e in ("Call to undefined function 'round'.  (1,8:12)", "Call to undefined function 'neighbourpoints'.",
              "Call to undefined function 'simplex'.", "Reference to undefined variable: name  (1,5:8)",
              "Ambiguous call to function len(). Candidates are: int len(int[]), int len(string[])",
              "Call to undefined function 'nelements'.", "Call to undefined function 'volumevoxelsize'.",
              "Call to undefined function 'polar'.", "Call to undefined function 'polarDecomposition'.",
              "Call to undefined function 'volumexsize'.", "Call to undefined function 'det'.",
              "Call to undefined function 'nametopointcount'.", "Call to undefined function 'npointsinGroup'.",
              "No matching function for int volumeres(int; string; int). Candidates are: vector volumeres(int; int)",
              "No matching function for int find(float; string)."):
        print(e[:60], "->", hints_for_error(e) or "(no hint)")


