# Splits and candidate features milestone

This stage freezes grouped_v1 assignments and implements candidate_v1 extraction. See evaluation_design.md and feature_catalog.md. Extraction uses all 32 admitted recordings; primary evaluation uses 27, with five retained for exploratory work.

From the project directory, use the .venv Python:
- python -B -m optibelt_hi.evaluation.splits --project .
- python -B -m optibelt_hi.features.batch --project . --name candidate_features_v1

The freeze command creates dataset/splits/grouped_v1 and refuses an existing version. Extraction creates a fresh outputs/runs directory and refuses overwrite. Failed runs retain their error and completed artifacts; they are not completed scientific runs.

Each NPZ contains features, feature-name strings and integer sample bounds; numpy.load(..., allow_pickle=False) suffices. windows.csv keeps identity and operating/fault metadata separate. run.json records input hashes, frozen protocol hashes, preprocessing, implementation hashes, versions and artifact hashes.

Q04 now has 60 candidate definitions and analytic tests; physical amplitude calibration, envelopes and harmonics remain open. Q05 selection has not occurred and known redundancy is documented. Q06/Q11 healthy-only fit/calibration roles and operating-group exclusion are frozen, while hardware/run independence remains unverified. Model fitting, calibration, smoothing and performance are subsequent stages.

No values from the old exported feature matrix enter the new feature arrays.

