"""
Result check: after a snippet has been applied, describe what it did to the geometry and let the model judge
whether that is what the request asked for.

    lines = observe(node)                               what the snippet did (text lines)
    ok, reason = review(node, task, context, code)      True / False / None (no verdict) and the model's sentence

The check needs a model that was trained for it (v56 and later): shown its own wrong answer, an untrained model
approves it (v55 approved 35 of 44 wrong answers on unseen tasks). v56 says NO to 31 of 54 of its wrong answers and
to 11 of 72 right ones (126 held-out prompts, 2026-11-15): an approved answer is right about four times in five, a
rejected one is wrong about three times in four. It is a warning for the user, not a repair: asked to fix what it
flags, the model fixes 2 of 54.

The description is exact on small geometry. Above MAX_ELEMENTS points or primitives it is computed on an evenly
spaced sample (and says so), so the check costs a fraction of a second on any input.

The request text and the system prompt are the ones the model was trained with: do not reword them.
"""
import math
import os
import re

import hou

MAX_ELEMENTS = 5000          # elements of one kind that are read; more are sampled evenly
MAX_GROUP_COUNT = 200000     # above this number of elements group sizes are not counted
MAX_VOXELS = 2000000
MAX_LINES = 14

REVIEW_SYSTEM = ("You are an expert SideFX Houdini VEX programmer reviewing what a wrangle did to its geometry. "
                 "Answer YES or NO, then one short sentence.")
VERDICT_ASK = ("Does this result do what the task asks for? Answer with the single word YES or NO, "
               "then one short sentence with the reason.")
_SIZES = {1: "float", 2: "vector2", 3: "vector", 4: "vector4", 9: "matrix3", 16: "matrix"}


def _plain(v):
    """hou.Vector2/3/4, hou.Matrix* and similar values (inside dict attributes) -> tuples."""
    if isinstance(v, (str, dict, tuple, list, int, float)) or v is None:
        return v
    try:
        return tuple(v.asTuple()) if hasattr(v, "asTuple") else tuple(v)
    except Exception:
        return str(v)


def _vals_close(a, b, tol):
    a, b = _plain(a), _plain(b)
    if isinstance(a, dict) or isinstance(b, dict):
        return (isinstance(a, dict) and isinstance(b, dict) and set(a) == set(b)
                and all(_vals_close(a[k], b[k], tol) for k in a))
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    if isinstance(a, (tuple, list)) or isinstance(b, (tuple, list)):
        a = list(a) if isinstance(a, (tuple, list)) else [a]
        b = list(b) if isinstance(b, (tuple, list)) else [b]
        return len(a) == len(b) and all(_vals_close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, int):
        return abs(a - float(b)) <= 1e-6 * max(1.0, abs(a))
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)))


def _is_quat(attr):
    n = attr.name()
    if attr.qualifier() == "Quaternion":
        return True
    return attr.size() == 4 and (n in ("orient", "rot") or "orient" in n.lower() or "quat" in n.lower())


def _flat(v):
    v = _plain(v)
    if isinstance(v, (tuple, list)):
        out = []
        for x in v:
            out += _flat(x)
        return out
    if isinstance(v, dict):
        out = []
        for x in v.values():
            out += _flat(x)
        return out
    return [v]


def _vex_type(a):
    dt, n = a.dataType(), a.size()
    arr = "[]" if a.isArrayType() else ""
    if dt == hou.attribData.String:
        return "string" + arr
    if dt == hou.attribData.Dict:
        return "dict" + arr
    if dt == hou.attribData.Int:
        return ("int" if n == 1 else f"int{n}") + arr
    if arr:
        return _SIZES.get(n, f"float{n}") + arr
    if _is_quat(a):
        return "vector4 (quaternion)"
    return _SIZES.get(n, f"float{n}")


def _short(v, nd=3):
    if isinstance(v, float):
        return repr(round(v, nd))
    if isinstance(v, (tuple, list)):
        return "(" + ", ".join(_short(x, nd) for x in list(v)[:9]) + (", ..." if len(v) > 9 else "") + ")"
    if isinstance(v, str):
        return '"' + (v if len(v) <= 40 else v[:37] + "...") + '"'
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {_short(x, nd)}" for k, x in list(v.items())[:4]) + "}"
    return repr(v)


def _counts(geo):
    return (int(geo.intrinsicValue("pointcount")), int(geo.intrinsicValue("primitivecount")),
            int(geo.intrinsicValue("vertexcount")))


def _pick(n):
    """Indices that are read: all of them, or MAX_ELEMENTS evenly spaced ones."""
    if n <= MAX_ELEMENTS:
        return None
    step = n / float(MAX_ELEMENTS)
    return sorted({min(n - 1, int(i * step)) for i in range(MAX_ELEMENTS)})


def _elems(geo, kind):
    """(elements that are read, attributes, True when they are a sample)"""
    npt, npr, _ = _counts(geo)
    if kind == "point":
        idx = _pick(npt)
        return (geo.points() if idx is None else [geo.iterPoints()[i] for i in idx]), geo.pointAttribs(), idx is not None
    if kind == "primitive":
        idx = _pick(npr)
        return (geo.prims() if idx is None else [geo.iterPrims()[i] for i in idx]), geo.primAttribs(), idx is not None
    if kind == "vertex":
        idx = _pick(npr)
        prims = geo.prims() if idx is None else [geo.iterPrims()[i] for i in idx]
        verts = [v for p in prims for v in p.vertices()]
        return verts[:MAX_ELEMENTS * 4], geo.vertexAttribs(), idx is not None or len(verts) > MAX_ELEMENTS * 4
    return [geo], geo.globalAttribs(), False


def _prim_points(prim):
    try:
        return [v.point().number() for v in prim.vertices()]
    except Exception:
        return []


def _closed(prim):
    try:
        return bool(prim.isClosed())
    except Exception:
        return False


def _prim_summary(geo):
    cnt = {}
    prims, _, sampled = _elems(geo, "primitive")
    for p in prims:
        name = p.type().name()
        if p.type() == hou.primType.Polygon:
            name = "closed polygon" if _closed(p) else "open polyline"
        cnt[name] = cnt.get(name, 0) + 1
    if sampled:
        return ", ".join(sorted(cnt)) or "none"
    return ", ".join(f"{k} x{v}" for k, v in sorted(cnt.items())) or "none"


def _stats(vals):
    flat = [x for v in vals for x in _flat(v)]
    nums = [float(x) for x in flat if isinstance(x, (int, float))]
    if not nums:
        uniq = sorted({str(x) for x in flat})
        return f"{len(uniq)} distinct value(s): " + ", ".join(_short(u) for u in uniq[:5]) + (" ..." if len(uniq) > 5 else "")
    bad = sum(1 for x in nums if math.isnan(x) or math.isinf(x))
    good = [x for x in nums if not (math.isnan(x) or math.isinf(x))]
    s = (f"min {round(min(good), 4)} max {round(max(good), 4)} mean {round(sum(good) / len(good), 4)}"
         if good else "no finite values")
    if flat and all(isinstance(x, int) for x in flat):
        uniq = sorted(set(flat))
        if len(uniq) <= 8:
            s += f" values {uniq}"
    if bad:
        s += f"  !! {bad} NaN/inf values"
    return s


def describe_delta(g0, g1, max_lines=40):
    """Lines describing what changed between the input (g0, may be None) and the output geometry (g1)."""
    lines = []
    n0 = _counts(g0) if g0 is not None else (0, 0, 0)
    n1 = _counts(g1)
    if n0 != n1:
        lines.append(f"element counts changed: points {n0[0]} -> {n1[0]}, primitives {n0[1]} -> {n1[1]}, "
                     f"vertices {n0[2]} -> {n1[2]} (output primitives: {_prim_summary(g1)})")
    same_layout = n0 == n1
    sampled_any = False
    for kind in ("point", "primitive", "vertex", "detail"):
        e1, a1, sampled = _elems(g1, kind)
        e0, a0, _ = _elems(g0, kind) if g0 is not None else ([], [], False)
        sampled_any = sampled_any or sampled
        old = {a.name() for a in a0}
        new_names = {a.name() for a in a1}
        for a in a1:
            if not e1:
                continue
            try:
                v1 = [e.attribValue(a.name()) for e in e1]
            except Exception:
                continue
            if a.name() not in old:
                lines.append(f"NEW {kind} attribute {a.name()} ({_vex_type(a)}): {_stats(v1)}; first {_short(v1[0])}")
            elif same_layout and len(e0) == len(e1):
                v0 = [e.attribValue(a.name()) for e in e0]
                ch = sum(1 for x, y in zip(v0, v1) if not _vals_close(x, y, 1e-6))
                if ch:
                    lines.append(f"CHANGED {kind} attribute {a.name()}: {ch} of {len(v1)} elements differ; now {_stats(v1)}")
            elif kind != "detail":
                lines.append(f"{kind} attribute {a.name()} on the new element layout: {_stats(v1)}")
        for a in a0:
            if a.name() not in new_names:
                lines.append(f"REMOVED {kind} attribute {a.name()}")
    for label in ("point", "primitive"):
        total = n1[0] if label == "point" else n1[1]

        def members(g):
            if total > MAX_GROUP_COUNT:
                return None
            return len(g.points()) if label == "point" else len(g.prims())

        def groups(geo):
            return (geo.pointGroups() if label == "point" else geo.primGroups()) if geo is not None else []

        old = {g.name(): members(g) for g in groups(g0)}
        for g in groups(g1):
            m = members(g)
            if g.name() not in old:
                lines.append(f"NEW {label} group {g.name()}" + (f" with {m} members" if m is not None else ""))
            elif m is not None and old[g.name()] != m:
                lines.append(f"CHANGED {label} group {g.name()}: {old[g.name()]} -> {m} members")
    if g0 is not None and same_layout and n1[1] <= MAX_ELEMENTS:
        rewired = sum(1 for p0, p1 in zip(g0.prims(), g1.prims())
                      if _prim_points(p0) != _prim_points(p1) or _closed(p0) != _closed(p1))
        if rewired:
            lines.append(f"CHANGED connectivity (vertex order / points / closed flag) of {rewired} primitives")
        for p0, p1 in zip(g0.prims(), g1.prims()):
            if p1.type() == hou.primType.Volume and p0.type() == hou.primType.Volume:
                try:
                    res = p1.resolution()
                    if res[0] * res[1] * res[2] > MAX_VOXELS:
                        continue
                except Exception:
                    pass
                a, b = p0.allVoxels(), p1.allVoxels()
                ch = sum(1 for x, y in zip(a, b) if abs(x - y) > 1e-6) if len(a) == len(b) else len(b)
                if ch:
                    lines.append(f"CHANGED volume {p1.number()}: {ch} of {len(b)} voxels differ; now {_stats(b)}")
            elif p1.type() != hou.primType.Polygon and "transform" in p1.intrinsicNames():
                try:
                    if not _vals_close(p0.intrinsicValue("transform"), p1.intrinsicValue("transform"), 1e-6):
                        lines.append(f"CHANGED transform intrinsic of primitive {p1.number()}")
                except Exception:
                    pass
    if not lines:
        lines.append("NOTHING changed (output identical to the input)")
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... {len(lines) - max_lines} more lines"]
    if sampled_any:
        lines.append(f"(large geometry: values read from a sample of {MAX_ELEMENTS} elements)")
    return lines


def _errors(node):
    errs = list(node.errors())
    try:
        vop = node.node("attribvop1")
        if vop:
            errs += list(vop.errors())
    except Exception:
        pass
    return [e for e in errs if "invalid source" not in e.lower()]


def observe(node, max_lines=MAX_LINES):
    """What the snippet on `node` did to its first input, as text lines. The node must have been cooked."""
    errs = _errors(node)
    if errs:
        return ["the code failed: " + errs[0][:300]]
    in0 = node.input(0)
    g0 = in0.geometry() if in0 is not None else None
    lines = describe_delta(g0, node.geometry(), max_lines=max_lines)
    try:
        warns = [w for w in node.warnings() if w]
    except Exception:
        warns = []
    lines += ["compiler warning: " + w[:200] for w in warns[:2]]
    return lines or ["nothing changed: the output geometry is identical to the input"]


def build_review_prompt(task, context, code, observed, geo_context=""):
    """The user message of the verdict request. `context` is e.g. "point wrangle"."""
    result = "\n".join("  - " + line for line in observed)
    body = (f"Context: {context}\nTask: {task}\n\nVEX code written for this task:\n{code}\n\n"
            f"What this code did when it ran on the input geometry:\n{result}\n\n" + VERDICT_ASK)
    return "\n\n".join(p for p in (geo_context, body) if p)


def parse_verdict(text):
    """(True | False | None, reason): None when the answer starts with neither YES nor NO."""
    t = (text or "").strip()
    if re.match(r"\W*no\b", t, re.I):
        return False, re.sub(r"^\W*no\W*", "", t, flags=re.I).strip()[:300]
    if re.match(r"\W*yes\b", t, re.I):
        return True, re.sub(r"^\W*yes\W*", "", t, flags=re.I).strip()[:300]
    return None, ""


def enabled(model_version, checker_loaded=False):
    """AI_WRANGLE_RESULT_CHECK=0 switches the check off. It is only meaningful with a model trained for it: v56 or
    later, or an earlier model with its checker adapter loaded (engine_manager.checker_adapter_for)."""
    return os.environ.get("AI_WRANGLE_RESULT_CHECK", "1") != "0" and (model_version >= 56 or bool(checker_loaded))


def review(node, task, context, code, query_llm, geo_context=""):
    """(verdict, reason, observed lines). `query_llm` is houdini_ai_wrangle.query_llm. Raises what query_llm raises."""
    observed = observe(node)
    prompt = build_review_prompt(task, context, code, observed, geo_context)
    _, answer = query_llm(prompt, max_tokens=96, reasoning_mode=False, system_prompt=REVIEW_SYSTEM)
    verdict, reason = parse_verdict(answer)
    return verdict, reason, observed
