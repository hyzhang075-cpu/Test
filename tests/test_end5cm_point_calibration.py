import numpy as np
import pytest

from optimiser import Optimiser


def point_optimizer():
    o = Optimiser.__new__(Optimiser)
    o.direct = 0
    o.end5cm_point_calib = True
    o.calib_shapes = ['circ']
    o.radii = {0: {'circ': [0, 30, 15]}}
    o.total_points = 4
    o.num_channels_recon = 3
    o.R = .0001
    o.active_angles = None
    o.interlaced_grating = False
    o.global_phases_set = .3
    o.samp_dist = np.array([.007, .018, .029, .040])
    o.base_segments = [(0, 2), (2, 4)]
    o.num_segments = 2
    o.num_levels = 2
    o.thresholds = [100.]
    o.min_consecutive = 1
    o.sharpness = 4.8
    o.soft = True
    o.end_weights = False
    o.end_mask = np.array([False, False, False, True])
    o.turn_threshold = 2.
    o.discont = np.pi
    o.multi_region_parameters = None
    o.weights = {0: np.ones(2)}
    o.slopes = {0: np.zeros((2, 2))}
    o.slopes_shape = (2, 2)
    theta = np.arange(3) * 2*np.pi/3
    o.processed_Data = {'circ': {0: {
        radius: np.tile(-o.R*(1000/radius)*np.cos(theta), (4, 1))
        for radius in (30, 15)
    }}}
    o.processed_Data['circ'][0][0] = np.full((4, 3), np.nan)
    return o


def test_direction_loss_uses_real_points_and_ignores_straight_sample():
    o = point_optimizer()
    assert o._real_point_loss(direction_only=True) == pytest.approx(0., abs=1e-12)
    o.slopes[0][:] = 30.
    assert o._real_point_loss(direction_only=True) > .1


def test_direction_loss_is_circular_and_keeps_reference_phase_fixed():
    o = point_optimizer()
    phase = o.global_phases_set
    o.slopes[0][:] = 10.
    before = o._real_point_loss(direction_only=True)
    o.global_phases_set += 2*np.pi
    assert o._real_point_loss(direction_only=True) == pytest.approx(before)
    assert o.global_phases_set == phase + 2*np.pi


def test_amplitude_loss_uses_known_radius_not_geometry_or_virtual_tip():
    o = point_optimizer()
    assert o._real_point_loss(direction_only=False) == pytest.approx(0., abs=1e-12)
    o.weights[0][:] = .8
    assert o._real_point_loss(direction_only=False) == pytest.approx(.04)
    o.slopes[0][:] = 40.
    assert o._real_point_loss(direction_only=False) == pytest.approx(.04)


def test_amplitude_loss_keeps_dual_weight_layout():
    o = point_optimizer()
    o.end_weights = True
    o.weights[0] = np.array([1., 1., 2., 2.])
    assert o._real_point_loss(direction_only=False) == pytest.approx(.25)


def test_new_loss_dispatch_keeps_two_stages():
    o = point_optimizer()
    flat = np.full(4, .2)
    direction = o._loss_fn(0, np.ones(2), flat, 50., force_ideal_magnitude=True)
    amplitude = o._loss_fn(0, np.full(2, .8), flat, 50., force_ideal_magnitude=False)
    assert direction > 0
    assert amplitude == pytest.approx(.04)


@pytest.mark.parametrize('radii', [[0], [0, -15], [0, float('nan')]])
def test_rejects_invalid_or_missing_nonzero_radius(radii):
    o = point_optimizer()
    o.radii[0]['circ'] = radii
    with pytest.raises(ValueError):
        o._real_point_loss(direction_only=False)


def test_flag_only_reaches_end5cm_optimizer():
    import main
    from calibration_batch import optimizer_parameters
    assert main.parse_main_args(['--task', 'optim']).end5cm_point_calib is False
    for region in ('full', 'end15cm', 'end5cm'):
        args = main.parse_main_args(['--task', 'optim', '--end5cm_point_calib', 'True',
                                     '--optimization_region', region])
        context = main.configure_calibration_args(args)
        assert optimizer_parameters(args)['end5cm_point_calib'] is (region == 'end5cm')
        assert context['calibration_objective'] == ('real_points' if region == 'end5cm' else 'geometry')
    assert main.parse_main_args(['--task','optim','--end5cm_point_calib','False']).end5cm_point_calib is False


def test_geometry_objective_remains_active_when_flag_is_off(monkeypatch):
    o = point_optimizer()
    o.end5cm_point_calib = False
    monkeypatch.setattr(o, 'reconstruct_shapes', lambda **kw: (None, None))
    monkeypatch.setattr(o, '_compute_error', lambda **kw: None)
    o.k_point, o.k_end, o.k_pitch, o.k_radius = 1., .3, 1., 1.
    o.avg_point_err, o.avg_end_err = {'calib': .02}, {'calib': .03}
    o.avg_pitch_err, o.avg_radius_err = 0., 0.
    assert o._loss_fn(0, np.ones(2), np.zeros(4), 50.) == pytest.approx(.029)


def test_batch_flag_keeps_full_and_end15cm_on_geometry():
    import main
    from calibration_batch import prepare_calibration_jobs, optimizer_parameters
    args = main.parse_main_args(['--task', 'optim', '--multi_region_calib', 'True',
                                 '--end5cm_point_calib', 'True'])
    jobs = prepare_calibration_jobs(args, main.configure_calibration_args)
    assert [optimizer_parameters(job)['end5cm_point_calib'] for job, _ in jobs] == [False, False, True]


def test_point_mode_rejects_non_circular_data_before_loading():
    import main
    args = main.parse_main_args(['--task', 'optim', '--optimization_region', 'end5cm',
                                 '--end5cm_point_calib', 'True', '--radii', "{'S':[15]}"])
    with pytest.raises(ValueError, match='circ'):
        main.configure_calibration_args(args)


def test_three_weight_groups_apply_to_real_points_only():
    o = point_optimizer()
    o.weight_group_ids = [0, 0, 1, 2]
    o.end_weights = True
    o.weights[0] = np.array([1., 1., 2., 2., 3., 3.])
    magnitude, _ = o._Strain_2_Cur([30], 'circ', o.processed_Data['circ'][0],
                                  o.weights[0], o.slopes[0], direct=0)
    np.testing.assert_allclose(magnitude, (1000/30)*np.array([1,1,2,3]))


def test_three_group_cli_and_shape_validation():
    import main
    from calibration_batch import optimizer_parameters
    args = main.parse_main_args(['--task','optim','--optimization_region','end5cm',
        '--end5cm_point_calib','True','--end5cm_independent_weights','True'])
    context = main.configure_calibration_args(args)
    assert context['weight_group_ids'] == [0,0,1,2]
    assert optimizer_parameters(args)['weight_group_ids'] == [0,0,1,2]
    args.weights = {d: [1.]*20 for d in args.exp_directs}
    with pytest.raises(ValueError, match='30'):
        main.configure_calibration_args(args)


def test_freeze_applies_same_level_to_every_weight_group():
    o = point_optimizer()
    o.weight_group_ids = [0,0,1,2]
    o.end_weights = True
    o.weights[0] = np.ones(6)
    o.freeze = [1]
    assert o._get_weight_freeze_mask().tolist() == [False,True,False,True,False,True]
