import hashlib
import json
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
ARTIFACTS = BACKEND / "artifacts" / "v4"


def test_checkpoint_sha256_matches_manifest():
    manifest = json.loads((ARTIFACTS / "v4_artifact_manifest.json").read_text(encoding="utf-8"))
    expected = manifest.get("checkpoint_sha256")
    entry = manifest.get("files", {}).get("checkpoints/best_v4.pt", {})
    if entry.get("sha256"):
        expected = entry["sha256"]
    ckpt = ARTIFACTS / "checkpoints" / "best_v4.pt"
    assert ckpt.is_file()
    h = hashlib.sha256()
    with ckpt.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    assert h.hexdigest().lower() == expected.lower()


def test_artifact_privacy_gitignore():
    root = BACKEND.parent
    gi = (root / ".gitignore").read_text(encoding="utf-8")
    assert "/backend/artifacts/" in gi or "backend/artifacts/" in gi
