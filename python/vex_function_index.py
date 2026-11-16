"""
Function lookup: which VEX functions does a task probably need, and what are their exact signatures?

Three sources of evidence are combined:
  * the function reference (data/vex_function_reference.json, built on first use from the help of the local
    Houdini installation by vex_function_reference.py): the task text is matched against each function's name,
    summary and tags;
  * plain-language search phrases per function (data/vex_function_aliases.json): how a user describes the job
    ("mean" for avg, "capitalise" for titlecase), which the terse help summaries do not say;
  * the verified card bank (vex_example_bank): the functions used by the solved tasks most similar to this one.

    for name, score in retrieve("distance along the mesh edges to the nearest point of group src"): ...
    block = build_signature_block(task, context="point wrangle")
    match_pages("polar decomposition")   # page match only: what a made-up function name probably stands for

Pure Python (no hou, no numpy). Measured on the concept cards with scratch/rag_recall.py: of the functions a
solution needs, the top 10 contain 71 % (62 % without the phrases and the page-match scaling), and 70 % of the
functions that no other solved task uses (42 % without; measured 2026-11-11 on 464 cards with the 410-card bank).
"""
import json
import math
import os
import re

import vex_example_bank as _bank
import vex_function_reference as _reference

_HERE = os.path.dirname(os.path.abspath(__file__))
_IDX = None

# functions every wrangle uses: listing their signatures would only spend prompt space
_COMMON = set("""set length normalize dot cross abs min max clamp sin cos sqrt pow floor ceil rand len append point
npoints nprimitives chf chi chv chs ch int float vector printf sprintf""".split())
# function groups that a SOP wrangle rarely needs: only offered when the task mentions the topic
_OFF_TOPIC = {"usd": ("usd", "lop", "stage"), "crowd": ("agent", "crowd"), "bsdf": ("bsdf",),
              "shading": ("shad", "render", "illuminance"), "ocio": ("ocio", "colorspace", "color space"),
              "texture": ("texture", "ptex", "image file"), "sensor": ("sensor",), "chprim": ("channel prim", "chprim"),
              "CHOP": ("chop",), "metaball": ("metaball",), "light": ("light",), "image": ("image",),
              "fuzzy": ("fuzzy",), "nodes": ("node", "operator", "op:", "path of", "parameter of")}

# A long request shares few of its words with any one function page, so even the best page match has a small
# cosine and used to lose against the task votes (worth up to 0.6): functions that no solved task uses were rarely
# offered. The page matches are therefore scaled so that the best one counts _W_PAGE, unless it is itself weak
# (cosine under _PAGE_S0): then nothing in the pages fits well and the votes decide.
_PAGE_S0 = 0.35
_W_PAGE = 0.85


def _phrases_on():
    """AI_WRANGLE_FUNCTION_ALIASES=0 switches the search phrases and the page-match scaling off (for comparisons)."""
    return os.environ.get("AI_WRANGLE_FUNCTION_ALIASES", "1") != "0"


def _words(text):
    return re.findall(r"[a-z_][a-z0-9_]*", (text or "").lower())


def _load():
    global _IDX
    if _IDX is not None and _IDX["phrases"] == _phrases_on():
        return _IDX
    root = os.environ.get("AI_WRANGLE_ROOT") or os.path.abspath(os.path.join(_HERE, ".."))
    ref = _reference.ensure(root)  # stored file, else built from the local Houdini help; {} when neither exists
    aliases = {}
    if _phrases_on():
        try:
            aliases = json.load(open(os.path.join(root, "data", "vex_function_aliases.json"), encoding="utf-8"))
        except Exception:
            aliases = {}
    docs, vocab = {}, set()
    for fn, e in ref.items():
        words = " ".join([fn, fn.replace("_", " ")] * 2 + [e.get("summary", "")] + e.get("tags", []) + [e.get("group", "")]
                         + [str(aliases.get(fn, ""))])
        docs[fn] = _bank._tokens(words)
        vocab.update(_words(words))
    df = {}
    for d in docs.values():
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    n = max(1, len(docs))
    idf = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}
    cards = _bank._load()["cards"]
    # how many bank cards use each function: rare functions are stronger evidence than ubiquitous ones
    use = {}
    for c in cards:
        for f in c.get("fns", []):
            use[f] = use.get(f, 0) + 1
    # Function names that are also ordinary words ("volume", "distance", "gradient", "sleep" ...): a name counts as
    # ordinary when it occurs in the prose of another function's summary, or in the plain-language request of a
    # solved task that does not use the function. Seeing such a word in a task is not a request for the function.
    prose = set()
    for fn, e in ref.items():
        for w in _words(e.get("summary", "")):
            if w in ref and w != fn:
                prose.add(w)
    for c in cards:
        used = set(c.get("fns", []))
        for k, p in enumerate(c.get("prompts", [])):
            if k == 1:
                continue  # the formula-style phrasing is code, not prose
            for w in _words(p):
                if w in ref and w not in used:
                    prose.add(w)
    _IDX = dict(ref=ref, idf=idf, vecs={fn: _bank._vector(d, idf) for fn, d in docs.items()}, use=use,
                ncards=max(1, len(cards)), prose=prose, vocab=vocab, phrases=_phrases_on())
    return _IDX


def _page_scores(idx, low):
    """{function: cosine between the text and the function's page (name, summary, tags, search phrases)}"""
    q = _bank._vector(_bank._tokens(low), idx["idf"])
    scores = {}
    for fn, vec in idx["vecs"].items():
        s = sum(w * vec.get(t, 0.0) for t, w in q.items())
        if s > 0:
            scores[fn] = s
    return scores


def _on_topic(idx, fn, low):
    topics = _OFF_TOPIC.get(idx["ref"][fn].get("group", ""))
    return not topics or any(t in low for t in topics)


def retrieve(task, context="", k=6, exclude=None, neighbours=8, rel=0.3):
    """[(function name, score), ...] best first. Functions scoring under `rel` times the best score (or under
    0.12) are dropped, so a vague task gets a short list instead of six guesses."""
    idx = _load()
    if not idx["ref"]:
        return []
    try:
        k = max(1, min(12, int(k)))
    except (TypeError, ValueError):
        k = 6
    low = (task or "").lower()
    scores = _page_scores(idx, low)
    if idx["phrases"] and scores:
        top_page = max(max(scores.values()), _PAGE_S0)
        for f in scores:
            scores[f] = _W_PAGE * scores[f] / top_page
    # votes of the most similar solved tasks
    votes = {}
    for sim, card in _bank.retrieve(low, context, k=neighbours, min_score=0.08, exclude=exclude):
        for f in card.get("fns", []):
            rarity = math.log((idx["ncards"] + 1) / (idx["use"].get(f, 0) + 1))
            votes[f] = votes.get(f, 0.0) + sim * rarity
    top = max(votes.values()) if votes else 0.0
    for f, v in votes.items():
        if f in idx["ref"]:
            scores[f] = scores.get(f, 0.0) + 0.6 * v / top
    # A function that the task names. Written as a call, name(...), it is certainly wanted; a bare name counts
    # only if it is not an ordinary word, and then only a little (it must not push the real matches out).
    named = {}
    for w in set(_words(low)):
        if w in idx["ref"] and w not in _COMMON:
            if re.search(rf"(?<![\w@]){re.escape(w)}\s*\(", low):
                named[w] = 1.0
            elif w not in idx["prose"] and (len(w) > 5 or "_" in w):
                named[w] = 0.35
    best = max(scores.values()) if scores else 0.0
    floor = max(0.12, rel * best)
    ranked = sorted(set(scores) | set(named), key=lambda f: -(scores.get(f, 0.0) + named.get(f, 0.0)))
    out = []
    for fn in ranked:
        if fn in _COMMON or not _on_topic(idx, fn, low):
            continue
        if scores.get(fn, 0.0) < floor and named.get(fn, 0.0) < 1.0:
            continue
        out.append((fn, scores.get(fn, 0.0) + named.get(fn, 0.0)))
        if len(out) >= k:
            break
    return out


def split_name(name):
    """A run-together identifier as words: polarDecomposition -> 'polar decomposition', volumexsize -> 'volume x
    size', npointsinGroup -> 'npoints in group', ptnumtoprim -> 'ptnum to prim'. Each part is cut into words the
    function pages know so that as few letters as possible are left over, then into as few pieces as possible
    (a greedy longest-word cut gave 'arrays um' for arraysum)."""
    vocab = _load()["vocab"]
    connectors = {"to", "in", "of", "by", "on", "at", "is"}
    out = []
    for part in re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name or "").replace("_", " ").lower().split():
        if part in vocab or len(part) > 60:
            out.append(part)
            continue
        n = len(part)
        # best[i] = (unknown letters, pieces, words) for part[i:]
        best = [None] * (n + 1)
        best[n] = (0, 0, [])
        for i in range(n - 1, -1, -1):
            cand = None
            for j in range(i + 1, n + 1):
                word = part[i:j]
                known = (word in vocab and len(word) >= 3) or word in connectors
                tail = best[j]
                if known:
                    c = (tail[0], tail[1] + 1, [word] + tail[2])
                elif j == i + 1:  # one unknown letter; neighbouring unknown letters are joined below
                    c = (tail[0] + 1, tail[1] + 1, [word] + tail[2])
                else:
                    continue
                if cand is None or (c[0], c[1]) < (cand[0], cand[1]):
                    cand = c
            best[i] = cand
        # join runs of single unknown letters into one piece
        merged = []
        for w in best[0][2]:
            single_unknown = len(w) == 1 and not ((w in vocab and len(w) >= 3) or w in connectors)
            if single_unknown and merged and merged[-1][1]:
                merged[-1] = (merged[-1][0] + w, True)
            else:
                merged.append((w, single_unknown))
        out.extend(w for w, _ in merged)
    return " ".join(out)


def match_pages(text, k=3, min_score=0.2, context_text=""):
    """[(function, score)]: the functions whose pages fit a short description best (page match only, no task
    votes). context_text decides which special-topic groups (USD, crowds ...) may be offered."""
    idx = _load()
    low = (text or "").lower()
    topic_text = low + " " + (context_text or "").lower()
    scores = _page_scores(idx, low)
    ranked = sorted((f for f in scores if _on_topic(idx, f, topic_text)), key=lambda f: -scores[f])
    return [(f, scores[f]) for f in ranked[:max(1, int(k))] if scores[f] >= min_score]


_NOTES = None


def _notes():
    """Usage notes per function (data/vex_function_notes.json): argument order, special argument values, return
    conventions. Shown when AI_WRANGLE_FUNCTION_NOTES=1; AI_WRANGLE_FUNCTION_USAGE_LINES sets how many usage lines
    a function gets (default 2; with 3 the vector form of the noise functions is shown as well)."""
    global _NOTES
    if os.environ.get("AI_WRANGLE_FUNCTION_NOTES", "0") == "0":  # off until measured: see the README of v53_cards
        return {}
    if _NOTES is None:
        root = os.environ.get("AI_WRANGLE_ROOT") or os.path.abspath(os.path.join(_HERE, ".."))
        try:
            _NOTES = json.load(open(os.path.join(root, "data", "vex_function_notes.json"), encoding="utf-8"))
        except Exception:
            _NOTES = {}
    return _NOTES


def note_for(fn):
    """the usage note of a function ('' if it has none)"""
    return str(_notes().get(fn, "")).strip()


def _pick_usage(usage, limit):
    """Up to `limit` usage lines for a SOP wrangle, in the order of the help: the first line, then the forms that
    take a vector, an array or have output arguments. The help lists scalar-coordinate forms first
    (noise(float pos), noised(float x, ...)), which hides the form a wrangle normally calls (noise(vector pos))."""
    if len(usage) <= limit:
        return list(usage)

    def params(u):
        return [p.strip() for p in u.partition("(")[2].rstrip(") ;").split(",") if p.strip()]

    returning = [params(u) for u in usage if not u.lstrip().startswith("void")]

    def score(u):
        ps = params(u)
        inputs = [p for p in ps if "&" not in p]
        vec = any(re.match(r"<?vector>?(?![24])", p) for p in inputs)  # takes a vector (a position, a direction)
        scalars = sum(p.startswith("float ") for p in inputs) >= 2 and not vec  # x, y given as separate floats
        array = any("[]" in p for p in ps)
        # the output-argument twin of a returning form: void f(int &result, a, b) next to int f(a, b). A void
        # form that changes its first argument in place (insert, append, rotate) is NOT one.
        twin = (u.lstrip().startswith("void") and len(ps) > 1 and "&" in ps[0] and "[]" not in ps[0]
                and any(inputs == r or ps[1:] == r for r in returning))
        return 2 * vec + ("&" in u and not twin) + array - ("vector4" in u) - scalars - 3 * twin

    rest = sorted(range(1, len(usage)), key=lambda i: (-score(usage[i]), i))[:limit - 1]
    return [usage[i] for i in sorted([0] + rest)]


def signature_lines(fn, max_usage=2):
    """The lines shown for a function: its first usage lines from the help and '// name: summary'.
    AI_WRANGLE_FUNCTION_USAGE_LINES=n shows n usage lines chosen by _pick_usage instead of the first two (off by
    default: the first two lines are what the shipped results were measured with); AI_WRANGLE_FUNCTION_NOTES=1
    appends the usage note."""
    e = _load()["ref"].get(fn)
    if not e:
        return []
    usage = [u for u in e.get("usage", []) if "string filename" not in u and "string geometry" not in u] or e.get("usage", [])
    usage = [u.rstrip().rstrip(";") for u in usage]
    wanted = os.environ.get("AI_WRANGLE_FUNCTION_USAGE_LINES", "")
    if wanted.strip().isdigit() and int(wanted) >= 1:
        lines = _pick_usage(usage, int(wanted))
    else:
        lines = usage[:max_usage]
    note = note_for(fn)
    if e.get("summary") or note:
        text = (e.get("summary") or "").strip()
        lines.append(f"// {fn}: {text}{' ' if text and note else ''}{'Note: ' + note if note else ''}")
    return lines


def build_signature_block(task, context="", k=6, exclude=None):
    hits = retrieve(task, context, k=k, exclude=exclude)
    if not hits:
        return ""
    lines = ["Official SideFX VEX Function Signatures (Ground Truth Reference):"]
    for fn, _ in hits:
        lines += [f"  - {s}" for s in signature_lines(fn)]
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) or "distance along the mesh edges from each point to the nearest point of the group src"
    for fn, s in retrieve(text, k=8):
        print(round(s, 3), fn)
    print(build_signature_block(text))
