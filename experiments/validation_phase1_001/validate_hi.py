"""Reproducible, read-only validation of the frozen OPTIBELT HI; fresh output only."""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def close(a, b, label):
    require(np.allclose(a, b, rtol=1e-10, atol=1e-10, equal_nan=True), label)


def independent_states(times, scores, eligible, seconds, hysteresis):
    warning = critical = latched = False
    pending = last = None
    rows = []
    for t, h, valid in zip(times, scores, eligible):
        gap = last is not None and not np.isclose(t-last, 1., rtol=0, atol=1e-9)
        last = t
        if gap:
            pending = None
        data_valid = bool(valid and h is not None and np.isfinite(h))
        elapsed, event, instant = 0., False, None
        if not data_valid:
            pending = None
            zone = 'warming_up' if not valid else 'data_unavailable'
        else:
            warning = (h < 60) or (warning and h < (65 if hysteresis else 60))
            critical = (h < 25) or (critical and h < (30 if hysteresis else 25))
            if h < 25:
                pending = t if pending is None else pending
                elapsed = t-pending
            else:
                pending = None
            event = bool(not latched and pending is not None and elapsed >= seconds)
            latched = latched or event
            zone = 'critical' if critical else 'warning' if warning else 'normal'
            instant = 'critical' if h < 25 else 'warning' if h < 60 else 'normal'
        rows.append(dict(zone_state=zone, instantaneous_zone=instant,
                         data_valid=data_valid, data_gap=bool(gap),
                         critical_elapsed_seconds=elapsed, new_operator_alarm=event,
                         operator_alarm_latched=latched, audible_alarm_requested=latched,
                         motor_stop_command=False))
    return rows


def alarm_contract(OperatorAlarm, operator_hi):
    tests = []
    for duration in (2, 3, 5):
        a = OperatorAlarm(duration, True)
        rows = [a.update(i, 20.) for i in range(duration+1)]
        require([r['new_operator_alarm'] for r in rows] == [False]*duration+[True], 'elapsed timer')
        tests.append(f'{duration}s needs {duration+1} readings')
    a = OperatorAlarm(3, True)
    scores = [60, 59, 60, 64, 65, 24, 25, 29, 30]
    require([a.update(i, h)['zone_state'] for i, h in enumerate(scores)] ==
            ['normal', 'warning', 'warning', 'warning', 'normal', 'critical', 'critical', 'critical', 'warning'], 'boundaries')
    tests.append('60/65 and 25/30 boundaries')
    a = OperatorAlarm(3, True)
    for i, h in enumerate([24, 24, 25, 24, 24, 24]):
        require(not a.update(i, h)['new_operator_alarm'], 'recovery band resets timer')
    require(a.update(6, 24)['new_operator_alarm'], 'restarted elapsed timer')
    tests.append('recovery band cancels pending timer')
    for interruption in ('gap', 'missing', 'warmup'):
        a = OperatorAlarm(3, True)
        a.update(0, 20); a.update(1, 20)
        if interruption == 'gap':
            r = a.update(3, 20); require(r['data_gap'], 'gap flag')
        else:
            r = a.update(2, None if interruption == 'missing' else 20, interruption != 'warmup')
            require(not r['data_valid'], 'invalid eligibility')
            a.update(3, 20)
        require(not a.update(4, 20)['new_operator_alarm'], 'timer crossed interruption')
        require(not a.update(5, 20)['new_operator_alarm'], 'early request after interruption')
        require(a.update(6, 20)['new_operator_alarm'], 'confirmation after interruption')
        a.update(7, None)
        require(a.latched, 'missing cleared latch')
        try:
            a.acknowledge()
        except ValueError:
            pass
        else:
            raise AssertionError('invalid acknowledgement accepted')
        a.update(8, 30)
        require(a.acknowledge() and not a.latched, 'recovered acknowledgement')
        tests.append(interruption+' resets timer; request survives missing data; acknowledgement gated')
    close(operator_hi(np.array([0., 1., np.sqrt(4.5)]), 1.), [100, 60, 25], 'HI anchor points')
    tests.append('HI mapping anchors 100/60/25')
    return tests


def main(project, output):
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, output/'validate_hi.py')
    shutil.copy2(Path(__file__).with_name('protocol.md'), output/'protocol.md')
    run = dict(status='running', started_utc=datetime.now(timezone.utc).isoformat(),
               project=str(project), evidence='exposed-data reproducibility and robustness; not independent validation',
               protocol_sha256=sha(output/'protocol.md'), script_sha256=sha(output/'validate_hi.py'),
               python=sys.version, numpy=np.__version__, pandas=pd.__version__)
    (output/'run.json').write_text(json.dumps(run, indent=2))
    sys.path.insert(0, str(project/'src'))
    from optibelt_hi.deployment.bundle import load_bundle
    from optibelt_hi.deployment.monitor import Monitor, UnsupportedCondition
    from optibelt_hi.alarms.zones import OperatorAlarm, operator_hi
    try:
        integrity = []
        def verify(path, expected, kind):
            actual = sha(path)
            integrity.append(dict(path=str(path), kind=kind, expected=expected, actual=actual, passed=actual == expected))
            require(actual == expected, 'Hash mismatch: '+str(path))

        bundle = load_bundle(project/'outputs/releases/hi_candidate_v1')
        operator_run = json.loads((project/'outputs/runs/operator_zones_001/run.json').read_text())
        for name, files in operator_run['previous_run_hashes'].items():
            for rel, digest in files.items():
                verify(project/'outputs/runs'/name/rel, digest, 'historical_output')
        for rel, digest in operator_run['release_hashes'].items():
            verify(project/'outputs/releases/hi_candidate_v1'/rel, digest, 'frozen_release')
        for rel, digest in operator_run['implementation_sha256'].items():
            verify(project/'src/optibelt_hi'/rel, digest, 'implementation')
        for rel, digest in operator_run['artifacts'].items():
            verify(project/'outputs/runs/operator_zones_001'/rel, digest, 'operator_evaluation')
        raw = pd.read_csv(project/'dataset/manifests/copy_receipt.csv')
        require(len(raw) == 41 and raw.relative_path.is_unique, 'raw inventory changed')
        for i, r in enumerate(raw.to_dict('records')):
            verify(project/r['relative_path'], r['sha256'], 'raw_recording')
            print(f"Raw hash verified {i+1}/41: {Path(r['relative_path']).name}", flush=True)
        raw[raw.sha256.duplicated(keep=False)].to_csv(output/'exact_raw_duplicates.csv', index=False)
        features_run = json.loads((project/'outputs/runs/candidate_features_v1/run.json').read_text())
        for rel, digest in features_run['implementation_sha256'].items():
            verify(project/'src/optibelt_hi'/rel, digest, 'feature_implementation')
        raw_hashes = dict(zip(raw.relative_path, raw.sha256))
        artifacts = {}
        for r in features_run['recordings']:
            path = project/'outputs/runs/candidate_features_v1'/r['artifact']
            verify(path, r['artifact_sha256'], 'feature_artifact')
            require(raw_hashes[r['input']] == r['input_sha256'], 'raw to feature lineage')
            with np.load(path, allow_pickle=False) as z:
                x, bounds, names = z['features'], z['bounds'], z['feature_names'].tolist()
            require(names == bundle['feature_names'], 'feature order')
            require(x.shape == (r['windows'], 60) and np.isfinite(x).all(), 'feature shape/finite')
            require(bounds.shape == (len(x), 2) and np.all(bounds[:, 1]-bounds[:, 0] == 51200), 'window length')
            require(bounds[0, 0] == 0 and np.all(np.diff(bounds[:, 0]) == 25600), 'window continuity')
            artifacts[r['recording_id']] = (x, bounds)
        pd.DataFrame(integrity).to_csv(output/'integrity.csv', index=False)
        routing = pd.read_csv(project/'outputs/runs/load_only_experiment_001/record_routing.csv')
        admission = pd.read_csv(project/'dataset/splits/data_admission.csv')
        require(routing.recording_id.is_unique and admission.recording_id.is_unique, 'recording IDs not unique')
        readiness = routing.merge(admission[['recording_id', 'relative_path', 'sha256', 'reason']], on='recording_id', validate='one_to_one')
        readiness['independent_test_eligible'] = False
        readiness['exposure'] = 'historically inspected; supported check data also used in development'
        readiness.to_csv(output/'recording_readiness.csv', index=False)
        supported = routing[routing.status == 'supported_development']
        require(len(supported) == 28 and len(artifacts) == 32, 'coverage changed')
        unsupported_rejected = []
        for r in routing[routing.status == 'unsupported'].to_dict('records'):
            cond = {k:r[k] for k in ('hp','load','profile','upper')}
            try:
                Monitor(bundle, cond, r['recording_id'])
            except UnsupportedCondition:
                unsupported_rejected.append(r['recording_id'])
            else:
                raise AssertionError('Unsupported condition admitted')
        contracts = alarm_contract(OperatorAlarm, operator_hi)
        old = pd.read_csv(project/'outputs/runs/operator_zones_001/predictions.csv')
        oldmetrics = pd.read_csv(project/'outputs/runs/operator_zones_001/record_metrics.csv')
        olddistance = pd.read_csv(project/'outputs/runs/continuous_calibration_001/predictions.csv')
        olddistance = olddistance[olddistance.policy == 'continuous']
        predictions, metrics, agreement = [], [], []
        for r in supported.to_dict('records'):
            rid = r['recording_id']; x, bounds = artifacts[rid]
            duration = 300 if r['profile'] == 'invariant_speed' else 120
            starts, stops = bounds[:, 0]/25600, bounds[:, 1]/25600
            require(stops[-1] == duration, 'nominal duration mismatch')
            check = (starts >= .75*duration+2) & (stops <= duration-2)
            roles = np.full(len(x), 'guard', dtype=object)
            for name, lo, hi in [('fit',2,.5*duration-2), ('calibration',.5*duration+2,.75*duration-2), ('check',.75*duration+2,duration-2)]:
                roles[(starts >= lo) & (stops <= hi)] = name
            cond = {k:r[k] for k in ('hp','load','profile','upper')}
            for arm in ('A','C'):
                spec = bundle['references'][arm]; model = spec['model']
                offset = np.asarray(bundle['load_centres'][str(r['load'])]) if arm == 'C' else 0.
                z = ((x-offset)[:, model['indices']]-np.array(model['mean']))/np.array(model['scale'])
                squared = np.einsum('ij,ij->i', z, np.linalg.solve(np.asarray(model['covariance']), z.T).T)
                require(np.all(squared >= 0), 'negative quadratic distance')
                all_md = np.sqrt(squared); q = spec['thresholds']['ewma']
                for mode, indices in [('reserved_check_reset', np.flatnonzero(check)), ('full_record', np.arange(len(x)))]:
                    monitor = Monitor(bundle, cond, rid, arm)
                    md = all_md[indices]; smooth = np.empty_like(md)
                    smooth[0] = md[0]
                    for j in range(1, len(md)):
                        smooth[j] = .2*md[j]+.8*smooth[j-1]
                    hi = 100/(1+(2/3)*(smooth/q)**2)
                    eligible = np.arange(len(indices)) >= 10
                    prod = [monitor.push(x[k], int(bounds[k,0]), int(bounds[k,1]), recording_id=rid, feature_names=bundle['feature_names']) for k in indices]
                    close(md, [p['distance'] for p in prod], 'independent MD vs production')
                    close(smooth, [p['distance_ewma'] for p in prod], 'independent EWMA vs production')
                    close(hi, operator_hi(smooth, q), 'independent HI vs production')
                    require(eligible.tolist() == [p['eligible'] for p in prod], 'eligibility')
                    if mode == 'reserved_check_reset':
                        prior = olddistance[(olddistance.recording_id == rid) & (olddistance.arm == arm)].sort_values('original_window_index')
                        require(prior.original_window_index.tolist() == indices.tolist(), 'saved check indices')
                        close(md, prior.distance, 'saved raw MD'); close(smooth, prior.distance_ewma, 'saved EWMA')
                    agreement.append(dict(recording_id=rid, arm=arm, mode=mode, windows=len(indices), maximum_md_absolute_error=float(np.max(np.abs(md-np.array([p['distance'] for p in prod]))))))
                    for hyst in (False, True):
                        for confirm in (2,3,5):
                            independent = independent_states(stops[indices], hi, eligible, confirm, hyst)
                            a = OperatorAlarm(confirm, hyst)
                            states = [a.update(float(t), float(h), bool(e)) for t,h,e in zip(stops[indices],hi,eligible)]
                            for expected, actual in zip(independent, states):
                                require(all(actual[k] == v for k,v in expected.items()), 'independent alarm state')
                            if mode == 'reserved_check_reset':
                                saved = old[(old.recording_id == rid) & (old.arm == arm) & (old.hysteresis == hyst) & (old.confirmation_seconds == confirm)].sort_values('original_window_index')
                                close(hi, saved.operator_hi, 'saved operator HI')
                                for key in ('zone_state','new_operator_alarm','operator_alarm_latched','motor_stop_command'):
                                    require(saved[key].tolist() == [s[key] for s in states], 'saved '+key)
                            base = {k:r[k] for k in ('recording_id','condition','load','hp','profile')}
                            base.update(arm=arm, mode=mode, duration=duration, hysteresis=hyst, confirmation_seconds=confirm)
                            for j,k in enumerate(indices):
                                predictions.append(dict(**base, original_window_index=int(k), stop_seconds=float(stops[k]), historical_interval=roles[k], eligible=bool(eligible[j]), distance=float(md[j]), distance_ewma=float(smooth[j]), operator_hi=float(hi[j]), **states[j]))
                            selections = [(mode, eligible)]
                            if mode == 'full_record':
                                selections += [('check_with_carried_state', eligible & check[indices])]
                            for scope, mask in selections:
                                selected = np.flatnonzero(mask)
                                selected_states = [states[j] for j in selected]
                                zones = [s['zone_state'] for s in selected_states]
                                requests = [j for j in selected if states[j]['new_operator_alarm']]
                                critical = [j for j in selected if states[j]['instantaneous_zone'] == 'critical']
                                m = dict(base, scope=scope, decision_steps=len(selected),
                                         minimum_operator_hi=float(hi[selected].min()),
                                         non_normal_steps=sum(z != 'normal' for z in zones),
                                         warning_steps=zones.count('warning'), critical_steps=zones.count('critical'),
                                         instantaneous_critical_steps=len(critical),
                                         state_transitions=sum(a != b for a,b in zip(zones,zones[1:])),
                                         operator_requests=len(requests),
                                         latched_steps=sum(s['operator_alarm_latched'] for s in selected_states),
                                         first_critical_record_seconds=float(stops[indices[critical[0]]]) if critical else np.nan,
                                         first_request_record_seconds=float(stops[indices[requests[0]]]) if requests else np.nan,
                                         request_seconds_after_first_decision=float(stops[indices[requests[0]]]-stops[indices[selected[0]]]) if requests else np.nan)
                                if scope == 'reserved_check_reset':
                                    prior = oldmetrics[(oldmetrics.recording_id == rid) & (oldmetrics.arm == arm) & (oldmetrics.hysteresis == hyst) & (oldmetrics.confirmation_seconds == confirm)]
                                    require(len(prior) == 1, 'unique saved metric')
                                    for key in ('decision_steps','minimum_operator_hi','non_normal_steps','warning_steps','critical_steps','instantaneous_critical_steps','state_transitions','operator_requests','latched_steps','first_critical_record_seconds','first_request_record_seconds','request_seconds_after_first_decision'):
                                        close(m[key], prior.iloc[0][key], 'saved record metric '+key)
                                metrics.append(m)
            print('Replay verified: '+rid, flush=True)
        pred = pd.DataFrame(predictions); met = pd.DataFrame(metrics)
        pred.to_csv(output/'predictions.csv', index=False)
        met.to_csv(output/'record_metrics.csv', index=False)
        pd.DataFrame(agreement).to_csv(output/'numerical_agreement.csv', index=False)
        summaries = []
        for keys,g in met.groupby(['scope','arm','hysteresis','confirmation_seconds'], sort=True):
            healthy = g[g.condition == 'normal']; fault = g[g.condition != 'normal']
            summaries.append(dict(zip(['scope','arm','hysteresis','confirmation_seconds'],keys),
                healthy_records=len(healthy), fault_records=len(fault),
                healthy_decision_steps=int(healthy.decision_steps.sum()), fault_decision_steps=int(fault.decision_steps.sum()),
                healthy_request_records=int((healthy.operator_requests>0).sum()), fault_request_records=int((fault.operator_requests>0).sum()),
                healthy_non_normal_records=int((healthy.non_normal_steps>0).sum()), fault_non_normal_records=int((fault.non_normal_steps>0).sum()),
                healthy_warning_steps=int(healthy.warning_steps.sum()), healthy_critical_steps=int(healthy.critical_steps.sum()),
                healthy_latched_records=int((healthy.latched_steps>0).sum()), fault_latched_records=int((fault.latched_steps>0).sum())))
        summary = pd.DataFrame(summaries); summary.to_csv(output/'summary.csv', index=False)
        primary = met[(met.arm == 'C') & met.hysteresis & (met.confirmation_seconds == 3)]
        primary.groupby(['scope','condition','hp','load','profile'], dropna=False).agg(
            records=('recording_id','count'),decision_steps=('decision_steps','sum'),
            request_records=('operator_requests','sum'),warning_steps=('warning_steps','sum'),critical_steps=('critical_steps','sum')).reset_index().to_csv(output/'primary_condition_metrics.csv', index=False)
        # Preserve a complete before/after input snapshot, including source receipts and saved evaluation manifests.
        tracked = {row['path']:row['actual'] for row in integrity}
        for rel in ['dataset/manifests/copy_receipt.csv','dataset/splits/data_admission.csv',
                    'outputs/runs/operator_zones_001/run.json','outputs/runs/candidate_features_v1/run.json']:
            tracked[str(project/rel)] = sha(project/rel)
        for path,digest in tracked.items():
            if not str(path).startswith(str(project/'dataset/raw')):
                require(sha(path) == digest, 'Input changed during replay: '+path)
        (output/'inputs.json').write_text(json.dumps(tracked, indent=2))
        run.update(status='complete', completed_utc=datetime.now(timezone.utc).isoformat(),
                   raw_records_verified=len(raw), exact_duplicate_raw_records=int(raw.sha256.duplicated(keep=False).sum()),
                   feature_artifacts_verified=len(artifacts), supported_records=len(supported),
                   unsupported_conditions_rejected=unsupported_rejected, alarm_contract_checks=contracts,
                   saved_record_policy_results_reproduced=len(oldmetrics),
                   independent_calculation_max_abs_md_error=max(v['maximum_md_absolute_error'] for v in agreement),
                   integrity_checks=len(integrity), historical_artifacts_verified=sum(v['kind']=='historical_output' for v in integrity),
                   input_preservation='Non-raw inputs verified before and after; raw hashes verified once at start; no raw writes performed',
                   artifacts={f.name:sha(f) for f in output.iterdir() if f.is_file() and f.name != 'run.json'})
        print(summary[(summary.arm == 'C') & summary.hysteresis & (summary.confirmation_seconds == 3)].to_string(index=False), flush=True)
    except Exception as exc:
        run.update(status='failed', error=repr(exc))
        raise
    finally:
        (output/'run.json').write_text(json.dumps(run, indent=2, allow_nan=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    main(args.project.resolve(), args.output.resolve())
