#!/usr/bin/env python3
"""Render CMU Panoptic Kinect pose GT (3D joints) to one undistorted RGB video.

This script projects ``hdPose3d_stage1_coco19/body3DScene_XXXXXXXX.json`` joints
to Kinect color frames, undistorts RGB first, then draws skeletons in the
undistorted image domain using the corresponding ``new_K`` intrinsics.
"""

from __future__ import annotations

import argparse
import json
import tarfile
from bisect import bisect_left
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import cv2
import numpy as np


DEFAULT_DATA_ROOT = Path("/media/s/HDD8/data/cmu_panoptic_kinect1")
DEFAULT_SEQUENCE = "170221_haggling_b3"
DEFAULT_OUTPUT_SUBDIR = Path("preprocessed_videos")
DEFAULT_POSE_SUBDIR = "hdPose3d_stage1_coco19"

BODY_EDGES_COCO19: np.ndarray = (
    np.array(
        [
            [1, 2],
            [1, 4],
            [4, 5],
            [5, 6],
            [1, 3],
            [3, 7],
            [7, 8],
            [8, 9],
            [3, 13],
            [13, 14],
            [14, 15],
            [1, 10],
            [10, 11],
            [11, 12],
        ],
        dtype=np.int64,
    )
    - 1
)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def as_array(value, dtype=np.float64) -> np.ndarray:
    return np.asarray(value, dtype=dtype)


def flatten_distortion(value: Iterable[float], count: int = 5) -> np.ndarray:
    return as_array(value).reshape(-1)[:count]


def make_writer(path: Path, fps: float, size: Tuple[int, int]) -> cv2.VideoWriter:
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, size)
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {path}")
    return writer


def camera_from_panoptic_calibration(calibration: dict, name: str) -> dict:
    for camera in calibration["cameras"]:
        if camera["name"] == name:
            return camera
    raise KeyError(f"Camera {name!r} not found in panoptic calibration")


def ksync_color_univ_time(ksync: dict, node: int) -> np.ndarray:
    node_name = f"KINECTNODE{node}"
    block = ksync["kinect"]["color"][node_name]
    if isinstance(block, dict) and "univ_time" in block:
        return as_array(block["univ_time"], dtype=np.float64).reshape(-1)
    raise ValueError(f"Unsupported ksync schema for kinect.color.{node_name}")


class PoseSceneSource:
    """Read body3DScene JSONs from either extracted folder or .tar archive."""

    def __init__(self, sequence_dir: Path, pose_subdir: str) -> None:
        self.sequence_dir = sequence_dir
        self.pose_subdir = pose_subdir
        self.pose_root = sequence_dir / pose_subdir
        self.pose_tar = sequence_dir / f"{pose_subdir}.tar"
        self._tar_index: Dict[int, tarfile.TarInfo] | None = None

        if not self.pose_root.exists() and not self.pose_tar.exists():
            raise FileNotFoundError(
                f"Neither pose folder nor tar exists: {self.pose_root} or {self.pose_tar}"
            )

    def _build_tar_index(self) -> Dict[int, tarfile.TarInfo]:
        if self._tar_index is not None:
            return self._tar_index
        index: Dict[int, tarfile.TarInfo] = {}
        with tarfile.open(self.pose_tar, "r") as tf:
            for member in tf.getmembers():
                name = Path(member.name).name
                if not name.startswith("body3DScene_") or not name.endswith(".json"):
                    continue
                try:
                    sid = int(name[len("body3DScene_") : -len(".json")])
                except ValueError:
                    continue
                index[sid] = member
        self._tar_index = index
        return index

    def load_scene(self, scene_id: int) -> dict | None:
        if self.pose_root.exists():
            path = self.pose_root / f"body3DScene_{scene_id:08d}.json"
            if not path.exists():
                return None
            return load_json(path)

        index = self._build_tar_index()
        member = index.get(scene_id)
        if member is None:
            return None
        with tarfile.open(self.pose_tar, "r") as tf:
            fobj = tf.extractfile(member)
            if fobj is None:
                return None
            return json.load(fobj)

    def sorted_univ_time_table(self) -> List[Tuple[float, int]]:
        if self.pose_root.exists():
            cache_path = self.pose_root / ".body3d_univtime_index.json"
            if cache_path.exists():
                raw = load_json(cache_path)
                return [(float(t), int(i)) for t, i in raw]

            pairs: List[Tuple[float, int]] = []
            for path in sorted(self.pose_root.glob("body3DScene_*.json")):
                stem = path.stem
                try:
                    scene_id = int(stem.split("_")[-1])
                except ValueError:
                    continue
                scene = load_json(path)
                if "univTime" in scene:
                    pairs.append((float(scene["univTime"]), scene_id))
            pairs.sort(key=lambda x: x[0])
            try:
                cache_path.write_text(json.dumps(pairs), encoding="utf-8")
            except OSError:
                pass
            return pairs

        index = self._build_tar_index()
        pairs = []
        with tarfile.open(self.pose_tar, "r") as tf:
            for sid in sorted(index.keys()):
                fobj = tf.extractfile(index[sid])
                if fobj is None:
                    continue
                scene = json.load(fobj)
                if "univTime" in scene:
                    pairs.append((float(scene["univTime"]), sid))
        pairs.sort(key=lambda x: x[0])
        return pairs


def nearest_scene_id_for_univ_time(univ_time_ms: float, table: Sequence[Tuple[float, int]]) -> Tuple[int, float]:
    if not table:
        raise ValueError("Pose univTime table is empty")
    times = [float(t) for t, _ in table]
    i = bisect_left(times, float(univ_time_ms))
    candidates: List[int] = []
    if i > 0:
        candidates.append(i - 1)
    if i < len(times):
        candidates.append(i)
    best = min(candidates, key=lambda idx: abs(times[idx] - float(univ_time_ms)))
    err = float(abs(times[best] - float(univ_time_ms)))
    return int(table[best][1]), err


def joints19_to_xyz_conf(flat: Sequence[float]) -> Tuple[np.ndarray, np.ndarray]:
    arr = as_array(flat, dtype=np.float64).reshape(19, 4)
    return arr[:, :3], arr[:, 3]


def _safe_int_pt(uv: np.ndarray, idx: int) -> Tuple[int, int] | None:
    if not np.all(np.isfinite(uv[idx])):
        return None
    x = int(round(float(uv[idx, 0])))
    y = int(round(float(uv[idx, 1])))
    i32_min = -(2**31)
    i32_max = 2**31 - 1
    if x < i32_min or x > i32_max or y < i32_min or y > i32_max:
        return None
    return x, y


def draw_skeleton_bgr(
    bgr: np.ndarray,
    uv: np.ndarray,
    conf: np.ndarray,
    *,
    conf_thr: float = 0.2,
    line_thickness: int = 2,
    joint_radius: int = 4,
) -> np.ndarray:
    out = bgr.copy()
    h, w = out.shape[:2]

    def ok(i: int) -> bool:
        return bool(conf[i] >= conf_thr and np.all(np.isfinite(uv[i])))

    palette = [
        (0, 255, 0),
        (0, 200, 255),
        (255, 128, 0),
        (255, 0, 128),
        (200, 255, 0),
        (100, 100, 255),
        (255, 100, 100),
        (180, 180, 0),
        (0, 180, 180),
        (220, 0, 220),
    ]

    for edge_idx, ij in enumerate(BODY_EDGES_COCO19):
        i, j = int(ij[0]), int(ij[1])
        if not (ok(i) and ok(j)):
            continue
        p0 = _safe_int_pt(uv, i)
        p1 = _safe_int_pt(uv, j)
        if p0 is None or p1 is None:
            continue
        color = palette[edge_idx % len(palette)]
        cv2.line(out, p0, p1, color, int(line_thickness), lineType=cv2.LINE_AA)

    for joint_idx in range(19):
        if not ok(joint_idx):
            continue
        pt = _safe_int_pt(uv, joint_idx)
        if pt is None:
            continue
        x, y = pt
        if 0 <= x < w and 0 <= y < h:
            cv2.circle(out, (x, y), int(joint_radius), (0, 255, 255), -1, lineType=cv2.LINE_AA)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render CMU Panoptic Kinect pose GT video on undistorted RGB frames."
    )
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--sequence", default=DEFAULT_SEQUENCE)
    parser.add_argument("--node", type=int, default=1)
    parser.add_argument("--start-frame", type=int, default=0, help="Inclusive first RGB frame index.")
    parser.add_argument("--end-frame", type=int, default=None, help="Exclusive last RGB frame index.")
    parser.add_argument("--stride", type=int, default=1, help="Frame stride.")
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to <sequence>/preprocessed_videos/<camera>.",
    )
    parser.add_argument("--pose-subdir", default=DEFAULT_POSE_SUBDIR)
    parser.add_argument("--pose-conf-thr", type=float, default=0.2)
    parser.add_argument("--line-thickness", type=int, default=2)
    parser.add_argument("--joint-radius", type=int, default=4)
    parser.add_argument(
        "--pose-index-mode",
        choices=("univ_time", "offset"),
        default="univ_time",
        help="How to map RGB frame -> body3DScene JSON.",
    )
    parser.add_argument(
        "--pose-scene-offset",
        type=int,
        default=1,
        help="Only in offset mode: body3DScene index = rgb_frame + offset.",
    )
    parser.add_argument(
        "--max-univ-time-error-ms",
        type=float,
        default=500.0,
        help="In univ_time mode, if nearest pose time is farther than this, treat as missing.",
    )
    parser.add_argument(
        "--include-missing-pose",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write RGB frame even when no usable pose JSON is found (default: true).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seq_dir = args.data_root / args.sequence
    camera_name = f"50_{args.node:02d}"
    video_path = seq_dir / "kinectVideos" / f"kinect_{camera_name}.mp4"
    panoptic_calib = load_json(seq_dir / f"calibration_{args.sequence}.json")
    camera = camera_from_panoptic_calibration(panoptic_calib, camera_name)

    if args.output_dir is None:
        output_dir = seq_dir / DEFAULT_OUTPUT_SUBDIR / camera_name
    else:
        output_dir = args.output_dir

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open RGB video: {video_path}")

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    start_frame = int(args.start_frame)
    end_frame = frame_count if args.end_frame is None else int(args.end_frame)

    if start_frame < 0:
        raise ValueError(f"start-frame must be >= 0, got {start_frame}")
    if end_frame <= start_frame:
        raise ValueError(f"end-frame must be greater than start-frame, got {start_frame}, {end_frame}")
    if end_frame > frame_count:
        raise ValueError(f"Requested end-frame {end_frame} exceeds frame count {frame_count}")
    if args.stride <= 0:
        raise ValueError(f"stride must be > 0, got {args.stride}")

    k_color = as_array(camera["K"], dtype=np.float64)
    d_color = flatten_distortion(camera["distCoef"])
    r_world_to_color = as_array(camera["R"], dtype=np.float64)
    t_world_to_color = as_array(camera["t"], dtype=np.float64).reshape(3, 1)
    rvec, _ = cv2.Rodrigues(r_world_to_color)
    new_k_color, _ = cv2.getOptimalNewCameraMatrix(k_color, d_color, (width, height), 1.0, (width, height))

    pose_source = PoseSceneSource(seq_dir, args.pose_subdir)
    pose_time_table: List[Tuple[float, int]] = []
    color_univ_time: np.ndarray | None = None
    if args.pose_index_mode == "univ_time":
        ksync = load_json(seq_dir / f"ksynctables_{args.sequence}.json")
        color_univ_time = ksync_color_univ_time(ksync, args.node)
        pose_time_table = pose_source.sorted_univ_time_table()

    range_suffix = ""
    if start_frame != 0 or end_frame != frame_count:
        range_suffix = f"_f{start_frame:06d}_{end_frame - 1:06d}"
    mode_suffix = ""
    if args.pose_index_mode == "offset":
        mode_suffix = f"_poseoff_{args.pose_scene_offset:+d}".replace("+", "p").replace("-", "m")
    output_path = output_dir / f"{args.sequence}_{camera_name}_pose_gt_undistorted{mode_suffix}{range_suffix}.mp4"
    writer = make_writer(output_path, args.fps / args.stride, (width, height))

    print(f"Sequence: {args.sequence}")
    print(f"Camera: {camera_name}")
    print(f"RGB video: {video_path}")
    print(f"Pose mode: {args.pose_index_mode}")
    print(f"Frame range: [{start_frame}, {end_frame}) stride={args.stride}")
    print(f"Output: {output_path}")

    total = 0
    with_pose = 0
    missing_pose = 0
    try:
        for frame_idx in range(start_frame, end_frame, args.stride):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, rgb_bgr = cap.read()
            if not ok:
                print(f"Stopping: could not read RGB frame {frame_idx}")
                break

            rgb_undist = cv2.undistort(rgb_bgr, k_color, d_color, None, new_k_color)
            pose_frame = rgb_undist.copy()

            if args.pose_index_mode == "offset":
                scene_id = frame_idx + args.pose_scene_offset
                scene = pose_source.load_scene(scene_id)
                pose_time_err = None
            else:
                assert color_univ_time is not None
                if frame_idx >= color_univ_time.shape[0]:
                    scene = None
                    pose_time_err = None
                else:
                    scene_id, pose_time_err = nearest_scene_id_for_univ_time(color_univ_time[frame_idx], pose_time_table)
                    scene = pose_source.load_scene(scene_id)

            pose_ok = False
            if scene is not None:
                if (
                    args.pose_index_mode == "univ_time"
                    and pose_time_err is not None
                    and pose_time_err > args.max_univ_time_error_ms
                ):
                    pose_ok = False
                else:
                    for body in scene.get("bodies", []):
                        xyz_cm, conf = joints19_to_xyz_conf(body["joints19"])
                        xyz_obj = np.ascontiguousarray(xyz_cm.reshape(-1, 1, 3), dtype=np.float64)
                        uv_dist, _ = cv2.projectPoints(
                            xyz_obj,
                            np.ascontiguousarray(rvec, dtype=np.float64),
                            np.ascontiguousarray(t_world_to_color, dtype=np.float64),
                            np.ascontiguousarray(k_color, dtype=np.float64),
                            np.ascontiguousarray(d_color, dtype=np.float64),
                        )
                        uv_dist = uv_dist.reshape(-1, 2)
                        uv_undist = cv2.undistortPoints(
                            uv_dist.reshape(-1, 1, 2), k_color, d_color, P=new_k_color
                        ).reshape(-1, 2)
                        pose_frame = draw_skeleton_bgr(
                            pose_frame,
                            uv_undist,
                            conf,
                            conf_thr=args.pose_conf_thr,
                            line_thickness=args.line_thickness,
                            joint_radius=args.joint_radius,
                        )
                    pose_ok = True

            if pose_ok:
                with_pose += 1
                writer.write(pose_frame)
            else:
                missing_pose += 1
                if args.include_missing_pose:
                    writer.write(rgb_undist)

            total += 1
            if total == 1 or total % 30 == 0:
                print(
                    f"Processed {total} frame(s), current RGB frame {frame_idx}, "
                    f"pose_ok={pose_ok}, written={with_pose + (missing_pose if args.include_missing_pose else 0)}"
                )
    finally:
        cap.release()
        writer.release()

    written_frames = with_pose + (missing_pose if args.include_missing_pose else 0)
    print(f"Done. Processed={total}, with_pose={with_pose}, missing_pose={missing_pose}, written={written_frames}")
    print(f"Video: {output_path}")


if __name__ == "__main__":
    main()
