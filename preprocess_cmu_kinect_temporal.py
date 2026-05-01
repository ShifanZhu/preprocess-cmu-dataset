from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt

DEFAULT_PANOPTIC_ROOT = Path("/media/s/8tb-data/data/cmu_panoptic")
DEFAULT_DATA_ROOT = DEFAULT_PANOPTIC_ROOT / "cmu_panoptic_kinect2"
DEFAULT_SEQUENCE = "170221_haggling_b1"
DEFAULT_OUTPUT_SUBDIR = Path("preprocessed_videos")
DEPTH_WIDTH = 512
DEPTH_HEIGHT = 424
CHECKPOINTS = (100, 200, 300)

""" for seq in /media/s/8tb-data/data/cmu_panoptic/cmu_panoptic_kinect1/*/; do
  name=$(basename "$seq")
  [[ "$name" == out_* ]] && continue
  python3 -u /home/s/repos/tool/preprocess_cmu_dataset/preprocess_cmu_kinect_temporal.py \
    --data-root /media/s/8tb-data/data/cmu_panoptic/cmu_panoptic_kinect1 \
    --sequence "$name" \
    --node 1
    --skip-video
done"""
def as_array(value, dtype=np.float64) -> np.ndarray:
    return np.asarray(value, dtype=dtype)


def flatten_distortion(value: Iterable[float], count: int = 5) -> np.ndarray:
    return as_array(value).reshape(-1)[:count]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def camera_from_panoptic_calibration(calibration: dict, name: str) -> dict:
    for camera in calibration["cameras"]:
        if camera["name"] == name:
            return camera
    raise KeyError(f"Camera {name!r} not found in panoptic calibration")


def camera_from_kcalibration(kcalibration: dict, node: int) -> dict:
    sensor = kcalibration["sensors"][node - 1]
    return {
        "name": sensor.get("name", f"KINECTNODE{node}"),
        "K": sensor["K_color"],
        "distCoef": sensor["distCoeffs_color"],
        "resolution": sensor.get("color_resolution", [1920, 1080]),
    }


def ksync_univ_time_vectors(ksync: dict, node: int) -> tuple[np.ndarray, np.ndarray]:
    kn = f"KINECTNODE{node}"
    ct = np.asarray(ksync["kinect"]["color"][kn]["univ_time"], dtype=np.float64)
    dt = np.asarray(ksync["kinect"]["depth"][kn]["univ_time"], dtype=np.float64)
    return ct, dt


def build_depth_index_map(
    color_ut: np.ndarray,
    depth_ut: np.ndarray,
    *,
    fallback_offset: int,
    large_match_warn_ms: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized RGB->depth index mapping.

    Returns:
      depth_idx_map: int32 [len(color_ut)]
      fallback_mask: bool [len(color_ut)] True where color_ut invalid
      err_ms: float64 [len(color_ut)] abs time error for ksync-matched rows
    """
    n_color = len(color_ut)
    out_idx = np.full(n_color, -1, dtype=np.int32)
    err_ms = np.full(n_color, np.nan, dtype=np.float64)

    valid_color = np.isfinite(color_ut) & (color_ut >= 0)
    fallback_mask = ~valid_color
    rgb_idx_all = np.arange(n_color, dtype=np.int64)

    # Fallback rows use index+offset policy.
    fb = rgb_idx_all + int(fallback_offset)
    out_idx[fallback_mask] = fb[fallback_mask].astype(np.int32)

    valid_depth = np.isfinite(depth_ut) & (depth_ut >= 0)
    if not np.any(valid_depth):
        return out_idx, fallback_mask, err_ms

    depth_t = depth_ut[valid_depth]
    depth_orig_idx = np.where(valid_depth)[0]

    # Ensure monotonic increasing times for searchsorted.
    order = np.argsort(depth_t)
    depth_t = depth_t[order]
    depth_orig_idx = depth_orig_idx[order]

    tc = color_ut[valid_color]
    pos = np.searchsorted(depth_t, tc, side="left")
    pos0 = np.clip(pos - 1, 0, len(depth_t) - 1)
    pos1 = np.clip(pos, 0, len(depth_t) - 1)

    e0 = np.abs(tc - depth_t[pos0])
    e1 = np.abs(tc - depth_t[pos1])
    choose1 = e1 < e0
    best = np.where(choose1, pos1, pos0)

    rgb_valid_idx = np.where(valid_color)[0]
    out_idx[rgb_valid_idx] = depth_orig_idx[best].astype(np.int32)
    err_ms[rgb_valid_idx] = np.minimum(e0, e1)

    max_err = np.nanmax(err_ms)
    if np.isfinite(max_err) and max_err > large_match_warn_ms:
        print(f"  (warn) large ksync match error exists: max {max_err:.2f} ms")
    return out_idx, fallback_mask, err_ms


def depth_frame_count_from_size(path: Path) -> int:
    return path.stat().st_size // (DEPTH_WIDTH * DEPTH_HEIGHT * np.dtype("<u2").itemsize)


class DepthReader:
    """Fast random-access depth reader backed by memmap."""

    def __init__(self, depth_path: Path) -> None:
        self.depth_path = depth_path
        self.n_frames = depth_frame_count_from_size(depth_path)
        self._mm = np.memmap(
            str(depth_path),
            mode="r",
            dtype="<u2",
            shape=(self.n_frames, DEPTH_HEIGHT, DEPTH_WIDTH),
        )

    def read(self, frame_index: int) -> np.ndarray:
        if frame_index < 0 or frame_index >= self.n_frames:
            raise EOFError(f"Depth frame {frame_index} is outside {self.depth_path}")
        # Match legacy shape/orientation.
        return np.fliplr(np.asarray(self._mm[frame_index], dtype=np.uint16))


def make_depth_grid() -> np.ndarray:
    xs, ys = np.meshgrid(
        np.arange(DEPTH_WIDTH, dtype=np.float32),
        np.arange(DEPTH_HEIGHT, dtype=np.float32),
    )
    return np.stack((xs, ys), axis=-1).reshape(-1, 1, 2)


def unproject_depth(depth: np.ndarray, norm_rays: np.ndarray, inv_m_depth: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    z = depth.reshape(-1).astype(np.float64) * 0.001
    points = np.column_stack((norm_rays[:, 0] * z, norm_rays[:, 1] * z, z, np.ones_like(z)))
    points = (inv_m_depth @ points.T).T[:, :3]
    valid = z > 0
    return points, valid


def project_points_undistorted(points: np.ndarray, m_color: np.ndarray, new_k: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    points_h = np.column_stack((points, np.ones((points.shape[0],), dtype=np.float64)))
    color_points = (m_color @ points_h.T).T[:, :3]
    z = color_points[:, 2]
    normalized = color_points[:, :2] / z[:, None]
    pixels = np.column_stack(
        (
            new_k[0, 0] * normalized[:, 0] + new_k[0, 2],
            new_k[1, 1] * normalized[:, 1] + new_k[1, 2],
        )
    )
    return pixels, z


def splat_depth(
    pixels: np.ndarray,
    depth_values: np.ndarray,
    z_values: np.ndarray,
    valid: np.ndarray,
    size: tuple[int, int],
) -> np.ndarray:
    width, height = size
    xi = np.rint(pixels[:, 0]).astype(np.int32)
    yi = np.rint(pixels[:, 1]).astype(np.int32)
    in_bounds = (
        valid
        & np.isfinite(z_values)
        & (z_values > 0)
        & (xi >= 0)
        & (xi < width)
        & (yi >= 0)
        & (yi < height)
    )
    depth_map = np.zeros((height, width), dtype=np.float32)
    if not np.any(in_bounds):
        return depth_map

    xi = xi[in_bounds]
    yi = yi[in_bounds]
    depth_values = depth_values[in_bounds]
    z_values = z_values[in_bounds]
    order = np.argsort(z_values)[::-1]
    depth_map[yi[order], xi[order]] = depth_values[order].astype(np.float32)
    return depth_map


def densify_depth_map(
    depth_map: np.ndarray,
    kernel_size: int,
    iterations: int,
    min_neighbors: int,
    use_min: bool = False,
    use_nearest: bool = False,
) -> np.ndarray:
    if kernel_size <= 1 or iterations <= 0:
        return depth_map
    if kernel_size % 2 == 0:
        raise ValueError(f"densify kernel size must be odd, got {kernel_size}")

    dense = depth_map.copy()
    if use_nearest:
        invalid = dense <= 0
        if np.any(invalid):
            _, indices = distance_transform_edt(invalid, return_indices=True)
            dense[invalid] = dense[indices[0][invalid], indices[1][invalid]]
        return dense

    kernel = np.ones((kernel_size, kernel_size), dtype=np.float32)
    for _ in range(iterations):
        valid = (dense > 0).astype(np.float32)
        neighbor_count = cv2.filter2D(valid, -1, kernel, borderType=cv2.BORDER_REPLICATE)
        fill_mask = (dense <= 0) & (neighbor_count >= float(min_neighbors))
        if not np.any(fill_mask):
            break
        if use_min:
            sentinel = np.where(dense > 0, dense, np.float32(1e9))
            neighbor_min = cv2.erode(sentinel, kernel, borderType=cv2.BORDER_REPLICATE)
            neighbor_min = np.where(neighbor_min >= 1e9, np.float32(0.0), neighbor_min)
            dense[fill_mask] = neighbor_min[fill_mask]
        else:
            neighbor_sum = cv2.filter2D(dense, -1, kernel, borderType=cv2.BORDER_REPLICATE)
            neighbor_avg = neighbor_sum / np.maximum(neighbor_count, 1.0)
            dense[fill_mask] = neighbor_avg[fill_mask]
    return dense


def colorize_depth(depth_m: np.ndarray, min_depth_m: float, max_depth_m: float) -> np.ndarray:
    valid = depth_m > 0
    scaled = np.zeros(depth_m.shape, dtype=np.uint8)
    scaled[valid] = np.clip(
        (1.0 - (depth_m[valid] - min_depth_m) / (max_depth_m - min_depth_m)) * 255.0,
        0,
        255,
    ).astype(np.uint8)
    colored = cv2.applyColorMap(scaled, cv2.COLORMAP_TURBO)
    colored[~valid] = 0
    return colored


def overlay_depth(
    rgb_bgr: np.ndarray, depth_m: np.ndarray, alpha: float, min_depth_m: float, max_depth_m: float
) -> np.ndarray:
    colored = colorize_depth(depth_m, min_depth_m, max_depth_m)
    mask = depth_m > 0
    out = rgb_bgr.copy()
    out[mask] = cv2.addWeighted(rgb_bgr[mask], 1.0 - alpha, colored[mask], alpha, 0.0)
    return out


def make_writer(path: Path, fps: float, size: tuple[int, int]) -> cv2.VideoWriter:
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, size)
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {path}")
    return writer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Align Kinect depth to RGB with ksynctables temporal matching + batch offset audit."
    )
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--sequence", default=DEFAULT_SEQUENCE)
    parser.add_argument("--node", type=int, default=1)
    parser.add_argument("--start-frame", type=int, default=0)
    parser.add_argument("--end-frame", type=int, default=None)
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument(
        "--depth-frame-offset",
        type=int,
        default=0,
        help="Fallback for invalid color timestamp rows (univ_time < 0).",
    )
    parser.add_argument("--legacy-pairing", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--alpha", type=float, default=0.55)
    parser.add_argument("--min-depth-m", type=float, default=0.5)
    parser.add_argument("--max-depth-m", type=float, default=6.0)
    parser.add_argument("--densify-kernel-size", type=int, default=9)
    parser.add_argument("--densify-iters", type=int, default=2)
    parser.add_argument("--densify-min-neighbors", type=int, default=3)
    parser.add_argument("--densify-use-min", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--densify-use-nearest", action="store_true")
    parser.add_argument("--use-kcalibration", action="store_true")
    parser.add_argument("--large-match-warn-ms", type=float, default=50.0)
    parser.add_argument(
        "--misalignment-log",
        type=Path,
        default=DEFAULT_PANOPTIC_ROOT / "depth_frame_misalignment.txt",
        help="Where to append unstable offset entries.",
    )
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Run all sequences in all cmu_panoptic_kinect* directories under --panoptic-root.",
    )
    parser.add_argument(
        "--panoptic-root",
        type=Path,
        default=DEFAULT_PANOPTIC_ROOT,
        help="Root containing cmu_panoptic_kinect1..10 folders.",
    )
    parser.add_argument(
        "--nodes",
        default="",
        help="Optional comma list, e.g. 1,2,3. Empty means infer from dataset dir name in --run-all.",
    )
    parser.add_argument(
        "--offset-only",
        action="store_true",
        help="Only compute/write offset files and misalignment log; skip video generation.",
    )
    parser.add_argument(
        "--pose-subdir",
        default="hdPose3d_stage1_coco19",
        help="Pose folder name under each sequence (or matching .tar).",
    )
    parser.add_argument(
        "--max-pose-time-error-ms",
        type=float,
        default=500.0,
        help="Reject frame if nearest pose scene is farther than this in univ_time.",
    )
    parser.add_argument(
        "--keep-no-human",
        action="store_true",
        help="Keep frames even if pose labels report no bodies.",
    )
    parser.add_argument(
        "--skip-pair-export",
        action="store_true",
        help="Do not save rgb/depth frame pairs to folders.",
    )
    parser.add_argument(
        "--skip-video",
        action="store_true",
        help="Skip writing overlay video.",
    )
    parser.add_argument("--rgb-dir-name", default="rgb", help="RGB frame folder name under sequence.")
    parser.add_argument("--depth-dir-name", default="depth", help="Depth frame folder name under sequence.")
    parser.add_argument(
        "--manifest-name",
        default="paired_frames_manifest.jsonl",
        help="Per-sequence manifest filename for kept rgb/depth pairs.",
    )
    parser.add_argument(
        "--reindex-pairs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "After human-presence filtering, save rgb/depth as contiguous 00000000.png, 00000001.png, ... "
            "and record original Kinect RGB indices in the manifest. "
            "Use --no-reindex-pairs to name files by original rgb frame index (sparse)."
        ),
    )
    return parser.parse_args()


def parse_nodes(spec: str) -> list[int]:
    s = spec.strip()
    if not s:
        return []
    out: list[int] = []
    for tok in s.split(","):
        tok = tok.strip()
        if tok:
            out.append(int(tok))
    return out


def infer_nodes_from_dataset_dir(data_root: Path) -> list[int]:
    name = data_root.name
    if name.startswith("cmu_panoptic_kinect"):
        tail = name.replace("cmu_panoptic_kinect", "")
        if tail.isdigit():
            return [int(tail)]
    return []


def discover_jobs_for_all(panoptic_root: Path, forced_nodes: list[int]) -> list[tuple[Path, str, int]]:
    jobs: list[tuple[Path, str, int]] = []
    for dset in sorted(panoptic_root.glob("cmu_panoptic_kinect*")):
        if not dset.is_dir():
            continue
        nodes = forced_nodes[:] if forced_nodes else infer_nodes_from_dataset_dir(dset)
        if not nodes:
            continue
        for seq_dir in sorted(p for p in dset.iterdir() if p.is_dir() and not p.name.startswith("out_")):
            seq = seq_dir.name
            for node in nodes:
                jobs.append((dset, seq, node))
    return jobs


def write_offset_file(seq_dir: Path, offset: int) -> None:
    for old in seq_dir.glob("depth_frame_offset_is_*.txt"):
        old.unlink(missing_ok=True)
    out = seq_dir / f"depth_frame_offset_is_{offset}.txt"
    out.write_text(f"{offset}\n", encoding="utf-8")


def append_misalignment_log(log_path: Path, data_root: Path, sequence: str, node: int, offsets: list[int]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{data_root.name}/{sequence} node={node} offsets@{CHECKPOINTS}={offsets}\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)


class PosePresenceSource:
    """Load body3DScene JSONs and answer whether any body is present."""

    def __init__(self, seq_dir: Path, pose_subdir: str) -> None:
        self.pose_root = seq_dir / pose_subdir
        self.pose_tar = seq_dir / f"{pose_subdir}.tar"
        self._cache: dict[int, bool] = {}
        self._tar_index: dict[int, tarfile.TarInfo] | None = None
        if not self.pose_root.is_dir() and not self.pose_tar.is_file():
            raise FileNotFoundError(
                f"Pose labels missing: neither {self.pose_root} nor {self.pose_tar}"
            )

    def _build_tar_index(self) -> dict[int, tarfile.TarInfo]:
        if self._tar_index is not None:
            return self._tar_index
        out: dict[int, tarfile.TarInfo] = {}
        with tarfile.open(self.pose_tar, "r") as tf:
            for m in tf.getmembers():
                name = Path(m.name).name
                if not name.startswith("body3DScene_") or not name.endswith(".json"):
                    continue
                try:
                    sid = int(name[len("body3DScene_") : -len(".json")])
                except ValueError:
                    continue
                out[sid] = m
        self._tar_index = out
        return out

    def load_scene(self, scene_id: int) -> dict | None:
        if self.pose_root.is_dir():
            p = self.pose_root / f"body3DScene_{scene_id:08d}.json"
            if not p.is_file():
                return None
            return load_json(p)
        idx = self._build_tar_index()
        member = idx.get(scene_id)
        if member is None:
            return None
        with tarfile.open(self.pose_tar, "r") as tf:
            fobj = tf.extractfile(member)
            if fobj is None:
                return None
            return json.load(fobj)

    def has_body(self, scene_id: int) -> bool:
        if scene_id in self._cache:
            return self._cache[scene_id]
        scene = self.load_scene(scene_id)
        ok = bool(scene is not None and len(scene.get("bodies", [])) > 0)
        self._cache[scene_id] = ok
        return ok

    def sorted_univ_time_table(self) -> tuple[np.ndarray, np.ndarray]:
        pairs: list[tuple[float, int]] = []
        if self.pose_root.is_dir():
            for p in sorted(self.pose_root.glob("body3DScene_*.json")):
                try:
                    sid = int(p.stem.split("_")[-1])
                except ValueError:
                    continue
                scene = load_json(p)
                if "univTime" in scene:
                    pairs.append((float(scene["univTime"]), sid))
        else:
            idx = self._build_tar_index()
            with tarfile.open(self.pose_tar, "r") as tf:
                for sid in sorted(idx):
                    fobj = tf.extractfile(idx[sid])
                    if fobj is None:
                        continue
                    scene = json.load(fobj)
                    if "univTime" in scene:
                        pairs.append((float(scene["univTime"]), sid))
        if not pairs:
            raise ValueError("No pose univTime entries found in pose labels")
        pairs.sort(key=lambda x: x[0])
        times = np.asarray([p[0] for p in pairs], dtype=np.float64)
        ids = np.asarray([p[1] for p in pairs], dtype=np.int32)
        return times, ids


def nearest_scene_ids_for_times(
    query_times: np.ndarray, pose_times: np.ndarray, pose_ids: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    pos = np.searchsorted(pose_times, query_times, side="left")
    pos0 = np.clip(pos - 1, 0, len(pose_times) - 1)
    pos1 = np.clip(pos, 0, len(pose_times) - 1)
    e0 = np.abs(query_times - pose_times[pos0])
    e1 = np.abs(query_times - pose_times[pos1])
    use1 = e1 < e0
    best = np.where(use1, pos1, pos0)
    return pose_ids[best], np.minimum(e0, e1)


def compute_offset_rule(
    seq_dir: Path,
    color_ut: np.ndarray,
    depth_idx_map: np.ndarray,
    fallback_mask: np.ndarray,
    *,
    log_path: Path,
    data_root: Path,
    sequence: str,
    node: int,
) -> tuple[int | None, bool]:
    offsets: list[int] = []
    for c in CHECKPOINTS:
        if c < 0 or c >= len(depth_idx_map) or fallback_mask[c]:
            # Missing reliable checkpoint -> unstable for this rule.
            append_misalignment_log(log_path, data_root, sequence, node, offsets + [999999])
            return None, False
        offsets.append(int(depth_idx_map[c] - c))

    stable = offsets[0] == offsets[1] == offsets[2]
    if stable:
        write_offset_file(seq_dir, offsets[0])
        return offsets[0], True
    append_misalignment_log(log_path, data_root, sequence, node, offsets)
    return None, False


def process_one(args: argparse.Namespace, data_root: Path, sequence: str, node: int) -> None:
    seq_dir = data_root / sequence
    node_name = f"KINECTNODE{node}"
    camera_name = f"50_{node:02d}"

    kinect_calib = load_json(seq_dir / f"kcalibration_{sequence}.json")
    panoptic_calib = load_json(seq_dir / f"calibration_{sequence}.json")
    sensor = kinect_calib["sensors"][node - 1]
    if args.use_kcalibration:
        panoptic_camera = camera_from_kcalibration(kinect_calib, node)
    else:
        panoptic_camera = camera_from_panoptic_calibration(panoptic_calib, camera_name)

    ksync_path = seq_dir / f"ksynctables_{sequence}.json"
    ksync = load_json(ksync_path) if ksync_path.is_file() else None
    color_ut: np.ndarray | None = None
    depth_ut: np.ndarray | None = None
    if ksync is not None and not args.legacy_pairing:
        color_ut, depth_ut = ksync_univ_time_vectors(ksync, node)
        print(f"[{data_root.name}/{sequence} n{node}] loaded ksync c={len(color_ut)} d={len(depth_ut)}")
    elif not args.legacy_pairing:
        raise FileNotFoundError(f"ksynctables required: {ksync_path} (or use --legacy-pairing)")

    video_path = seq_dir / "kinectVideos" / f"kinect_{camera_name}.mp4"
    depth_path = seq_dir / "kinect_shared_depth" / node_name / "depthdata.dat"

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open RGB video: {video_path}")
    rgb_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    depth_reader = DepthReader(depth_path)
    depth_frame_count = depth_reader.n_frames
    start_frame = int(args.start_frame)
    end_frame = rgb_frame_count if args.end_frame is None else int(args.end_frame)
    if end_frame > rgb_frame_count:
        end_frame = rgb_frame_count
    if start_frame < 0 or end_frame <= start_frame:
        raise ValueError(f"Bad frame range [{start_frame},{end_frame})")

    if color_ut is not None and end_frame > len(color_ut):
        end_frame = min(end_frame, len(color_ut))

    # Vectorized temporal mapping once per sequence/node.
    if args.legacy_pairing:
        depth_idx_map = np.arange(rgb_frame_count, dtype=np.int32) + int(args.depth_frame_offset)
        fallback_mask = np.zeros(rgb_frame_count, dtype=bool)
    else:
        assert color_ut is not None and depth_ut is not None
        depth_idx_map, fallback_mask, _err = build_depth_index_map(
            color_ut,
            depth_ut,
            fallback_offset=args.depth_frame_offset,
            large_match_warn_ms=float(args.large_match_warn_ms),
        )
        _stable_offset, _stable = compute_offset_rule(
            seq_dir,
            color_ut,
            depth_idx_map,
            fallback_mask,
            log_path=args.misalignment_log,
            data_root=data_root,
            sequence=sequence,
            node=node,
        )

    # Range bounds check for mapped depth indices.
    sub_idx = depth_idx_map[start_frame:end_frame]
    if np.any(sub_idx < 0) or np.any(sub_idx >= depth_frame_count):
        bad = np.where((sub_idx < 0) | (sub_idx >= depth_frame_count))[0][:5]
        raise ValueError(
            f"Mapped depth index out of range for {data_root.name}/{sequence} node={node}. "
            f"First bad local idx={bad.tolist()} values={sub_idx[bad].tolist()}"
        )

    # Human-presence filtering using pose labels (unless explicitly kept).
    keep_mask = np.zeros(rgb_frame_count, dtype=bool)
    scene_id_map = np.full(rgb_frame_count, -1, dtype=np.int32)
    pose_err_map = np.full(rgb_frame_count, np.nan, dtype=np.float64)
    if args.keep_no_human:
        keep_mask[start_frame:end_frame] = True
    else:
        if color_ut is None:
            raise RuntimeError(
                "Human-presence filtering requires ksync color times. Disable --legacy-pairing "
                "or pass --keep-no-human."
            )
        pose_src = PosePresenceSource(seq_dir, args.pose_subdir)
        pose_times, pose_ids = pose_src.sorted_univ_time_table()
        valid_window = np.arange(start_frame, end_frame, dtype=np.int64)
        valid_time_mask = np.isfinite(color_ut[valid_window]) & (color_ut[valid_window] >= 0)
        if np.any(valid_time_mask):
            q_idx = valid_window[valid_time_mask]
            q_times = color_ut[q_idx]
            sids, errs = nearest_scene_ids_for_times(q_times, pose_times, pose_ids)
            scene_id_map[q_idx] = sids
            pose_err_map[q_idx] = errs
            unique_sids = np.unique(sids)
            has_body = {int(sid): pose_src.has_body(int(sid)) for sid in unique_sids}
            ok_err = errs <= float(args.max_pose_time_error_ms)
            ok_body = np.asarray([has_body[int(s)] for s in sids], dtype=bool)
            keep_mask[q_idx] = ok_err & ok_body

    if args.offset_only:
        kept = int(np.sum(keep_mask[start_frame:end_frame]))
        total = int(end_frame - start_frame)
        print(f"[{data_root.name}/{sequence} n{node}] offset-only done (keep {kept}/{total})")
        return

    expected_size = tuple(int(v) for v in panoptic_camera["resolution"])
    if (width, height) != expected_size:
        print(f"[{data_root.name}/{sequence} n{node}] RGB size {width}x{height} expected {expected_size}")

    k_color = as_array(panoptic_camera["K"])
    d_color = flatten_distortion(panoptic_camera["distCoef"])
    new_k_color, _ = cv2.getOptimalNewCameraMatrix(k_color, d_color, (width, height), 1, (width, height))
    map1, map2 = cv2.initUndistortRectifyMap(
        k_color, d_color, None, new_k_color, (width, height), cv2.CV_32FC1
    )
    k_depth = as_array(sensor["K_depth"])
    d_depth = flatten_distortion(sensor["distCoeffs_depth"])
    inv_m_depth = np.linalg.inv(as_array(sensor["M_depth"]))
    norm_rays = cv2.undistortPoints(make_depth_grid(), k_depth, d_depth).reshape(-1, 2)
    m_color = as_array(sensor["M_color"])

    output_dir = args.output_dir if args.output_dir is not None else (seq_dir / DEFAULT_OUTPUT_SUBDIR / camera_name)
    range_suffix = ""
    if start_frame != 0 or end_frame != rgb_frame_count:
        range_suffix = f"_f{start_frame:06d}_{end_frame - 1:06d}"
    dense_suffix = ""
    if args.densify_kernel_size > 1 and args.densify_iters > 0:
        dense_suffix = f"_dense_k{args.densify_kernel_size:02d}_i{args.densify_iters:02d}"
    mode_tag = "_legacy_offset" if args.legacy_pairing else "_ksync_temporal"
    undist_output = output_dir / (
        f"{sequence}_{camera_name}_depth_on_rgb_undistorted_full_fov{mode_tag}{dense_suffix}{range_suffix}.mp4"
    )

    writer = None
    if not args.skip_video:
        writer = make_writer(undist_output, args.fps / max(1, args.stride), (width, height))
    min_kernel = np.ones((5, 5), dtype=np.float32)

    rgb_dir = seq_dir / args.rgb_dir_name
    depth_dir = seq_dir / args.depth_dir_name
    manifest_path = seq_dir / args.manifest_name
    manifest_f = None
    if not args.skip_pair_export:
        rgb_dir.mkdir(parents=True, exist_ok=True)
        depth_dir.mkdir(parents=True, exist_ok=True)
        manifest_f = manifest_path.open("w", encoding="utf-8")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        if writer is not None:
            writer.release()
        if manifest_f is not None:
            manifest_f.close()
        raise RuntimeError(f"Could not reopen RGB video: {video_path}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    total_written = 0
    total_kept = 0
    pair_index = 0
    try:
        # Faster: sequential read (no per-frame CAP_PROP_POS_FRAMES set).
        for frame_idx in range(start_frame, end_frame):
            ok, rgb = cap.read()
            if not ok:
                break
            if (frame_idx - start_frame) % max(1, args.stride) != 0:
                continue
            if not bool(keep_mask[frame_idx]):
                continue

            depth_frame_index = int(depth_idx_map[frame_idx])
            depth = depth_reader.read(depth_frame_index)
            points, valid = unproject_depth(depth, norm_rays, inv_m_depth)
            depth_m = depth.reshape(-1).astype(np.float32) * 0.001

            rgb_undist = cv2.remap(rgb, map1, map2, interpolation=cv2.INTER_LINEAR)
            pixels_undist, z_undist = project_points_undistorted(points, m_color, new_k_color)
            aligned_depth = splat_depth(pixels_undist, depth_m, z_undist, valid, (width, height))
            aligned_depth = densify_depth_map(
                aligned_depth,
                kernel_size=args.densify_kernel_size,
                iterations=args.densify_iters,
                min_neighbors=args.densify_min_neighbors,
                use_min=args.densify_use_min,
                use_nearest=args.densify_use_nearest,
            )
            sentinel = np.where(aligned_depth > 0, aligned_depth, np.float32(1e9))
            eroded = cv2.erode(sentinel, min_kernel)
            aligned_depth = np.where(eroded >= 1e9, np.float32(0.0), eroded)

            if writer is not None:
                writer.write(
                    overlay_depth(
                        rgb_undist,
                        aligned_depth,
                        args.alpha,
                        args.min_depth_m,
                        args.max_depth_m,
                    )
                )
            if not args.skip_pair_export:
                if args.reindex_pairs:
                    stem = f"{pair_index:08d}"
                else:
                    stem = f"{frame_idx:08d}"
                rgb_out = rgb_dir / f"{stem}.png"
                depth_out = depth_dir / f"{stem}.png"
                cv2.imwrite(str(rgb_out), rgb_undist)
                depth_mm_u16 = np.clip(np.round(aligned_depth * 1000.0), 0, 65535).astype(np.uint16)
                cv2.imwrite(str(depth_out), depth_mm_u16)
                if manifest_f is not None:
                    rec = {
                        # Original Kinect RGB frame index in the video (sparse after filtering).
                        "frame_idx": int(frame_idx),
                        "rgb_frame_idx": int(frame_idx),
                        "depth_frame_idx": int(depth_frame_index),
                        "scene_id": int(scene_id_map[frame_idx]) if scene_id_map[frame_idx] >= 0 else None,
                        "pose_time_err_ms": (
                            float(pose_err_map[frame_idx]) if np.isfinite(pose_err_map[frame_idx]) else None
                        ),
                        "rgb_path": str(rgb_out),
                        "depth_path": str(depth_out),
                    }
                    if args.reindex_pairs:
                        # Contiguous index matching 00000000.png, 00000001.png, ...
                        rec["pair_index"] = int(pair_index)
                    manifest_f.write(json.dumps(rec) + "\n")
                pair_index += 1
            total_kept += 1
            total_written += 1
            if total_written == 1 or total_written % 60 == 0:
                print(
                    f"[{data_root.name}/{sequence} n{node}] "
                    f"written={total_written} rgb={frame_idx} depth={depth_frame_index}"
                )
    finally:
        cap.release()
        if writer is not None:
            writer.release()
        if manifest_f is not None:
            manifest_f.close()

    msg = f"[{data_root.name}/{sequence} n{node}] kept={total_kept} wrote={total_written}"
    if not args.skip_video:
        msg += f" -> {undist_output}"
    if not args.skip_pair_export:
        msg += f" pairs:{rgb_dir.name}/{depth_dir.name} manifest:{manifest_path.name}"
    print(msg)


def main() -> None:
    args = parse_args()
    forced_nodes = parse_nodes(args.nodes)

    if args.run_all:
        jobs = discover_jobs_for_all(args.panoptic_root, forced_nodes)
        if not jobs:
            raise RuntimeError(f"No jobs found under {args.panoptic_root}")
        print(f"Found {len(jobs)} jobs")
        failed: list[str] = []
        for i, (data_root, seq, node) in enumerate(jobs, start=1):
            print(f"[{i}/{len(jobs)}] {data_root.name}/{seq} node={node}")
            try:
                process_one(args, data_root, seq, node)
            except Exception as e:  # keep batch running
                msg = f"{data_root.name}/{seq} node={node}: {e}"
                print(f"  ERROR: {msg}")
                failed.append(msg)
        if failed:
            print(f"Done with failures: {len(failed)}")
            for m in failed[:20]:
                print(f"  - {m}")
            raise SystemExit(1)
        print("Done.")
        return

    # Single-job mode (backward compatible with old usage).
    process_one(args, Path(args.data_root), args.sequence, int(args.node))


if __name__ == "__main__":
    main()
