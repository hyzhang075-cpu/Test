"""Small full-only parameter trial using unchanged production reconstruction.

This is an auxiliary parameter search, not main.py --task optim.
Local-region parameters in its output remain unvalidated after the 9-segment change.
"""
import contextlib
import io
import json
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main
from calibration_batch import optimizer_parameters
from optimiser import Optimiser

SOURCE = ROOT / 'params/09B7_20261102_full9_seed.json'
OUTPUT = ROOT / 'params/09B7_20261102_full_under1_trial.json'
REPORT = ROOT / 'docs/09B7-20261102-full-parameter-refine.json'
p = json.loads(SOURCE.read_text(encoding='utf-8'))
with contextlib.redirect_stdout(io.StringIO()):
    args = main.parse_main_args(['--task','recon','--sensor_params',str(SOURCE),
        '--multi_region_calib','False','--optimization_region','full',
        '--use_full_transported_phase','False','--exp_directs','[0,120,240]'])
    args.use_stored_zero = False
    main.configure_calibration_args(args)
    obj = Optimiser(**optimizer_parameters(args))

report = {'source':str(SOURCE), 'production_optimizer_modified':False,
    'basis':'unchanged production standalone full recon; each mean normalized by full evaluation length',
    'search':'minimize max(mean point ratio, mean end ratio); first-segment slope offset and uniform weight multiplier, then six per-level weight factors if needed',
    'rot_ang':float(obj.rot_ang), 'directions':{}}

for direct in (0,120,240):
    base_s = np.asarray(obj.slopes[direct]).copy()
    base_w = np.asarray(obj.weights[direct]).copy()
    evaluations = [0]

    def evaluate(x):
        slopes = base_s.copy()
        slopes[:,0] += float(x[0])
        obj.slopes[direct] = slopes
        obj.weights[direct] = base_w * float(x[1])
        rs = {}
        for shape in obj.calib_shapes:
            rs[shape], dist = obj.reconstruct_shapes(calib_shape=shape,direct=direct,verbose=False)
        obj._compute_error(interp_dist=dist,rs=rs)
        return {'point_ratio':float(obj.avg_point_err['calib']), 'end_ratio':float(obj.avg_end_err['calib'])}

    before = evaluate([0.,1.])
    selected = np.asarray([0.,1.])
    if max(before.values()) > .01:
        def loss(x):
            m = evaluate(x)
            evaluations[0] += 1
            if evaluations[0] % 100 == 0:
                print(json.dumps({'direct':direct,'evaluations':evaluations[0],'metrics':m}),flush=True)
            return max(m.values())
        fit = minimize(loss, selected, method='Powell', bounds=[(-2.,2.),(.9,1.1)],
            options={'maxiter':80,'xtol':1e-5,'ftol':1e-6})
        candidate = evaluate(fit.x)
        if max(candidate.values()) < max(before.values()):
            selected = fit.x.copy()
    after = evaluate(selected)
    level_multipliers = np.ones_like(base_w)
    if max(after.values()) > .01:
        fixed_s = obj.slopes[direct].copy()
        fixed_w = obj.weights[direct].copy()
        fixed_metrics = dict(after)

        def evaluate_levels(factors):
            obj.slopes[direct] = fixed_s.copy()
            obj.weights[direct] = fixed_w * np.asarray(factors)
            rs = {}
            for shape in obj.calib_shapes:
                rs[shape], dist = obj.reconstruct_shapes(calib_shape=shape,direct=direct,verbose=False)
            obj._compute_error(interp_dist=dist,rs=rs)
            return {'point_ratio':float(obj.avg_point_err['calib']), 'end_ratio':float(obj.avg_end_err['calib'])}

        def level_loss(factors):
            metrics = evaluate_levels(factors)
            evaluations[0] += 1
            if evaluations[0] % 100 == 0:
                print(json.dumps({'direct':direct,'stage':'six weight levels','evaluations':evaluations[0],'metrics':metrics}),flush=True)
            return max(metrics.values())

        fit_levels = minimize(level_loss, level_multipliers, method='Powell',
            bounds=[(.95,1.05)]*len(base_w), options={'maxiter':60,'xtol':1e-6,'ftol':1e-7})
        candidate = evaluate_levels(fit_levels.x)
        if max(candidate.values()) < max(fixed_metrics.values()):
            level_multipliers = fit_levels.x.copy()
        after = evaluate_levels(level_multipliers)
    p['regions']['full']['slopes'][str(direct)] = obj.slopes[direct].tolist()
    p['regions']['full']['weights'][str(direct)] = obj.weights[direct].tolist()
    row = {'before':before,'after':after,'first_segment_slope_offset_rad_per_m':float(selected[0]),
        'weight_multiplier':float(selected[1]), 'per_level_weight_multipliers':level_multipliers.tolist(),
        'evaluations':evaluations[0],
        'point_and_end_within_1pct':bool(max(after.values()) <= .01)}
    report['directions'][str(direct)] = row
    print(json.dumps({'direct':direct,**row}),flush=True)

report['all_directions_within_1pct'] = all(x['point_and_end_within_1pct'] for x in report['directions'].values())
p['regions']['full']['errors'] = {}
p['regions']['full']['optimization'] = {}
p['provenance']['full_parameter_refine'] = {'source':str(SOURCE),'report':str(REPORT),
    'local_regions_validated':False,'description':report['search']}
OUTPUT.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'output':str(OUTPUT),'all_directions_within_1pct':report['all_directions_within_1pct']}),flush=True)
