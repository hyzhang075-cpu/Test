"""Full-data assembly loss for an independent end15cm slope trial."""
from copy import deepcopy
from pathlib import Path
import numpy as np

class End15AssemblyLoss:
    def __init__(self, owner):
        import main
        from optimiser import Optimiser
        from calibration_batch import optimizer_parameters
        source = Path(owner.source_sensor_params).resolve()
        argv = ['--task', 'recon', '--sensor_params', str(source),
                '--multi_region_calib', 'True', '--use_full_transported_phase', 'False',
                '--direct', str(owner.direct), '--exp_directs', str([owner.direct])]
        args = main.parse_main_args(argv)
        args.end15cm_assembly_loss = False
        args.use_stored_zero = False
        data_root = Path(args.calibration_data_root)
        if not data_root.is_absolute():
            data_root = source.parent.parent / data_root
        args.calibration_data_root = str(data_root.resolve())
        context = main.configure_calibration_args(args)
        self.replay = Optimiser(**optimizer_parameters(args))
        self.replay.calibration_context = context
        self.direct = owner.direct
        if not np.isclose(owner.rot_ang, self.replay.rot_ang):
            raise ValueError('assembly loss requires the source package rot_ang')
        if (owner.calibration_context['global_point_ids'] !=
                args._sensor_package['regions']['end15cm']['support_point_ids']):
            raise ValueError('end15cm support differs from source package')
        config = self.replay.multi_region_parameters
        config['region_order'] = ['full', 'end15cm']
        config['regions'] = {k: config['regions'][k] for k in config['region_order']}
        local = config['regions']['end15cm']
        if not np.array_equal(owner.thresholds, local['thresholds']):
            raise ValueError('assembly trial must retain source thresholds')
        if list(owner.segmentation) != list(local['local_segmentation']):
            raise ValueError('assembly trial must retain source segmentation')
        owned = list(local['support_point_ids'])
        local['owned_point_ids'] = owned
        full = config['regions']['full']
        full['owned_point_ids'] = [p for p in full['support_point_ids'] if p not in owned]
        self.block = local
        self.radii = [r for r in self.replay.radii[self.direct]['circ'] if r > 0]
        if not self.radii:
            raise ValueError('assembly loss requires nonzero full calibration samples')
        self.source = str(source)
        self.baseline = self.evaluate(owner)

    def evaluate(self, owner):
        from tools.calibration_validation import _reconstruct_frame, straight_prefix_circular_tail
        self.block['slopes'][self.direct] = np.asarray(owner.slopes[self.direct]).copy()
        self.block['weights'][self.direct] = np.asarray(owner.weights[self.direct]).copy()
        values = []
        length = float(self.replay.ideal_len)
        for radius in self.radii:
            frame = np.asarray(self.replay.processed_Data['circ'][self.direct][radius])
            dist, curve, _, _ = _reconstruct_frame(self.replay, frame, self.direct)
            ideal, _ = straight_prefix_circular_tail(dist-dist[0], 0., radius/1000.)
            squared = np.sum((curve-ideal)**2, axis=1) / length**2
            values.append(float(np.mean(squared) + squared[-1]))
        result = float(np.mean(values))
        if not np.isfinite(result):
            raise ValueError('nonfinite assembly loss')
        return result
