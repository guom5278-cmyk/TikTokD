from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np


class StabilizeError(Exception):
    pass


@dataclass
class StabilizeConfig:
    use_gpu: bool = False
    anti_black_border: bool = True
    auto_detect: bool = True
    smoothing_alpha: float = 0.85
    preview: bool = False


def detect_subject_roi(frame: np.ndarray) -> tuple[int, int, int, int]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = face_detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(48, 48))
    if len(faces) > 0:
        x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
        return int(x), int(y), int(w), int(h)

    h, w = frame.shape[:2]
    roi_w = int(w * 0.35)
    roi_h = int(h * 0.35)
    x = (w - roi_w) // 2
    y = (h - roi_h) // 2
    return x, y, roi_w, roi_h


def choose_manual_roi(video_path: str) -> Optional[tuple[int, int, int, int]]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return None

    roi = cv2.selectROI("选择要跟踪稳定的部位（Enter确认）", frame, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow("选择要跟踪稳定的部位（Enter确认）")
    x, y, w, h = roi
    if w <= 0 or h <= 0:
        return None
    return int(x), int(y), int(w), int(h)


def _compute_flow_shift(
    prev_gray: np.ndarray,
    curr_gray: np.ndarray,
    roi: tuple[int, int, int, int],
) -> tuple[float, float]:
    x, y, w, h = roi
    mask = np.zeros_like(prev_gray)
    mask[y : y + h, x : x + w] = 255

    pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=120, qualityLevel=0.01, minDistance=8, mask=mask)
    if pts is None or len(pts) < 6:
        return 0.0, 0.0

    pts2, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, pts, None)
    if pts2 is None:
        return 0.0, 0.0

    valid = st.flatten() == 1
    if valid.sum() < 6:
        return 0.0, 0.0

    movement = pts2[valid] - pts[valid]
    dx = float(np.median(movement[:, 0]))
    dy = float(np.median(movement[:, 1]))
    return dx, dy


def _resize_without_black_border(frame: np.ndarray, border_ratio: float) -> np.ndarray:
    if border_ratio <= 1.0:
        return frame

    h, w = frame.shape[:2]
    scaled = cv2.resize(frame, None, fx=border_ratio, fy=border_ratio, interpolation=cv2.INTER_LINEAR)
    sh, sw = scaled.shape[:2]
    x0 = (sw - w) // 2
    y0 = (sh - h) // 2
    return scaled[y0 : y0 + h, x0 : x0 + w]


def stabilize_video(
    input_path: str,
    output_path: str,
    config: StabilizeConfig,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    manual_roi: Optional[tuple[int, int, int, int]] = None,
) -> Path:
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise StabilizeError(f"无法打开视频：{input_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    ok, first = cap.read()
    if not ok or first is None:
        cap.release()
        raise StabilizeError("视频首帧读取失败")

    roi = manual_roi
    if roi is None:
        roi = detect_subject_roi(first) if config.auto_detect else (width // 3, height // 3, width // 3, height // 3)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        cap.release()
        raise StabilizeError(f"无法写入输出文件：{output_path}")

    alpha = float(np.clip(config.smoothing_alpha, 0.05, 0.98))
    prev_gray = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)

    raw_tx = raw_ty = 0.0
    smooth_tx = smooth_ty = 0.0

    frame_idx = 0
    max_offset = 0.0

    while True:
        curr = first if frame_idx == 0 else None
        if curr is None:
            ok, curr = cap.read()
            if not ok or curr is None:
                break

        curr_gray = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
        dx, dy = _compute_flow_shift(prev_gray, curr_gray, roi)

        raw_tx += dx
        raw_ty += dy

        smooth_tx = alpha * smooth_tx + (1 - alpha) * raw_tx
        smooth_ty = alpha * smooth_ty + (1 - alpha) * raw_ty

        diff_x = smooth_tx - raw_tx
        diff_y = smooth_ty - raw_ty
        max_offset = max(max_offset, abs(diff_x), abs(diff_y))

        transform = np.array([[1, 0, diff_x], [0, 1, diff_y]], dtype=np.float32)
        stabilized = cv2.warpAffine(curr, transform, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

        if config.anti_black_border:
            border_ratio = 1.0 + (max_offset / max(width, height)) * 1.4
            border_ratio = float(np.clip(border_ratio, 1.0, 1.2))
            stabilized = _resize_without_black_border(stabilized, border_ratio)

        writer.write(stabilized)

        if config.preview:
            preview = np.hstack([curr, stabilized])
            cv2.putText(preview, "Raw", (16, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 255), 2)
            cv2.putText(preview, "Stabilized", (width + 16, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 255), 2)
            cv2.imshow("实时预览（Q 退出预览）", preview)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                config.preview = False
                cv2.destroyWindow("实时预览（Q 退出预览）")

        frame_idx += 1
        if progress_cb:
            progress_cb(frame_idx, total, "稳定处理中")

        prev_gray = curr_gray

    cap.release()
    writer.release()
    cv2.destroyAllWindows()

    if progress_cb:
        progress_cb(frame_idx, total, "编码完成")

    return Path(output_path)


def gpu_available() -> bool:
    try:
        return cv2.cuda.getCudaEnabledDeviceCount() > 0
    except Exception:
        return False
