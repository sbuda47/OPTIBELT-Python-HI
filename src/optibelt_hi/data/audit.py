"""Full-file scientific inspection, independent of health-index outcomes."""
import csv
import hashlib
import json
import platform
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import scipy

from .recordings import CHANNELS, RATES, matrix, metadata, profile_channel, validate_matrix


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_csv(path, rows):
    with Path(path).open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def audit(project: Path, name: str):
    if not name or Path(name).name != name or name in {".", ".."}:
        raise ValueError("Use a single new directory name for the audit.")
    folder = project / "outputs/runs" / name
    folder.mkdir(parents=True, exist_ok=False)
    records, channels, errors = [], [], []
    with (project / "dataset/manifests/copy_receipt.csv").open(encoding="utf-8-sig") as handle:
        receipt = list(csv.DictReader(handle))
    expected_paths = {item["relative_path"] for item in receipt}
    actual_paths = {p.relative_to(project).as_posix() for p in (project / "dataset/raw").rglob("*.mat")}
    if actual_paths != expected_paths or len(expected_paths) != len(receipt):
        raise ValueError("Raw files differ from the copy receipt; audit provenance before proceeding.")
    for item in sorted(receipt, key=lambda row: row["relative_path"]):
        relative = Path(item["relative_path"])
        path = (project / relative).resolve()
        if not path.is_relative_to((project / "dataset/raw").resolve()):
            raise ValueError("Receipt contains a path outside dataset/raw.")
        try:
            actual_hash = sha256(path)
            if actual_hash != item["sha256"]:
                raise ValueError("Content hash differs from the copy receipt.")
            info = metadata(path)
            profiles = []
            with matrix(path) as data:
                validate_matrix(data)
                for index, (channel, rate) in enumerate(zip(CHANNELS, RATES, strict=True)):
                    profile = profile_channel(data[:, index], rate, rate * info["expected_duration_s"])
                    profiles.append(profile)
                    channels.append({"recording_id": relative.stem, "channel": channel, **profile})
                shape = list(data.shape)
                dtype = str(data.dtype)
            with path.open("rb") as handle:
                header = handle.read(116).decode("latin-1").rstrip("\x00 ")
            records.append({
                "recording_id": relative.stem,
                "relative_path": relative.as_posix(),
                "sha256": actual_hash, "bytes": path.stat().st_size,
                **info, "matrix_shape": str(shape), "dtype": dtype,
                "mat_header": header,
                "complete_five_channel_recording": all(p["usable"] for p in profiles),
                "unusable_channels": "|".join(n for n, p in zip(CHANNELS, profiles, strict=True) if not p["usable"]),
                "split_status": "unassigned",
            })
            print(f"{len(records):02d}/{len(receipt)} {relative.name}: "
                  f"{records[-1]['unusable_channels'] or 'all channels complete'}", flush=True)
        except (OSError, ValueError, KeyError) as exc:
            errors.append({"path": relative.as_posix(), "error": str(exc)})
    if records:
        write_csv(folder / "recordings.csv", records)
    if channels:
        write_csv(folder / "channels.csv", channels)
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "numpy": np.__version__,
        "scipy": scipy.__version__, "h5py": h5py.__version__,
        "expected_recordings": len(receipt),
        "readable_recordings": len(records),
        "complete_five_channel_recordings": sum(r["complete_five_channel_recording"] for r in records),
        "conditions": dict(Counter(r["condition"] for r in records)),
        "unusable_channels": dict(Counter(c["channel"] for c in channels if not c["usable"])),
        "duplicate_hashes": {h: n for h, n in Counter(r["sha256"] for r in records).items() if n > 1},
        "errors": errors,
        "interpretation": "File integrity and channel availability audit. No model was fitted.",
    }
    (folder / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if errors:
        raise ValueError(f"{len(errors)} files failed audit; see {folder / 'summary.json'}")
    return folder

