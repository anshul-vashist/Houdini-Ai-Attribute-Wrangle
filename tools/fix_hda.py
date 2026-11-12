"""One-shot HDA maintenance for otls/ai_attribwrangle.hda (run with hython).

- removes the embedded copy of SideFX's Sop/attribwrangle (it shadowed the native operator)
- flags OnCreated as Python (it was executed as HScript and failed on every node creation)
- makes ai_model_select a string menu keyed by model file name (an ordinal menu stored an index
  that pointed at a different model whenever a model was added to models/)
- adds a help page
"""
import sys
import hou

HDA = sys.argv[1]

for d in hou.hda.definitionsInFile(HDA):
    if d.nodeTypeName() == "attribwrangle":
        print("removing embedded Sop/attribwrangle definition")
        d.destroy()

d = [x for x in hou.hda.definitionsInFile(HDA) if x.nodeTypeName() == "ai_attribwrangle"][0]

oncreated = '''import hou
node = kwargs.get("node")
try:
    import houdini_ai_wrangle
    p = node.parm("ai_model_info") if node else None
    if p:
        p.set(houdini_ai_wrangle.get_active_ai_model_display_string())
except Exception as exc:  # never break node creation
    if node and node.parm("ai_status"):
        node.parm("ai_status").set("AI controller not loaded: %s" % exc)
'''
d.sections()["OnCreated"].setContents(oncreated)
d.setExtraFileOption("OnCreated/IsPython", True)
d.setExtraFileOption("OnCreated/IsScript", True)
d.setExtraFileOption("OnCreated/IsExpr", False)
d.setExtraFileOption("OnCreated/Cursor", "1,1")

ptg = d.parmTemplateGroup()
old = ptg.find("ai_model_select")
new = hou.StringParmTemplate(
    "ai_model_select", "AI Model", 1, default_value=("auto",),
    menu_type=hou.menuType.Normal,
    item_generator_script="import houdini_ai_wrangle\nreturn houdini_ai_wrangle.get_available_models_menu_items()",
    item_generator_script_language=hou.scriptLanguage.Python,
    script_callback="import houdini_ai_wrangle; houdini_ai_wrangle.on_model_select_changed(kwargs)",
    script_callback_language=hou.scriptLanguage.Python,
    join_with_next=old.joinsWithNext(),
    help="Model weights file from models/. 'Auto' uses the newest fine-tuned model (or AI_WRANGLE_MODEL_PATH).")
ptg.replace("ai_model_select", new)
d.setParmTemplateGroup(ptg)

help_text = '''= AI Attribute Wrangle =

#type: node
#context: sop
#internal: ai_attribwrangle
#icon: SOP/attribwrangle

"""An Attribute Wrangle with a local, offline VEX copilot."""

Behaves exactly like the native Attribute Wrangle (same VEXpression, Run Over, bindings). The
*AI VEX Copilot* folder adds natural-language code generation that runs on a local model; nothing
leaves the machine.

== Workflow ==

# Describe the task in *Prompt* (attribute names and numbers you give are used literally).
# Press *Generate*. The code is compiled on this node first; only if Houdini rejects it are
  automatic repairs and compiler-feedback retries applied.
# Use *History* (Prev / Next) and the A/B variants to compare versions without losing work.
# A prompt that says fix / modify / optimize edits the existing snippet instead of replacing it.

== Parameters ==

Prompt:
    Plain-English description of what the wrangle should do.

Deep Reasoning:
    Lets the model think before writing code. Slower; helps on multi-step math.

AI Model:
    Weights file from the package's models/ folder. Auto picks the newest fine-tuned model.
    Labels show scores on the held-out Houdini benchmark (57 unseen tasks checked on cooked geometry).

SideFX Micro-RAG:
    Adds matching VEX function signatures to the prompt.

== Notes ==

* Inference runs in a local llama-server process started on first use; the first Generate after
  launching Houdini loads the model (several seconds).
* Generated loops are bounded (1,000,000 iterations per loop) so a runaway while-loop cannot hang the cook.
'''
d.sections()["Help"].setContents(help_text)
print("updated:", d.nodeTypeName(), "| defs now in file:", [x.nodeTypeName() for x in hou.hda.definitionsInFile(HDA)])
