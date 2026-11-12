"""
Compile-and-cook VEX snippets in a real Houdini scene (run with hython).

    hython tools/vex_validate.py in.jsonl out.jsonl
in.jsonl rows: {"id": ..., "code": "...", "context": "point|primitive|detail|vertex"}
out.jsonl rows: {"id", "compiled": bool, "errors": [...], "warnings": [...], "cook_s": float}

The test scene gives every snippet a plausible world: input 0 is a 10x10 grid with P, N, Cd, v, pscale,
id, mass, age, life, name and a point group; input 1 is a polygon sphere with N and Cd; input 2 is a
density + sdf volume pair. "compiled" means Houdini compiled AND cooked the wrangle without an error,
which says nothing about whether the result is what a task asked for (that needs a task check).
Results are appended per row, so a crash or hang can be resumed by re-running.
"""
import json
import os
import sys
import time

import hou

CLASS = {"detail": 0, "primitive": 1, "point": 2, "vertex": 3, "prim": 1, "pt": 2}

SETUP0 = """
v@N = {0,1,0}; v@Cd = set(rand(@ptnum), 0.5, 0.2); v@v = set(0, 1, 0) * rand(@ptnum + 3);
f@pscale = 0.1; i@id = @ptnum; f@mass = 1.0; f@age = rand(@ptnum) * 2; f@life = 3.0;
s@name = sprintf("piece%d", @ptnum % 4); if (@ptnum % 3 == 0) setpointgroup(0, "picked", @ptnum, 1);
"""


def build_scene():
    obj = hou.node("/obj")
    geo = obj.createNode("geo", "vex_validate")
    grid = geo.createNode("grid")
    grid.parmTuple("size").set((9, 9))
    grid.parm("rows").set(10)
    grid.parm("cols").set(10)
    a0 = geo.createNode("attribwrangle", "in0_attrs")
    a0.setInput(0, grid)
    a0.parm("snippet").set(SETUP0)
    sph = geo.createNode("sphere")
    sph.parm("type").set(1)  # polygon
    sph.parm("freq").set(6)
    n1 = geo.createNode("normal")
    n1.setInput(0, sph)
    c1 = geo.createNode("color")
    c1.setInput(0, n1)
    box = geo.createNode("box")
    vol_d = geo.createNode("isooffset", "density")
    vol_d.setInput(0, box)
    vol_s = geo.createNode("isooffset", "sdf")
    vol_s.setInput(0, box)
    try:
        vol_s.parm("output").set(1)  # SDF
        vol_s.parm("name").set("surface")
    except Exception:
        pass
    vol = geo.createNode("merge", "volumes")
    vol.setInput(0, vol_d)
    vol.setInput(1, vol_s)
    w = geo.createNode("attribwrangle", "candidate")
    w.setInput(0, a0)
    w.setInput(1, c1)
    w.setInput(2, vol)
    return geo, w


def errors_of(node):
    out = list(node.errors())
    for child in node.allSubChildren():
        try:
            out += [e for e in child.errors() if e not in out]
        except Exception:
            pass
    return [e for e in out if "invalid source" not in e.lower()]


def validate(w, code, context):
    w.parm("class").set(CLASS.get((context or "point").split()[0].lower(), 2))
    w.parm("snippet").set(code)
    t0 = time.time()
    try:
        w.cook(force=True)
    except hou.OperationFailed:
        pass
    errs = errors_of(w)
    return dict(compiled=not errs, errors=[e[:400] for e in errs], warnings=[x[:300] for x in w.warnings()],
                cook_s=round(time.time() - t0, 3))


def main():
    src, dst = sys.argv[1], sys.argv[2]
    done = set()
    if os.path.exists(dst):
        done = {json.loads(l)["id"] for l in open(dst, encoding="utf-8") if l.strip()}
    _, w = build_scene()
    with open(dst, "a", encoding="utf-8") as out:
        for line in open(src, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            if r["id"] in done:
                continue
            res = validate(w, r["code"], r.get("context"))
            res["id"] = r["id"]
            out.write(json.dumps(res) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
