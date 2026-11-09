"""Commands for the first, source-data milestone."""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np

from .configuration import load_config
from .data.audit import audit, sha256, write_csv
from .data.recordings import CHANNELS, metadata
from .preprocessing.signals import prepare_recording, window_bounds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[2])
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("audit", help="Audit all original channels and verify copy hashes")
    inspect.add_argument("--name", required=True)
    prepare = commands.add_parser("prepare", help="Prepare one complete recording at 25.6 kHz")
    prepare.add_argument("--recording", type=Path, required=True, help="Path relative to the project")
    prepare.add_argument("--name", required=True)
    args = parser.parse_args()
    project = args.project.resolve()
    if args.command == "audit":
        audit(project, args.name)
        return
    if Path(args.name).name != args.name or args.name in {"", ".", ".."}:
        parser.error("Use a single new directory name.")
    path = (project / args.recording).resolve()
    if not path.is_relative_to(project / "dataset/raw"):
        parser.error("Recording must be inside dataset/raw.")
    config_path = project / "configs/preprocessing.yaml"
    config = load_config(config_path)
    info = metadata(path)
    folder = project / "outputs/runs" / args.name
    folder.mkdir(parents=True, exist_ok=False)
    try:
        values = prepare_recording(path, info["expected_duration_s"])
        np.save(folder / "signals.npy", values, allow_pickle=False)
        bounds = [{"recording_id": path.stem, "window_index": i,
                   "start_sample": start, "stop_sample": stop,
                   "start_seconds": start / 25600, "stop_seconds": stop / 25600}
                  for i, (start, stop) in enumerate(window_bounds(len(values), rate=config["target_rate_hz"],
                                                         window_seconds=config["window_seconds"],
                                                         hop_seconds=config["hop_seconds"]))]
        write_csv(folder / "windows.csv", bounds)
        report = {
            "status": "complete", "created_utc": datetime.now(timezone.utc).isoformat(),
            "environment": {name: version(name) for name in ("optibelt-hi", "numpy", "scipy", "h5py")},
            "input": path.relative_to(project).as_posix(),
            "input_sha256": sha256(path), "channels": CHANNELS,
            "native_rates_hz": [25600, 25600, 100000, 100000, 100000],
            "target_rate_hz": 25600, "shape": list(values.shape),
            "window_count": len(bounds), "window_seconds": config["window_seconds"],
            "hop_seconds": config["hop_seconds"],
            "config_sha256": sha256(config_path), "configuration": config,
            "implementation_sha256": {p.relative_to(Path(__file__).parent).as_posix(): sha256(p)
                                      for p in sorted(Path(__file__).parent.rglob("*.py"))},
            "current_resample_ratio": "32/125",
            "filter": "scipy.signal.resample_poly, Kaiser beta=5.0, padtype=line",
            "alignment": "Common recording start per source paper; hardware offset unverified.",
            "mode": "Offline. FIR boundary handling and delay require further streaming design.",
        }
    except Exception as exc:
        (folder / "run.json").write_text(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        raise
    (folder / "run.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

