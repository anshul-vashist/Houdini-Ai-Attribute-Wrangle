"""
Check the plugin's hand-written VEX signatures (python/vex_ground_truth_signatures.py, shown to the model by the
retrieval step) against the compiler's own list (data/vex_signatures_vcc.json, from `vcc -X cvex`).

    python tools/validate_signatures.py

Reports functions that do not exist and signature lines whose argument types match no real overload.
"""
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "python"))
from vex_ground_truth_signatures import VEX_GROUND_TRUTH_SIGNATURES as GT  # noqa: E402

VCC = json.load(open(os.path.join(ROOT, "data", "vex_signatures_vcc.json"), encoding="utf-8"))
TYPES = ("vector2", "vector4", "vector", "matrix2", "matrix3", "matrix", "float", "int", "string", "dict", "bsdf")


def norm_vcc(sig):
    inner = sig[sig.index("(") + 1:sig.rindex(")")]
    args = [a.strip().replace(" ", "") for a in inner.split(";") if a.strip()]
    return tuple(args)


def norm_gt(line):
    m = re.match(r"\s*(\S+)\s+(\w+)\s*\((.*)\)\s*;?\s*$", line)
    if not m:
        return None
    args = []
    for a in [x.strip() for x in m.group(3).split(",") if x.strip()]:
        if a == "...":
            args.append("...")
            continue
        t = next((t for t in TYPES if re.match(rf"(const\s+)?{t}\b", a)), None)
        if t is None:
            t = "?" if a.startswith("<") else a.split()[0]
        arr = "[]" if "[]" in a else ""
        ref = "&" if "&" in a else ""
        args.append(t + arr + ref)
    return m.group(2), tuple(args)


def matches(gt_args, vcc_args):
    if "..." in vcc_args:
        k = vcc_args.index("...")
        return len(gt_args) >= k and all(matches_one(g, v) for g, v in zip(gt_args[:k], vcc_args[:k]))
    return len(gt_args) == len(vcc_args) and all(matches_one(g, v) for g, v in zip(gt_args, vcc_args))


def matches_one(g, v):
    g, v = g.replace("&", ""), v.replace("&", "")
    return g == v or g.startswith("?") or (g == "int" and v == "string")  # geometry handle may be a file name


def main():
    missing, bad, checked = [], [], 0
    for fn, lines in GT.items():
        if fn not in VCC:
            missing.append(fn)
            continue
        real = [norm_vcc(s) for s in VCC[fn]]
        for line in lines:
            if line.strip().startswith("//"):
                continue
            parsed = norm_gt(line)
            if not parsed:
                continue
            checked += 1
            if not any(matches(parsed[1], r) for r in real):
                bad.append((fn, line, VCC[fn][:6]))
    print(f"{len(GT)} functions, {checked} signature lines checked")
    print("functions that do not exist in VEX:", missing)
    for fn, line, real in bad:
        print(f"\nWRONG  {line}\n  real: " + "\n        ".join(real))
    return 1 if missing or bad else 0


if __name__ == "__main__":
    sys.exit(main())
