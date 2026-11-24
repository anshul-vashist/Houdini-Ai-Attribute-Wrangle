"""
Wording notes: what everyday artist phrases mean in a wrangle.

Artists type requests in casual words ("my grad ramp", "for the instances", "from bottom to top", "centred around
zero"). The model answers precise requests far better than casual ones (everyday test set, v55 through the plugin,
2026-11-24: precise 43 of 48, casual 28 of 48) while solving 47 of the 48 tasks in some wording, so it lacks the
translation, not the VEX. A note is added to the prompt for each phrase of this list that occurs in the request.

The list is written from ordinary Houdini usage, not from test failures. AI_WRANGLE_WORDING_NOTES=1 switches it on
(off until measured).

    notes_for("colour it with my grad ramp from bottom to top")   -> list of note strings
"""
import os
import re

# (pattern on the lower-case request, note). Patterns are word-bounded; a note is given once.
NOTES = [
    (r"\bmy (\w+)\b|\b(\w+) (?:slider|parameter|param|control|knob)\b|\b(?:slider|parameter|control) (?:called|named) (\w+)",
     "A value the artist calls 'my X', 'X slider' or 'X parameter' is a channel parameter of the wrangle named X: "
     "chf(\"X\") for a number, chi(\"X\") for a count, seed or integer, chv(\"X\") for a position, direction or "
     "colour, chs(\"X\") for text, chramp(\"X\", t) for a ramp."),
    (r"\b(?:colou?r )?(?:ramp|gradient)\b",
     "A ramp is read with chramp(\"name\", t) where t runs from 0 (left end) to 1 (right end); a colour ramp "
     "returns a vector (assign it to a vector, e.g. @Cd = chramp(...)), a float ramp a float."),
    (r"\bfor (?:the )?(?:instances|copies|copying)\b|\bcopy to points\b|\binstanc",
     "Rotations meant for instances or copies are written to the quaternion attribute p@orient (and sizes to "
     "f@pscale); the point positions @P stay where they are."),
    (r"\bbottom to (?:the )?top\b|\bhow high\b|\brelative height\b|\b(?:fills?|from) 0 to 1\b|\b0 (?:to|-) 1 (?:across|over)\b|\bacross the (?:whole )?(?:object|geometry|bounding box)\b",
     "'From bottom to top', 'how high on the object' or 'filling 0 to 1 across the object' means the position "
     "relative to the bounding box: relbbox(0, @P) gives each axis from 0 at the minimum to 1 at the maximum."),
    (r"\bcent(?:er|re)d? (?:around|on|at) zero\b|\bboth (?:up and down|ways|directions)\b|\bpositive and negative\b",
     "noise() returns values from about 0 to 1; 'centred around zero' or 'both up and down' means subtracting "
     "0.5 (noise(...) - 0.5) before scaling."),
    (r"\b(?:along|way along|up) the (?:curve|strand|hair|line|wire)\b|\broot\b|\btip\b",
     "Position along a curve, strand or hair: u = the point's vertex index in its primitive divided by (number "
     "of vertices - 1), 0 at the root (first point) and 1 at the tip (last point); vertexprimindex(0, "
     "pointvertex(0, @ptnum)) and primvertexcount(0, prim) give them."),
    (r"\baway from\b|\boutwards? from\b|\bpointing (?:straight )?out\b",
     "'Away from X' or 'outward from X' is the direction normalize(@P - X)."),
    (r"\btowards?\b",
     "'Towards X' is the direction normalize(X - @P)."),
    (r"\b(?:from above|top[- ]down|looking down|ignor\w* (?:the )?height|height doesn'?t matter|in the ground plane|flat on the ground)\b",
     "Seen from above / ignoring height: use only X and Z, e.g. set(@P.x, 0, @P.z) or the distance of those "
     "components."),
    (r"\b(?:label|tag|name) (?:each|every|the)\b|\bnamed?\b",
     "A name or label is the string attribute s@name unless another attribute name is given."),
    (r"\bselect\b|\bgroup (?:called|named)\b|\bput (?:them|it|those) in a group\b",
     "Selecting into a group called G: @group_G = 1 (or setpointgroup / setprimgroup) for the elements that "
     "qualify."),
    (r"\b(?:delete|remove|get rid of|kill|cull)\b",
     "Deleting the current element: removepoint(0, @ptnum) or removeprim(0, @primnum, 1)."),
    (r"\bhow fast\b|\bspeed of\b|\bby speed\b|\btheir speed\b",
     "How fast a point moves is length(v@v); velocity is the vector attribute v@v."),
    (r"\b(?:2nd|second) input\b|\bplugged into\b|\bother input\b",
     "The second input of the wrangle is input 1 (the first is input 0): point(1, ...), nearpoint(1, @P), "
     "xyzdist(1, @P, prim, uv)."),
    (r"\bevery (?:other|second|third|\d+(?:st|nd|rd|th)|nth)\b",
     "'Every n-th' element: @ptnum % n == 0 (or @primnum for primitives)."),
    (r"\bhow many\b|\bcount\b|\bin total\b|\badd up\b|\bsum\b|\baverage\b|\bmean\b",
     "A count, total or average over the whole geometry is usually computed once in a detail wrangle and stored "
     "as a detail attribute (i@ / f@ on the detail)."),
    (r"\bover time\b|\banimat\w*\b|\bmoves?\b.*\btime\b",
     "Animation over time uses @Time (seconds) or @Frame."),
]
_COMPILED = [(re.compile(p), n) for p, n in NOTES]


def enabled():
    return os.environ.get("AI_WRANGLE_WORDING_NOTES", "0") == "1"


def notes_for(task, limit=4):
    """Notes for the phrases that occur in the request, in list order, at most `limit`."""
    t = " ".join((task or "").lower().split())
    out = []
    for rx, note in _COMPILED:
        if rx.search(t) and note not in out:
            out.append(note)
            if len(out) >= limit:
                break
    return out


def block(task):
    notes = notes_for(task)
    if not notes:
        return ""
    return "Wording notes (what the words of this request mean in Houdini):\n" + "\n".join("- " + n for n in notes)
