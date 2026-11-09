from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from calibration_batch import summarize_score_runs


def sample(radius, median, masses):
    return {
        'shape': 'circ', 'keys': [radius], 'direct': 0,
        'theoretical_curvature_m_inv': 0 if radius == 0 else 1000 / radius,
        'global_point_ids': [19, 20, 21, 22],
        'score_magnitude': [median] * 4,
        'scores': [[0.1] * 4], 'masses': [[value] * 4 for value in masses],
        'quantiles': {'min': median, 'p10': median, 'median': median,
                      'p90': median, 'max': median},
        'mean_level_mass': masses, 'tip_level_mass': masses,
    }


def report(direct):
    rows = [sample(30, 25.0, [0.0, 0.1, 0.9]),
            sample(20, 32.0, [0.0, 0.1, 0.9]),
            sample(15, 34.0, [0.0, 0.1, 0.9])]
    for row in rows:
        row['direct'] = direct
    return {
        'direct': direct,
        'regions': {'end5cm': {'status': 'complete', 'score_distribution': {
            'basis': 'strain base magnitude before weights; magnitude_ratio=1.0',
            'thresholds': [20, 35], 'sharpness': 4.8, 'score_window': 3,
            'boundary_mode': 'constant', 'sigmoid_10_90_width_m_inv': .9155,
            'samples': rows,
        }}},
    }


def test_summary_preserves_measured_fields_and_flags_indistinguishable_radii():
    summary = summarize_score_runs([report(240), report(0), report(120)])

    assert summary['directions'] == [0, 120, 240]
    block = summary['regions']['end5cm']
    assert block['thresholds'] == [20, 35]
    assert block['sigmoid_10_90_width_m_inv'] == .9155
    row = block['directions']['120']['samples'][0]
    assert row['radius_mm'] == 30
    assert row['global_point_ids'] == [19, 20, 21, 22]
    assert row['quantiles']['median'] == 25.0
    assert row['mean_level_mass'] == [0.0, 0.1, 0.9]
    assert row['tip_level_mass'] == [0.0, 0.1, 0.9]
    assert block['directions']['0']['high_curvature_separable'] is False


def test_summary_uses_literal_directions_and_rejects_incomplete_runs():
    bad = [report(0), report(120), report(240)]
    bad[2]['regions']['end5cm']['status'] = 'failed'
    try:
        summarize_score_runs(bad)
    except ValueError as exc:
        assert '240/end5cm' in str(exc)
    else:
        raise AssertionError('incomplete score run was accepted')
