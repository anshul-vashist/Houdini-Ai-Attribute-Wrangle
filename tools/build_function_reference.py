"""
Rebuild data/vex_function_reference.json from the help of the local Houdini installation.

    hython tools/build_function_reference.py              (uses $HFS)
    python tools/build_function_reference.py [HFS]        (plain Python: newest installed Houdini, or the given one)

The plugin builds this file by itself the first time the function lookup needs it (python/vex_function_reference.py
has the details and the entry format); run this after a Houdini upgrade, or to see the statistics. The file is not
part of the repository: it holds text from the SideFX documentation.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "python"))

import vex_function_reference as reference  # noqa: E402


def main():
    hfs = reference.find_hfs(sys.argv[1] if len(sys.argv) > 1 else None)
    if not hfs:
        sys.exit("No Houdini installation with houdini/help/vex.zip found: run with hython, set HFS, or pass the "
                 "installation folder.")
    ref = reference.build(ROOT, hfs)
    out = reference.reference_path(ROOT)
    reference.write(ref, out)
    no_usage = sum(1 for e in ref.values() if not e["usage"])
    print(f"{len(ref)} functions from {hfs} -> {out} ({os.path.getsize(out) / 1024:.0f} KB); "
          f"{no_usage} without a usage line")


if __name__ == "__main__":
    main()
