"""Verify an allow-listed release package before upload or delivery."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path


REQUIRED = {
    "Install_AI_Wrangle.bat", "Setup_Wizard.py", "install_in_houdini.py",
    "README.txt", "EULA.txt", "PRIVACY.txt",
    "THIRD_PARTY_NOTICES.txt", "MODEL_PROVENANCE.md", "SECURITY_MODEL.md", "SUPPORT.txt", "manifest.json", "SHA256SUMS.txt",
    "otls/ai_attribwrangle.hda",
    "license/README.txt",
    "python/houdini_ai_wrangle.cp311-win_amd64.pyd", "python/engine_manager.cp311-win_amd64.pyd",
    "python/license_validator.cp311-win_amd64.pyd", "python/model_vault.cp311-win_amd64.pyd", "python/vex_rag_engine.cp311-win_amd64.pyd",
}
FORBIDDEN_PARTS = (
    "developer_tools/", "__pycache__/", ".pyc", "private_key", "adapter_model", ".safetensors",
    "vex_grandmaster_core_key", "_internal_vault_seed",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_package(package: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = package / "manifest.json"
    if not manifest_path.is_file():
        return ["manifest.json is missing"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    listed = {entry["path"]: entry for entry in manifest.get("files", [])}
    actual = {path.relative_to(package).as_posix() for path in package.rglob("*") if path.is_file()}
    missing = REQUIRED - actual
    if missing:
        errors.append(f"Required files missing: {sorted(missing)}")
    if "models/qwen3-vex.gguf" not in actual and "models/vex_brain.dat" not in actual:
        errors.append("Model weights file (models/qwen3-vex.gguf or models/vex_brain.dat) is missing.")
    forbidden = [
        name for name in actual
        if any(part.lower() in name.lower() for part in FORBIDDEN_PARTS)
        or (name.startswith("python/") and name.endswith(".py"))
    ]
    if forbidden:
        errors.append(f"Forbidden release files: {sorted(forbidden)}")
    for rel, entry in listed.items():
        target = package / rel
        if not target.is_file():
            errors.append(f"Manifest lists missing file: {rel}")
        elif sha256(target) != entry["sha256"]:
            errors.append(f"Hash mismatch: {rel}")
    vault = package / "models" / "vex_brain.dat"
    if vault.is_file():
        with vault.open("rb") as stream:
            vault_magic = stream.read(9)
        if vault_magic not in (b"VEXVAULT\x03", b"VEXVAULT\x02"):
            errors.append("Model vault is not the customer-bound v2/v3 format.")
    return errors


def validate_hda(hython: Path, hda: Path) -> list[str]:
    script = (
        "import hou; "
        f"p=r'{hda}'; hou.hda.installFile(p, force_use_assets=True); "
        "d=hou.hda.definitionsInFile(p)[0]; "
        "names={x.name() for x in d.parmTemplateGroup().entriesWithoutFolders()}; "
        "required={'ai_status','ai_perf','ai_history_json','ai_version_info','ai_thought_trace'}; "
        "missing=required-names; print('MISSING='+','.join(sorted(missing))); "
        "print('TYPE='+d.nodeTypeName())"
    )
    result = subprocess.run([str(hython), "-c", script], capture_output=True, text=True, check=False)
    if result.returncode:
        return [f"HDA validation failed: {result.stderr or result.stdout}"]
    if "MISSING=" not in result.stdout or "MISSING=\n" not in result.stdout:
        return [f"HDA parameter contract failed: {result.stdout.strip()}"]
    if "TYPE=ai_attribwrangle" not in result.stdout:
        return [f"Unexpected HDA node type: {result.stdout.strip()}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--zip", dest="zip_path", type=Path)
    parser.add_argument("--hython", type=Path)
    parser.add_argument(
        "--require-hosted-inference", action="store_true",
        help="Fail if this package contains a local model or local llama runtime; use for IP-protected commercial release gating.",
    )
    args = parser.parse_args()
    errors = validate_package(args.package)
    if args.zip_path:
        with zipfile.ZipFile(args.zip_path) as archive:
            bad = archive.testzip()
            if bad:
                errors.append(f"ZIP CRC failure: {bad}")
    if args.hython:
        errors.extend(validate_hda(args.hython, args.package / "otls" / "ai_attribwrangle.hda"))
    if args.require_hosted_inference:
        local_model = args.package / "models" / "vex_brain.dat"
        local_engine = args.package / "bin" / "llama-server.exe"
        if local_model.exists() or local_engine.exists():
            errors.append(
                "Hosted-inference gate failed: the package ships model/runtime assets to a customer-controlled machine. "
                "It cannot be certified as uncrackable."
            )
    if errors:
        print("RELEASE VERIFICATION FAILED")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("RELEASE VERIFICATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
