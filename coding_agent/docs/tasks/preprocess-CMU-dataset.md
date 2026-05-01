# Task: preprocess-CMU-dataset
Status: open
Started: 2026-04-23
Last updated: 2026-04-23

## Goal
Try to un-distort depth image and RGB image, and project depth image onto RGB image with distortion parameters and extrinsic, intrinsic parameters. Reference C++ implementations may be consulted, but deliver Python scripts only.

## Evaluator
- Metrics: Manual visual inspection of aligned videos
- Thresholds: Aligned depth overlay appears visually consistent with RGB content
- Tools: Saved video outputs
- Baseline:

## Current state
Implemented `preprocess_cmu_kinect.py`, a Python-only CMU Panoptic Kinect RGB/depth alignment script. It reads raw Kinect depth frames, undistorts depth rays, projects depth points into the RGB camera using Kinect calibration, undistorts the RGB target with full-FOV `new_K` (`alpha=1`), and writes only the undistorted overlay MP4 by default. The script now uses `--start-frame` and `--end-frame` to define the processed frame range and adds a filename suffix for partial ranges. The full `170221_haggling_b1` / `50_01` RGB-length stream has been generated under `/media/s/HDD8/data/cmu_panoptic_kinect1/170221_haggling_b1/preprocessed_videos/50_01/`; manual visual inspection remains.

Added `preprocess_cmu_kinect_temporal.py`: same spatial pipeline as `preprocess_cmu_kinect.py`, but **temporal** RGB↔depth pairing uses `ksynctables_*.json` — for each RGB frame index `i`, depth index is `argmin |depth.univ_time - color.univ_time[i]|` (with fallback to `i + depth_frame_offset` when `color.univ_time[i]` is invalid, e.g. `-1`). Output filenames include `_ksync_temporal` vs `_legacy_offset` when using `--legacy-pairing`.

## Open items
- [x] Inspect sequence layout and calibration format for `170221_haggling_b1`
- [x] Implement Python preprocessing script for undistortion and depth-to-RGB projection
- [x] Save aligned video outputs for manual inspection
- [x] Run the script on a small sample and verify outputs are created
- [ ] Manual visual inspection of generated aligned videos

## Sessions
### 2026-04-23 (Session 1)
manager: task=created  note=Using provided goal/evaluation/notes; local specialist roles are documented but not callable as separate agents in this environment.
repo_navigator: files=preprocess_cmu_kinect.py,reference/sensors/CamRadtan.h,reference/sensors/CamBase.h  build=python3 -m py_compile preprocess_cmu_kinect.py  risks=kinect sync tables contain -1 timestamps for this sequence, so RGB/depth frame indices are paired directly
coder: changed=preprocess_cmu_kinect.py,coding_agent/docs/tasks/index.md,coding_agent/docs/tasks/preprocess-CMU-dataset.md  tests=python3 -m py_compile preprocess_cmu_kinect.py; python3 preprocess_cmu_kinect.py --frames 30 --output-dir outputs/preprocess-CMU-dataset-smoke; python3 preprocess_cmu_kinect.py --frames 300  build=pass  risks=manual alignment quality still needs visual inspection
runner: cmds=ffprobe on raw and undistorted output videos  status=pass
user-input: preference=keep full FOV and save outputs in the `/media/s/HDD8` data folder  notes=only save overlaid undistorted video, not raw overlay
coder: changed=preprocess_cmu_kinect.py  tests=python3 -m py_compile preprocess_cmu_kinect.py; python3 preprocess_cmu_kinect.py --frames 5; python3 preprocess_cmu_kinect.py --frames 300  build=pass  risks=full-FOV undistortion keeps black-border regions by design
runner: cmds=ffprobe /media/s/HDD8/data/cmu_panoptic_kinect1/170221_haggling_b1/preprocessed_videos/50_01/170221_haggling_b1_50_01_depth_on_rgb_undistorted_full_fov.mp4  status=pass
user-input: preference=process the whole data, not just 10 seconds  notes=RGB stream has 16251 frames; depth stream has 16258 frames
runner: cmds=python3 preprocess_cmu_kinect.py --frames 16251; ffprobe final full-FOV overlay; cv2 metadata check  status=pass
user-input: preference=use start-frame and end-frame instead of a frame count  notes=partial-range outputs should be distinguishable from full-range outputs
coder: changed=preprocess_cmu_kinect.py  tests=python3 -m py_compile preprocess_cmu_kinect.py; python3 preprocess_cmu_kinect.py --start-frame 10 --end-frame 15 --output-dir /tmp/preprocess-range-check  build=pass  risks=none
