"""
Verified-example retrieval (a "cookbook" for the model).

For a task description, return the most similar teacher-written concept cards (request + solution). Every solution
in the bank was verified in Houdini (ai_model_training/v53_cards). Shown in the prompt as worked examples, they
give the model the exact function names, argument orders and idioms it tends to get wrong on its own.

    block = build_examples_block("round the weights to the nearest eighth", context="point wrangle")

Pure Python (no hou, no numpy). The bank is data/vex_card_bank.json (tools/build_card_bank.py); cards that are
held out for evaluation are not in it.
"""
import json
import math
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_BANK = None

_STOP = set("""a an the of to in on at by for from with and or is are be as it its this that each every all any into onto
than then so if which who whose their there here not no only also using use used store stored create set make give put
called named name value values i me my we you your want need should must can will would please one two three""".split())
_SYN = {"colour": "color", "colours": "color", "colors": "color", "neighbours": "neighbor", "neighbour": "neighbor",
        "neighbors": "neighbor", "centre": "center", "centred": "center", "centered": "center", "normalise": "normalize",
        "normalised": "normalize", "normalized": "normalize", "primitives": "primitive", "prims": "primitive",
        "prim": "primitive", "faces": "primitive", "face": "primitive", "polygons": "primitive", "polygon": "primitive",
        "pts": "point", "points": "point", "verts": "vertex", "vertices": "vertex", "delete": "remove", "deleted": "remove",
        "erase": "remove", "kill": "remove", "drop": "remove", "sliders": "parameter", "slider": "parameter",
        "parameters": "parameter", "param": "parameter", "params": "parameter", "attrib": "attribute",
        "attributes": "attribute", "attr": "attribute", "curves": "curve", "strands": "curve", "hairs": "curve",
        "velocity": "v", "position": "p", "positions": "p", "normals": "normal", "sdf": "distancefield",
        "random": "rand", "randomise": "rand", "randomize": "rand", "nearest": "closest", "near": "closest"}
# a request that is itself about repairing or speeding up given code
_FIX_REQUEST = re.compile(r";|\bfix\b|\bbug|\bbroken\b|\bwrong\b|\berror\b|does not compile|doesn't compile|"
                          r"does nothing|not working|doesn't work|\brepair\b|\bfaster\b|\boptimi[sz]e", re.I)


def _tokens(text):
    out = []
    for w in re.findall(r"[a-z_]+[0-9]*|[0-9]+", text.lower()):
        w = _SYN.get(w, w)
        if w in _STOP or len(w) < 2:
            continue
        for suf in ("ies", "ing", "ed", "es", "s"):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                w = w[:-len(suf)] + ("y" if suf == "ies" else "")
                break
        out.append(_SYN.get(w, w))
    return out


def _vector(tokens, idf):
    tf = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    vec = {t: (1 + math.log(c)) * idf.get(t, 0.0) for t, c in tf.items()}
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {t: v / norm for t, v in vec.items()}


def _load():
    global _BANK
    if _BANK is not None:
        return _BANK
    root = os.environ.get("AI_WRANGLE_ROOT") or os.path.abspath(os.path.join(_HERE, ".."))
    path = os.environ.get("AI_WRANGLE_CARD_BANK") or os.path.join(root, "data", "vex_card_bank.json")
    try:
        cards = json.load(open(path, encoding="utf-8"))
    except Exception:
        cards = []
    docs = [_tokens(" ".join(c["prompts"]) + " " + " ".join(c.get("fns", []))) for c in cards]
    df = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    n = max(1, len(docs))
    idf = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}
    _BANK = dict(cards=cards, idf=idf, vecs=[_vector(d, idf) for d in docs])
    return _BANK


def retrieve(task, context="", k=2, min_score=0.16, exclude=None):
    """[(score, card), ...] best first; cards scoring under min_score are not returned.

    Which cards are eligible:
      * a Volume Wrangle request only gets volume cards and every other wrangle never gets one (their code binds
        voxel values such as @density, which would mislead a point / primitive / detail wrangle);
      * "fix this code" cards, whose request contains the broken program, are only offered when the task itself
        looks like a repair or optimisation request;
      * exclude: card ids or concept names that must not be returned. Used when training rows are built from the
        cards themselves (a card must not be shown as its own example); AI_WRANGLE_EXAMPLES_EXCLUDE
        (comma-separated) adds to it."""
    bank = _load()
    if not bank["cards"]:
        return []
    try:
        k = max(1, min(12, int(k)))
    except (TypeError, ValueError):
        k = 2
    exclude = set(exclude or ()) | {x.strip() for x in os.environ.get("AI_WRANGLE_EXAMPLES_EXCLUDE", "").split(",")
                                    if x.strip()}
    q = _vector(_tokens(task or ""), bank["idf"])
    ctx = (context or "").split()[0].lower() if (context or "").split() else ""
    want_volume = ctx == "volume"
    fix_request = bool(_FIX_REQUEST.search(task or ""))
    scored = []
    for card, vec in zip(bank["cards"], bank["vecs"]):
        if exclude and (card.get("id") in exclude or card.get("concept") in exclude):
            continue
        if ctx and (card.get("context") == "volume") != want_volume:
            continue
        if card.get("fix") and not fix_request:
            continue
        s = sum(w * vec.get(t, 0.0) for t, w in q.items())
        if ctx and card.get("context") == ctx:
            s += 0.03
        scored.append((s, card))
    scored.sort(key=lambda x: -x[0])
    return [(s, c) for s, c in scored[:k] if s >= min_score]


def select_examples(task, context="", k=2, min_score=0.16, exclude=None, lam=None):
    """The examples to show for a task.

    lam = 0: the k most similar cards by text (retrieve).
    lam > 0 (AI_WRANGLE_EXAMPLES_RERANK): function-aware choice. The function lookup (vex_function_index) predicts
    which functions the task needs; among the 10 most similar cards the examples are picked greedily by
    similarity + lam * (weight of the predicted functions the card demonstrates and no earlier example did), so the
    two examples show different needed functions instead of the same one twice. On the open concept cards this
    raises the share of needed functions that the examples demonstrate from 0.30 to 0.38 (unseen concepts: 0.32 to
    0.47), see scratch/next/rerank_experiment.py."""
    if lam is None:
        try:
            lam = float(os.environ.get("AI_WRANGLE_EXAMPLES_RERANK", "0"))
        except ValueError:
            lam = 0.0
    try:
        k = max(1, min(6, int(k)))
    except (TypeError, ValueError):
        k = 2
    if lam <= 0:
        return retrieve(task, context, k, min_score, exclude)
    cands = retrieve(task, context, k=10, min_score=0.10, exclude=exclude)
    try:
        import vex_function_index
        pred = dict(vex_function_index.retrieve(task, context, k=8, exclude=exclude, rel=0.0))
    except Exception:
        pred = {}
    if not pred or not cands:
        return [(s, c) for s, c in cands[:k] if s >= min_score]
    top = max(pred.values()) or 1.0
    chosen, covered = [], set()
    while cands and len(chosen) < k:
        def value(sc):
            return sc[0] + lam * sum(pred[f] / top for f in (set(sc[1].get("fns", [])) & set(pred)) - covered)
        best = max(cands, key=value)
        cands.remove(best)
        shows = (set(best[1].get("fns", [])) & set(pred)) - covered
        if best[0] >= min_score or shows:
            chosen.append(best)
        covered |= set(best[1].get("fns", []))
    return chosen


def build_examples_block(task, context="", k=2, min_score=0.16):
    hits = select_examples(task, context, k, min_score)
    if not hits:
        return ""
    lines = ["Verified examples of related tasks (they show correct function names and idioms; adapt, do not copy):"]
    for i, (_, c) in enumerate(hits, 1):
        kind = "volume wrangle" if c.get("context") == "volume" else f"{c.get('context', 'point')} wrangle"
        lines.append(f"Example {i} ({kind}): {c['prompts'][0]}\n{c['code']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    for s, c in retrieve(" ".join(sys.argv[1:]) or "round the weight to the nearest eighth", k=3, min_score=0.0):
        print(round(s, 3), c["id"], "|", c["prompts"][0][:90])
