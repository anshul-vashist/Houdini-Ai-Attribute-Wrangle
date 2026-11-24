"""Single place the Hugging Face token comes from: the HF_TOKEN environment variable, else the
git-ignored file <repo>/.secrets/hf_token. Never hard-code tokens in scripts.

    from hf_secret import hf_token          # (add <repo>/tools to sys.path first)
"""
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOKEN_FILE = os.path.join(ROOT, ".secrets", "hf_token")


def hf_token(required: bool = True) -> str | None:
    tok = os.environ.get("HF_TOKEN")
    if not tok and os.path.isfile(TOKEN_FILE):
        tok = open(TOKEN_FILE, encoding="utf-8").read().strip()
    if not tok and required:
        raise RuntimeError(f"No Hugging Face token: set HF_TOKEN or put it in {TOKEN_FILE}")
    return tok or None
