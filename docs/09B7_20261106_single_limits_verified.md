# Single-region limits verified

Errors are means including straight state. Standalone local rotations require explicit CLI. Merged replay is a separate criterion.

| Direction | Region | Point % | End % | rot_ang |
|---|---|---:|---:|---:|
| 0 | full | 0.4605 | 0.9605 | 0.00000000 |
| 0 | end15cm | 1.6226 | 3.8228 | 23.68090914 |
| 0 | end5cm | 2.8170 | 6.8508 | 0.00000000 |
| 120 | full | 0.5402 | 0.9552 | 0.00000000 |
| 120 | end15cm | 2.3722 | 5.8016 | 0.00000000 |
| 120 | end5cm | 1.0945 | 2.5199 | 44.21527322 |
| 240 | full | 0.5658 | 0.9692 | 0.00000000 |
| 240 | end15cm | 1.8885 | 3.7077 | 36.17996625 |
| 240 | end5cm | 1.1000 | 2.4006 | 0.00000000 |

## Assembled replay

| Direction | Region | Point % | End % |
|---|---|---:|---:|
| 0 | full | 0.4775 | 1.1641 |
| 0 | end15cm | 2.3586 | 3.9202 |
| 0 | end5cm | 13.6540 | 17.4843 |
| 120 | full | 0.5846 | 1.6465 |
| 120 | end15cm | 2.8106 | 5.9672 |
| 120 | end5cm | 15.7403 | 19.8796 |
| 240 | full | 0.5700 | 0.9246 |
| 240 | end15cm | 3.4205 | 5.8337 |
| 240 | end5cm | 12.2106 | 17.0547 |

```powershell
python docs/09B7_compat_dispatch.py main.py --task recon --sensor_params params/09B7_20261106_single_limits_candidate.json --multi_region_calib False --optimization_region full --use_full_transported_phase False --direct 0 --exp_directs "[0,120,240]" --rot_ang 0
python docs/09B7_compat_dispatch.py main.py --task recon --sensor_params params/09B7_20261106_single_limits_candidate.json --multi_region_calib False --optimization_region end15cm --use_full_transported_phase False --direct 0 --exp_directs "[0,120,240]" --rot_ang 23.6809091435044
python docs/09B7_compat_dispatch.py main.py --task recon --sensor_params params/09B7_20261106_single_limits_candidate.json --multi_region_calib False --optimization_region end5cm --use_full_transported_phase False --direct 0 --exp_directs "[0,120,240]" --rot_ang 0
python docs/09B7_compat_dispatch.py main.py --task recon --sensor_params params/09B7_20261106_single_limits_candidate.json --multi_region_calib False --optimization_region full --use_full_transported_phase False --direct 120 --exp_directs "[0,120,240]" --rot_ang 0
python docs/09B7_compat_dispatch.py main.py --task recon --sensor_params params/09B7_20261106_single_limits_candidate.json --multi_region_calib False --optimization_region end15cm --use_full_transported_phase False --direct 120 --exp_directs "[0,120,240]" --rot_ang 0
python docs/09B7_compat_dispatch.py main.py --task recon --sensor_params params/09B7_20261106_single_limits_candidate.json --multi_region_calib False --optimization_region end5cm --use_full_transported_phase False --direct 120 --exp_directs "[0,120,240]" --rot_ang 44.2152732186053
python docs/09B7_compat_dispatch.py main.py --task recon --sensor_params params/09B7_20261106_single_limits_candidate.json --multi_region_calib False --optimization_region full --use_full_transported_phase False --direct 240 --exp_directs "[0,120,240]" --rot_ang 0
python docs/09B7_compat_dispatch.py main.py --task recon --sensor_params params/09B7_20261106_single_limits_candidate.json --multi_region_calib False --optimization_region end15cm --use_full_transported_phase False --direct 240 --exp_directs "[0,120,240]" --rot_ang 36.1799662489316
python docs/09B7_compat_dispatch.py main.py --task recon --sensor_params params/09B7_20261106_single_limits_candidate.json --multi_region_calib False --optimization_region end5cm --use_full_transported_phase False --direct 240 --exp_directs "[0,120,240]" --rot_ang 0
```