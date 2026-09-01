# Security model — v1.0.3

Each offline delivery is built specifically for a customer license. In v3, the
model vault is encrypted with AES-256-GCM using a key derived cryptographically
from BOTH the customer's RSA-PSS license signature AND their immutable
Hardware Machine ID:

  Decryption Key = HKDF-SHA256(Salt, RSA_Signature + "::" + Local_Machine_ID)

This mathematically enforces node-locking: copying the encrypted model vault
(`vex_brain.dat`) and customer license (`ai_wrangle.lic`) to an unauthorized
machine produces an invalid AES key, causing AES-GCM tag verification to fail
at the cryptographic layer rather than relying on bypassable software checks.

At startup, license validation occurs inside the engine manager before the
vault is decrypted. The model weights are loaded into process memory using
`--no-mmap`, and the ephemeral staging directory is purged immediately after
the health check succeeds and on shutdown or error. No persistent decrypted
cache is ever written to disk. All Python modules are compiled to native C++
binaries (`.pyd`) to prevent source inspection and tampering.

This provides state-of-the-art offline IP protection against casual copying,
generic extraction, and unauthorized machine distribution. Protecting model
weights from an authorized customer who has local kernel/debugger access
ultimately requires hosted/cloud inference, or hardware enclaves (TPM / SGX).
The verifier's `--require-hosted-inference` option is available as a release
gate for cloud-only deployments.
