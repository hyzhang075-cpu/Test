import pytest

import main


def single_args(direct=0, *extra):
    return main.parse_main_args([
        '--task', 'recon', '--multi_region_calib', 'False',
        '--optimization_region', 'end5cm', '--direct', str(direct),
        '--weights', repr({direct: [1.] * 20}),
        '--slopes', repr({direct: [[0., 0.]] * 10}),
        '--global_phases_set', '.6969803684104529', *extra,
    ])


@pytest.mark.parametrize('direct', [0, 120, 240])
def test_single_region_recon_only_requires_requested_direction(direct):
    args = single_args(direct)
    main.configure_calibration_args(args)
    assert args.exp_directs == [direct]
    assert list(args.weights) == [direct]
    assert args.weights[direct].shape == (20,)
    assert args.slopes[direct].shape == (10, 2)


def test_exp_directs_cli_parses_integer_angles():
    args = single_args(0, '--exp_directs', '[0]')
    assert args.exp_directs == [0]
    main.configure_calibration_args(args)


def test_explicit_direction_scope_is_preserved_and_validated():
    args = single_args(0, '--exp_directs', '[0,120,240]')
    with pytest.raises(ValueError, match='缺少方向 120'):
        main.configure_calibration_args(args)
    args = single_args(0, '--exp_directs', '[120]')
    with pytest.raises(ValueError, match='direct.*exp_directs'):
        main.configure_calibration_args(args)


def test_optimization_keeps_default_three_direction_scope():
    args = main.parse_main_args(['--task','optim','--optimization_region','end5cm'])
    main.configure_calibration_args(args)
    assert args.exp_directs == [0,120,240]
