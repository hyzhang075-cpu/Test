from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.replay_end5cm_groupwise import (
    curvature_tail_metrics,
    summarize_variant_timeline,
)


def test_curvature_tail_metrics_integrates_scalar_and_vector_turning():
    x = np.linspace(0., .1, 101)
    magnitude = np.full_like(x, np.pi / .05)
    angle = np.zeros_like(x)

    result = curvature_tail_metrics(x, magnitude, angle, tail_length_m=.05)

    assert result['scalar_integral_deg'] == pytest.approx(180., rel=1e-6)
    assert result['vector_integral_deg'] == pytest.approx(180., rel=1e-6)
    assert result['max_curvature_m_inv'] == pytest.approx(np.pi / .05)


def test_curvature_tail_metrics_vector_integral_cancels_opposite_directions():
    x = np.linspace(0., .05, 101)
    magnitude = np.ones_like(x) * 20.
    angle = np.where(x < .025, 0., np.pi)

    result = curvature_tail_metrics(x, magnitude, angle, tail_length_m=.05)

    assert result['scalar_integral_deg'] == pytest.approx(20. * .05 * 180. / np.pi, rel=1e-6)
    assert result['vector_integral_deg'] < 1.0


def test_summarize_variant_timeline_reports_peak_threshold_and_post_peak_residual():
    rows = [
        {'elapsed_s': 0., 'scalar_integral_deg': 10., 'vector_integral_deg': 8., 'max_curvature_m_inv': 1.},
        {'elapsed_s': 1., 'scalar_integral_deg': 200., 'vector_integral_deg': 150., 'max_curvature_m_inv': 2.},
        {'elapsed_s': 2., 'scalar_integral_deg': 40., 'vector_integral_deg': 30., 'max_curvature_m_inv': 3.},
        {'elapsed_s': 3., 'scalar_integral_deg': 20., 'vector_integral_deg': 10., 'max_curvature_m_inv': 4.},
    ]

    summary = summarize_variant_timeline(rows, over_threshold_deg=180.)

    assert summary['peak_frame'] == 1
    assert summary['over_180_fraction'] == pytest.approx(.25)
    assert summary['post_peak_residual']['scalar_integral_deg'] == pytest.approx(30.)
    assert summary['post_peak_residual']['vector_integral_deg'] == pytest.approx(20.)
