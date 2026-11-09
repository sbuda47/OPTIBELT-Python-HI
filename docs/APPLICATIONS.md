# Optional application setup

From the repository root, create a separate environment and install the recorded application dependencies:

```sh
python -m venv .venv-web
# Linux/macOS:
.venv-web/bin/python -m pip install -r web_dashboard/requirements-lock.txt
# Windows equivalent:
.venv-web/Scripts/python -m pip install -r web_dashboard/requirements-lock.txt
```

Use that environment's Python for the following commands. No editable install is required for the application wrappers, which resolve the checkout's frozen `src/` directory.

## Simulated-live monitor

```sh
python -B -m uvicorn optibelt_live.api:app --app-dir live_pipeline --host 127.0.0.1 --port 8766
```

Open http://127.0.0.1:8766. The catalogue and API documentation work without data. Simulation needs the selected hash-matching raw file at `dataset/raw/<profile>/<filename>.mat`. The recording source currently loads a full MAT file before paced replay. Do not expose this unauthenticated single-process engineering service to an untrusted network or start multiple workers against its one active session.

The five-channel packet contract is documented by `/docs` and `live_pipeline/optibelt_live/engine.py`: atomic 100 ms intervals, 2,560 vibration/torque samples and 10,000 per current phase; consecutive sequence and timestamps; declared supported stable condition. Missing/late/invalid input invalidates the segment. Confirmed alarms survive stops and service restart. Acknowledgement needs current recovered HI. There is no motor-control endpoint. Hardware calibration, physical clock alignment and load-transition behavior remain installation work.

## Playback and FFT/envelope UI

First complete `scripts/reproduce_current.py` with its default output `outputs/runs/reproduction_001`. For a different directory set `OPTIBELT_REPLAY_RUN` to its absolute path or a repository-relative path. `OPTIBELT_PROJECT` optionally overrides the checkout root; it is not required normally.

```sh
cd web_dashboard
npm ci
npm run build
cd ..
python -B -m uvicorn api.app:app --app-dir web_dashboard --host 127.0.0.1 --port 8765
```

The app can start before reproduction, but catalogue/data endpoints return a clear unavailable error. It does not ship saved per-window predictions. Analysis additionally requires raw files at the admitted `dataset/raw` paths, even if the reproduction command read data from another external location. `dashboard/data.py` is the shared Python adapter; the old Streamlit UI is not part of this prepared repository.

## Checks

```sh
python -B -m pytest live_pipeline/tests web_dashboard/tests/test_spectra.py -q -p no:cacheprovider
python -B -m pytest web_dashboard/tests/test_api.py -q -p no:cacheprovider
```

The API integration tests need reproduction predictions and authorized raw samples; they skip if the playback source is unavailable. Pure numerical spectra and live lifecycle tests do not need raw recordings. Raw replay verification scripts are separate and require a new output folder.

Browser checks need Node, Playwright and its browser. Install Playwright in the repository root (so both applications can resolve it) with `npm install --no-save --package-lock=false playwright`, then `npx playwright install chromium`. The scripts use bundled Chromium by default; `BROWSER_CHANNEL=msedge` selects an installed Edge browser. Set `PIPELINE_URL` for live tests (normally http://127.0.0.1:8766) and `DASHBOARD_URL` for playback tests. Live paced browser tests require authorized recordings and create simulation sessions.
