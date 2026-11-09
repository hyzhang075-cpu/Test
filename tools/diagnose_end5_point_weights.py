"""Compare bounded weight layouts on recorded real-point calibration scores."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import lsq_linear


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--scores', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = json.loads(args.results.read_text(encoding='utf-8'))
    score_result = json.loads(args.scores.read_text(encoding='utf-8'))
    entry = result['regions']['end5cm']
    score_entry = score_result['regions']['end5cm']
    direct = result['direct']
    if direct != score_result['direct']:
        raise ValueError('Score and optimization directions differ')
    for key in ('thresholds', 'radii', 'global_point_ids'):
        if entry['context'][key] != score_entry['context'][key]:
            raise ValueError(f'Score and optimization contexts differ: {key}')
    for key in ('sharpness', 'min_consecutive', 'R', 'active_angles', 'interlaced_grating'):
        if entry['configuration'][key] != score_entry['configuration'][key]:
            raise ValueError(f'Score and optimization configurations differ: {key}')
    if (entry['configuration']['active_angles'] is not None
            or entry['configuration']['interlaced_grating']):
        raise ValueError('This linear diagnostic requires uniform outer channels')
    samples = [s for s in score_entry['score_distribution']['samples']
               if s['shape'] == 'circ' and s['keys'][0] > 0]
    base = np.array([s['score_magnitude'] for s in samples])
    masses = np.array([s['masses'] for s in samples])
    targets = np.array([s['theoretical_curvature_m_inv'] for s in samples])
    levels = masses.shape[1]
    points = base.shape[1]
    if points != 4 or entry['context']['global_point_ids'] != [19, 20, 21, 22]:
        raise ValueError('Expected end5cm points19–22')
    weights = np.array(entry['parameters']['weights'][str(direct)])
    effective = np.einsum('rlp,l->rp', masses, weights[:levels])
    groups = entry['context'].get('weight_group_ids')
    if groups is not None:
        point_weights = weights.reshape(-1,levels)[np.asarray(groups)].T
        effective = np.sum(masses * point_weights[None,:,:],axis=1)
    elif entry['context']['end_weights']:
        effective[:, entry['context']['end_start']:] = np.einsum(
            'rlp,l->rp', masses, weights[levels:])[:, entry['context']['end_start']:]
    current = base * effective
    loss = float(np.mean((current/targets[:, None]-1.)**2))
    stored_loss = entry['optimization']['stages']['weights']['final_loss']
    if not np.isclose(loss, stored_loss, atol=1e-10, rtol=1e-8):
        raise ValueError(f'Scores do not reproduce optimization loss: {loss} != {stored_loss}')
    bounds = entry['configuration']['weight_bounds']
    comparisons = {}
    for name, groups in [('end_start_minus1', [0, 0, 0, 1]),
                         ('end_start_minus2', [0, 0, 1, 1]),
                         ('independent_21_22', [0, 0, 1, 2])]:
        design = np.zeros((base.size, (max(groups)+1)*levels))
        for r in range(len(samples)):
            for p, group in enumerate(groups):
                design[r*points+p, group*levels:(group+1)*levels] = (
                    base[r,p]/targets[r]*masses[r,:,p])
        fit = lsq_linear(design, np.ones(base.size), bounds=bounds,
                         tol=1e-12, max_iter=1000)
        relative = (design @ fit.x).reshape(base.shape) - 1.
        compensated = (relative+1.) * targets[:,None]
        comparisons[name] = {
            'success': bool(fit.success), 'parameter_count': len(fit.x),
            'design_rank': int(np.linalg.matrix_rank(design)),
            'relative_curvature_rmse_percent': float(np.sqrt(np.mean(relative**2))*100),
            'per_point_relative_rmse_percent': (np.sqrt(np.mean(relative**2,axis=0))*100).tolist(),
            'weights_by_group': fit.x.reshape(-1, levels).tolist(),
            'lower_hits': int(np.isclose(fit.x,bounds[0],atol=1e-4,rtol=0).sum()),
            'upper_hits': int(np.isclose(fit.x,bounds[1],atol=1e-4,rtol=0).sum()),
            'compensated_curvature_by_radius': {
                str(s['keys'][0]): compensated[r].tolist() for r,s in enumerate(samples)},
        }
    report = {
        'direction': direct, 'global_point_ids': [19,20,21,22],
        'basis': 'Actual CSV score task, reproduced real-point optimization loss; amplitude-only bounded in-sample least squares, no geometry optimization or generalization claim.',
        'weight_bounds': bounds, 'reproduced_loss': loss, 'stored_loss': stored_loss,
        'current_relative_curvature_rmse_percent': float(np.sqrt(loss)*100),
        'current_per_point_relative_rmse_percent': (
            np.sqrt(np.mean((current/targets[:,None]-1.)**2,axis=0))*100).tolist(),
        'samples': [{
            'radius_mm': s['keys'][0], 'theory_curvature': targets[r],
            'base_curvature': base[r].tolist(), 'effective_weight': effective[r].tolist(),
            'compensated_curvature': current[r].tolist(),
            'relative_error_percent': ((current[r]/targets[r]-1.)*100).tolist(),
            'required_weight': (targets[r]/base[r]).tolist(),
        } for r,s in enumerate(samples)],
        'layouts': comparisons,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'analysis.json').write_text(json.dumps(report, indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('samples','layouts')},indent=2))
    for name, fit in comparisons.items():
        print(name, fit['success'],fit['relative_curvature_rmse_percent'],
              fit['per_point_relative_rmse_percent'])


if __name__ == '__main__':
    main()
