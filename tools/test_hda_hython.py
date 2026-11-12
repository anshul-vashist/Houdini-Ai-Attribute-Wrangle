"""
End-to-end tests for the AI Attribute Wrangle HDA, run inside hython (no GPU / LLM needed):

    hython tools/test_hda_hython.py

LLM calls (generate_vex / refine_vex / repair_vex / optimize / explain) and hou.ui dialogs are
mocked; everything else (HDA definition, parameters, callbacks, VEX compile/cook, spare parms,
history, variants, header export) runs for real in Houdini.
"""
import os
import sys
import tempfile
import time
import traceback

import hou

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "python"))
os.environ.setdefault("AI_WRANGLE_ROOT", ROOT)
hou.hda.installFile(os.path.join(ROOT, "otls", "ai_attribwrangle.hda"))

import houdini_ai_wrangle as hw  # noqa: E402

RESULTS = []


def _newest_version():
    """Highest vNN among the exported plugin models, e.g. 'v51' (the tests must not hard-code a version)."""
    import glob
    import re
    vers = [int(m.group(1)) for m in (re.search(r"Qwen3-8B-Houdini-VEX-v(\d+)", os.path.basename(f))
                                      for f in glob.glob(os.path.join(ROOT, "models", "Qwen3-8B-Houdini-VEX-v*.gguf"))) if m]
    return f"v{max(vers)}" if vers else "v"


NEWEST_V = _newest_version()
NEWEST_PREFIX = "Qwen3-8B-Houdini-VEX-" + NEWEST_V
# A fresh clone has no model file yet: the model checks then test what the node says and does without one.
HAVE_MODEL = NEWEST_V != "v"


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""), flush=True)


class FakeUI:
    """Stands in for hou.ui (absent in hython); records messages, answers dialogs."""
    def __init__(self):
        self.messages = []
        self.read_input_answer = (0, "ai_test_header")

    def displayMessage(self, text, *a, **k):
        self.messages.append(text)
        return 0

    def readInput(self, *a, **k):
        return self.read_input_answer

    def setStatusMessage(self, *a, **k):
        pass

    def copyTextToClipboard(self, *a, **k):
        pass


fake_ui = FakeUI()
if not hou.isUIAvailable():
    hou.ui = fake_ui

# ---- LLM mocks -------------------------------------------------------------------------------
LLM = {"generate": [], "repair": [], "refine": [], "calls": {"generate": 0, "repair": 0, "refine": 0}}
hw.ensure_embedded_engine = lambda *a, **k: True


def fake_generate(task, context="point wrangle", geo_context="", reasoning_mode=False, enable_rag=None, **kw):
    LLM["calls"]["generate"] += 1
    return "", LLM["generate"].pop(0)


def fake_repair(task, context, faulty, err, geo_context=""):
    LLM["calls"]["repair"] += 1
    return "", (LLM["repair"].pop(0) if LLM["repair"] else "")


def fake_refine(task, existing, context="point wrangle", geo_context="", reasoning_mode=False, enable_rag=None):
    LLM["calls"]["refine"] += 1
    return "", LLM["refine"].pop(0)


hw.generate_vex = fake_generate
hw.repair_vex = fake_repair
hw.refine_vex = fake_refine
hw.optimize_vex_code = lambda code, context="point wrangle": code.replace("  ", " ")
hw.explain_and_document_vex = lambda code, context="point wrangle": "// documented\n" + code


def reset_llm(generate=(), repair=(), refine=()):
    LLM["generate"], LLM["repair"], LLM["refine"] = list(generate), list(repair), list(refine)
    LLM["calls"] = {"generate": 0, "repair": 0, "refine": 0}


def make_node(src="grid", klass="point"):
    geo = hou.node("/obj").createNode("geo")
    s = geo.createNode(src)
    if src == "grid":
        s.parmTuple("size").set((9, 9))
        s.parm("rows").set(10)
        s.parm("cols").set(10)
    n = geo.createNode("ai_attribwrangle")
    n.setInput(0, s)
    n.parm("class").set(klass)
    if n.parm("ai_autodetect"):
        n.parm("ai_autodetect").set(0)
    if n.parm("ai_num_candidates"):
        n.parm("ai_num_candidates").set(1)  # single answer unless a test asks for best-of-N
    return n


def generate(node, prompt):
    node.parm("ai_prompt").set(prompt)
    hw.on_generate_clicked({"node": node})


def T(name):
    def deco(fn):
        try:
            fn()
        except Exception:
            check(name + " (no exception)", False, traceback.format_exc()[-600:])
        return fn
    return deco


# =============================================================================================
@T("definition")
def _():
    aw = hou.nodeType(hou.sopNodeTypeCategory(), "attribwrangle")
    check("native Attribute Wrangle is not shadowed", "OPlibSop" in aw.definition().libraryFilePath(),
          aw.definition().libraryFilePath())
    defs = hou.hda.definitionsInFile(os.path.join(ROOT, "otls", "ai_attribwrangle.hda"))
    check("HDA file holds only ai_attribwrangle", [d.nodeTypeName() for d in defs] == ["ai_attribwrangle"])
    d = hou.nodeType(hou.sopNodeTypeCategory(), "ai_attribwrangle").definition()
    check("OnCreated flagged as Python", d.extraFileOptions().get("OnCreated/IsPython") is True)
    check("help page present", len(d.sections()["Help"].contents()) > 200)


@T("node creation")
def _():
    n = make_node()
    info = n.parm("ai_model_info").eval()
    if HAVE_MODEL:
        check("OnCreated sets Active Engine field", NEWEST_V in info, info)
    else:
        check("OnCreated names a base model or says that no model is installed",
              "No model found" in info or ".gguf" in info or ".dat" in info, info)
    check("node has no errors", not n.errors(), str(n.errors()))


@T("model menu")
def _():
    n = make_node()
    p = n.parm("ai_model_select")
    check("model menu is a string parm", p.parmTemplate().type() == hou.parmTemplateType.String)
    items = hw.get_available_models_menu_items()
    tokens = items[0::2]
    if HAVE_MODEL:
        check("auto is first and names the newest version", items[0] == "auto" and NEWEST_V in items[1], items[1])
        check("tokens are file names", any(t.endswith(".gguf") for t in tokens))
        check("newest model listed first", tokens[1].startswith(NEWEST_PREFIX), tokens[1])
    else:
        found = hw._discover_models()
        check("without a fine-tuned model Auto names a base model or says that none was found", items[0] == "auto"
              and (os.path.basename(found[0]) in items[1] if found else "no model found" in items[1]), items[1])
        check("the menu ends with the custom file entry", tokens[-1] == "custom", repr(tokens))
        check("the entries between Auto and custom are model files",
              all(t.lower().endswith((".gguf", ".dat")) for t in tokens[1:-1]), repr(tokens))
    check("no LoRA / 16-bit intermediates listed", not any("lora" in t.lower() or "merged-16bit" in t for t in tokens))
    p.set("custom")
    hw.on_model_select_changed({"node": n})
    check("custom model choice reaches its branch", "Custom model selected" in n.parm("ai_status").eval(),
          n.parm("ai_status").eval())
    default = hw._default_model_path()
    if HAVE_MODEL:
        check("auto resolves to newest model", os.path.basename(default).startswith(NEWEST_PREFIX))
    else:
        check("without a fine-tuned model auto resolves to a base model or to nothing",
              default is None or hw._model_version(default) < 0, repr(default))


@T("vex cooking")
def _():
    for klass, code, probe in [
        ("point", "@P.y += 1;", lambda g: abs(g.points()[0].position()[1] - 1) < 1e-6),
        ("primitive", "f@a = primintrinsic(0, 'measuredarea', @primnum);", lambda g: g.findPrimAttrib("a") is not None),
        ("detail", "i@n = npoints(0);", lambda g: g.attribValue("n") == 100),
    ]:
        n = make_node(klass=klass)
        n.parm("snippet").set(code.replace("'", '"'))
        n.cook(force=True)
        check(f"{klass} wrangle cooks", probe(n.geometry()) and not n.errors(), str(n.errors()))


@T("try_apply_snippet")
def _():
    n = make_node()
    n.parm("snippet").set("@P.y += 2;")
    ok, err = hw.try_apply_snippet(n, "int a[] = array(1);\nint b = a[];")
    check("'Empty array index' is reported as a failure", not ok and err, str(err)[:120])
    check("previous snippet restored after failure", n.parm("snippet").eval() == "@P.y += 2;")
    ok, err = hw.try_apply_snippet(n, "@P.y += 3;")
    check("valid code applies", ok and err is None)


@T("generate: correct code is applied unchanged")
def _():
    n = make_node()
    sphere_geo = n.parent().createNode("sphere")
    sphere_geo.parm("type").set(1)
    n.setInput(1, sphere_geo)
    code = 'int n = nearpoint(1, @P);\nf@pdist = distance(@P, point(1, "P", n));'
    reset_llm(generate=[code])
    generate(n, "store distance to nearest point of input 1 in pdist")
    check("snippet identical to model output", n.parm("snippet").eval().strip() == code, n.parm("snippet").eval())
    g = n.geometry()
    check("result attribute cooked", g.findPointAttrib("pdist") is not None and not n.errors())
    check("no repair call for valid code", LLM["calls"]["repair"] == 0)
    check("history recorded", len(hw.get_history_stack(n)) == 1)


@T("generate: alias fixed by fallback sanitizer")
def _():
    n = make_node()
    reset_llm(generate=["f@d = mag(@P);"])
    generate(n, "store length of position in d")
    snip = n.parm("snippet").eval()
    check("heavy sanitizer used only when compile fails", "length(@P)" in snip and not n.errors(), snip)
    check("no LLM repair needed", LLM["calls"]["repair"] == 0)


@T("generate: compiler-feedback repair")
def _():
    n = make_node()
    reset_llm(generate=["f@x = undefined_function_xyz(@P);"], repair=["f@x = @P.x;"])
    generate(n, "copy x into attribute x")
    snip = n.parm("snippet").eval()
    check("repair pass produced working code", snip.strip() == "f@x = @P.x;" and not n.errors(), snip)
    check("exactly one repair call", LLM["calls"]["repair"] == 1, str(LLM["calls"]))


@T("generate: unrecoverable code keeps node safe")
def _():
    n = make_node()
    n.parm("snippet").set("@P.y += 5;")
    reset_llm(generate=["this is not vex"], repair=["still not vex", "nope"])
    generate(n, "do something")
    check("status reports the failure", "failed" in n.parm("ai_status").eval().lower(), n.parm("ai_status").eval())
    check("user's previous code is kept", n.parm("snippet").eval().strip() == "@P.y += 5;", n.parm("snippet").eval())
    check("failed attempt shown in Reasoning Trace", "this is not vex" in n.parm("ai_thought_trace").eval()
          or "still not vex" in n.parm("ai_thought_trace").eval() or "nope" in n.parm("ai_thought_trace").eval())
    check("bounded number of repair calls", LLM["calls"]["repair"] <= 2, str(LLM["calls"]))


@T("failed attempt keeps tuned slider values")
def _():
    n = make_node()
    reset_llm(generate=['float amp = chf("amp");\n@P.y += amp;'])
    generate(n, "raise by amp")
    n.parm("amp").set(3.7)
    ok, _ = hw.try_apply_snippet(n, '@P.y += undefined_thing_xyz;')
    check("rollback after rejected attempt", not ok)
    check("tuned slider value survives rollback", n.parm("amp") is not None and abs(n.parm("amp").eval() - 3.7) < 1e-6,
          str(n.parm("amp").eval() if n.parm("amp") else None))


@T("loop guard")
def _():
    n = make_node(klass="detail")
    code = "float x = 1e6; int k = 0;\nwhile (x > 1) { x *= 0.999; k++; }\ni@k = k;\nint s[] = array(1,2,3);\nwhile (len(s) > 0) pop(s);\ni@left = len(s);\nint j = 0;\nif (1) while (j < 3) j++;\ni@j = j;\nint d = 0;\ndo { d++; } while (d < (4 + 1));\ni@d = d;"
    reset_llm(generate=[code])
    generate(n, "loops")
    g = n.geometry()
    vals = {a: g.attribValue(a) for a in ("k", "left", "j", "d")} if not n.errors() else {}
    check("guarded loops compile and give exact results",
          vals == {"k": 13809, "left": 0, "j": 3, "d": 5}, f"{vals} {n.errors()}")
    check("guard present in applied code", "__safety_iter_0" in n.parm("snippet").eval())


@T("refine flow")
def _():
    n = make_node()
    n.parm("snippet").set("@P.y += 1;")
    reset_llm(refine=["@P.y += 2;"])
    generate(n, "modify the code to raise points by 2 instead")
    check("edit intent routes to refine", LLM["calls"]["refine"] == 1 and n.parm("snippet").eval().strip() == "@P.y += 2;",
          f"{LLM['calls']} {n.parm('snippet').eval()!r}")


@T("spare parameters")
def _():
    n = make_node()
    reset_llm(generate=['float amp = chf("amp");\n@P.y += amp * sin(@P.x);\n@Cd = chramp("ramp", relbbox(0, @P).x);'])
    generate(n, "wave with amp slider")
    check("chf slider created", n.parm("amp") is not None)
    check("chramp ramp created", n.parm("ramp") is not None)
    check("non-zero default for amp", n.parm("amp") is not None and abs(n.parm("amp").eval()) > 0)


@T("history & variants")
def _():
    n = make_node()
    reset_llm(generate=["@P.y += 1;", "@P.y += 2;"])
    generate(n, "raise by 1")
    generate(n, "raise by 2 from scratch")
    hw.on_prev_version_clicked({"node": n})
    check("prev restores version 1", n.parm("snippet").eval().strip() == "@P.y += 1;", n.parm("snippet").eval())
    hw.on_next_version_clicked({"node": n})
    check("next restores version 2", n.parm("snippet").eval().strip() == "@P.y += 2;", n.parm("snippet").eval())
    hw.on_store_variant_a_clicked({"node": n})
    hw.on_prev_version_clicked({"node": n})
    hw.on_store_variant_b_clicked({"node": n})
    hw.on_toggle_variants_clicked({"node": n})
    check("A/B toggle switches snippet", n.parm("snippet").eval().strip() in ("@P.y += 1;", "@P.y += 2;"))


@T("other buttons")
def _():
    n = make_node()
    n.parm("snippet").set('float  w = chf("w");\n@P.y += w;')
    for name, fn in [("preset", hw.on_load_preset_clicked), ("sanitize", hw.on_sanitize_guards_clicked),
                     ("stats", hw.on_inspect_stats_clicked), ("optimize", hw.on_optimize_clicked),
                     ("explain", hw.on_explain_clicked)]:
        try:
            fn({"node": n})
            check(f"{name} button runs", True)
        except Exception as e:
            check(f"{name} button runs", False, f"{type(e).__name__}: {e}")
        n.cook(force=True)
        check(f"node valid after {name}", not n.errors(), str(n.errors()))


@T("header export")
def _():
    n = make_node()
    n.parm("snippet").set("@P.y += 0.5;\nf@h = @P.y;")
    inc_dir = tempfile.mkdtemp(prefix="vexinc_")
    real_home = hou.homeHoudiniDirectory
    hou.homeHoudiniDirectory = lambda: inc_dir
    try:
        fake_ui.read_input_answer = (0, "ai_test_header")
        hw.on_export_header_clicked({"node": n})
    finally:
        hou.homeHoudiniDirectory = real_home
    header = os.path.join(inc_dir, "vex", "include", "ai_test_header.h")
    check("header written", os.path.isfile(header))
    n.cook(force=True)
    ref = [p.attribValue("h") for p in n.geometry().points()]
    # use the exported header exactly as the success message instructs
    _, call_line = hw.snippet_to_vex_function(n.parm("snippet").eval(), "ai_test_header")
    m = make_node()
    m.parm("snippet").set(f'#include "{header.replace(chr(92), "/")}"\n{call_line}')
    try:
        m.cook(force=True)
    except hou.OperationFailed:
        pass
    g = m.geometry()
    ok = not m.errors() and g is not None and g.findPointAttrib("h") is not None
    check("exported function compiles in another wrangle", ok, str(m.errors())[:200])
    check("exported function gives identical results", ok and [p.attribValue("h") for p in g.points()] == ref)
    fake_ui.messages.clear()
    hou.homeHoudiniDirectory = lambda: inc_dir
    try:
        hw.on_export_header_clicked({"node": n})  # file exists now -> asks before overwriting
    finally:
        hou.homeHoudiniDirectory = real_home
    check("asks before overwriting an existing header", any("already exists" in msg for msg in fake_ui.messages))


@T("refine button uses the generate pipeline")
def _():
    n = make_node()
    n.parm("snippet").set("@P.y += 1;")
    n.parm("ai_prompt").set("raise points by 3 instead")
    reset_llm(refine=["@P.y += 3;"])
    hw.on_refine_clicked({"node": n})
    check("refine button edits existing code", LLM["calls"]["refine"] == 1 and n.parm("snippet").eval().strip() == "@P.y += 3;",
          f"{LLM['calls']} {n.parm('snippet').eval()!r}")
    check("refine recorded in history", len(hw.get_history_stack(n)) == 1)


@T("one undo step per generate")
def _():
    n = make_node(klass="point")
    n.parm("snippet").set("@P.y += 1;")
    hou.undos.clear()
    reset_llm(generate=["f@a = 1;"])
    generate(n, "set attribute a from scratch")
    changed = n.parm("snippet").eval().strip() == "f@a = 1;"
    hou.undos.performUndo()
    check("single undo restores the previous snippet", changed and n.parm("snippet").eval().strip() == "@P.y += 1;",
          n.parm("snippet").eval())


@T("fork to branch")
def _():
    n = make_node()
    n.parm("ai_snippet_a").set("@P.y += 1;")
    n.parm("ai_snippet_b").set("@P.y += 2;")
    n.parm("snippet").set("@P.y += 1;")
    before = set(c.path() for c in n.parent().children())
    hw.on_fork_branch_clicked({"node": n})
    new = [c for c in n.parent().children() if c.path() not in before]
    fork = [c for c in new if c.type().name() == "ai_attribwrangle"]
    sw = [c for c in new if c.type().name() == "switch"]
    check("fork node and compare switch created", len(fork) == 1 and len(sw) == 1, [c.name() for c in new])
    if fork:
        check("fork carries variant B and the same input", fork[0].parm("snippet").eval().strip() == "@P.y += 2;"
              and fork[0].input(0) == n.input(0))


@T("model choice is deferred")
def _():
    n = make_node()
    calls = {"n": 0}
    real = hw.ensure_embedded_engine
    hw.ensure_embedded_engine = lambda *a, **k: calls.__setitem__("n", calls["n"] + 1) or True
    try:
        tokens = hw.get_available_models_menu_items()[0::2]
        older = [t for t in tokens if "v48" in t]
        if older:
            n.parm("ai_model_select").set(older[0])
        hw.on_model_select_changed({"node": n})
        check("picking a model does not load it", calls["n"] == 0, str(calls))
        check("status says when it loads", "loads on next Generate" in n.parm("ai_status").eval(), n.parm("ai_status").eval())
        chosen = hw.resolve_selected_model_path(n) or ""
        if HAVE_MODEL:
            check("selected model resolves to that file", chosen.endswith(older[0] if older else ".gguf"))
        else:
            check("without a fine-tuned model the choice resolves to a base model or to nothing",
                  chosen == "" or hw._model_version(chosen) < 0, chosen)
        n.parm("ai_model_select").set("auto")
        auto = hw.resolve_selected_model_path(n) or ""
        if HAVE_MODEL:
            check("auto resolves to newest model", os.path.basename(auto).startswith(NEWEST_PREFIX))
        else:
            check("without a fine-tuned model auto resolves to a base model or to nothing",
                  auto == "" or hw._model_version(auto) < 0, auto)
    finally:
        hw.ensure_embedded_engine = real


@T("best-of-N picks the answer candidates agree on")
def _():
    n = make_node()
    n.parm("ai_num_candidates").set(3)
    wrong = "@P.y += 5;"
    right_a = "@P.y += 1;"
    right_b = "@P.y = @P.y + 1.0;"  # different text, same geometry
    seq = [wrong, right_a, right_b]
    calls = {"n": 0}

    def gen(task, context="point wrangle", geo_context="", reasoning_mode=False, enable_rag=None, temperature=None, seed=None):
        calls["n"] += 1
        return "", seq[calls["n"] - 1]

    def gen_train(task, context="point wrangle", temperature=0.0, seed=0):
        calls["n"] += 1
        calls["train"] = calls.get("train", 0) + 1
        return "", seq[calls["n"] - 1]

    real, real_train = hw.generate_vex, hw.generate_vex_training_format
    hw.generate_vex, hw.generate_vex_training_format = gen, gen_train
    try:
        generate(n, "raise points by one unit")
    finally:
        hw.generate_vex, hw.generate_vex_training_format = real, real_train
    check("three candidates generated", calls["n"] == 3, str(calls))
    check("second candidate uses the training prompt format", calls.get("train") == 1, str(calls))
    check("majority answer applied (2 of 3 agree)", n.parm("snippet").eval().strip() in (right_a, right_b), n.parm("snippet").eval())
    check("selection noted in Reasoning Trace", "agreed" in n.parm("ai_thought_trace").eval())
    n.parm("ai_num_candidates").set(1)
    seq[:] = [right_a]
    calls["n"] = 0
    hw.generate_vex = gen
    try:
        generate(n, "raise points by one unit again from scratch")
    finally:
        hw.generate_vex = real
    check("AI Candidates = 1 makes a single request", calls["n"] == 1, str(calls))


@T("generated sliders default to the code's own fallback value")
def _():
    geo = hou.node("/obj").createNode("geo")
    box = geo.createNode("box")
    w = geo.createNode("attribwrangle")
    w.setInput(0, box)
    code = 'float step = chf("step");\nif (step == 0.0) step = 0.1;\n@P += normalize(@N) * step;'
    ok, err = hw.try_apply_snippet(w, code)
    check("snippet with fallback guard applies", ok, str(err))
    check("slider default taken from the fallback (0.1, not 1.0)", abs(w.parm("step").eval() - 0.1) < 1e-6,
          str(w.parm("step").eval()))
    # a later answer that asks for a different fallback updates an untouched slider ...
    hw.try_apply_snippet(w, 'float step = chf("step");\nif (step <= 0.0) step = 0.25;\n@P.y += step;')
    check("untouched slider follows the new fallback", abs(w.parm("step").eval() - 0.25) < 1e-6, str(w.parm("step").eval()))
    # ... but never overrides a value the artist set
    w.parm("step").set(3.0)
    hw.try_apply_snippet(w, 'float step = chf("step");\nif (step <= 0.0) step = 0.5;\n@P.y += step;')
    check("artist-set slider value kept", abs(w.parm("step").eval() - 3.0) < 1e-6, str(w.parm("step").eval()))
    # divide-by-zero guards are not treated as intent
    hw.try_apply_snippet(w, 'float d = chf("dist_k");\nif (abs(d) < 1e-4) d = 1.0;\n@P.y /= d;')
    check("abs() zero-guard ignored", hw.channel_default_hints('float d = chf("d");\nif (abs(d) < 1e-4) d = 1.0;') == {})


@T("retrofit / upgrade keeps user parameters")
def _():
    geo = hou.node("/obj").createNode("geo")
    w = geo.createNode("attribwrangle")
    w.parm("snippet").set('float amp = chf("amp");\n@P.y += amp;')
    hw.setup_ai_parameters(w, force=True)
    hw.sync_spare_parameters(w, w.parm("snippet").eval())
    w.parm("amp").set(2.5)
    ptg = w.parmTemplateGroup()
    ptg.append(hou.FloatParmTemplate("my_own_parm", "Mine", 1, default_value=(4.0,)))
    w.setParmTemplateGroup(ptg)
    w.parm("bindings").set(2)
    w.parm("bindname1").set("Cd")
    hw.setup_ai_parameters(w, force=True)  # simulate an interface upgrade
    check("AI interface present after upgrade", w.parm("ai_generate") is not None and w.parm("ai_model_select") is not None)
    check("model menu is string-based on retrofit", w.parm("ai_model_select").parmTemplate().type() == hou.parmTemplateType.String)
    check("generated slider kept with its value", w.parm("amp") is not None and abs(w.parm("amp").eval() - 2.5) < 1e-6)
    check("user's own spare parm kept", w.parm("my_own_parm") is not None)
    check("bindings multiparm intact", w.parm("bindings").eval() == 2 and w.parm("bindname1").eval() == "Cd")


@T("interruptible request")
def _():
    import http.server
    import json as _json
    import threading

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            time.sleep(0.4)
            body = _json.dumps({"choices": [{"message": {"content": "@P.y += 1;"}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        res = hw._post_json_interruptible(f"http://127.0.0.1:{srv.server_port}/v1/chat/completions",
                                          b"{}", {"Content-Type": "application/json"}, timeout=10, label="test")
        check("threaded request returns the response", res["choices"][0]["message"]["content"] == "@P.y += 1;")
    finally:
        srv.shutdown()


@T("performance")
def _():
    geo = hou.node("/obj").createNode("geo")
    grid = geo.createNode("grid")
    grid.parm("rows").set(1000)
    grid.parm("cols").set(1000)
    n = geo.createNode("ai_attribwrangle")
    n.setInput(0, grid)
    grid.cook(force=True)
    t0 = time.time()
    hw.introspect_geometry(n)
    t_intro = time.time() - t0
    n.parm("snippet").set("@P.y += 0.1;")
    n.cook(force=True)
    t0 = time.time()
    hw.verify_physical_invariants(n)
    t_inv = time.time() - t0
    t0 = time.time()
    hw.scan_geometry_health(n)
    t_scan = time.time() - t0
    print(f"     1M points: introspect {t_intro:.2f}s, invariants {t_inv:.2f}s, health scan {t_scan:.2f}s")
    check("introspection under 1 s on 1M points", t_intro < 1.0, f"{t_intro:.2f}s")
    check("post-apply checks under 1 s on 1M points", t_inv + t_scan < 1.0, f"{t_inv + t_scan:.2f}s")


@T("verified-example retrieval")
def _():
    import vex_example_bank as bank
    task = "Animate a bounce: move the points up and down over time with a parameter for the height"
    hits = bank.retrieve(task, "point wrangle", k=2)
    check("the example bank returns related verified examples", len(hits) == 2 and all(c.get("code") for _, c in hits))
    old = os.environ.get("AI_WRANGLE_EXAMPLES")
    try:
        os.environ.pop("AI_WRANGLE_EXAMPLES", None)
        on = hw.build_generation_prompt(task, context="point wrangle", geo_context="")
        os.environ["AI_WRANGLE_EXAMPLES"] = "0"
        off = hw.build_generation_prompt(task, context="point wrangle", geo_context="")
    finally:
        if old is None:
            os.environ.pop("AI_WRANGLE_EXAMPLES", None)
        else:
            os.environ["AI_WRANGLE_EXAMPLES"] = old
    check("generation prompt shows verified examples by default", "Verified examples of related tasks" in on)
    check("AI_WRANGLE_EXAMPLES=0 removes them", "Verified examples of related tasks" not in off)
    first = hits[0][1]
    loo = bank.retrieve(task, "point wrangle", k=2, exclude={first["id"]})
    check("an excluded card is never returned (leave-one-out for training rows)",
          all(c["id"] != first["id"] for _, c in loo))
    check("unrelated text retrieves nothing", bank.retrieve("zzz qqq", "point wrangle") == [])


@T("function lookup")
def _():
    import vex_function_index as fidx
    names = [f for f, _ in fidx.retrieve("store the mean of the values of the array attribute samples", "point wrangle", k=10)]
    check("plain words find the function (mean -> avg)", "avg" in names, str(names))
    names = [f for f, _ in fidx.retrieve("split the matrix into its pure rotation by polar decomposition", "point wrangle", k=10)]
    check("a function no solved task needs to show is still offered (polardecomp)", "polardecomp" in names, str(names))
    check("run-together names are split into words", fidx.split_name("polarDecomposition") == "polar decomposition"
          and fidx.split_name("volumexsize") == "volume x size", fidx.split_name("polarDecomposition"))
    pages = fidx.match_pages("polar decomposition")
    check("page match alone finds the function for a description", bool(pages) and pages[0][0] == "polardecomp", str(pages))
    block = fidx.build_signature_block("rotate each vector by the orient quaternion", "point wrangle", k=6)
    check("signature block lists documented usage lines", "qrotate(" in block, block[:200])
    old = os.environ.get("AI_WRANGLE_FUNCTION_ALIASES")
    try:
        os.environ["AI_WRANGLE_FUNCTION_ALIASES"] = "0"
        plain = fidx.retrieve("store the mean of the values of the array attribute samples", "point wrangle", k=10)
        check("AI_WRANGLE_FUNCTION_ALIASES=0 still answers (search phrases off)", isinstance(plain, list))
    finally:
        if old is None:
            os.environ.pop("AI_WRANGLE_FUNCTION_ALIASES", None)
        else:
            os.environ["AI_WRANGLE_FUNCTION_ALIASES"] = old
    check("garbage text offers nothing", fidx.retrieve("zzz qqq", "point wrangle") == [])
    # usage lines and notes of a function
    saved_n = {k: os.environ.pop(k, None) for k in ("AI_WRANGLE_FUNCTION_NOTES", "AI_WRANGLE_FUNCTION_USAGE_LINES")}
    try:
        base = fidx.signature_lines("invlerp")
        os.environ["AI_WRANGLE_FUNCTION_NOTES"] = "1"
        os.environ["AI_WRANGLE_FUNCTION_USAGE_LINES"] = "3"
        noted = fidx.signature_lines("invlerp")
        check("usage notes are shown when switched on", any("Note:" in x for x in noted)
              and len([x for x in noted if not x.startswith("//")]) == len([x for x in base if not x.startswith("//")]),
              str(noted))
        three = [x for x in fidx.signature_lines("noise") if not x.startswith("//")]
        check("with three usage lines the vector form of noise is shown", len(three) == 3
              and three[0] == "float noise(float pos)" and any("noise(vector pos)" in x for x in three), str(three))
        check("the output-argument twin of addprim is not preferred",
              not any(x.startswith("void addprim") for x in fidx.signature_lines("addprim")))
    finally:
        for k, v in saved_n.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    # defaults of the generation prompt: lookup block on, placed directly in front of the task, no blueprint
    saved = {k: os.environ.pop(k, None) for k in ("AI_WRANGLE_FUNCTION_INDEX", "AI_WRANGLE_REFERENCE_LAST",
                                                  "AI_WRANGLE_BLUEPRINTS", "AI_WRANGLE_FUNCTION_INDEX_K")}
    try:
        task = "Scale the geometry about the centre of its bounding box by the parameter s"
        p = hw.build_generation_prompt(task, context="point wrangle", geo_context="Live Node & Geometry Context:\nx")
        head = "Official SideFX VEX Function Signatures"
        check("the function lookup block is in the prompt by default", head in p and "getbbox_center(" in p, p[:300])
        check("the reference block sits directly in front of the task",
              head in p and p.index("Live Node & Geometry Context") < p.index(head) < p.index("Context: point wrangle"))
        check("no blueprint pattern by default", "Master Architectural Reference Pattern" not in p)
        os.environ["AI_WRANGLE_REFERENCE_LAST"] = "0"
        os.environ["AI_WRANGLE_BLUEPRINTS"] = "1"
        old = hw.build_generation_prompt(task, context="point wrangle", geo_context="Live Node & Geometry Context:\nx")
        check("AI_WRANGLE_REFERENCE_LAST=0 puts the block back at the top",
              head in old and old.index(head) < old.index("Live Node & Geometry Context"))
        os.environ["AI_WRANGLE_FUNCTION_INDEX"] = "0"
        legacy = hw.build_generation_prompt(task, context="point wrangle", geo_context="")
        check("AI_WRANGLE_FUNCTION_INDEX=0 still builds a prompt (keyword matcher)", "Task Instruction:" in legacy)
        os.environ.pop("AI_WRANGLE_FUNCTION_INDEX", None)
        os.environ.pop("AI_WRANGLE_REFERENCE_LAST", None)
        rep = hw.build_repair_prompt("Create a single triangle from three points", "detail wrangle",
                                     "addprim(0, \"poly\", {0, 1, 2});", "Syntax error, unexpected identifier.  (1,21)")
        check("a repair prompt's block is about the task, not about the word 'error'",
              "// error:" not in rep and "addprim(" in rep.split("Faulty VEX Code")[0], rep[:400])
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@T("compile-error hints")
def _():
    import vex_api_hints as hints
    h = hints.hints_for_error("Call to undefined function 'round'.  (1,8:12)")
    check("known near-miss gets its note (round -> rint)", "rint" in h, h)
    h = hints.hints_for_error("Call to undefined function 'polar'.  (2,13:17)")
    check("a made-up name is matched to the real function (polar -> polardecomp)", "polardecomp(" in h, h)
    h = hints.hints_for_error("Call to undefined function 'npointsinGroup'.")
    check("a run-together made-up name is matched by its words", "npointsgroup(" in h, h)
    h = hints.hints_for_error("No matching function for int volumeres(int; string; int). Candidates are: vector volumeres(int; int)")
    check("wrong arguments get the documented usage", "Documented usage" in h and "volumeres(" in h, h)
    h = hints.hints_for_error("Reference to undefined variable: keep  (2,37:40)")
    check("an undeclared name is explained as attribute or parameter", "s@keep" in h and 'chf("keep")' in h, h)
    check("no hint for an error it knows nothing about", hints.hints_for_error("Syntax error, unexpected identifier.") == "")
    h = hints.hints_for_error("Reference to undefined variable: P\t (1,12)")
    check("a bare built-in name gets its one binding", "@P" in h and "s@P" not in h, h)
    check("wrong letter case is matched to the real function alone", hints.similar_functions("Rand") == ["rand"],
          str(hints.similar_functions("Rand")))
    sim = hints.similar_functions("getvertexattrib")
    check("a made-up getter is not answered with the setter", "setvertexattrib" not in sim and "vertexattrib" in sim, str(sim))
    import vex_function_index as fidx2
    check("run-together names are cut at word borders", fidx2.split_name("arraysum") == "array sum"
          and fidx2.split_name("ptnumtoprim") == "ptnum to prim", fidx2.split_name("arraysum"))
    two = [x for x in fidx2.signature_lines("insert") if not x.startswith("//")]
    check("default usage lines are the first two of the help", two == ["void insert(string &str, int index, string value)",
                                                                       "void insert(<type> &array[], int index, <type> value)"], str(two))
    check("hints stay short", len(hints.hints_for_error("Call to undefined function 'simplex'. Call to undefined function "
                                                        "'polar'. Call to undefined function 'volumexsize'.")) <= 900)
    prompt_on = prompt_off = ""
    old = os.environ.get("AI_WRANGLE_API_HINTS")
    try:
        os.environ["AI_WRANGLE_API_HINTS"] = "1"
        prompt_on = hw.build_repair_prompt("strip the scale", "point wrangle", "matrix3 r = polar(3@m);",
                                           "Call to undefined function 'polar'.")
        os.environ["AI_WRANGLE_API_HINTS"] = "0"
        prompt_off = hw.build_repair_prompt("strip the scale", "point wrangle", "matrix3 r = polar(3@m);",
                                            "Call to undefined function 'polar'.")
    finally:
        if old is None:
            os.environ.pop("AI_WRANGLE_API_HINTS", None)
        else:
            os.environ["AI_WRANGLE_API_HINTS"] = old
    check("repair prompt carries the hint when hints are on", "Hint:" in prompt_on and "polardecomp" in prompt_on)
    check("AI_WRANGLE_API_HINTS=0 leaves the repair prompt without it", "Hint:" not in prompt_off)


@T("empty answers and failed repairs")
def _():
    import http.server
    import json as _json
    import threading

    replies = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            body = _json.dumps({"choices": [{"message": replies.pop(0) if replies else {"content": ""}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    real_port = hw._engine_port
    hw._engine_port = lambda: srv.server_port
    try:
        # the token budget went into thinking: the answer alone is asked for once more
        replies[:] = [{"content": "", "reasoning_content": "the user wants the points higher"}, {"content": "@P.y += 1;"}]
        thought, code = hw.query_llm("raise the points", reasoning_mode=True)
        check("thinking-only answer is retried without thinking", code == "@P.y += 1;" and not replies, repr(code))
        check("separately returned thinking becomes the thought trace", "points higher" in thought, repr(thought))
        replies[:] = [{"content": "@P.y += 2;", "reasoning_content": "plan"}]
        thought, code = hw.query_llm("raise the points", reasoning_mode=True)
        check("a normal thinking answer needs one request", code == "@P.y += 2;" and thought == "plan")
        replies[:] = [{"content": "", "reasoning_content": "still thinking"}, {"content": ""}]
        thought, code = hw.query_llm("raise the points", reasoning_mode=True)
        check("no code after the retry returns empty code with the thinking, not an exception",
              code == "" and "still thinking" in thought)
        replies[:] = [{"content": ""}]
        try:
            hw.query_llm("raise the points")  # turbo mode: thinking is already off, no second request
            raised = None
        except Exception as exc:  # noqa: BLE001
            raised = exc
        check("an entirely empty answer raises EmptyModelResponse, not 'engine unavailable'",
              isinstance(raised, hw.EmptyModelResponse) and "unavailable" not in str(raised), repr(raised))
    finally:
        hw._engine_port = real_port
        srv.shutdown()

    n = make_node()
    n.parm("snippet").set("@P.y += 0.25;")
    real_repair = hw.repair_vex

    def broken_repair(*a, **k):
        raise RuntimeError("engine hiccup")

    hw.repair_vex = broken_repair
    try:
        code, ok, err = hw._apply_generated_vex(n, "lift", "point wrangle", "@P.y += undefined_fn(1);", "")
        check("a failing repair request ends the repair instead of raising", ok is False and bool(err), repr((ok, err)))
    except Exception as exc:  # noqa: BLE001
        check("a failing repair request ends the repair instead of raising", False, repr(exc))
    finally:
        hw.repair_vex = real_repair
    check("the working snippet is kept after a failed repair", n.parm("snippet").eval().strip() == "@P.y += 0.25;",
          n.parm("snippet").eval())

    def cancelled_repair(*a, **k):
        raise hw.GenerationCancelled("Generation cancelled by user.")

    hw.repair_vex = cancelled_repair
    try:
        code, ok, err = hw._apply_generated_vex(n, "lift", "point wrangle", "@P.y += undefined_fn(1);", "")
        check("Esc during the auto-repair is reported as a cancel", ok is False and "cancelled" in (err or "").lower(), repr(err))
    finally:
        hw.repair_vex = real_repair

    # Optimize / Explain must never hand back an answer without VEX (it would replace the user's snippet)
    for bad in ("", "   ", "I would vectorise the loop."):
        try:
            hw._require_vex(bad)
            raised = False
        except hw.EmptyModelResponse:
            raised = True
        check(f"an answer without VEX is refused ({bad[:12]!r})", raised)
    check("an answer with VEX passes", hw._require_vex("@P.y += 1;") == "@P.y += 1;")

    # the retry without thinking is only for requests that asked for thinking
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    hw._engine_port = lambda: srv.server_port
    try:
        replies[:] = [{"content": "", "reasoning_content": "x"}, {"content": "@P.y += 9;"}]
        thought, code = hw.query_llm("raise the points", template_kwargs={})
        check("a training-format request is not retried in another format", code == "" and len(replies) == 1,
              repr((code, len(replies))))
    finally:
        hw._engine_port = real_port
        srv.shutdown()


# ---- function reference: built from the help of the local Houdini installation, not shipped ----------------
import json  # noqa: E402
import shutil  # noqa: E402

import vex_function_reference as vfr  # noqa: E402

built = vfr.build(ROOT)
check("the function reference builds from the local Houdini help",
      len(built) > 900 and bool(built.get("xyzdist", {}).get("usage")), f"{len(built)} functions")
vfr.ensure(ROOT)
check("the plugin's own function reference exists after first use", os.path.isfile(vfr.reference_path(ROOT)))
try:
    with open(vfr.reference_path(ROOT), encoding="utf-8") as _f:
        stored_ref = json.load(_f)
except Exception:
    stored_ref = None
check("the stored function reference is current (if not: hython tools/build_function_reference.py)",
      stored_ref == built)
ref_root = tempfile.mkdtemp(prefix="aw_ref_")
try:
    os.makedirs(os.path.join(ref_root, "data"))
    shutil.copy(os.path.join(ROOT, "data", "vex_signatures_vcc.json"), os.path.join(ref_root, "data"))
    check("without the Houdini help the reference is empty, not an error",
          vfr.ensure(ref_root, hfs=os.path.join(ref_root, "no_houdini")) == {}
          and not os.path.exists(vfr.reference_path(ref_root)))
    os.environ["AI_WRANGLE_BUILD_REFERENCE"] = "0"
    try:
        check("AI_WRANGLE_BUILD_REFERENCE=0 switches the automatic build off", vfr.ensure(ref_root) == {})
    finally:
        del os.environ["AI_WRANGLE_BUILD_REFERENCE"]
    check("a missing function reference is built and stored on first use",
          vfr.ensure(ref_root) == built and os.path.isfile(vfr.reference_path(ref_root)))
    with open(vfr.reference_path(ref_root), "w", encoding="utf-8") as _f:
        _f.write("{")  # a file cut off by a crash
    check("a damaged reference file is rebuilt", vfr.ensure(ref_root) == built)
    for wrong in ('{"point": 1}', '{"point": {}}', '[1]'):  # valid JSON that is not a reference
        with open(vfr.reference_path(ref_root), "w", encoding="utf-8") as _f:
            _f.write(wrong)
        check(f"a reference file of the wrong shape is rebuilt ({wrong})", vfr.ensure(ref_root) == built)
    leftovers = [f for f in os.listdir(os.path.join(ref_root, "data")) if f.endswith(".tmp")]
    check("no temporary files are left next to the reference", not leftovers, repr(leftovers))
finally:
    shutil.rmtree(ref_root, ignore_errors=True)


print()
failed = [r for r in RESULTS if not r[1]]
print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
for name, _, detail in failed:
    print(f"  FAILED: {name} :: {detail}")
