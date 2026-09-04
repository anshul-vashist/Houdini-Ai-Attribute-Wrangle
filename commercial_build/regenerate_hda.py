"""Regenerate the HDA parameter interface from the supported controller.

Run with Houdini's hython, not the system Python.  Keeping this transformation
script in source control prevents the HDA dialog script from drifting away from
the callback module again.
"""

from pathlib import Path
import sys

import hou

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHON_DIR = PROJECT_ROOT / "python"
HDA_PATH = PROJECT_ROOT / "dist" / "AI_Attribute_Wrangle_v1.0" / "hda" / "ai_attribwrangle.hda"

sys.path.insert(0, str(PYTHON_DIR))
import houdini_ai_wrangle


def main() -> None:
    hou.hda.installFile(str(HDA_PATH), force_use_assets=True)
    definition = hou.hda.definitionsInFile(str(HDA_PATH))[0]

    obj = hou.node("/obj")
    geo = obj.createNode("geo", "__ai_wrangle_hda_build__")
    try:
        reference = geo.createNode("attribwrangle", "reference")
        if not houdini_ai_wrangle.setup_ai_parameters(reference):
            raise RuntimeError("Could not create the AI parameter interface on the reference wrangle.")
        full_ptg = reference.parmTemplateGroup()

        # Build unlocked instance with core wrangle inside
        inst = geo.createNode("ai_attribwrangle", "__builder_inst__")
        inst.allowEditingOfContents()
        inst.setParmTemplateGroup(full_ptg)

        vop = inst.node("attribvop1")
        if not vop:
            vop = inst.createNode("attribwranglecore", "attribvop1")

        for i in range(4):
            vop.setInput(i, inst.indirectInputs()[i])

        vop.setDisplayFlag(True)
        vop.setRenderFlag(True)

        if vop.parm("vexsrc"):
            vop.parm("vexsrc").set("snippet")

        if vop.parm("vex_multithread"):
            vop.parm("vex_multithread").deleteAllKeyframes()
            vop.parm("vex_multithread").set(1)

        expr_map = {
            "bindgroup": 'chs("../group")',
            "bindgrouptype": 'ch("../grouptype")',
            "bindclass": 'ch("../class")',
            "vex_numcount": 'ch("../vex_numcount")',
            "vex_threadjobsize": 'ch("../vex_threadjobsize")',
            "vexsnippet": 'chs("../snippet")',
            "vex_strict": 'ch("../vex_strict")',
            "vex_exportlist": 'chs("../exportlist")',
            "vex_strictvariables": 'ch("../vex_strictvariables")',
            "vex_cwdpath": 'chsop("../vex_cwdpath")',
            "vex_outputmask": 'chs("../vex_outputmask")',
            "vex_precision": 'chs("../vex_precision")',
            "autobind": 'ch("../autobind")',
            "bindings": 'ch("../bindings")',
            "groupautobind": 'ch("../groupautobind")',
            "groupbindings": 'ch("../groupbindings")',
            "vex_updatenmls": 'ch("../vex_updatenmls")',
            "vex_matchattrib": 'chs("../vex_matchattrib")',
            "vex_inplace": 'ch("../vex_inplace")',
            "vex_selectiongroup": 'chs("../vex_selectiongroup")',
        }
        for parm_name, expr in expr_map.items():
            p = vop.parm(parm_name)
            if p:
                try:
                    p.setExpression(expr)
                except Exception:
                    pass

        definition.setParmTemplateGroup(full_ptg)
        definition.setDescription("AI Attribute Wrangle")
        options = definition.options()
        definition.save(str(HDA_PATH), template_node=inst, options=options)
    finally:
        geo.destroy()

    required = {"ai_status", "ai_perf", "ai_model_info", "ai_history_json", "ai_version_info", "ai_thought_trace", "ai_compact_mode"}
    installed = hou.hda.definitionsInFile(str(HDA_PATH))[0]
    found = {parm.name() for parm in installed.parmTemplateGroup().entriesWithoutFolders()}
    missing = required - found
    if missing:
        raise RuntimeError(f"Regenerated HDA is missing required parameters: {sorted(missing)}")
    
    # Also synchronize all target HDA and python locations
    import shutil
    destinations = [
        PROJECT_ROOT / "otls" / "ai_attribwrangle.hda",
        PROJECT_ROOT / "houdini_hda_package" / "otls" / "ai_attribwrangle.hda",
        PROJECT_ROOT / "houdini_hda_package" / "dist" / "AI_Attribute_Wrangle_v1.0" / "hda" / "ai_attribwrangle.hda",
        Path("C:/Users/Anshul/Documents/houdini21.0/otls/ai_attribwrangle.hda"),
    ]
    for dst in destinations:
        if dst.parent.exists():
            shutil.copyfile(str(HDA_PATH), str(dst))
            print(f"Copied HDA to {dst}")

    py_source = PYTHON_DIR / "houdini_ai_wrangle.py"
    py_destinations = [
        PROJECT_ROOT / "commercial_build" / "houdini_ai_wrangle.py",
        PROJECT_ROOT / "dist" / "AI_Attribute_Wrangle_v1.0" / "python" / "houdini_ai_wrangle.py",
        PROJECT_ROOT / "houdini_hda_package" / "python" / "houdini_ai_wrangle.py",
        PROJECT_ROOT / "houdini_hda_package" / "commercial_build" / "houdini_ai_wrangle.py",
        PROJECT_ROOT / "houdini_hda_package" / "dist" / "AI_Attribute_Wrangle_v1.0" / "python" / "houdini_ai_wrangle.py",
        Path("C:/Users/Anshul/Documents/houdini21.0/scripts/python/houdini_ai_wrangle.py"),
    ]
    for dst in py_destinations:
        if dst.parent.exists():
            shutil.copyfile(str(py_source), str(dst))
            print(f"Copied Python to {dst}")
        
    print(f"Regenerated and synced {HDA_PATH}")


if __name__ == "__main__":
    main()
