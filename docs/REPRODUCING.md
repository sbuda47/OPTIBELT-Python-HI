# Reproduction guide

## What a collaborator can establish

1. Without the dataset: run the synthetic core tests, verify frozen bytes/model integrity, inspect formulas and alarm logic.
2. With authorized raw data: independently re-extract, refit and recalibrate the current candidate and reproduce the recorded check metrics.
3. With additional independent acquisitions: assess generalization. Reproducing the existing subset is not independent-acquisition validation.

## Environment and inputs

Use Python 3.14 and `uv sync --locked` from the root. `uv.lock` records the core/development resolution. The full application environment is separately pinned in `web_dashboard/requirements-lock.txt`. Record OS, Python and package versions with your report. Windows was tested locally. The initial [Linux GitHub Actions run](https://github.com/sbuda47/OPTIBELT-Python-HI/actions/runs/42645910112) also passed the pinned core installation, frozen-release check, core tests and repository audit. The full raw-data reproduction was tested locally; CI does not download the dataset.

For the publisher links, seven-part archive extraction instructions and current availability, see [the README dataset section](../README.md#dataset-download-separately). The repository deliberately contains no raw MAT files. Obtain the files through an authorized route, preserve their exact names/folder structure, and keep them outside Git. `dataset/manifests/recording_hashes.csv` identifies all 41 original inputs without personal source paths. `dataset/splits/data_admission.csv` records initial eligibility. The current recipe selects the 28 supported cases through `reproducibility/reference/record_routing.csv`; it does not fit or calibrate on faults. Nine initial quality exclusions and four complete unsupported conditions remain outside this primary comparison. Historical `grouped_v1` splits are preserved for earlier studies; they are not the current temporal protocol.

## Current candidate

```sh
uv run python -B scripts/verify_release.py
uv run pytest tests -q -p no:cacheprovider
uv run python -B scripts/reproduce_current.py --data-root /authorized/raw --output outputs/runs/reproduction_001
```

Windows paths containing spaces must be quoted. The data root contains the two speed-profile directories, not the repository itself. Raw files need not be copied into the repository. The recipe verifies each selected input SHA-256, extracts frozen features, refits A/C using healthy fit blocks, calibrates from guarded healthy intervals, then evaluates the reserved check blocks. It compares fitted model parameters, thresholds and recording-level outcomes with frozen references before reporting success. The primary C thresholds must reproduce raw 5.941378031107631 / EWMA 5.8646090304501115 within numerical tolerance. A EWMA is 5.8215248790603775.

Outputs include `run.json`, a separately saved `refitted_bundle.json`, calibration evidence, `predictions.csv` and `record_metrics.csv`. The distributed frozen release is never overwritten. Current fixed expectations are 28 records, 17 healthy, 11 fault, 2,210 A/C prediction rows and 56 recording/reference metrics. In C, 570 healthy and 255 fault eligible check steps produce zero healthy critical requests and ten faulty recordings with requests. The coil case remains a documented critical-request miss.

If an authorized collaborator already has the complete original `candidate_features_v1` artifact set and its manifest, the faster route is:

```sh
uv run python -B scripts/reproduce_current.py --features-cache /authorized/candidate_features_v1 --output outputs/runs/reproduction_cache_001
```

This verifies the feature manifest and skips raw extraction. Report it as feature-level reproduction, not independent raw processing. Never weaken a failed hash check or numerical tolerance just to obtain PASS; retain the failed output and investigate input identity, environment and method differences.

## Additional studies

The original experiment sources are preserved under `experiments/`. The supported ablation/window/native-rate and streaming reruns use the full candidate feature artifact set:

1. Place the 32 authorized complete raw recordings at their admitted `dataset/raw/` paths. They remain ignored by Git.
2. `uv run python -B -m optibelt_hi.features.batch --project . --name candidate_features_v1`
3. Install the pinned application dependencies (includes pandas) in the application environment.
4. With that environment's Python, run `experiments/research_comparisons_002/research_parallel_driver.py`, then `experiments/streaming_experiment_001/streaming_experiment.py`.

These scripts refuse existing output directories, use the same prespecified methods and create ignored `outputs/runs/` directories. The parallel study uses three workers; plan roughly 8–12 GB of free RAM and reduce workers deliberately on smaller machines. Do not compare its extraction timings as a controlled serial benchmark. Compare resulting summary tables to `reproducibility/reference/research_summary.csv` and per-record metrics, rather than expecting identical runtime or compressed-file hashes.

The independent raw and shorter-record scripts can also be inspected/run with their documented prerequisites. Some historical phase-1 audit scripts verify exact earlier run trees and require the original private provenance archive; they are not advertised as fresh-checkout entry points. Historical prose records the original results, not a claim that every historical workflow is available without its source artifacts.

## Returning an independent reproduction report

Provide the repository commit ID (once committed), environment versions, input hashes/access route, exact commands, generated run manifest and a list of matches/differences. Distinguish software-test success, raw numerical reproduction and independent-data performance. Include warnings and missed requests. Avoid sharing raw data or derived archives without permission. No real motor control should be connected during software reproduction.
