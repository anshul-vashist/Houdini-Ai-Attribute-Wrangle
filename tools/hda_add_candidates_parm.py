"""Add the 'AI Candidates' parameter (best-of-N) to the HDA's Advanced Options. Idempotent.
    hython tools/hda_add_candidates_parm.py <path/to/ai_attribwrangle.hda>
"""
import sys

import hou

HDA = sys.argv[1]
d = [x for x in hou.hda.definitionsInFile(HDA) if x.nodeTypeName() == "ai_attribwrangle"][0]
ptg = d.parmTemplateGroup()
if ptg.find("ai_num_candidates") is None:
    tpl = hou.IntParmTemplate(
        "ai_num_candidates", "AI Candidates", 1, default_value=(3,), min=1, max=8, min_is_strict=True, max_is_strict=True,
        help="Answers generated for a new snippet. Each is compiled and cooked on this node and the one most "
             "candidates agree on is kept (1 = fastest, single answer). Edits and Deep Reasoning use one answer.")
    ptg.insertAfter(ptg.find("ai_use_rag"), tpl)
    d.setParmTemplateGroup(ptg)
    print("added ai_num_candidates")
else:
    print("already present")
