"""Regenerate the HDA parameter interface from the supported controller.

Run with Houdini's hython, not the system Python.  Keeping this transformation
script in source control prevents the HDA dialog script from drifting away from
the callback module again.
"""

from pathlib import Path
import sys

import hou

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INTEGRATION_DIR = PROJECT_ROOT / "houdini_vex_project" / "03_houdini_integration"
HDA_PATH = INTEGRATION_DIR / "ai_attribwrangle.hda"

sys.path.insert(0, str(INTEGRATION_DIR))
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
        definition.setParmTemplateGroup(reference.parmTemplateGroup())
        definition.setDescription("AI Attribute Wrangle")
        definition.save(str(HDA_PATH), template_node=reference, options=definition.options())
    finally:
        geo.destroy()

    required = {"ai_status", "ai_perf", "ai_history_json", "ai_version_info", "ai_thought_trace"}
    installed = hou.hda.definitionsInFile(str(HDA_PATH))[0]
    found = {parm.name() for parm in installed.parmTemplateGroup().entriesWithoutFolders()}
    missing = required - found
    if missing:
        raise RuntimeError(f"Regenerated HDA is missing required parameters: {sorted(missing)}")
    print(f"Regenerated {HDA_PATH}")


if __name__ == "__main__":
    main()
