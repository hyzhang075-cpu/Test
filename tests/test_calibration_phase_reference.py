"""Fixed phase transport excludes straight states and pins bridge slopes."""
from types import SimpleNamespace
import numpy as np
import pytest

from calibration_phase_reference import build_fixed_phase_reference, apply_full_bridge_slopes


def sensor(ids, distances, phase, slopes, frames):
    result = SimpleNamespace(global_point_ids=np.array(ids), samp_dist=np.array(distances),
                             global_phases_set=phase, slopes={0:np.array([slopes])},
                             base_segments=[(0,len(ids))], processed_Data={'circ':{0:frames}})
    result._get_base=lambda **kwargs: (None,np.ones(len(ids)),None,None)
    result._get_scores=lambda **kwargs: np.empty((0,len(ids)))
    result._alloc_mass=lambda scores: np.ones((1,len(ids)))
    return result


def test_fixed_reference_uses_bent_states_and_full_zero_level_bridge():
    full=sensor([1,2,3,4],[0,.1,.2,.3],.2,[2.],{0:None,200:None,300:None})
    context={'global_point_ids':[3,4], 'global_sample_dist_m':[.2,.3], 'crop_origin_m':.15}
    reference=build_fixed_phase_reference(full,full,context,0)
    assert reference['source_radii_mm']==[200,300]
    assert reference['phase_at_crop_origin_rad']==pytest.approx(.5)
    assert reference['phase_at_first_point_rad']==pytest.approx(.6)
    assert reference['bridge_slope_rad_per_m']==2.
    full.processed_Data['circ'][0]={0:None}
    with pytest.raises(ValueError,match='nonzero'):
        build_fixed_phase_reference(full,full,context,0)


def test_end5_reference_includes_upstream_end15_phase():
    full=sensor([1,2,3,4],[0,.1,.2,.3],.2,[2.],{200:None})
    upstream=sensor([2,3,4],[.02,.12,.22],1.,[3.],{0:None,30:None})
    context={'global_point_ids':[4], 'global_sample_dist_m':[.3], 'crop_origin_m':.25}
    reference=build_fixed_phase_reference(full,upstream,context,0)
    assert reference['phase_at_first_point_rad']==pytest.approx(1.5)


def test_bridge_override_changes_only_region_start_intervals():
    config={'regions':{'full':{'support_point_ids':[1,2,3,4], 'local_segmentation':np.array([2,2]),
                              'slopes':{0:np.array([[2.,4.],[10.,20.]])}},
                       'end15cm':{'support_point_ids':[3,4]}}, 'region_order':['full','end15cm']}
    values=np.array([10.,10.,30.,40.])
    apply_full_bridge_slopes(values,config,[1,2,3,4],0)
    np.testing.assert_allclose(values,[10.,10.,4.,40.])
