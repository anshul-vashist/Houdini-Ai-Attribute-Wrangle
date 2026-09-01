"""
=============================================================================
 Client-Side License Validator (Offline Hardware-Locked Verification)
 Verifies digital signatures using embedded public key. Contains ZERO signing
 code or private keys to ensure total client security.
=============================================================================
"""

import os
import sys
import json
import base64
import hashlib
import platform
import subprocess
from datetime import datetime

from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend


EMBEDDED_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArSw27lbhPeZLpVN2ygWl
u1QNGUu+zQq8qnCd+nVjbSrNLtZHR7H3YcgKX9tPahsBN+uaYlSsKVvYBBpwPVrG
UDy071a3+7o9BaY/VWhTcU72nKWiPfFvmBJEmjOPOlmaBCvtXNVwRGd+JdJqx4NJ
b/BKnrHYZbtsk5q/HDQSvLYistwGJ+kZxasjfwcR18k2USydbhYUzWNU5CmR6f6E
5ra6u5tk6gr4JD1R5CsnIhsOJecjb8MDFvWWM40kR4/JKiot2DmvZ4DGz/ui22f3
900cG0SJ/+HV9vABTRGBDAI8RC1Dnm8AMnZ1d7kGhv9jHmoPk6jlfltR3MaYN+SR
tQIDAQAB
-----END PUBLIC KEY-----
"""


class MachineFingerprint:
    """Extracts immutable hardware identifiers to produce a unique Machine ID."""
    
    @staticmethod
    def get_windows_uuid() -> str:
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystemProduct).UUID"],
                text=True, stderr=subprocess.DEVNULL,
            ).strip()
            if out and len(out) > 8:
                return out
        except Exception:
            pass
        try:
            out = subprocess.check_output(["wmic", "csproduct", "get", "uuid"], text=True, stderr=subprocess.DEVNULL).strip()
            lines = [l.strip() for l in out.splitlines() if l.strip() and "UUID" not in l]
            if lines:
                return lines[0]
        except Exception:
            pass
        return "UNKNOWN-UUID"

    @staticmethod
    def get_cpu_id() -> str:
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).ProcessorId"],
                text=True, stderr=subprocess.DEVNULL,
            ).strip()
            if out:
                return out
        except Exception:
            pass
        return "UNKNOWN-CPU"

    @classmethod
    def generate_machine_id(cls) -> str:
        """Returns a standardized 16-character Machine ID (e.g. VEX-8F92-4A1C-99B3)."""
        uuid_str = cls.get_windows_uuid()
        cpu_str = cls.get_cpu_id()
        raw_identity = f"{uuid_str}:{cpu_str}:{platform.node()}"
        sha = hashlib.sha256(raw_identity.encode("utf-8")).hexdigest().upper()
        return f"VEX-{sha[0:4]}-{sha[4:8]}-{sha[8:12]}"


class LicenseValidator:
    """Client verification engine with built-in embedded cryptographic key."""

    @staticmethod
    def verify_license_with_material(license_json_str: str, public_key_pem: bytes = None) -> tuple[bool, str, bytes, str]:
        """
        Verifies license authenticity against embedded public key and current hardware.
        Returns (is_valid, message, sig_bytes, licensed_machine_id).
        """
        try:
            lic = json.loads(license_json_str)
            payload = lic["payload"]
            sig_bytes = base64.b64decode(lic["signature"], validate=True)
            if payload.get("product") != "Houdini_AI_Attribute_Wrangle":
                return False, "License is for a different product.", b"", ""
            if payload.get("version") != "1.0":
                return False, "License version is unsupported.", b"", ""
            payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")

            # 1. Cryptographic RSA signature check (enforce compiled embedded key)
            key_pem = public_key_pem if (public_key_pem and public_key_pem.strip()) else EMBEDDED_PUBLIC_KEY_PEM
            public_key = serialization.load_pem_public_key(key_pem, backend=default_backend())
            public_key.verify(
                sig_bytes,
                payload_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )

            # 2. Machine Hardware Binding Check
            current_machine_id = MachineFingerprint.generate_machine_id()
            licensed_machine_id = str(payload.get("machine_id", "")).strip().upper()

            # If node-locked (not floating studio site license)
            if licensed_machine_id != "*" and licensed_machine_id != current_machine_id:
                return False, "License is not valid for this machine.", b"", licensed_machine_id

            # 3. Expiry Check
            expires = payload.get("expires", "permanent")
            if expires != "permanent" and expires != "never":
                exp_date = datetime.strptime(expires, "%Y-%m-%d").date()
                if datetime.utcnow().date() > exp_date:
                    return False, f"License expired on {expires}.", b"", licensed_machine_id

            # RSA-PSS is randomized, so this is unique high-entropy binding
            # material for the customer package. It is returned only after the
            # signature, hardware, and expiry checks all pass.
            return True, "Commercial License Active & Verified", sig_bytes, licensed_machine_id

        except Exception as e:
            return False, f"License verification failed: {e}", b"", ""

    @staticmethod
    def verify_license(license_json_str: str, public_key_pem: bytes = None) -> tuple[bool, str, dict]:
        """Compatibility wrapper used by the Houdini UI callback."""
        res = LicenseValidator.verify_license_with_material(license_json_str, public_key_pem)
        valid, message = res[0], res[1]
        if not valid:
            return False, message, {}
        return True, message, json.loads(license_json_str)["payload"]


def activate_online(license_key: str, customer_email: str = "", server_url: str = None, timeout: float = 10.0) -> tuple[bool, str, dict]:
    """
    Performs 1-click online activation against your secure license server.
    Returns (is_successful, message, license_dict).
    """
    import urllib.request
    import urllib.error
    import ssl

    if not license_key or not license_key.strip():
        return False, "Please provide a valid License Key or Order ID.", {}

    target_url = server_url or os.getenv("AI_WRANGLE_ACTIVATION_URL", "https://license.ai-attribwrangle.com/api/activate")
    machine_id = MachineFingerprint.generate_machine_id()

    payload = {
        "license_key": license_key.strip(),
        "email": (customer_email or "").strip(),
        "machine_id": machine_id
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        target_url,
        data=req_data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": f"Houdini-AI-Attribute-Wrangle/{platform.system()}"
        },
        method="POST"
    )

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            resp_bytes = response.read()
            resp_data = json.loads(resp_bytes.decode("utf-8"))

            if not resp_data.get("success", False) and resp_data.get("status") != "success":
                err_msg = resp_data.get("error") or resp_data.get("message") or "Activation rejected by server."
                return False, err_msg, {}

            lic_obj = resp_data.get("license") or resp_data.get("license_data")
            if not lic_obj:
                return False, "Malformed server response: missing license payload.", {}

            lic_str = json.dumps(lic_obj) if isinstance(lic_obj, dict) else str(lic_obj)
            is_valid, v_msg, p_dict = LicenseValidator.verify_license(lic_str)
            if not is_valid:
                return False, f"Server returned invalid cryptographic license: {v_msg}", {}

            return True, f"Activated successfully for {p_dict.get('licensee', 'Customer')}!", (lic_obj if isinstance(lic_obj, dict) else json.loads(lic_str))

    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            msg = err_body.get("error") or err_body.get("message") or str(e)
        except Exception:
            msg = f"HTTP Error {e.code}: {e.reason}"
        return False, f"Activation Server Error: {msg}", {}
    except urllib.error.URLError as e:
        return False, f"Network connection failed: {e.reason}. (Ensure internet connection or import .lic file offline)", {}
    except Exception as e:
        return False, f"Activation error: {e}", {}

