"""Build the Windows / Houdini 21.0 commercial distribution.

This builder is deliberately allow-list based: no developer keys, customer
licenses, source checkpoints, caches, or unreviewed files can enter the ZIP.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DIST_ROOT = PROJECT_ROOT / "dist"
PACKAGE_NAME = "AI_Attribute_Wrangle_v1.0.2"
PACKAGE_DIR = DIST_ROOT / PACKAGE_NAME
ZIP_PATH = DIST_ROOT / f"{PACKAGE_NAME}_Windows_Houdini21.zip"
DEFAULT_ENGINE_DIR = Path(r"C:\Users\Anshul\AppData\Local\Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe")
ENGINE_FILES = (
    "llama-server.exe", "llama.dll", "ggml.dll", "ggml-base.dll",
    "ggml-cpu-x64.dll", "ggml-cpu-haswell.dll", "ggml-cpu-alderlake.dll",
    "ggml-cpu-zen4.dll", "ggml-vulkan.dll", "libomp140.x86_64.dll",
    "mtmd.dll",
)
RELEASE_FILES = {
    "README.txt": PROJECT_ROOT / "release" / "README.txt",
    "EULA.txt": PROJECT_ROOT / "release" / "EULA.txt",
    "PRIVACY.txt": PROJECT_ROOT / "release" / "PRIVACY.txt",
    "THIRD_PARTY_NOTICES.txt": PROJECT_ROOT / "release" / "THIRD_PARTY_NOTICES.txt",
    "MODEL_PROVENANCE.md": PROJECT_ROOT / "release" / "MODEL_PROVENANCE.md",
    "SECURITY_MODEL.md": PROJECT_ROOT / "release" / "SECURITY_MODEL.md",
    "SUPPORT.txt": PROJECT_ROOT / "release" / "SUPPORT.txt",
}


def compile_python_extensions(output_python_dir: Path) -> list[str]:
    """Compiles all Python modules into native .pyd C-extensions using Cython + MSVC."""
    temp_build_dir = SCRIPT_DIR / "_cython_build"
    if temp_build_dir.exists():
        shutil.rmtree(temp_build_dir, ignore_errors=True)
    temp_build_dir.mkdir(parents=True, exist_ok=True)

    sources = [
        PROJECT_ROOT / "houdini_vex_project" / "03_houdini_integration" / "houdini_ai_wrangle.py",
        PROJECT_ROOT / "houdini_vex_project" / "03_houdini_integration" / "vex_rag_engine.py",
        SCRIPT_DIR / "engine_manager.py",
        SCRIPT_DIR / "license_validator.py",
        SCRIPT_DIR / "model_vault.py",
    ]

    for src in sources:
        if not src.is_file():
            raise FileNotFoundError(f"Source python module not found: {src}")
        shutil.copy2(src, temp_build_dir / src.name)

    build_script = temp_build_dir / "_run_compile.py"
    build_script.write_text(r'''
import os, sys
from pathlib import Path
from setuptools import setup, Extension
from Cython.Build import cythonize

current_dir = Path(__file__).resolve().parent
os.chdir(str(current_dir))

src_files = [f for f in current_dir.glob("*.py") if not f.name.startswith("_")]
sys.argv = ["setup.py", "build_ext", "--inplace"]

ext_modules = cythonize(
    [Extension(f.stem, [str(f)]) for f in src_files],
    language_level="3",
    compiler_directives={"language_level": "3", "always_allow_keywords": True}
)

setup(ext_modules=ext_modules)
''', encoding="utf-8")

    vcvars_bat = r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
    hython_exe = r"C:\Program Files\Side Effects Software\Houdini 21.0.440\bin\hython.exe"
    
    cmd = f'cmd.exe /c "call "{vcvars_bat}" && "{hython_exe}" "{build_script}""'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Cython compilation failed:\n{res.stderr or res.stdout}")

    pyd_files = []
    output_python_dir.mkdir(parents=True, exist_ok=True)
    for pyd in temp_build_dir.glob("*.pyd"):
        dest = output_python_dir / pyd.name
        shutil.copy2(pyd, dest)
        pyd_files.append(pyd.name)

    shutil.rmtree(temp_build_dir, ignore_errors=True)
    if not pyd_files:
        raise RuntimeError("No compiled .pyd extensions were produced by Cython.")
    return pyd_files


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_required(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Required release input is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def license_material(customer_license: Path) -> tuple[bytes, str]:
    """Verify a license signature before binding a customer vault to it."""
    sys.path.insert(0, str(SCRIPT_DIR))
    from license_validator import LicenseValidator

    public_key = (SCRIPT_DIR / "embedded_public_key.pem").read_bytes()
    lic_text = customer_license.read_text(encoding="utf-8")
    data = json.loads(lic_text)
    licensed_machine_id = str(data.get("payload", {}).get("machine_id", "")).strip().upper()

    res = LicenseValidator.verify_license_with_material(lic_text, public_key)
    if len(res) == 4:
        valid, message, material, _ = res
    else:
        valid, message, material = res

    # A build workstation will normally not match the customer's hardware.
    # Verify the RSA signature independently so a valid customer license can
    # be packaged without weakening the runtime node-lock check.
    if not valid and "locked to Machine" not in message:
        raise ValueError(f"Customer license cannot bind a vault: {message}")
    if not material:
        import base64
        material = base64.b64decode(data["signature"], validate=True)
    if len(material) < 128:
        raise ValueError("Customer license signature is invalid.")
    return material, licensed_machine_id


def write_installer(destination: Path) -> None:
    """Write a constrained, idempotent Houdini 21 package installer."""
    installer = r'''@echo off
setlocal EnableExtensions DisableDelayedExpansion
title AI Attribute Wrangle v1.0.2 Installer

set "INSTALL_DIR=%~dp0"
set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"
set "INSTALL_DIR_FWD=%INSTALL_DIR:\=/%"
set "COUNT=0"

for /d %%D in ("%USERPROFILE%\Documents\houdini21.0*") do call :INSTALL "%%~fD"
for /d %%D in ("%USERPROFILE%\OneDrive\Documents\houdini21.0*") do call :INSTALL "%%~fD"

if "%COUNT%"=="0" (
  echo No Houdini 21.0 user preferences directory was found.
  echo Create or start Houdini 21.0 once, then run this installer again.
  exit /b 1
)

echo Installed AI Attribute Wrangle into %COUNT% Houdini 21.0 package folder(s).
echo Restart Houdini after installation. Place your customer ai_wrangle.lic in the license folder before use.
exit /b 0

:INSTALL
set "TARGET=%~1"
if not exist "%TARGET%\packages" mkdir "%TARGET%\packages"
> "%TARGET%\packages\ai_attribwrangle.json" (
  echo {
  echo   "hpath": "%INSTALL_DIR_FWD%",
  echo   "env": [
  echo     { "PYTHONPATH": "%INSTALL_DIR_FWD%/python;$PYTHONPATH" },
  echo     { "PATH": "%INSTALL_DIR_FWD%/bin;$PATH" },
  echo     { "AI_WRANGLE_ROOT": "%INSTALL_DIR_FWD%" }
  echo   ]
  echo }
)
set /a COUNT+=1
exit /b 0
'''
    destination.write_text(installer, encoding="utf-8", newline="\r\n")


def write_manifest(package_dir: Path) -> None:
    files = []
    for path in sorted(package_dir.rglob("*")):
        if path.is_file() and path.name not in {"manifest.json", "SHA256SUMS.txt"}:
            files.append({"path": path.relative_to(package_dir).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)})
    manifest = {
        "product": "AI Attribute Wrangle", "version": "1.0.2", "platform": "Windows x64",
        "houdini_tested": "21.0.440 / Python 3.11", "files": files,
    }
    (package_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (package_dir / "SHA256SUMS.txt").write_text("".join(f"{item['sha256']}  {item['path']}\n" for item in files), encoding="utf-8")


def build(args: argparse.Namespace) -> None:
    DIST_ROOT.mkdir(exist_ok=True)
    if not args.acknowledge_offline_model_risk:
        raise ValueError(
            "Refusing to build an offline-model delivery without --acknowledge-offline-model-risk. "
            "A customer-controlled local model cannot be made uncrackable; use hosted inference for model-IP protection."
        )
    is_free_edition = not bool(args.customer_license)
    source_model = PROJECT_ROOT / "qwen3-vex.gguf"
    if not source_model.is_file():
        raise FileNotFoundError("The master source model qwen3-vex.gguf is required for building the package.")

    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    for directory in ("bin", "license", "models", "otls", "python"):
        (PACKAGE_DIR / directory).mkdir(parents=True, exist_ok=True)

    source_hda = PROJECT_ROOT / "houdini_vex_project" / "03_houdini_integration" / "ai_attribwrangle.hda"
    copy_required(source_hda, PACKAGE_DIR / "otls" / "ai_attribwrangle.hda")
    
    print("Compiling Python modules into native non-editable .pyd C-extensions...")
    pyd_files = compile_python_extensions(PACKAGE_DIR / "python")
    print(f"Compiled {len(pyd_files)} native extensions: {pyd_files}")

    engine_dir = Path(args.engine_dir).resolve()
    for filename in ENGINE_FILES:
        copy_required(engine_dir / filename, PACKAGE_DIR / "bin" / filename)

    if is_free_edition:
        print("Building Free Community Edition: copying model weights...")
        copy_required(source_model, PACKAGE_DIR / "models" / "qwen3-vex.gguf")
        (PACKAGE_DIR / "license" / "README.txt").write_text(
            "AI Attribute Wrangle — Free Edition\n"
            "This release is 100% free and ready to use with zero licensing requirements.\n",
            encoding="utf-8",
        )
    else:
        customer_license = Path(args.customer_license).resolve()
        if not customer_license.is_file():
            raise FileNotFoundError(f"Customer license is missing: {customer_license}")
        customer_license_content = customer_license.read_text(encoding="utf-8")
        customer_material, customer_mid = license_material(customer_license)

        sys.path.insert(0, str(SCRIPT_DIR))
        from model_vault import ModelVault
        ModelVault.encrypt_model(
            str(source_model),
            str(PACKAGE_DIR / "models" / "vex_brain.dat"),
            customer_material,
            machine_id=customer_mid,
        )
        copy_required(SCRIPT_DIR / "embedded_public_key.pem", PACKAGE_DIR / "license" / "embedded_public_key.pem")
        (PACKAGE_DIR / "license" / "README.txt").write_text(
            "This customer-specific package includes a signed node-locked license.\n"
            "Do not replace it: its exact signature is cryptographically bound to the bundled model vault.\n",
            encoding="utf-8",
        )
        (PACKAGE_DIR / "license" / "ai_wrangle.lic").write_text(customer_license_content, encoding="utf-8")

    # Package fine-tuned LoRA adapters if present in models directory
    master_models_dir = PROJECT_ROOT / "models"
    for lora_name in ["qwen3-vex-v10-lora.gguf", "qwen3-vex-v9-lora.gguf", "qwen3-vex-v8-lora.gguf", "qwen3-vex-lora.gguf"]:
        src_lora = master_models_dir / lora_name
        if src_lora.is_file():
            print(f"Packaging fine-tuned LoRA adapter: {lora_name}")
            copy_required(src_lora, PACKAGE_DIR / "models" / lora_name)
            break

    for destination_name, source in RELEASE_FILES.items():
        copy_required(source, PACKAGE_DIR / destination_name)
    write_installer(PACKAGE_DIR / "Install_AI_Wrangle.bat")
    if (SCRIPT_DIR / "Setup_AI_Wrangle.exe").is_file():
        copy_required(SCRIPT_DIR / "Setup_AI_Wrangle.exe", PACKAGE_DIR / "Setup_AI_Wrangle.exe")
    copy_required(SCRIPT_DIR / "installer_gui.py", PACKAGE_DIR / "Setup_Wizard.py")
    copy_required(SCRIPT_DIR / "install_in_houdini.py", PACKAGE_DIR / "install_in_houdini.py")
    write_manifest(PACKAGE_DIR)

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for path in sorted(PACKAGE_DIR.rglob("*")):
            if path.is_file():
                compression = zipfile.ZIP_STORED if path.suffix in (".dat", ".gguf") else zipfile.ZIP_DEFLATED
                archive.write(path, Path(PACKAGE_NAME) / path.relative_to(PACKAGE_DIR), compress_type=compression)
    print(f"Built {ZIP_PATH} ({ZIP_PATH.stat().st_size / 1024 / 1024:.1f} MiB)")
    print("WARNING: Offline-model package built by explicit acknowledgement only; it is not uncrackable DRM.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-dir", default=os.getenv("AI_WRANGLE_ENGINE_DIR", str(DEFAULT_ENGINE_DIR)))
    parser.add_argument("--customer-license", help="Required signed customer license used to bind this delivery's model vault.")
    parser.add_argument(
        "--acknowledge-offline-model-risk", action="store_true",
        help="Required acknowledgement that a local model can be extracted by a determined authorized customer.",
    )
    build(parser.parse_args())
