"""
=============================================================================
 In-Houdini 1-Click Drag-and-Drop Installer for AI Attribute Wrangle
 Drag and drop this file into Houdini or run via: File -> Run Script
=============================================================================
"""

import json
import os
import shutil
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
            {
                "PYTHONPATH": {
                    "method": "prepend",
                    "value": f"{fwd_root}/python"
                }
            },
            {"AI_WRANGLE_ROOT": fwd_root},
            {
                "PATH": {
                    "method": "prepend",
                    "value": f"{fwd_root}/bin"
                }
            }
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

    # Check inference engine binary status
    bin_path = plugin_root / "bin" / "llama-server.exe"
    winget_engine = Path(os.path.expanduser(
        r"~\AppData\Local\Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-server.exe"
    ))
    has_bin = bin_path.exists() or winget_engine.exists() or (shutil.which("llama-server.exe") is not None)
    if has_bin:
        engine_status = "llama-server.exe (Installed ✅)"
    else:
        engine_status = (
            "Not Found ⚠️\n"
            "   -> Fix: Open PowerShell and run: winget install ggml.llamacpp\n"
            "   -> Or place 'llama-server.exe' inside 'bin/'"
        )

    # Check model weights status
    model_candidates = [
        plugin_root / "models" / "Qwen3-8B-Houdini-VEX-v11-Q5_K_M.gguf",
        plugin_root / "models" / "Qwen3-8B-Houdini-VEX-v11-Q8_0.gguf",
        plugin_root / "models" / "Qwen3-8B-Houdini-VEX-v10-Q5_K_M.gguf",
        plugin_root / "models" / "Qwen3-8B-Q5_K_M.gguf",
        plugin_root / "models" / "qwen3-vex.gguf",
    ]
    found_model = next((m for m in model_candidates if m.exists()), None)
    if found_model:
        model_status = f"{found_model.name} (Installed ✅)"
    else:
        model_status = (
            "Not Found ⚠️\n"
            "   -> Place 'Qwen3-8B-Houdini-VEX-v11-Q5_K_M.gguf' into 'models/'"
        )

    msg = (
        "🎉 AI Attribute Wrangle Installed Successfully!\n\n"
        f"• Package Definition: {json_path}\n"
        f"• Live HDA Loaded: {'YES ✅' if hda_installed else 'Restart Required'}\n"
        f"• AI Engine: {engine_status}\n"
        f"• AI Model: {model_status}\n"
        "• Edition: Free Community Edition (No License Required ✅)\n\n"
        "You can now create an 'AI Attribute Wrangle' node in any /obj/geo network!"
    )

    if hou.isUIAvailable():
        hou.ui.displayMessage(msg, title="AI Attribute Wrangle Installer", severity=hou.severityType.Message)
    else:
        print(msg)


if __name__ == "__main__":
    main()
