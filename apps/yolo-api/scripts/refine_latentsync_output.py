from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import soundfile as sf


SILENCE_THRESHOLD_DB = -38.0
SPEECH_THRESHOLD_DB = -32.0
SILENCE_PADDING_MS = 80
MIN_SILENCE_MS = 180
DEFAULT_MOUTH_BLEND_ALPHA = 0.78
DEFAULT_SHARPEN_AMOUNT = 0.25
DEFAULT_TRANSITION_FRAMES = 4
EPSILON = 1e-8

MOUTH_LANDMARKS = [
    61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291,
    78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308,
]
UPPER_LIP_INDEX = 13
LOWER_LIP_INDEX = 14
LEFT_MOUTH_INDEX = 78
RIGHT_MOUTH_INDEX = 308


@dataclass
class MouthROI:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        return max(0, self.y2 - self.y1)

    def valid(self) -> bool:
        return self.width > 1 and self.height > 1


@dataclass
class FrameAnalysis:
    roi: MouthROI
    mouth_points: np.ndarray | None
    openness: float
    detected: bool


@dataclass
class SilentSegment:
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refine LatentSync output without modifying LatentSync itself.")
    parser.add_argument("--template-video", required=True, type=Path)
    parser.add_argument("--synced-video", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mouth-blend-alpha", type=float, default=DEFAULT_MOUTH_BLEND_ALPHA)
    parser.add_argument("--sharpen-amount", type=float, default=DEFAULT_SHARPEN_AMOUNT)
    parser.add_argument("--transition-frames", type=int, default=DEFAULT_TRANSITION_FRAMES)
    return parser.parse_args()


def ensure_dependencies() -> object:
    try:
        import mediapipe as mp  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "缺少 mediapipe。请先在 apps/yolo-api 环境中安装 mediapipe，再运行本脚本。"
        ) from exc

    if shutil.which("ffmpeg") is None:
        raise SystemExit("未检测到 ffmpeg，请先安装 ffmpeg。")
    return mp


def open_capture(path: Path) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise SystemExit(f"无法打开视频：{path}")
    return capture


def video_meta(capture: cv2.VideoCapture) -> tuple[float, int, int, int]:
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if fps <= 0 or width <= 0 or height <= 0 or frame_count <= 0:
        raise SystemExit("视频元信息无效，无法继续处理。")
    return fps, width, height, frame_count


def load_audio_mono(path: Path) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(str(path), always_2d=False)
    if isinstance(audio, np.ndarray) and audio.ndim == 2:
        audio = audio.mean(axis=1)
    audio = np.asarray(audio, dtype=np.float32)
    if audio.size == 0:
        raise SystemExit("音频为空，无法进行静音门控。")
    return audio, int(sample_rate)


def rms_db_for_frames(audio: np.ndarray, sample_rate: int, fps: float, frame_count: int) -> np.ndarray:
    samples_per_frame = max(1, int(round(sample_rate / fps)))
    frame_db = np.full(frame_count, -120.0, dtype=np.float32)
    for index in range(frame_count):
        start = index * samples_per_frame
        end = min(audio.shape[0], start + samples_per_frame)
        if start >= audio.shape[0]:
            break
        chunk = audio[start:end]
        if chunk.size == 0:
            continue
        rms = float(np.sqrt(np.mean(np.square(chunk), dtype=np.float64)))
        frame_db[index] = 20.0 * math.log10(max(rms, EPSILON))
    return frame_db


def hysteresis_speech_mask(frame_db: np.ndarray) -> np.ndarray:
    speaking = False
    mask = np.zeros(frame_db.shape[0], dtype=bool)
    for index, db in enumerate(frame_db):
        if speaking:
            speaking = db >= SILENCE_THRESHOLD_DB
        else:
            speaking = db >= SPEECH_THRESHOLD_DB
        mask[index] = speaking
    return mask


def mask_to_segments(mask: np.ndarray, active_value: bool) -> list[SilentSegment]:
    segments: list[SilentSegment] = []
    start: int | None = None
    for index, value in enumerate(mask.tolist()):
        if value == active_value and start is None:
            start = index
        elif value != active_value and start is not None:
            segments.append(SilentSegment(start=start, end=index - 1))
            start = None
    if start is not None:
        segments.append(SilentSegment(start=start, end=mask.shape[0] - 1))
    return segments


def finalize_silence_mask(speech_mask: np.ndarray, fps: float) -> tuple[np.ndarray, list[SilentSegment]]:
    silence_segments = mask_to_segments(~speech_mask, True)
    min_silence_frames = max(1, int(round((MIN_SILENCE_MS / 1000.0) * fps)))
    pad_frames = max(0, int(round((SILENCE_PADDING_MS / 1000.0) * fps)))
    refined = np.zeros_like(speech_mask, dtype=bool)

    for segment in silence_segments:
        if segment.length < min_silence_frames:
            continue
        start = max(0, segment.start - pad_frames)
        end = min(speech_mask.shape[0] - 1, segment.end + pad_frames)
        refined[start : end + 1] = True

    merged_segments = mask_to_segments(refined, True)
    return refined, merged_segments


def transition_strength(index: int, segment: SilentSegment, transition_frames: int) -> float:
    if transition_frames <= 0 or segment.length <= 2:
        return 1.0
    start_ramp_end = min(segment.end, segment.start + transition_frames - 1)
    end_ramp_start = max(segment.start, segment.end - transition_frames + 1)

    if index <= start_ramp_end:
        return min(1.0, (index - segment.start + 1) / float(transition_frames + 1))
    if index >= end_ramp_start:
        return min(1.0, (segment.end - index + 1) / float(transition_frames + 1))
    return 1.0


def extract_landmarks(result: object, width: int, height: int) -> np.ndarray | None:
    faces = getattr(result, "multi_face_landmarks", None)
    if not faces:
        return None
    landmarks = faces[0].landmark
    points = np.array([(lm.x * width, lm.y * height) for lm in landmarks], dtype=np.float32)
    return points


def mouth_roi_from_landmarks(points: np.ndarray, width: int, height: int) -> tuple[MouthROI, np.ndarray]:
    mouth_points = points[MOUTH_LANDMARKS]
    min_xy = mouth_points.min(axis=0)
    max_xy = mouth_points.max(axis=0)
    box_width = max(4.0, float(max_xy[0] - min_xy[0]))
    box_height = max(4.0, float(max_xy[1] - min_xy[1]))

    pad_x = box_width * 0.22
    pad_top = box_height * 0.30
    pad_bottom = box_height * 0.42

    x1 = max(0, int(round(min_xy[0] - pad_x)))
    x2 = min(width, int(round(max_xy[0] + pad_x)))
    y1 = max(0, int(round(min_xy[1] - pad_top)))
    y2 = min(height, int(round(max_xy[1] + pad_bottom)))
    return MouthROI(x1=x1, y1=y1, x2=x2, y2=y2), mouth_points


def mouth_openness(points: np.ndarray) -> float:
    upper = points[UPPER_LIP_INDEX]
    lower = points[LOWER_LIP_INDEX]
    left = points[LEFT_MOUTH_INDEX]
    right = points[RIGHT_MOUTH_INDEX]
    vertical = float(np.linalg.norm(upper - lower))
    horizontal = max(float(np.linalg.norm(left - right)), 1.0)
    return vertical / horizontal


def fallback_roi(frame_shape: tuple[int, int, int], prev_roi: MouthROI | None) -> MouthROI:
    if prev_roi is not None and prev_roi.valid():
        return prev_roi
    height, width = frame_shape[:2]
    center_x = width // 2
    center_y = int(height * 0.68)
    roi_width = max(32, int(width * 0.18))
    roi_height = max(24, int(height * 0.11))
    return MouthROI(
        x1=max(0, center_x - roi_width // 2),
        y1=max(0, center_y - roi_height // 2),
        x2=min(width, center_x + roi_width // 2),
        y2=min(height, center_y + roi_height // 2),
    )


def analyze_template_frames(template_video: Path, mp: object) -> tuple[list[FrameAnalysis], float, int, int, int]:
    capture = open_capture(template_video)
    fps, width, height, frame_count = video_meta(capture)
    mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    analyses: list[FrameAnalysis] = []
    prev_roi: MouthROI | None = None

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = mesh.process(rgb)
            points = extract_landmarks(result, width, height)
            if points is not None:
                roi, mouth_points = mouth_roi_from_landmarks(points, width, height)
                prev_roi = roi if roi.valid() else prev_roi
                analyses.append(
                    FrameAnalysis(
                        roi=roi if roi.valid() else fallback_roi(frame.shape, prev_roi),
                        mouth_points=mouth_points,
                        openness=mouth_openness(points),
                        detected=True,
                    )
                )
            else:
                roi = fallback_roi(frame.shape, prev_roi)
                analyses.append(FrameAnalysis(roi=roi, mouth_points=None, openness=1e6, detected=False))
    finally:
        mesh.close()
        capture.release()

    if not analyses:
        raise SystemExit("模板视频没有可处理帧。")
    return analyses, fps, width, height, len(analyses)


def choose_closed_patch_index(analyses: list[FrameAnalysis], segment: SilentSegment, search_radius: int) -> int:
    left = max(0, segment.start - search_radius)
    right = min(len(analyses) - 1, segment.end + search_radius)
    best_index = segment.start
    best_openness = float("inf")
    for index in range(left, right + 1):
        item = analyses[index]
        if not item.roi.valid():
            continue
        score = item.openness
        if score < best_openness:
            best_index = index
            best_openness = score
    return best_index


def extract_frame_patch(video_path: Path, frame_index: int, roi: MouthROI) -> np.ndarray:
    capture = open_capture(video_path)
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok:
            raise SystemExit(f"无法读取模板视频第 {frame_index} 帧。")
        return frame[roi.y1 : roi.y2, roi.x1 : roi.x2].copy()
    finally:
        capture.release()


def build_closed_patch_map(
    template_video: Path,
    analyses: list[FrameAnalysis],
    silent_segments: list[SilentSegment],
    fps: float,
) -> dict[int, np.ndarray]:
    search_radius = max(2, int(round(0.35 * fps)))
    patch_map: dict[int, np.ndarray] = {}
    for segment in silent_segments:
        best_index = choose_closed_patch_index(analyses, segment, search_radius)
        roi = analyses[best_index].roi
        if roi.valid():
            patch_map[segment.start] = extract_frame_patch(template_video, best_index, roi)
    return patch_map


def create_mouth_mask(roi: MouthROI, mouth_points: np.ndarray | None, frame_shape: tuple[int, int, int]) -> np.ndarray:
    mask = np.zeros(frame_shape[:2], dtype=np.float32)
    if not roi.valid():
        return mask

    if mouth_points is not None and mouth_points.shape[0] >= 3:
        polygon = np.round(mouth_points).astype(np.int32)
        hull = cv2.convexHull(polygon)
        cv2.fillConvexPoly(mask, hull, 1.0)
    else:
        center = ((roi.x1 + roi.x2) // 2, (roi.y1 + roi.y2) // 2)
        axes = (
            max(2, int(round(roi.width * 0.44))),
            max(2, int(round(roi.height * 0.36))),
        )
        cv2.ellipse(mask, center, axes, 0, 0, 360, 1.0, thickness=-1)

    blur_size = max(3, int(round(max(roi.width, roi.height) * 0.18)))
    if blur_size % 2 == 0:
        blur_size += 1
    return cv2.GaussianBlur(mask, (blur_size, blur_size), 0)


def resize_patch(patch: np.ndarray, target_shape: tuple[int, int]) -> np.ndarray:
    target_width, target_height = target_shape
    if patch.shape[1] == target_width and patch.shape[0] == target_height:
        return patch
    return cv2.resize(patch, (target_width, target_height), interpolation=cv2.INTER_CUBIC)


def unsharp_mask(image: np.ndarray, amount: float) -> np.ndarray:
    if amount <= 0:
        return image
    blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=1.0, sigmaY=1.0)
    sharpened = cv2.addWeighted(image, 1.0 + amount, blurred, -amount, 0.0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def blend_roi(
    base_frame: np.ndarray,
    source_patch: np.ndarray,
    roi: MouthROI,
    mask: np.ndarray,
    alpha_scale: float,
    sharpen_amount: float,
) -> np.ndarray:
    if not roi.valid():
        return base_frame
    target = base_frame.copy()
    source_patch = resize_patch(source_patch, (roi.width, roi.height))
    source_patch = unsharp_mask(source_patch, sharpen_amount)

    base_roi = target[roi.y1 : roi.y2, roi.x1 : roi.x2].astype(np.float32)
    src_roi = source_patch.astype(np.float32)
    local_mask = mask[roi.y1 : roi.y2, roi.x1 : roi.x2].astype(np.float32)
    local_mask = np.clip(local_mask * alpha_scale, 0.0, 1.0)[..., None]

    blended = base_roi * (1.0 - local_mask) + src_roi * local_mask
    target[roi.y1 : roi.y2, roi.x1 : roi.x2] = np.clip(blended, 0, 255).astype(np.uint8)
    return target


def run_ffmpeg_mux(video_path: Path, audio_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg 合成音频失败：{result.stderr.strip() or result.stdout.strip()}")


def process_video(
    template_video: Path,
    synced_video: Path,
    temp_video_path: Path,
    analyses: list[FrameAnalysis],
    silent_segments: list[SilentSegment],
    closed_patch_map: dict[int, np.ndarray],
    fps: float,
    width: int,
    height: int,
    mouth_blend_alpha: float,
    sharpen_amount: float,
    transition_frames: int,
) -> None:
    template_capture = open_capture(template_video)
    synced_capture = open_capture(synced_video)

    current_segment_index = 0
    active_closed_patch: np.ndarray | None = None

    writer = cv2.VideoWriter(
        str(temp_video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise SystemExit("无法创建临时输出视频。")

    try:
        frame_index = 0
        while True:
            ok_template, template_frame = template_capture.read()
            ok_synced, synced_frame = synced_capture.read()
            if not ok_template or not ok_synced or frame_index >= len(analyses):
                break

            analysis = analyses[frame_index]
            roi = analysis.roi
            mask = create_mouth_mask(roi, analysis.mouth_points, template_frame.shape)
            result_frame = template_frame.copy()

            while current_segment_index < len(silent_segments) and frame_index > silent_segments[current_segment_index].end:
                current_segment_index += 1
                active_closed_patch = None

            current_segment = (
                silent_segments[current_segment_index]
                if current_segment_index < len(silent_segments)
                else None
            )
            in_silence = current_segment is not None and current_segment.start <= frame_index <= current_segment.end

            synced_patch = synced_frame[roi.y1 : roi.y2, roi.x1 : roi.x2].copy() if roi.valid() else None
            if synced_patch is None or synced_patch.size == 0:
                writer.write(result_frame)
                frame_index += 1
                continue

            if in_silence:
                if active_closed_patch is None:
                    active_closed_patch = closed_patch_map.get(current_segment.start)
                closed_patch = active_closed_patch if active_closed_patch is not None else synced_patch
                silence_strength = transition_strength(frame_index, current_segment, transition_frames)
                mouth_patch = cv2.addWeighted(
                    synced_patch.astype(np.float32),
                    max(0.0, 1.0 - silence_strength),
                    resize_patch(closed_patch, (roi.width, roi.height)).astype(np.float32),
                    min(1.0, silence_strength),
                    0.0,
                ).astype(np.uint8)
            else:
                mouth_patch = synced_patch

            result_frame = blend_roi(
                result_frame,
                mouth_patch,
                roi,
                mask,
                alpha_scale=mouth_blend_alpha,
                sharpen_amount=sharpen_amount,
            )
            writer.write(result_frame)
            frame_index += 1
    finally:
        writer.release()
        template_capture.release()
        synced_capture.release()


def validate_inputs(args: argparse.Namespace) -> None:
    for path in (args.template_video, args.synced_video, args.audio):
        if not path.exists() or not path.is_file():
            raise SystemExit(f"输入文件不存在：{path}")


def main() -> None:
    args = parse_args()
    validate_inputs(args)
    mp = ensure_dependencies()

    analyses, fps, width, height, frame_count = analyze_template_frames(args.template_video, mp)
    audio, sample_rate = load_audio_mono(args.audio)
    frame_db = rms_db_for_frames(audio, sample_rate, fps, frame_count)
    speech_mask = hysteresis_speech_mask(frame_db)
    silence_mask, silent_segments = finalize_silence_mask(speech_mask, fps)
    closed_patch_map = build_closed_patch_map(args.template_video, analyses, silent_segments, fps)

    final_video_path = args.output if args.output.suffix.lower() == ".mp4" else args.output.with_suffix(".mp4")
    with tempfile.TemporaryDirectory(prefix="latentsync_refine_") as tmp_dir:
        temp_video_path = Path(tmp_dir) / "refined_no_audio.mp4"
        process_video(
            template_video=args.template_video,
            synced_video=args.synced_video,
            temp_video_path=temp_video_path,
            analyses=analyses,
            silent_segments=mask_to_segments(silence_mask, True),
            closed_patch_map=closed_patch_map,
            fps=fps,
            width=width,
            height=height,
            mouth_blend_alpha=float(args.mouth_blend_alpha),
            sharpen_amount=float(args.sharpen_amount),
            transition_frames=max(1, int(args.transition_frames)),
        )
        run_ffmpeg_mux(temp_video_path, args.audio, final_video_path)
    print(str(final_video_path))


if __name__ == "__main__":
    main()
