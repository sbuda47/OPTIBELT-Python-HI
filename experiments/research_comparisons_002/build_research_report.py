import json,hashlib,platform,os
from pathlib import Path
import pandas as pd
P=Path(__file__).resolve().parents[2];R=P/'outputs/runs/research_comparisons_002';S=P/'outputs/runs/streaming_experiment_001'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(df,columns):
 lines=['| '+' | '.join(title for _,title in columns)+' |','|'+'|'.join('---' for _ in columns)+'|']
 for _,row in df.iterrows():
  cells=[]
  for key,_ in columns:
   v=row[key];cells.append(str(round(v,4)) if isinstance(v,float) else str(v))
  lines.append('| '+' | '.join(cells)+' |')
 return '\n'.join(lines)
def main():
 for folder in [R,S]:
  run=json.loads((folder/'run.json').read_text());assert run['status']=='complete'
  for name,digest in run['artifacts'].items():assert sha(folder/name)==digest,name
 summary=pd.read_csv(R/'summary.csv');ablation=summary[(summary.scope=='check')&(~summary.variant.str.startswith(('window_','native_')))]
 sampling=summary[summary.variant.str.startswith(('window_','native_'))]
 cols=[('variant','Variant'),('selected_features','Retained features'),('healthy_decisions','Healthy decisions'),('healthy_warning_records','Healthy non-normal /17'),('healthy_request_records','Healthy critical requests /17'),('fault_non_normal_records','Fault non-normal /11'),('fault_request_records','Fault critical requests /11')]
 stream=pd.read_csv(S/'comparisons.csv');down=stream[stream.phase=='downstream'];chunk=pd.read_csv(S/'chunk_timing.csv');feat=pd.read_csv(S/'feature_md_timing.csv')
 combined=chunk.groupby(['recording_id','chunk']).compute_seconds.sum()*1000;fm=feat.compute_seconds*1000
 hf=pd.read_csv(R/'current_high_frequency_power.csv')
 # Reconcile summaries independently from per-record metrics, including denominator consistency.
 for file in ['ablation_metrics.csv','sensitivity_metrics.csv']:
  d=pd.read_csv(R/file)
  assert not d.duplicated(['variant','scope','recording_id']).any()
  for (v,scope),g in d.groupby(['variant','scope']):
   assert len(g)==28
   h=g[g.condition=='normal'];f=g[g.condition!='normal'];s=summary[(summary.variant==v)&(summary.scope==scope)].iloc[0]
   assert len(h)==17 and len(f)==11
   assert int(h.request.sum())==s.healthy_request_records and int(f.request.sum())==s.fault_request_records
   assert int(h.decision_steps.sum())==s.healthy_decisions
  if file=='sensitivity_metrics.csv':
   assert d.groupby('recording_id').decision_steps.nunique().eq(1).all()
   # Every variant uses identical saved healthy calibration window end times.
   baseline=json.loads((R/'models/window_2s_matched.json').read_text())['calibration']
   baseline={v['recording_id']:[i+2 for i in v['indices']] for v in baseline}
   for label,L in [('window_1s',1),('window_4s',4),('native_2s_fullband',2)]:
    entries=json.loads((R/f'models/{label}.json').read_text())['calibration']
    assert all([i+L for i in e['indices']]==baseline[e['recording_id']] for e in entries)
 text=f'''# Three HI research investigations

8 November 2026. Frozen deployment release: hi_candidate_v1 / operator_zones_v1. Research runs: research_comparisons_002 and streaming_experiment_001. **These are controlled development experiments on exposed data, not independent-acquisition validation. The deployed model is unchanged.**

## 1. Does sensor and feature fusion justify its complexity?

Same 28-record cohort, 17 healthy records supply guarded temporal fit/calibration blocks, and 11 fault records are evaluated. Each feature subset is refitted and recalibrated using the same healthy-only procedure; reusing a 60-feature threshold with a smaller model would not be comparable. Feature selection never uses fault/check outcomes. Full models reproduce the frozen A/C scores and thresholds. The common policy is EWMA alpha .2, ten warm-up windows, HI boundary 60/25, recovery 65/30 and three-second confirmation. Global calibration remains the maximum healthy three-window-minimum event level; this is a fixed procedure, not an independently established false-alarm probability.

{table(ablation,cols)}

Each check variant has 570 healthy and 255 fault eligible decision steps. All have zero healthy critical requests, but warnings and missed critical requests differ. Fusion reaches 10/11 critical requests and 11/11 non-normal indications, versus 4/11 critical requests for either vibration-only or current-only. Vibration plus torque retains 17 features instead of 36, yields 9/11 critical requests and 11/11 non-normal indications, and no healthy warning records in the check scope. It misses critical confirmation on the coil case and Misalign0p3mm_3HP_0%_52Hz. Full fusion catches that misalignment case.

The compact model retains 16 features and reaches 8/11 critical requests. Time-only reaches 9/11, but its missed cases differ from full fusion: it catches the low-severity coil case while missing Bearing_3HP_30%_58Hz and Misalign0p3mm_3HP_0%_52Hz. Diagonal covariance reaches 5/11 compared with full fusion's 10/11 under this procedure. These results support retaining the current fusion/covariance candidate for now, with vibration+torque as a worthwhile simpler comparator. They do not prove universal superiority or optimize feature count, pruning threshold or shrinkage strength.

Full-record replay is also saved, but includes fitting and calibration data and is secondary. Full fusion has four healthy warning records and ten critical fault requests; vibration+torque has one healthy warning record and nine critical fault requests. Do not replace held-check numbers with these more exposed full-record outcomes.

## 2. Sampling and window sensitivity

The alternatives below all use identical guarded window END times, with enough space for the longest four-second window. This gives the same eligibility and calibration timestamps across variants. Consequently these check denominators differ from section 1; compare within this table. Hop remains one second, so EWMA alpha and warm-up update count do not change. Each alternative is fitted and calibrated separately on the same healthy roles. No variant is deployed based on this comparison.

{table(sampling,cols)}

The native-rate/full-band variant retains current at 100 kHz and vibration/torque at 25.6 kHz, combining equal-duration features rather than equally sampled signals. Current centroids and band denominators extend to 50 kHz and include an additional high-frequency fraction. This changes bandwidth and time statistics together, so it is not an isolated causal test of sample rate. The range of per-record/per-phase **median** current power above 12.8 kHz is {hf.median_fraction_above_12800.min()*100:.6f}% to {hf.median_fraction_above_12800.max()*100:.6f}%; the largest individual-window fraction is {hf.max_fraction_above_12800.max()*100:.6f}%. Low power alone does not prove absence of diagnostic information.

With one-second updates and the existing ten-window warm-up, nominal first-score times are 1/2/4 seconds for 1/2/4-second windows. Earliest critical requests, assuming immediately critical eligible scores, are 14/15/17 seconds respectively. Reducing window length from two seconds to one saves one second at startup; it does not remove the warm-up and confirmation policy. Fault onset is unknown, so these recordings cannot establish physical detection latency or timely intervention. Native-rate processing does not inherently require resampling for feature-level fusion.

## 3. Streaming equivalence and compute timing

An experimental bounded-history current resampler uses the same FIR coefficients and waits for the necessary input before emitting an output. Interior outputs match offline resampling with maximum absolute difference {stream.interior_max_abs_error.max():.3g}. Chunk-invariance checks passed for 137, 10,000 and 50,000 input samples; nonfinite input is rejected without advancing state. The check of equal prefixes confirms emitted outputs do not depend on later chunks.

Live startup extrapolates from the first two samples. The original offline line padding uses the final recording endpoint, which is unavailable at startup. Therefore the first eleven common-rate samples are compared as a deliberate boundary difference, not asserted identical. The maximum startup sample difference across the measured trials is {stream.startup_max_abs_error.max():.6g} stored units. After the first window, extracted features match numerically. The first-window difference propagates briefly through EWMA, but maximum HI difference over the six 30-second trials is {down.maximum_hi_difference.max():.6g} points. All six have the same alarm states and requests in the paired live/offline-prefix replay.

These comparisons use offline processing of the same 30-second prefixes, including their endpoint convention. They do not claim that flushing a truncated prefix reproduces filtering the entire original recording at that boundary. The maximum measured input buffer is {int(stream.peak_buffer_samples.max())} samples per phase, including the incoming 10,000-sample chunk. This verifies bounded filter history; the experiment harness stores outputs for comparison and is not a fully integrated streaming dashboard.

Compute-only observations on this workstation, while the other experiment was also running:

| Operation | Median | 95th percentile | Maximum |
|---|---:|---:|---:|
| Three current phases, summed per 100 ms input-chunk index | {combined.median():.2f} ms | {combined.quantile(.95):.2f} ms | {combined.max():.2f} ms |
| Five-channel features plus MD, per one-second update | {fm.median():.2f} ms | {fm.quantile(.95):.2f} ms | {fm.max():.2f} ms |

Current phases were timed separately and summed by matching chunk index; this is not a measured integrated acquisition-loop latency. Feature/MD timing uses three repetitions per window and excludes file loading. Reported computation fits the sampled data-arrival budgets on this workstation, but neither a worst-case bound nor a target-device guarantee has been established. Runtime versions and host details are in the streaming run manifest.

Interior FIR look-ahead is approximately 0.391 ms. With 100 ms input batching, scheduling adds up to roughly a chunk interval before the required sample is delivered; compute, acquisition, network and UI delays are additional. A live implementation must align native vibration/torque buffers with delayed current outputs. This prototype does not measure acquisition clocks, network/UI/operator response, hardware power or motor stopping. It is not deployed.

## Evidence and reproducibility

Protocols were saved before evaluation. Calibration models and thresholds were saved before check scoring. The original sequential extraction was resumed with three workers without changing formulas or hypotheses; previously completed feature artifacts were reused with hashes recorded in reused_features.json. The interrupted run remains preserved as research_comparisons_001. Timing from parallel extraction is not used as a controlled performance comparison.

The completed comparison run retains models, feature arrays, per-window predictions, per-record metrics, summary.csv, extraction_timing.csv and current_high_frequency_power.csv. The streaming run retains sample/downstream comparisons, chunk timing, feature/MD timing, paired predictions and the prototype. Input file hashes and frozen release checks are enforced. This report's check also reconciles record counts, summary outcomes and matched calibration timestamps. Hash manifests make each output inspectable. No independent statistical trials are inferred from overlapping windows.

The research questions now have measured development answers: fusion has an observed sensitivity/complexity trade-off; alternative windows and native-rate features have paired results; buffered streaming is feasible in the tested prototype with explicit boundary differences. Independent acquisitions, physical calibration/synchronization and operational alarm tolerances remain unresolved.
'''
 dest=Path(__file__).with_name('research_report.md');dest.write_text(text,encoding='utf-8')
 print('Report built; summary and matched timestamp checks passed.')
if __name__=='__main__':main()
