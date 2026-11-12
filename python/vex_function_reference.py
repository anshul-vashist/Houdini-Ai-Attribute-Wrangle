"""
Function reference for the function lookup (vex_function_index): one compact entry per VEX function

    {"summary": one line, "usage": [signatures with argument names], "context": "all" | "...", "tags": [...],
     "group": "...", "overloads": number of compiler signatures}

taken from the help that ships with the local Houdini installation ($HFS/houdini/help/vex.zip) and limited to the
functions the compiler knows in the CVEX context (data/vex_signatures_vcc.json, made with `vcc -X cvex`; wrangles
run CVEX).

The reference is not part of the repository: its summaries are text from the SideFX documentation, and it should
describe the Houdini version in use. It is built from the local help the first time the lookup needs it (a
fraction of a second) and stored as data/vex_function_reference.json. If that folder cannot be written the
reference lives in memory for the session; if the Houdini help is not installed the lookup offers nothing and the
rest of the plugin works as before.

    ensure(root)            the stored reference, built first when it is missing
    build(root, hfs=None)   build from the help; nothing is written
    python tools/build_function_reference.py     rebuild the stored file by hand, e.g. after a Houdini upgrade

AI_WRANGLE_BUILD_REFERENCE=0 switches the automatic build off.

The help writes signatures in several styles; they are normalised so that a model does not copy help markup into
code: `<geometry>` becomes `int geometry`, parameters are separated by commas (the help often uses the declaration
style with semicolons), `const` is dropped, `int []` becomes `int[]`. `<type>` (any attribute type) is kept: it is
how the reference marks functions whose return type follows the variable they are assigned to.

Pure Python (no hou, no numpy).
"""
import glob
import json
import os
import re
import zipfile

FILE_NAME = "vex_function_reference.json"


def reference_path(root):
    return os.path.join(root, "data", FILE_NAME)


def _help_zip(hfs):
    return os.path.join(hfs, "houdini", "help", "vex.zip")


def find_hfs(hfs=None):
    """The Houdini installation whose help is read: the argument, else $HFS (always set inside Houdini and
    hython), else - for scripts started with a plain Python on Windows - the newest installed version that has
    the help. None when there is none."""
    if hfs:
        return hfs if os.path.isfile(_help_zip(hfs)) else None
    env = os.environ.get("HFS")
    if env:
        return env if os.path.isfile(_help_zip(env)) else None
    found = []
    for d in glob.glob(os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                                    "Side Effects Software", "Houdini *")):
        m = re.search(r"Houdini (\d+)\.(\d+)\.(\d+)", os.path.basename(d))
        if m and os.path.isfile(_help_zip(d)):
            found.append((tuple(int(g) for g in m.groups()), d))
    return max(found)[1] if found else None


def clean_usage(u):
    u = u.strip().strip("`").strip()
    u = re.sub(r"<geometry>\s*(?:geometry)?", "int geometry", u)
    u = re.sub(r"\bconst\s+", "", u)
    u = re.sub(r"\s+", " ", u)
    m = re.match(r"^(.*?\()(.*)(\).*)$", u)
    if m:  # parameter list: commas between parameters, no padding inside the parentheses
        params = re.sub(r"\s*;\s*", ", ", m.group(2)).strip()
        params = re.sub(r"\s*,\s*", ", ", params)
        u = m.group(1).rstrip() + params + m.group(3)
    u = re.sub(r"(\w)\s+\[\]", r"\1[]", u)
    u = re.sub(r"\(\s+", "(", u)
    u = re.sub(r"\s+\)", ")", u)
    return u


def build(root, hfs=None):
    """{function: entry} from the local Houdini help. Raises when the help or the compiler's signature list is
    not there."""
    hfs = find_hfs(hfs)
    if not hfs:
        raise FileNotFoundError("no Houdini installation with houdini/help/vex.zip found (is $HFS set?)")
    with open(os.path.join(root, "data", "vex_signatures_vcc.json"), encoding="utf-8") as f:
        vcc = json.load(f)
    ref = {}
    with zipfile.ZipFile(_help_zip(hfs)) as z:
        for name in sorted(z.namelist()):
            m = re.fullmatch(r"functions/(\w+)\.txt", name)
            if not m or m.group(1) not in vcc:
                continue
            fn = m.group(1)
            text = z.read(name).decode("utf-8", "replace")
            summary = re.search(r'"""(.*?)"""', text, re.S)

            def head(key, text=text):
                found = re.search(rf"^#{key}:\s*(.*)$", text, re.M)
                return found.group(1).strip() if found else ""

            usage = []
            for u in re.findall(r"^:usage:\s*`([^`]+)`", text, re.M):
                u = clean_usage(u)
                if u and u not in usage and fn in u and u.count("(") == u.count(")"):
                    usage.append(u)
            ref[fn] = dict(summary=re.sub(r"\s+", " ", summary.group(1)).strip() if summary else "",
                           usage=usage[:8], context=head("context") or "all",
                           tags=[t.strip() for t in head("tags").split(",") if t.strip()], group=head("group"),
                           overloads=len(vcc[fn]))
    return ref


def write(ref, path):
    """Store the reference; the file appears complete or not at all (two Houdini sessions may start together)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(ref, f, indent=0, sort_keys=True)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def ensure(root, hfs=None):
    """The function reference for this plugin folder: the stored file, else built from the local help and stored.
    Never raises: {} when there is neither a stored reference nor a Houdini help to build it from."""
    path = reference_path(root)
    try:
        with open(path, encoding="utf-8") as f:
            ref = json.load(f)
        if isinstance(ref, dict) and ref:
            return ref
    except Exception:
        pass
    if os.environ.get("AI_WRANGLE_BUILD_REFERENCE", "1") == "0":
        return {}
    try:
        ref = build(root, hfs)
    except Exception:
        return {}
    if ref:
        try:
            write(ref, path)
        except Exception:
            pass  # read-only installation: the reference is rebuilt in memory each session
    return ref
