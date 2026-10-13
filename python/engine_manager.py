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


def get_working_port(preferred: int = 58421, fallback: int = 58321) -> int:
    env_port = os.getenv("AI_WRANGLE_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", preferred))
        s.close()
        return preferred
    except OSError:
        return fallback

DEFAULT_PORT = get_working_port()
DEFAULT_HOST = "127.0.0.1"
_STAGING_ROOT = os.path.join(tempfile.gettempdir(), "ai_wrangle_runtime")


def get_recommended_gpu_layers(model_size_gb: float = 5.45) -> int:
    """Dynamically detects available GPU VRAM to prevent OutOfDeviceMemory crashes."""
    override = os.getenv("AI_WRANGLE_GPU_LAYERS")
    if override is not None:
        try:
            return int(override)
        except ValueError:
            pass
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        cmd = ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,nounits,noheader"]
        if sys.platform == "win32" and not shutil.which("nvidia-smi"):
            for cand in [r"C:\Windows\System32\nvidia-smi.exe", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"]:
                if os.path.isfile(cand):
                    cmd[0] = cand
                    break
        out = subprocess.check_output(
            cmd,
            text=True, stderr=subprocess.DEVNULL, timeout=5.0,
            creationflags=creation_flags
        ).strip()
        free_vram_mb = int(out.splitlines()[0])
        # Model has ~36 transformer layers; estimate per-layer VRAM requirements:
        layer_size_mb = max(80, int((model_size_gb * 1024) / 36))
        # Keep 800 MB safe headroom for Houdini OpenGL/Vulkan viewport, UI, and OS compositor
        safe_vram_budget = max(0, free_vram_mb - 800)
        max_layers = min(36, safe_vram_budget // layer_size_mb)
        # Avoid split CPU-GPU bottleneck: if >= 28 layers fit, offload all 36
        if max_layers >= 28 or free_vram_mb >= 5200:
            return 36
        return max(0, max_layers)
    except Exception:
        # High-performance default: offload all 36 layers
        return 36


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
        self.active_model_name = ""
        self.active_lora_name = None
        self.active_gpu_layers = 0

    def get_model_info_string(self) -> str:
        if not self.active_model_name and self.is_healthy():
            try:
                headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                req = urllib.request.Request(f"{self.base_url}/v1/models", headers=headers)
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(req, timeout=1.0) as resp:
                    m_data = json.loads(resp.read().decode("utf-8"))
                    models = m_data.get("data", []) or m_data.get("models", [])
                    if models:
                        self.active_model_name = models[0].get("id") or models[0].get("name", "")
            except Exception:
                pass
        model = self.active_model_name or "qwen3-vex.gguf"
        if self.active_lora_name:
            extra = " (v11 Grandmaster)" if "v11" in self.active_lora_name else (" (v10 Grandmaster - Sept 8)" if "v10" in self.active_lora_name else "")
            return f"{model} + LoRA: {self.active_lora_name}{extra}"
        if "v42" in model:
            return f"{model} (Standalone Merged v42 Master - Organic CITL Self-Repair)"
        if "v41" in model:
            return f"{model} (Standalone Merged v41 Master - SFT-Grounded RLVR)"
        if "v39" in model:
            return f"{model} (Standalone Merged v39 Master - Bulletproof Intelligence)"
        if "v38" in model:
            return f"{model} (Standalone Merged v38 Master - Axiomatic Reasoning)"
        if "v37" in model:
            return f"{model} (Standalone Merged v37 Master)"
        if "v36" in model:
            return f"{model} (Standalone Merged v36 Master)"
        if "v35" in model:
            return f"{model} (Standalone Merged v35 Master)"
        if "v34" in model:
            return f"{model} (Standalone Merged v34 Master)"
        if "v33" in model:
            return f"{model} (Standalone Merged v33 Master)"
        if "v32" in model:
            return f"{model} (Standalone Merged v32 Master)"
        if "v31" in model:
            return f"{model} (Standalone Merged v31 Master)"
        if "v30" in model:
            return f"{model} (Standalone Merged v30 Master)"
        if "v29" in model:
            return f"{model} (Standalone Merged v29 Master)"
        if "v28" in model:
            return f"{model} (Standalone Merged v28 Master)"
        if "v27" in model:
            return f"{model} (Standalone Merged v27 Master)"
        if "v26" in model:
            return f"{model} (Standalone Merged v26 Master)"
        if "v25" in model:
            return f"{model} (Standalone Merged v25 Master)"
        if "v24" in model:
            return f"{model} (Standalone Merged v24 Master)"
        if "v23" in model:
            return f"{model} (Standalone Merged v23 Master)"
        if "v22" in model:
            return f"{model} (Standalone Merged v22 Master)"
        if "v21" in model:
            return f"{model} (Standalone Merged v21 Master)"
        if "v20" in model:
            return f"{model} (Standalone Merged v20 Master)"
        if "v19" in model:
            return f"{model} (Standalone Merged v19 Master)"
        if "v18" in model:
            return f"{model} (Standalone Merged v18 Master)"
        if "v17" in model:
            return f"{model} (Standalone Merged v17 Master)"
        if "v16" in model:
            return f"{model} (Standalone Merged v16 Master)"
        if "v15" in model:
            return f"{model} (Standalone Merged v15 Master)"
        if "v14" in model:
            return f"{model} (Standalone Merged v14 Master)"
        if "v13" in model:
            return f"{model} (Standalone Merged v13 Master)"
        if "v11" in model:
            return f"{model} (Standalone Merged v11 Grandmaster)"
        import re
        v_match = re.search(r"v(\d+)", model)
        if v_match:
            return f"{model} (Standalone Merged v{v_match.group(1)} Master)"
        if "Houdini-VEX" in model:
            return f"{model} (Standalone Merged v10.1)"
        return f"{model} (Base)"

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
        target_model = os.path.basename(vault_model_path)
        if self.is_healthy():
            current_info = self.get_model_info_string()
            if target_model in current_info or (self.active_model_name and target_model == self.active_model_name):
                return True
            # Model mismatch: stop running instance and switch to requested model
            self.stop_engine()
            if sys.platform == "win32":
                try:
                    subprocess.run(
                        ["powershell", "-Command", "Stop-Process -Name 'llama-server' -Force -ErrorAction SilentlyContinue"],
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                except Exception:
                    pass
                time.sleep(1.0)

        self.active_model_name = target_model
        if not os.path.isfile(engine_bin_path):
            self.last_error = f"Engine executable not found: {engine_bin_path}"
            return False
        try:
            resolved_model_path = self._resolve_model_path(vault_model_path)
        except Exception as error:
            self.last_error = str(error)
            return False

        gpu_layers = str(get_recommended_gpu_layers())
        self.active_gpu_layers = int(gpu_layers)
        self.active_model_name = os.path.basename(vault_model_path)
        self.active_lora_name = None

        command = [
            engine_bin_path, "--model", resolved_model_path, "--port", str(self.port),
            "--host", self.host, "--ctx-size", "4096", "--n-gpu-layers",
            gpu_layers, "--no-warmup", "--parallel", "1",
        ]
        # Check for fine-tuned LoRA adapter (only if the model is not already standalone merged)
        is_already_merged = "Houdini-VEX" in os.path.basename(vault_model_path) or "merged" in os.path.basename(vault_model_path).lower()
        if not is_already_merged:
            model_dir = os.path.dirname(vault_model_path)
            lora_candidates = [
                os.path.join(model_dir, "qwen3-vex-v10-lora.gguf"),
                os.path.join(model_dir, "lora.gguf"),
            ]
            for lora_path in lora_candidates:
                if os.path.isfile(lora_path):
                    command.extend(["--lora", lora_path])
                    self.active_lora_name = os.path.basename(lora_path)
                    break
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

    def switch_model(self, engine_bin_path: str, vault_model_path: str) -> bool:
        """Gracefully switch active engine to a different model weights file."""
        self.stop_engine()
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["powershell", "-Command", "Stop-Process -Name 'llama-server' -Force -ErrorAction SilentlyContinue"],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception:
                pass
            time.sleep(1.0)
        return self.start_embedded_engine(engine_bin_path, vault_model_path)

