#!/usr/bin/env python3
"""Preprocess CMU Panoptic Kinect depth/RGB alignment videos."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Tuple

import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt
# command: python preprocess_cmu_kinect.py --start-frame 4000 --end-frame 4150 --node 2 --depth-frame-offset -1

DEFAULT_DATA_ROOT = Path("/media/s/8tb-data/data/cmu_panoptic/cmu_panoptic_kinect2")
DEFAULT_SEQUENCE = "170221_haggling_b1"                    #need to change
# DEFAULT_SEQUENCE = "170404_haggling_a2"
# DEFAULT_SEQUENCE = "170404_haggling_a1"
DEFAULT_OUTPUT_SUBDIR = Path("preprocessed_videos")
DEPTH_WIDTH = 512
DEPTH_HEIGHT = 424


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
    """Return a camera dict compatible with camera_from_panoptic_calibration, using kcalibration color fields."""
    sensor = kcalibration["sensors"][node - 1]
    return {
        "name": sensor.get("name", f"KINECTNODE{node}"),
        "K": sensor["K_color"],
        "distCoef": sensor["distCoeffs_color"],
        "resolution": sensor.get("color_resolution", [1920, 1080]),
    }


def read_depth_frame(depth_path: Path, frame_index: int) -> np.ndarray:
    frame_values = DEPTH_WIDTH * DEPTH_HEIGHT
    offset = frame_index * frame_values * np.dtype("<u2").itemsize
    with depth_path.open("rb") as f:
        f.seek(offset)
        data = np.fromfile(f, dtype="<u2", count=frame_values)
    if data.size != frame_values:
        raise EOFError(f"Depth frame {frame_index} is outside {depth_path}")
    depth = data.reshape((DEPTH_HEIGHT, DEPTH_WIDTH))
    return np.fliplr(depth)


def make_depth_grid() -> np.ndarray:
    xs, ys = np.meshgrid(
        np.arange(DEPTH_WIDTH, dtype=np.float32),
        np.arange(DEPTH_HEIGHT, dtype=np.float32),
    )
    return np.stack((xs, ys), axis=-1).reshape(-1, 1, 2)


def unproject_depth(depth: np.ndarray, sensor: dict, grid: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    k_depth = as_array(sensor["K_depth"])
    d_depth = flatten_distortion(sensor["distCoeffs_depth"])
    # print("k_depth from calibration json: ", k_depth)
    # print("d_depth from calibration json: ", d_depth)
    m_depth = as_array(sensor["M_depth"])

    # For each distorted pixel, recover the true ray direction in normalized camera space.
    # We remap coordinates (not depth values) to avoid interpolating depth across object boundaries.
    norm = cv2.undistortPoints(grid, k_depth, d_depth).reshape(-1, 2)
    # Convert raw integer millimeter depths to meters.
    z = depth.reshape(-1).astype(np.float64) * 0.001
    # Scale the normalized ray direction by depth to get 3D camera-space points, then append w=1 for the extrinsic transform.
    points = np.column_stack((norm[:, 0] * z, norm[:, 1] * z, z, np.ones_like(z)))
    # Apply inverse of the depth camera extrinsic to go from camera space to world space.
    points = (np.linalg.inv(m_depth) @ points.T).T[:, :3]
    # Zero-depth pixels are holes (no return from the sensor).
    valid = z > 0
    return points, valid


def project_points_undistorted(points: np.ndarray, sensor: dict, new_k: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    m_color = as_array(sensor["M_color"])
    points_h = np.column_stack((points, np.ones((points.shape[0],), dtype=np.float64)))
    color_points = (m_color @ points_h.T).T[:, :3] # verified by Simon
    # color_points = (np.linalg.inv(m_color) @ points_h.T).T[:, :3] # verified by Simon, now it is in Kinect's weird color frame where x is left, y is up, and z is forward
    # color_points[:, 0] = -color_points[:, 0] # flip x to get right-handed coordinates where x is right, y is down, and z is forward, which matches the RGB image coordinates
    # color_points[:, 1] = -color_points[:, 1] # flip y to get right-handed coordinates where x is right, y is down, and z is forward, which matches the RGB image coordinatess
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
    size: Tuple[int, int],
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
            # Erode with a large sentinel so zero-holes don't compete; restore unfilled holes to 0.
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


def overlay_depth(rgb_bgr: np.ndarray, depth_m: np.ndarray, alpha: float, min_depth_m: float, max_depth_m: float) -> np.ndarray:
    colored = colorize_depth(depth_m, min_depth_m, max_depth_m)
    mask = depth_m > 0
    out = rgb_bgr.copy()
    out[mask] = cv2.addWeighted(rgb_bgr[mask], 1.0 - alpha, colored[mask], alpha, 0.0)
    return out


def make_writer(path: Path, fps: float, size: Tuple[int, int]) -> cv2.VideoWriter:
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, size)
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {path}")
    return writer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Align CMU Panoptic Kinect depth frames to Kinect RGB video."
    )
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--sequence", default=DEFAULT_SEQUENCE)
    parser.add_argument("--node", type=int, default=1)
    parser.add_argument("--start-frame", type=int, default=0, help="Inclusive first RGB/depth frame index to process.")
    parser.add_argument("--end-frame", type=int, default=None, help="Exclusive last RGB/depth frame index to process.")
    parser.add_argument("--stride", type=int, default=1, help="Frame stride.")
    parser.add_argument(
        "--depth-frame-offset",
        type=int,
        default=0,
        help="Temporal offset applied to depth frame indices relative to RGB. Positive means later depth.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to <sequence>/preprocessed_videos/<camera>.",
    )
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--alpha", type=float, default=0.55)
    parser.add_argument("--min-depth-m", type=float, default=0.5)
    parser.add_argument("--max-depth-m", type=float, default=6.0)
    parser.add_argument("--densify-kernel-size", type=int, default=9, help="Odd neighbor window size for filling empty projected depth pixels.")
    parser.add_argument("--densify-iters", type=int, default=2, help="Number of local-average fill passes after projection.")
    parser.add_argument("--densify-min-neighbors", type=int, default=3, help="Minimum valid neighbors required before filling an empty pixel.")
    parser.add_argument("--densify-use-min", action=argparse.BooleanOptionalAction, default=True, help="Fill holes with minimum non-zero neighbor depth instead of mean (default: true).")
    parser.add_argument("--densify-use-nearest", action="store_true", help="Fill all holes with the depth of the nearest valid pixel in pixel coordinates (single pass, ignores kernel/iter/min-neighbors).")
    parser.add_argument("--use-kcalibration", action="store_true", help="Use kcalibration_*.json instead of calibration_*.json for all camera parameters.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seq_dir = args.data_root / args.sequence
    node_name = f"KINECTNODE{args.node}"
    camera_name = f"50_{args.node:02d}"

    kinect_calib = load_json(seq_dir / f"kcalibration_{args.sequence}.json")
    panoptic_calib = load_json(seq_dir / f"calibration_{args.sequence}.json")
    sensor = kinect_calib["sensors"][args.node - 1]
    if args.use_kcalibration:
        panoptic_camera = camera_from_kcalibration(kinect_calib, args.node)
    else:
        panoptic_camera = camera_from_panoptic_calibration(panoptic_calib, camera_name)

    video_path = seq_dir / "kinectVideos" / f"kinect_{camera_name}.mp4"
    depth_path = seq_dir / "kinect_shared_depth" / node_name / "depthdata.dat"
    if args.output_dir is None:
        output_dir = seq_dir / DEFAULT_OUTPUT_SUBDIR / camera_name
    else:
        output_dir = args.output_dir

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open RGB video: {video_path}")

    rgb_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    depth_frame_count = depth_path.stat().st_size // (DEPTH_WIDTH * DEPTH_HEIGHT * np.dtype("<u2").itemsize)
    start_frame = args.start_frame
    end_frame = rgb_frame_count if args.end_frame is None else args.end_frame
    if start_frame < 0:
        raise ValueError(f"start-frame must be >= 0, got {start_frame}")
    if end_frame <= start_frame:
        raise ValueError(f"end-frame must be greater than start-frame, got start={start_frame}, end={end_frame}")
    if args.densify_kernel_size % 2 == 0:
        raise ValueError(f"densify-kernel-size must be odd, got {args.densify_kernel_size}")

    if end_frame > rgb_frame_count:
        raise ValueError(f"Requested end-frame {end_frame} exceeds RGB frame count {rgb_frame_count}")

    depth_start = start_frame + args.depth_frame_offset
    depth_end_inclusive = (end_frame - 1) + args.depth_frame_offset
    if depth_start < 0 or depth_end_inclusive >= depth_frame_count:
        raise ValueError(
            "Requested RGB range with depth-frame-offset exceeds depth frame bounds: "
            f"rgb=[{start_frame}, {end_frame}), depth-offset={args.depth_frame_offset}, "
            f"depth-frame-count={depth_frame_count}"
        )

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    expected_size = tuple(int(v) for v in panoptic_camera["resolution"])
    if (width, height) != expected_size:
        print(f"RGB video size: {width}x{height}")

    k_color = as_array(panoptic_camera["K"])
    d_color = flatten_distortion(panoptic_camera["distCoef"])
    print("k_color from calibration json: ", k_color)
    print("d_color from calibration json: ", d_color)
    new_k_color, _ = cv2.getOptimalNewCameraMatrix(k_color, d_color, (width, height), 1, (width, height))
    print("new_k_color full FOV: ", new_k_color)

    range_suffix = ""
    if start_frame != 0 or end_frame != rgb_frame_count:
        range_suffix = f"_f{start_frame:06d}_{end_frame - 1:06d}"
    dense_suffix = ""
    if args.densify_kernel_size > 1 and args.densify_iters > 0:
        dense_suffix = f"_dense_k{args.densify_kernel_size:02d}_i{args.densify_iters:02d}"
    offset_suffix = ""
    if args.depth_frame_offset != 0:
        offset_suffix = f"_dtoff_{args.depth_frame_offset:+d}".replace("+", "p").replace("-", "m")
    undist_output = output_dir / (
        f"{args.sequence}_{camera_name}_depth_on_rgb_undistorted_full_fov{dense_suffix}{offset_suffix}{range_suffix}.mp4"
    )

    undist_writer = make_writer(undist_output, args.fps / args.stride, (width, height))

    grid = make_depth_grid()
    total_written = 0
    calib_source = "kcalibration" if args.use_kcalibration else "calibration"
    print(f"Using {calib_source} sensor {args.node} and camera {panoptic_camera['name']}")
    print(f"RGB: {video_path}")
    print(f"Depth: {depth_path}")
    print(f"Frame range: [{start_frame}, {end_frame}) with stride {args.stride}")
    print(f"Depth frame offset: {args.depth_frame_offset}")
    print(
        f"Densify: kernel={args.densify_kernel_size}, iterations={args.densify_iters}, "
        f"min_neighbors={args.densify_min_neighbors}, use_min={args.densify_use_min}, use_nearest={args.densify_use_nearest}"
    )

    try:
        for frame_index in range(start_frame, end_frame, args.stride):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, rgb = cap.read()
            if not ok:
                print(f"Stopping: RGB frame {frame_index} could not be read")
                break

            depth_frame_index = frame_index + args.depth_frame_offset
            depth = read_depth_frame(depth_path, depth_frame_index)
            points, valid = unproject_depth(depth, sensor, grid)
            depth_m = depth.reshape(-1).astype(np.float32) * 0.001

            # M_color is from world to color: T_color_world
            # M_depth is from world to depth: T_depth_world
            rgb_undist = cv2.undistort(rgb, k_color, d_color, None, new_k_color)
            pixels_undist, z_undist = project_points_undistorted(points, sensor, new_k_color)
            aligned_depth_undist = splat_depth(
                pixels_undist, depth_m, z_undist, valid, (width, height)
            )
            aligned_depth_undist = densify_depth_map(
                aligned_depth_undist,
                kernel_size=args.densify_kernel_size,
                iterations=args.densify_iters,
                min_neighbors=args.densify_min_neighbors,
                use_min=args.densify_use_min,
                use_nearest=args.densify_use_nearest,
            )
            min_kernel = np.ones((5, 5), dtype=np.float32)
            sentinel = np.where(aligned_depth_undist > 0, aligned_depth_undist, np.float32(1e9))
            eroded = cv2.erode(sentinel, min_kernel)
            aligned_depth_undist = np.where(eroded >= 1e9, np.float32(0.0), eroded)
            undist_writer.write(
                overlay_depth(
                    rgb_undist,
                    aligned_depth_undist,
                    args.alpha,
                    args.min_depth_m,
                    args.max_depth_m,
                )
            )

            total_written += 1
            if total_written == 1 or total_written % 30 == 0:
                print(
                    f"Processed {total_written} frames through RGB frame {frame_index} "
                    f"and depth frame {depth_frame_index}"
                )
    finally:
        cap.release()
        undist_writer.release()

    print(f"Wrote {total_written} frames")
    print(f"Undistorted full-FOV overlay: {undist_output}")


if __name__ == "__main__":
    main()
