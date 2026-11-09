# Reference evidence

`reference/` stores portable expected outcomes and supported-condition routing. These are data-derived research artifacts, not raw sensor measurements. Confirm sharing terms before publication. The frozen model lives under `outputs/releases/hi_candidate_v1/` so its code-integrity checks retain their established layout.

No raw files, per-window feature arrays, private source paths or per-window playback exports are shipped. Run `scripts/reproduce_current.py` with authorized data to create playback exports locally. Historical original run folders remain outside this repository; the portable recipe reproduces numerical model/results equivalence rather than historical run timestamps.
