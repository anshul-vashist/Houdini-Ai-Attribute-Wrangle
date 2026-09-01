"""
=============================================================================
 Commercial Licensing Engine (Hardware-Locked RSA-2048)
 Generates immutable Machine Fingerprints and verifies digitally signed
 offline licenses without requiring an internet connection.
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

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend


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


class LicenseManager:
    """Manages RSA-2048 key generation, license signing, and offline validation."""

    @staticmethod
    def generate_master_keypair(save_dir: str = "."):
        """Generates the developer's Master Private Key and ship-ready Public Key."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()

        priv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        pub_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        priv_path = os.path.join(save_dir, "developer_master_private_key.pem")
        pub_path = os.path.join(save_dir, "embedded_public_key.pem")

        with open(priv_path, "wb") as f:
            f.write(priv_pem)
        with open(pub_path, "wb") as f:
            f.write(pub_pem)

        return priv_path, pub_path

    @staticmethod
    def issue_license(
        private_key_path: str,
        customer_name: str,
        order_id: str,
        machine_id: str,
        tier: str = "Commercial",
        expiry_date: str = "permanent"
    ) -> str:
        """Issues a cryptographically signed license file for a customer."""
        with open(private_key_path, "rb") as f:
            private_key = serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )

        payload = {
            "product": "Houdini_AI_Attribute_Wrangle",
            "version": "1.0",
            "licensee": customer_name,
            "order_id": order_id,
            "machine_id": machine_id.strip().upper(),
            "tier": tier,
            "issued_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ"),
            "expires": expiry_date
        }

        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = private_key.sign(
            payload_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

        license_data = {
            "payload": payload,
            "signature": base64.b64encode(signature).decode("ascii")
        }

        return json.dumps(license_data, indent=2)

    @staticmethod
    def verify_license(license_json_str: str, public_key_pem: bytes) -> tuple[bool, str, dict]:
        """
        Verifies license authenticity against embedded public key and current hardware.
        Returns (is_valid, message, payload_dict).
        """
        try:
            lic = json.loads(license_json_str)
            payload = lic["payload"]
            sig_bytes = base64.b64decode(lic["signature"], validate=True)
            if payload.get("product") != "Houdini_AI_Attribute_Wrangle":
                return False, "License is for a different product.", payload
            if payload.get("version") != "1.0":
                return False, "License version is unsupported.", payload
            payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")

            # 1. Cryptographic RSA signature check
            public_key = serialization.load_pem_public_key(public_key_pem, backend=default_backend())
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
            licensed_machine_id = payload.get("machine_id", "")

            # If node-locked (not floating studio site license)
            if licensed_machine_id != "*" and licensed_machine_id != current_machine_id:
                return False, "License is not valid for this machine.", payload

            # 3. Expiry Check
            expires = payload.get("expires", "permanent")
            if expires != "permanent" and expires != "never":
                exp_date = datetime.strptime(expires, "%Y-%m-%d").date()
                if datetime.utcnow().date() > exp_date:
                    return False, f"License expired on {expires}.", payload

            return True, "Commercial License Active & Verified", payload

        except Exception as e:
            return False, f"License verification failed: {e}", {}
