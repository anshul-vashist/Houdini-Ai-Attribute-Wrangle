"""Lifecycle manager for the customer-bound local inference sidecar."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


DEFAULT_PORT = 58421
DEFAULT_HOST = "127.0.0.1"
_STAGING_ROOT = os.path.join(tempfile.gettempdir(), "ai_wrangle_runtime")


def get_recommended_gpu_layers(model_size_gb: float = 8.3) -> int:
    """Dynamically detects available GPU VRAM to prevent OutOfDeviceMemory crashes."""
    override = os.getenv("AI_WRANGLE_GPU_LAYERS")
    if override is not None:
        try:
            return int(override)
        except ValueError:
            pass
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,nounits,noheader"],
            text=True, stderr=subprocess.DEVNULL, timeout=2.0
        ).strip()
        free_vram_mb = int(out.splitlines()[0])
        # Model has ~36 transformer layers; estimate per-layer VRAM requirements:
        layer_size_mb = max(100, int((model_size_gb * 1024) / 36))
        # Keep 1.2 GB safe headroom for Houdini OpenGL/Vulkan viewport, UI, and OS compositor
        safe_vram_budget = max(0, free_vram_mb - 1200)
        max_layers = min(36, safe_vram_budget // layer_size_mb)
        return max(0, max_layers)
    except Exception:
        # Safe default fallback for systems without nvidia-smi or CPU-only workflows
        return 12


class EngineManager:
    """Starts llama-server for local Houdini inference with zero persistent disk cache."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.api_key = None
        self.process = None
        self._staging_dir = None
        self._staging_model_path = None
        self.last_error = ""

    def get_api_key(self) -> str | None:
        return self.api_key

    def is_port_open(self, timeout: float = 0.5) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            return sock.connect_ex((self.host, self.port)) == 0
        except OSError:
            return False
        finally:
            sock.close()

    def is_healthy(self) -> bool:
        if not self.is_port_open():
            return False
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            request = urllib.request.Request(f"{self.base_url}/health", headers=headers)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=1.0) as response:
                return json.loads(response.read().decode("utf-8")).get("status") == "ok"
        except urllib.error.HTTPError:
            return False
        except Exception:
            return False

    @staticmethod
    def _package_root(vault_model_path: str) -> str:
        return os.environ.get("AI_WRANGLE_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(vault_model_path)))

    def _verified_license_material(self, vault_model_path: str) -> tuple[bytes, str]:
        try:
            from license_validator import LicenseValidator, MachineFingerprint
        except ImportError:
            from .license_validator import LicenseValidator, MachineFingerprint

        package_root = self._package_root(vault_model_path)
        license_path = os.path.join(package_root, "license", "ai_wrangle.lic")
        public_key_path = os.path.join(package_root, "license", "embedded_public_key.pem")
        if not os.path.isfile(license_path) or not os.path.isfile(public_key_path):
            raise RuntimeError("A customer license is required before the model vault can be opened.")
        with open(license_path, "r", encoding="utf-8") as stream:
            license_json = stream.read()
        with open(public_key_path, "rb") as stream:
            public_key = stream.read()
        res = LicenseValidator.verify_license_with_material(license_json, public_key)
        if len(res) == 4:
            valid, message, material, licensed_mid = res
        else:
            valid, message, material = res
            licensed_mid = json.loads(license_json).get("payload", {}).get("machine_id", "")
        if not valid:
            raise RuntimeError(f"Customer license rejected: {message}")
        current_mid = MachineFingerprint.generate_machine_id()
        effective_mid = "*" if licensed_mid == "*" else current_mid
        return material, effective_mid

    def _resolve_model_path(self, model_path: str) -> str:
        if not model_path.endswith(".dat"):
            return model_path
        try:
            from model_vault import ModelVault
        except ImportError:
            from .model_vault import ModelVault

        self.cleanup_cache()
        os.makedirs(_STAGING_ROOT, exist_ok=True)
        self._staging_dir = tempfile.mkdtemp(prefix="aw-", dir=_STAGING_ROOT)
        self._staging_model_path = os.path.join(self._staging_dir, f"{secrets.token_hex(16)}.gguf")
        try:
            material, effective_mid = self._verified_license_material(model_path)
            with open(self._staging_model_path, "xb") as output_stream:
                ModelVault.decrypt_stream(model_path, output_stream, material, machine_id=effective_mid)
            return self._staging_model_path
        except Exception:
            self.cleanup_cache()
            raise

    def start_embedded_engine(self, engine_bin_path: str, vault_model_path: str) -> bool:
        self.last_error = ""
        if self.is_healthy():
            return True
        if not os.path.isfile(engine_bin_path):
            self.last_error = f"Engine executable not found: {engine_bin_path}"
            return False
        try:
            resolved_model_path = self._resolve_model_path(vault_model_path)
        except Exception as error:
            self.last_error = str(error)
            return False

        gpu_layers = str(get_recommended_gpu_layers())
        command = [
            engine_bin_path, "--model", resolved_model_path, "--port", str(self.port),
            "--host", self.host, "--ctx-size", "2048", "--n-gpu-layers",
            gpu_layers,
        ]
        if resolved_model_path.endswith(".dat"):
            command.append("--no-mmap")
        if self.api_key:
            command.extend(["--api-key", self.api_key])
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.process = subprocess.Popen(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags
            )
            for _ in range(180):
                time.sleep(0.5)
                if self.is_healthy():
                    # --no-mmap makes llama load the model into process memory; remove the
                    # staging artifact as soon as load has completed.
                    self.cleanup_cache()
                    return True
                if self.process.poll() is not None:
                    self.last_error = f"Engine exited during startup with exit code {self.process.returncode}."
                    self.cleanup_cache()
                    return False
            self.last_error = "Timed out waiting for the AI engine to load the model."
            self.stop_engine()
            return False
        except Exception as error:
            self.last_error = f"Could not start the AI engine: {error}"
            self.cleanup_cache()
            return False

    def stop_engine(self) -> None:
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        self.cleanup_cache()

    def cleanup_cache(self) -> None:
        """Erase the short-lived staging directory; no reusable plaintext cache exists."""
        staging_dir, self._staging_dir = self._staging_dir, None
        self._staging_model_path = None
        if staging_dir:
            shutil.rmtree(staging_dir, ignore_errors=True)
