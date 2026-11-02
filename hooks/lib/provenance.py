"""provenance.py -- the provenance sidecar: who promoted these exact bytes.

See ../docs/provenance-contract.md for the contract.

A deliverable is "backed" when a sidecar `<file>.provenance.json` exists, names the trusted
promoter, and carries the sha256 of the file's CURRENT bytes. The promoter writes it from
the bytes it just promoted, so any later edit to the file breaks the match.

Honest limit: the `promoter` field is a convention, not a signature. Anything with write
access can forge a matching sidecar. What this buys is that drift is caught and a forgery
has to be a deliberate act, not an accident.
"""
import hashlib
import json

SIDECAR_SUFFIX = ".provenance.json"
TRUSTED_PROMOTER = "promote.py"


def sha256_bytes(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def sidecar_path(deliverable_path):
    return deliverable_path + SIDECAR_SUFFIX


def read_sidecar(deliverable_path):
    try:
        with open(sidecar_path(deliverable_path), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def has_valid_provenance(deliverable_path):
    """True iff the trusted promoter stamped a sidecar whose sha256 matches the current bytes."""
    sc = read_sidecar(deliverable_path)
    if not sc or sc.get("promoter") != TRUSTED_PROMOTER:
        return False
    cur = sha256_file(deliverable_path)
    return bool(cur) and sc.get("target_sha256") == cur


def write_sidecar(deliverable_path, target_rel, promoted_bytes, workspace_draft,
                  artifacts=None, promoted_at="", review_attestation=None):
    """Write the sidecar from the exact promoted bytes. Called ONLY by the promoter."""
    record = {
        "target_file": target_rel,
        "target_sha256": sha256_bytes(promoted_bytes),
        "promoted_at": promoted_at,
        "promoter": TRUSTED_PROMOTER,
        "workspace_draft": workspace_draft,
        "artifacts": artifacts or [],
    }
    if review_attestation is not None:
        record["review_attestation"] = review_attestation
    with open(sidecar_path(deliverable_path), "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return record
