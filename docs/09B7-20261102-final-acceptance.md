# 09B7 calibration replay acceptance

Means across available calibration radii; not worst-case per-radius or independent/live accuracy.

## Standalone replay

| Region | Direction | Point (%) | End (%) | rot_ang |
|---|---|---:|---:|---:|
| full | 0 | 0.3995 | 0.8594 | -31.40000000 |
| end15cm | 0 | 2.6116 | 5.4061 | 120.30411862 |
| end5cm | 0 | 4.1685 | 8.8310 | 133.30567399 |
| full | 120 | 0.4579 | 0.9546 | -31.40000000 |
| end15cm | 120 | 2.9781 | 7.5373 | 124.34188822 |
| end5cm | 120 | 4.0759 | 8.7428 | 120.83025225 |
| full | 240 | 0.5186 | 0.8211 | -31.40000000 |
| end15cm | 240 | 2.4001 | 4.8184 | 127.66717242 |
| end5cm | 240 | 4.0168 | 7.4848 | 138.24078220 |

## Assembled replay

Full assembled errors are listed separately and are not subject to the standalone full 1% gate. Local cases substitute local measurements into the full straight frame.

| Region | Direction | Point (%) | End (%) |
|---|---|---:|---:|
| full | 0 | 0.3733 | 0.8415 |
| end15cm | 0 | 2.6568 | 5.3082 |
| end5cm | 0 | 7.2228 | 7.3890 |
| full | 120 | 0.4749 | 1.3628 |
| end15cm | 120 | 3.6021 | 7.3018 |
| end5cm | 120 | 8.5555 | 9.7891 |
| full | 240 | 0.5101 | 0.7030 |
| end15cm | 240 | 2.6064 | 5.2024 |
| end5cm | 240 | 5.0302 | 7.0329 |

## Phase reference alignment

Actual assembled theta_dynamic is used. Local replay references are converted to the full rotation frame; raw stored references are preserved. These are different metrics and raw differences are not claimed below 30 degrees. Legacy validator gates are not claimed passed.

| Region | Direction | Raw reference max (deg) | Aligned max (deg) |
|---|---|---:|---:|
| end15cm | 0 | 176.1583 | 26.1583 |
| end5cm | 0 | 177.7678 | 26.3180 |
| end15cm | 120 | 178.4117 | 29.5917 |
| end5cm | 120 | 172.5518 | 22.3137 |
| end15cm | 240 | 177.8032 | 25.4295 |
| end5cm | 240 | 172.5318 | 23.8390 |

## Reconstruct

Standalone local commands must supply their recorded rot_ang; the current application does not automatically select per-region replay angles. Full assembled reconstruction uses rot_ang=-31.4.

The old foreign-sensor stored-zero path was disabled. Live inference is not validated; first-frame zero requires a straight initial sensor state.

```powershell
python main.py --task recon --sensor_params params/09B7_20261102_multi_region_10pct.json --multi_region_calib False --optimization_region full --use_full_transported_phase False --direct 0 --exp_directs "[0,120,240]" --rot_ang -31.4
python main.py --task recon --sensor_params params/09B7_20261102_multi_region_10pct.json --multi_region_calib False --optimization_region end15cm --use_full_transported_phase False --direct 0 --exp_directs "[0,120,240]" --rot_ang 120.304118621181
python main.py --task recon --sensor_params params/09B7_20261102_multi_region_10pct.json --multi_region_calib False --optimization_region end5cm --use_full_transported_phase False --direct 0 --exp_directs "[0,120,240]" --rot_ang 133.3056739878
python main.py --task recon --sensor_params params/09B7_20261102_multi_region_10pct.json --multi_region_calib True --use_full_transported_phase False --direct 0 --exp_directs "[0,120,240]" --rot_ang -31.4
python main.py --task recon --sensor_params params/09B7_20261102_multi_region_10pct.json --multi_region_calib False --optimization_region full --use_full_transported_phase False --direct 120 --exp_directs "[0,120,240]" --rot_ang -31.4
python main.py --task recon --sensor_params params/09B7_20261102_multi_region_10pct.json --multi_region_calib False --optimization_region end15cm --use_full_transported_phase False --direct 120 --exp_directs "[0,120,240]" --rot_ang 124.34188821805
python main.py --task recon --sensor_params params/09B7_20261102_multi_region_10pct.json --multi_region_calib False --optimization_region end5cm --use_full_transported_phase False --direct 120 --exp_directs "[0,120,240]" --rot_ang 120.83025224596
python main.py --task recon --sensor_params params/09B7_20261102_multi_region_10pct.json --multi_region_calib True --use_full_transported_phase False --direct 120 --exp_directs "[0,120,240]" --rot_ang -31.4
python main.py --task recon --sensor_params params/09B7_20261102_multi_region_10pct.json --multi_region_calib False --optimization_region full --use_full_transported_phase False --direct 240 --exp_directs "[0,120,240]" --rot_ang -31.4
python main.py --task recon --sensor_params params/09B7_20261102_multi_region_10pct.json --multi_region_calib False --optimization_region end15cm --use_full_transported_phase False --direct 240 --exp_directs "[0,120,240]" --rot_ang 127.667172423732
python main.py --task recon --sensor_params params/09B7_20261102_multi_region_10pct.json --multi_region_calib False --optimization_region end5cm --use_full_transported_phase False --direct 240 --exp_directs "[0,120,240]" --rot_ang 138.24078220037
python main.py --task recon --sensor_params params/09B7_20261102_multi_region_10pct.json --multi_region_calib True --use_full_transported_phase False --direct 240 --exp_directs "[0,120,240]" --rot_ang -31.4
```

Parameter SHA256: `635732b0915fa4a51b0636cf6e25967379c7ff385844a48845fa81fb8a3f9bf5`.
