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


def _can_bind(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def get_working_port(preferred: int = 58421, fallback: int = 58321) -> int:
    """AI_WRANGLE_PORT if set, else the first bindable of preferred / fallback, else an OS-assigned
    free port. (Windows Hyper-V/WSL can reserve whole ranges, e.g. 58385-58484 covers 58421.)"""
    env_port = os.getenv("AI_WRANGLE_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass
    for port in (preferred, fallback):
        if _can_bind(port):
            return port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port

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


def _kill_with_parent(process):
    """Windows: put the engine in a job object that is killed when Houdini exits, even on a crash or
    End Task (atexit alone left ~6 GB VRAM orphans). Returns the job handle; keep it alive."""
    if sys.platform != "win32" or process is None:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.OpenProcess.restype = wintypes.HANDLE

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                           "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

        class EXTENDED(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        JobObjectExtendedLimitInformation = 9
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = EXTENDED()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k32.SetInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)):
            k32.CloseHandle(job)
            return None
        PROCESS_SET_QUOTA, PROCESS_TERMINATE = 0x0100, 0x0001
        h = k32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, process.pid)
        if not h:
            k32.CloseHandle(job)
            return None
        ok = k32.AssignProcessToJobObject(job, h)
        k32.CloseHandle(h)
        if not ok:
            k32.CloseHandle(job)
            return None
        return job  # handle closes when Houdini exits -> engine is killed
    except Exception:
        return None


class EngineManager:
    """Starts llama-server for local Houdini inference with zero persistent disk cache."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        # Random per-session key: other local programs cannot drive this Houdini's engine.
        self.api_key = secrets.token_hex(16)
        self.process = None
        self._job = None
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
            return f"{model} + LoRA: {self.active_lora_name}"
        return model

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

    def is_healthy(self, timeout: float = 1.0) -> bool:
        if not self.is_port_open():
            return False
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            request = urllib.request.Request(f"{self.base_url}/health", headers=headers)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=timeout) as response:
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

    def start_embedded_engine(self, engine_bin_path: str, vault_model_path: str, wait_callback=None) -> bool:
        """Start llama-server and wait until it serves. `wait_callback()` is called while waiting
        (about every 0.25 s); it may raise to cancel, which stops the engine and re-raises."""
        self.last_error = ""
        target_model = os.path.basename(vault_model_path)
        if self.is_healthy():
            current_info = self.get_model_info_string()
            if target_model in current_info or (self.active_model_name and target_model == self.active_model_name):
                return True
            # Model mismatch: stop running instance and switch to requested model
            self.stop_engine()
            if self.is_healthy():
                # A server we do not own (e.g. another tool's llama-server) holds the port: never kill
                # foreign processes, run ours on a free port instead.
                self._use_port(get_working_port(preferred=self.port + 1, fallback=self.port + 2))

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
            "--host", self.host, "--ctx-size", "8192", "--n-gpu-layers",
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
        if vault_model_path.endswith(".dat"):
            # decrypted vault weights: load fully into memory so the staged plaintext copy can be
            # deleted right after startup (a memory-mapped file cannot be removed on Windows)
            command.append("--no-mmap")
        if self.api_key:
            command.extend(["--api-key", self.api_key])
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.process = subprocess.Popen(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags
            )
            self._job = _kill_with_parent(self.process)
            deadline = time.time() + 180.0
            while time.time() < deadline:
                for _ in range(2):
                    time.sleep(0.25)
                    if wait_callback is not None:
                        try:
                            wait_callback()
                        except BaseException:
                            self.stop_engine()
                            self.last_error = "Model loading cancelled."
                            return False
                if self.is_healthy(timeout=0.4):
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

    def _use_port(self, port: int) -> None:
        self.port = port
        self.base_url = f"http://{self.host}:{port}"

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
        self._job = None
        self.cleanup_cache()

    def cleanup_cache(self) -> None:
        """Erase the short-lived staging directory; no reusable plaintext cache exists."""
        staging_dir, self._staging_dir = self._staging_dir, None
        self._staging_model_path = None
        if staging_dir:
            shutil.rmtree(staging_dir, ignore_errors=True)

    def switch_model(self, engine_bin_path: str, vault_model_path: str, wait_callback=None) -> bool:
        """Gracefully switch active engine to a different model weights file."""
        self.stop_engine()
        if self.is_healthy():
            self._use_port(get_working_port(preferred=self.port + 1, fallback=self.port + 2))
        return self.start_embedded_engine(engine_bin_path, vault_model_path, wait_callback=wait_callback)

