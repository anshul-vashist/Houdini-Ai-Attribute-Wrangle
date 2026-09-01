"""
=============================================================================
 In-Houdini 1-Click Drag-and-Drop Installer for AI Attribute Wrangle
 Drag and drop this file into Houdini or run via: File -> Run Script
=============================================================================
"""

import json
import os
import sys
from pathlib import Path

try:
    import hou
except ImportError:
    print("This script is designed to be run inside SideFX Houdini.")
    sys.exit(1)


def get_plugin_root() -> Path:
    # If run directly from plugin directory
    script_dir = Path(__file__).resolve().parent
    if (script_dir / "otls").exists() or (script_dir / "python").exists():
        return script_dir
    if (script_dir.parent / "otls").exists():
        return script_dir.parent
    # Fallback to AI_WRANGLE_ROOT or current directory
    env_root = os.getenv("AI_WRANGLE_ROOT")
    if env_root:
        return Path(env_root)
    return script_dir


def main():
    plugin_root = get_plugin_root()
    pref_dir = Path(hou.homeHoudiniDirectory())
    packages_dir = pref_dir / "packages"
    packages_dir.mkdir(parents=True, exist_ok=True)
    json_path = packages_dir / "ai_attribwrangle.json"

    fwd_root = plugin_root.as_posix()
    package_def = {
        "hpath": fwd_root,
        "env": [
            {"PYTHONPATH": f"{fwd_root}/python;$PYTHONPATH"},
            {"PATH": f"{fwd_root}/bin;$PATH"},
            {"AI_WRANGLE_ROOT": fwd_root},
        ]
    }

    json_path.write_text(json.dumps(package_def, indent=2) + "\n", encoding="utf-8")

    # Add python directory to sys.path immediately for live session
    python_dir = str(plugin_root / "python")
    if python_dir not in sys.path:
        sys.path.insert(0, python_dir)

    # Install HDA dynamically in current session
    hda_path = plugin_root / "otls" / "ai_attribwrangle.hda"
    hda_installed = False
    if hda_path.exists():
        try:
            hou.hda.installFile(str(hda_path), force_use_assets=True)
            hda_installed = True
        except Exception as e:
            print(f"Could not live-install HDA: {e}")

    # Check license & Machine ID
    mid = "UNKNOWN"
    try:
        import license_validator
        mid = license_validator.MachineFingerprint.generate_machine_id()
    except Exception:
        pass

    lic_path = plugin_root / "license" / "ai_wrangle.lic"
    lic_status = "No license found"
    if lic_path.exists():
        lic_status = "Active & Installed ✅"

    msg = (
        "🎉 AI Attribute Wrangle Installed Successfully!\n\n"
        f"• Package Definition: {json_path}\n"
        f"• Live HDA Loaded: {'YES ✅' if hda_installed else 'Restart Required'}\n"
        f"• Machine ID: {mid}\n"
        f"• License Status: {lic_status}\n\n"
        "You can now create an 'AI Attribute Wrangle' node in any /obj/geo network!"
    )

    if hou.isUIAvailable():
        hou.ui.displayMessage(msg, title="AI Attribute Wrangle Installer", severity=hou.severityType.Message)
    else:
        print(msg)


if __name__ == "__main__":
    main()
