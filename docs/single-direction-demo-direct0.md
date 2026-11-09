# Direct-0 single-direction dynamic demo package

This package is an experimental, non-deployable mix:

- `full` and `end15cm` are preserved from `params/06B6_NeTi_v2_ftube_nophase_endpointcalib_endslopenew.json`.
- `end5cm` uses the complete direct-0 result from `calibration_results/06B6_NeTi_v2_ftube-20260919T192950+0800-direct0-3d3aaf/results.json`.
- Runtime `exp_directs=[0]`, `direction_reference_direct=0`, and direction blending is disabled.
- The internal three-direction schema remains only for multi-region structural validation; end5cm 120/240 slots are schema-only copies of direct0 and must not be treated as calibrated directions.
- `deployment_ready=false` is intentional.

The package can be regenerated with:

```powershell
python tools/build_single_direction_demo_package.py `
  --base-package params/06B6_NeTi_v2_ftube_nophase_endpointcalib_endslopenew.json `
  --override-result calibration_results/06B6_NeTi_v2_ftube-20260919T192950+0800-direct0-3d3aaf/results.json `
  --output params/06B6_NeTi_v2_ftube_nophase_installed_endweights_direct0_demo.json `
  --direction 0
```

Run only the dynamic demo validation with:

```powershell
python main.py --task demo `
  --sensor_params params/06B6_NeTi_v2_ftube_nophase_installed_endweights_direct0_demo.json
```

Do not enable `--direction_blend_enabled`; the package intentionally has no
same-configuration 120/240-degree end5cm calibration.
