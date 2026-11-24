"""Rebuild the parameter interface stored in the HDA from the layout in python/houdini_ai_wrangle.py
(_strip_ai_layout + _build_ai_layout): tabs Wrangle / History / Tools / Settings / Bindings. Idempotent.

    hython tools/hda_rebuild_ui.py [path/to/ai_attribwrangle.hda]

Parameter names do not change, so nodes in saved scenes keep their code and values.
"""
import os
import sys

import hou

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "python"))
os.environ.setdefault("AI_WRANGLE_ROOT", ROOT)
HDA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "otls", "ai_attribwrangle.hda")
hou.hda.installFile(HDA)

import houdini_ai_wrangle as hw  # noqa: E402

HELP = r"""= AI Attribute Wrangle =

#type: node
#context: sop
#internal: ai_attribwrangle
#icon: SOP/attribwrangle

'''An Attribute Wrangle that writes its VEX from a prompt, with a local model.'''

It is the native Attribute Wrangle (same VEXpression, Run Over, Group and bindings) with a prompt on top.
The model runs on this machine; nothing leaves it.

== Workflow ==

# Describe the result in *Prompt*. Name attributes, groups and inputs as they are called in your scene.
# Press *Generate*. The code is compiled and cooked on this node before you see it.
# Read *Understood As*: one sentence from the model about what the code does. If it is not what you meant,
  the request was misunderstood: say it more exactly, or correct it with *Edit Code*.
# Read *Status*. "Check: the result may not match the request" means the model itself doubts the result:
  look at that one before you trust it.
# To work on code that is already there, type only what you want and press *Edit Code*. *Generate* always
  writes new code.
# Small changes work best: "add amplitude", "use the z position instead of x", "use time so it animates".
  *Status* counts the lines added, changed and removed.
# When you ask for something more ("also ...", "add ...") your existing lines are never reduced: if the model's
  edit would take something away from them, only the new lines are appended instead.
# For any other change the model may alter more than you asked. *Status* then says how many existing lines
  were rewritten; the version before stays in *History*, and Ctrl+Z undoes the edit.
# Sliders and ramps the code asks for (chf, chv, chramp) appear under *Controls*, below the code.

== Tabs ==

Wrangle:
    Prompt, Generate, Edit Code, Status, Run Over, Group and the code.

History:
    Step back and forward through earlier versions; keep two variants (A and B) and swap between them.

Tools:
    Presets to start from, safety guards, attribute statistics, a help card, export as a .h file, and
    *AI Notes* (the result check, which answer was chosen, and the model's plan).

Settings:
    The model and how answers are produced.

Bindings:
    The wrangle's own bindings and options.

== Parameters ==

Think First (Slower):
    The model plans step by step before writing the code and gives one answer. For hard problems.

Auto (next to Run Over):
    Run Over is chosen from the prompt. Turn off to keep your own choice.

Model:
    Model file from the package's models folder. Auto uses the newest fine-tuned model.

Answers to Compare:
    For a new snippet the model answers this many times; each answer is cooked here and the result most of
    them agree on is kept.

Use Examples and Reference:
    Sends similar verified examples and the signatures of likely VEX functions with the prompt.

Warn If Result Looks Wrong:
    After a generation the model judges what the code did to the geometry. A warning is right about three
    times in four; code that passes is right about four times in five. The code is never changed.

== Notes ==

* The first Generate after starting Houdini loads the model (several seconds).
* Generated loops are bounded (1,000,000 iterations per loop), so a runaway loop cannot hang the cook.
* Review generated code before it goes into a shot.
"""

HELP = HELP.replace("'''", '"""')  # the help format marks the summary line with triple double quotes

d = [x for x in hou.hda.definitionsInFile(HDA) if x.nodeTypeName() == "ai_attribwrangle"][0]
ptg = d.parmTemplateGroup()
hw._strip_ai_layout(ptg)
hw._build_ai_layout(ptg)
# the field is filled in when a node is created; the asset itself must not carry this machine's model name
info = ptg.find("ai_model_info")
info.setDefaultValue(("",))
ptg.replace("ai_model_info", info)
d.setParmTemplateGroup(ptg)
d.sections()["Help"].setContents(HELP)
d.save(HDA)


def walk(templates, depth=0):
    for t in templates:
        kind = t.type().name()
        flags = (" (hidden)" if t.isHidden() else "") + (" +" if t.joinsWithNext() else "")
        print("  " * depth + f"{t.label() or t.name()}  [{t.name()}]{flags}")
        if kind == "Folder" and t.folderType() != hou.folderType.MultiparmBlock:
            walk(t.parmTemplates(), depth + 1)


walk(d.parmTemplateGroup().entries())
print("saved", HDA)
