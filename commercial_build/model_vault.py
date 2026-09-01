"""Customer-bound model-vault format used by the commercial packager.

Version 3 binds the AES-256-GCM encryption key to BOTH the signed customer
license RSA signature AND the customer's immutable Machine ID:
  Decryption Key = HKDF-SHA256(Salt, RSA_Signature + "::" + Local_Machine_ID)

This mathematically guarantees that copying the encrypted model vault and license
to an unauthorized machine produces an invalid AES decryption key, causing GCM
decryption and authentication tag validation to fail at the cryptographic level.
"""

from __future__ import annotations

import os
import struct

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


_VAULT_MAGIC_V3 = b"VEXVAULT\x03"
_VAULT_MAGIC_V2 = b"VEXVAULT\x02"
CHUNK_SIZE = 64 * 1024 * 1024


def derive_encryption_key(salt: bytes, license_material: bytes, machine_id: str = "") -> bytes:
    """Derive the vault key from customer's signed license material and machine ID.

    Formula: HKDF-SHA256(Salt, Signature + "::" + Local_Machine_ID)
    """
    if not isinstance(license_material, bytes) or len(license_material) < 128:
        raise ValueError("Customer license binding material is invalid.")
    if len(salt) != 16:
        raise ValueError("Vault salt is invalid.")
    
    mid_bytes = (machine_id or "").strip().upper().encode("utf-8")
    kdf_input = license_material + b"::" + mid_bytes

    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"AI-Attribute-Wrangle/Vault/v3/hardware-license-binding",
        backend=default_backend(),
    ).derive(kdf_input)


def derive_v2_encryption_key(salt: bytes, license_material: bytes) -> bytes:
    """Legacy v2 key derivation for backwards compatibility."""
    if not isinstance(license_material, bytes) or len(license_material) < 128:
        raise ValueError("Customer license binding material is invalid.")
    if len(salt) != 16:
        raise ValueError("Vault salt is invalid.")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"AI-Attribute-Wrangle/Vault/v2/customer-license-binding",
        backend=default_backend(),
    ).derive(license_material)


class ModelVault:
    """AES-256-GCM streaming vault tied cryptographically to hardware ID & customer license."""

    @classmethod
    def encrypt_model(
        cls,
        input_gguf_path: str,
        output_vault_path: str,
        license_material: bytes,
        machine_id: str = "",
        progress_callback=None,
    ) -> bool:
        if not os.path.isfile(input_gguf_path):
            raise FileNotFoundError(f"Input model not found: {input_gguf_path}")

        total_size = os.path.getsize(input_gguf_path)
        salt = os.urandom(16)
        key = derive_encryption_key(salt, license_material, machine_id=machine_id)
        aesgcm = AESGCM(key)
        with open(input_gguf_path, "rb") as fin, open(output_vault_path, "wb") as fout:
            fout.write(_VAULT_MAGIC_V3)
            fout.write(salt)
            fout.write(struct.pack("<Q", total_size))
            bytes_processed = 0
            chunk_index = 0
            while True:
                chunk = fin.read(CHUNK_SIZE)
                if not chunk:
                    break
                nonce = os.urandom(8) + struct.pack("<I", chunk_index)
                encrypted_chunk = aesgcm.encrypt(nonce, chunk, None)
                fout.write(nonce)
                fout.write(struct.pack("<I", len(encrypted_chunk)))
                fout.write(encrypted_chunk)
                bytes_processed += len(chunk)
                chunk_index += 1
                if progress_callback:
                    progress_callback(bytes_processed, total_size)
        return True

    @classmethod
    def decrypt_stream(
        cls,
        vault_path: str,
        output_stream,
        license_material: bytes,
        machine_id: str = "",
    ) -> None:
        """Decrypt only after EngineManager has validated the customer license and hardware ID."""
        with open(vault_path, "rb") as fin:
            magic = fin.read(9)
            if magic == _VAULT_MAGIC_V3:
                salt = fin.read(16)
                raw_size = fin.read(8)
                if len(salt) != 16 or len(raw_size) != 8:
                    raise ValueError("Truncated vault header.")
                total_size = struct.unpack("<Q", raw_size)[0]
                key = derive_encryption_key(salt, license_material, machine_id=machine_id)
            elif magic == _VAULT_MAGIC_V2:
                salt = fin.read(16)
                raw_size = fin.read(8)
                if len(salt) != 16 or len(raw_size) != 8:
                    raise ValueError("Truncated vault header.")
                total_size = struct.unpack("<Q", raw_size)[0]
                key = derive_v2_encryption_key(salt, license_material)
            else:
                raise ValueError("Unsupported, corrupted, or legacy vault format.")

            aesgcm = AESGCM(key)
            bytes_written = 0
            while bytes_written < total_size:
                nonce = fin.read(12)
                enc_len_raw = fin.read(4)
                if len(nonce) != 12 or len(enc_len_raw) != 4:
                    raise ValueError("Truncated vault chunk header.")
                enc_len = struct.unpack("<I", enc_len_raw)[0]
                if enc_len < 17 or enc_len > CHUNK_SIZE + 16:
                    raise ValueError("Invalid encrypted vault chunk length.")
                encrypted_chunk = fin.read(enc_len)
                if len(encrypted_chunk) != enc_len:
                    raise ValueError("Truncated vault chunk.")
                decrypted_chunk = aesgcm.decrypt(nonce, encrypted_chunk, None)
                if bytes_written + len(decrypted_chunk) > total_size:
                    raise ValueError("Vault plaintext exceeds its declared size.")
                output_stream.write(decrypted_chunk)
                bytes_written += len(decrypted_chunk)
            if fin.read(1):
                raise ValueError("Vault contains unexpected trailing data.")

    @classmethod
    def get_plaintext_size(cls, vault_path: str) -> int:
        with open(vault_path, "rb") as fin:
            magic = fin.read(9)
            if magic not in (_VAULT_MAGIC_V3, _VAULT_MAGIC_V2):
                raise ValueError("Unsupported, corrupted, or legacy vault format.")
            salt = fin.read(16)
            if len(salt) != 16:
                raise ValueError("Truncated vault header.")
            raw_size = fin.read(8)
            if len(raw_size) != 8:
                raise ValueError("Truncated vault header.")
            return struct.unpack("<Q", raw_size)[0]
