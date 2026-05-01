# preprocess-cmu-dataset

Python helpers for CMU Panoptic / Kinoptic–style preprocessing: Kinect RGB–depth alignment, temporal alignment via `ksynctables`, and related utilities.

See `coding_agent/docs/tasks/preprocess-CMU-dataset.md` for task notes.

## Scripts

- `preprocess_cmu_kinect.py` — baseline preprocessing (spatial alignment focus).
- `preprocess_cmu_kinect_temporal.py` — temporal alignment, optional human-presence filtering, paired frame export.
- `preprocess_cmu_pose_gt_video.py` — pose / GT overlay videos.

Dataset paths and CMU downloads are not included in this repository.
