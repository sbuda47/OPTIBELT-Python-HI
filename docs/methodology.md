# Python methodology, first milestone

Current implemented stages
- Inspect and hash all supplied raw recordings.
- Read numeric N x 5 matrices from classic MAT files and HDF5 containers.
- Profile every channel in its native sampling interval.
- Reject incomplete native channels or unexpected padding.
- Retain vibration/torque at 25.6 kHz and resample current from 100 kHz to 25.6 kHz.
- Enumerate full 2-second windows with a 1-second hop within each recording.

The loader expects explicit N x 5 orientation. MATLAB 7.3 containers with reversed storage axes require an explicit schema extension before admission. The inspected source files use classic MAT format.

Preparation is offline and uses a common-start assumption based on the source paper. Its polyphase FIR uses samples on both sides of a point; live streaming requires a separately tested stateful implementation and delay accounting.

Feature selection, baseline fitting, HI normalization, smoothing, status thresholds, model comparison and the new dashboard are subsequent stages. Their parameters will be chosen using the agreed training/calibration protocol.

The first dataset audit evaluates the paper's nominal recording durations. Any shorter stored recording must have its actual duration documented before admission.


## Candidate feature stage
The next completed stage freezes grouped_v1 before numerical extraction and produces candidate_v1 arrays from all 32 admitted inputs. See evaluation_design.md and feature_catalog.md. Fixed extraction is independent of labels and fitted statistics; labels remain separate metadata. Selecting features, covariance estimation and HI calibration remain subsequent work.

## First fitted Python model
The subsequently completed model stage implements model_protocol_v1 and evaluates the frozen operating-group rounds. Feature reduction, scaling and covariance are fitted only on healthy fitting records; calibration and EWMA thresholds use separate healthy records. Full score definitions, model-state serialization and limitations are in model_protocol_v1.md. model_results_v1.md records the false-alarm findings; earlier stage descriptions above remain historical.
