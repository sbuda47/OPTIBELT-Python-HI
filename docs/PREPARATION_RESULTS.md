# Repository preparation checks — 9 November 2026

The clean repository was exported through Git's index into a separate folder.
The original research workspace and provenance archive were preserved. Frozen
core source, configuration, split artifacts and release bytes were preserved;
portable paths and entry points were added around them.

## Verified locally on Windows

- `uv lock --check --offline` and a fresh `uv sync --locked --offline` succeeded.
- The freshly installed Python 3.14.5 core environment passed all **108 core
  tests** and the frozen-release integrity/synthetic monitor smoke check.
- Both the verified-feature-cache recipe and the raw-data recipe independently
  refitted the healthy reference statistics and recalibrated the thresholds.
  Both matched the frozen candidate and all **56 recording/reference checks**
  over **28 recordings**, producing **2,210** prediction rows each.
- Raw reproduction used the existing authorized local data through an external
  root. No raw recordings were added to the repository.
- With regenerated predictions and a temporary ignored raw-data link, the full
  core/live/spectra/playback integration suite passed **140 tests**. This includes
  Python/UI playback parity, acknowledgement rules, native signal access and
  independent-periodogram comparisons. The temporary link was then removed.
- The clean Git export passed the frozen-release smoke check. Its application
  tests passed **26 tests** and correctly skipped **6** integration tests that
  require regenerated playback data. The export contains neither raw recordings
  nor generated playback runs.
- `npm ci --offline` and `npm run build` succeeded for the web dashboard,
  including TypeScript checking. The local npm installation reported that it
  blocked the esbuild postinstall script; the build nevertheless completed.
- The Git-index content audit found no prohibited raw/generated files, detected
  credential patterns, personal user paths or files above its 10 MiB limit.
  This heuristic check does not determine redistribution or branding rights.

The application tests emitted a Starlette/httpx TestClient deprecation warning.
The pinned working environment was retained rather than upgrading application
dependencies during repository preparation.

## Evidence and limits

The raw run manifest records successful completion at
`2026-11-09T00:55:13` UTC (the full timestamp is in the local generated manifest).
The frozen bundle SHA-256 is
`3092a15c60c24cdd38b21648baa14e3a1796a2bda79bb6ee756ad66b0cd5a0ae`.
Machine-specific logs and generated run manifests remain in the local preparation
workspace, outside the proposed commit.

The raw/cache reproduction and application tests used the existing pinned
application environment; the separate fresh core installation verifies the
dataset-free setup. This preparation did not test on another person's computer,
run GitHub CI, acquire new independent recordings, perform a new browser visual
review, or validate physical sensors/actuators. The supplied browser checks remain
optional and require their documented setup.

No remote was configured, no commit was authored and nothing was pushed.
Publication choices are recorded in `PUBLICATION_CHECKLIST.md`. A collaborator
can record their own findings in `reproducibility/REPORT_TEMPLATE.md`.
