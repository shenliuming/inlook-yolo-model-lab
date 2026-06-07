from __future__ import annotations

import importlib.util
import json
import logging
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.common import error_code
from app.common.exceptions import AppException
from app.config.settings import (
    get_cosyvoice_device,
    get_cosyvoice_model_dir,
    get_cosyvoice_sample_rate,
    get_whisper_beam_size,
    get_whisper_compute_type,
    get_whisper_device,
    get_whisper_language,
    get_whisper_model,
    get_whisper_vad_filter,
)
from app.utils.subprocess_utils import run_command

logger = logging.getLogger("inlook.yolo_api")

MIN_REFERENCE_SECONDS = 10.0
LOW_MEAN_VOLUME_DB = -45.0
LOW_MAX_VOLUME_DB = -35.0
SHORT_TEXT_MAX_CHARS = 120


@dataclass
class TTSResult:
    ok: bool
    engine: str
    outputPath: str
    sampleRate: int
    segments: list[dict[str, Any]] = field(default_factory=list)
    modelDir: str = ""
    promptText: str = ""
    referenceAudioPath: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CosyVoiceEngine:
    def __init__(
        self,
        *,
        model_dir: str | Path | None = None,
        device: str | None = None,
        sample_rate: int | None = None,
    ) -> None:
        self.model_dir = Path(model_dir).expanduser().resolve() if model_dir else get_cosyvoice_model_dir()
        self.device = (device or get_cosyvoice_device()).strip().lower() or "auto"
        self.sample_rate = sample_rate or get_cosyvoice_sample_rate()
        self._model: Any | None = None
        self._cosyvoice_class: Any | None = None
        self._load_wav: Any | None = None
        self._torchaudio: Any | None = None

    def health(self) -> dict[str, Any]:
        installed = self._cosyvoice_installed()
        model_exists = self.model_dir.exists()
        payload = {
            "available": installed and model_exists,
            "engine": "cosyvoice",
            "modelDir": str(self.model_dir),
            "modelExists": model_exists,
            "installed": installed,
            "device": self.device,
            "sampleRate": self.sample_rate,
            "supportsZeroShot": False,
            "requiresPromptText": True,
            "message": "CosyVoice ready" if installed and model_exists else "CosyVoice 未安装或模型目录不存在",
        }
        if not installed:
            payload["errorType"] = "cosyvoice_not_installed"
        elif not model_exists:
            payload["errorType"] = "cosyvoice_model_missing"
        return payload

    def synthesize(
        self,
        text: str,
        output_path: str,
        reference_audio_path: str | None = None,
        prompt_text: str | None = None,
    ) -> TTSResult:
        clean_text = (text or "").strip()
        if not clean_text:
            raise AppException(
                error_code.BAD_REQUEST,
                "请提供要合成的文本。",
                data={"errorType": "tts_text_required"},
                status_code=400,
            )

        target_output = Path(output_path).expanduser().resolve()
        target_output.parent.mkdir(parents=True, exist_ok=True)
        model = self._load_model()

        reference_wav: Path | None = None
        resolved_prompt_text = (prompt_text or "").strip()
        with tempfile.TemporaryDirectory(prefix="inlook_cosyvoice_") as temp_dir:
            temp_root = Path(temp_dir)
            if reference_audio_path:
                reference_wav = self.normalize_reference_audio(reference_audio_path, temp_root / "reference.wav")
                if not resolved_prompt_text:
                    resolved_prompt_text = self.infer_prompt_text(reference_wav)
                if not resolved_prompt_text:
                    raise AppException(
                        error_code.BAD_REQUEST,
                        "CosyVoice zero-shot 需要参考音频对应文本，请提供 prompt_text。",
                        data={"errorType": "prompt_text_required", "referenceAudioPath": str(reference_wav)},
                        status_code=400,
                    )

            chunks = split_tts_text(clean_text)
            segment_outputs: list[Path] = []
            for index, chunk in enumerate(chunks, 1):
                segment_path = temp_root / f"segment_{index:03d}.wav"
                self._synthesize_chunk(
                    model=model,
                    text=chunk,
                    output_path=segment_path,
                    reference_wav=reference_wav,
                    prompt_text=resolved_prompt_text,
                )
                segment_outputs.append(segment_path)

            if len(segment_outputs) == 1:
                _copy_audio(segment_outputs[0], target_output)
            else:
                concat_wavs(segment_outputs, target_output)

        return TTSResult(
            ok=True,
            engine="cosyvoice",
            outputPath=str(target_output),
            sampleRate=self.sample_rate,
            segments=[
                {"index": index, "text": chunk, "charCount": len(chunk)}
                for index, chunk in enumerate(chunks, 1)
            ],
            modelDir=str(self.model_dir),
            promptText=resolved_prompt_text,
            referenceAudioPath=str(reference_wav) if reference_wav else "",
        )

    def normalize_reference_audio(self, source_path: str | Path, destination_path: str | Path) -> Path:
        source = Path(source_path).expanduser().resolve()
        destination = Path(destination_path).expanduser().resolve()
        if not source.exists() or not source.is_file():
            raise AppException(
                error_code.BAD_REQUEST,
                "参考音频不存在。",
                data={"errorType": "reference_audio_missing", "referenceAudioPath": str(source)},
                status_code=400,
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(self.sample_rate),
            "-acodec",
            "pcm_s16le",
            str(destination),
        ]
        result = run_command(command)
        if result.returncode != 0 or not destination.exists() or destination.stat().st_size <= 44:
            logger.warning("cosyvoice reference normalize failed: %s", (result.stdout or "")[-1200:])
            raise AppException(
                error_code.BAD_REQUEST,
                "参考音频预处理失败，请上传清晰人声 wav/m4a/mp3。",
                data={"errorType": "reference_audio_normalize_failed"},
                status_code=400,
            )
        self._validate_reference_audio(destination)
        return destination

    def infer_prompt_text(self, reference_wav: Path) -> str:
        try:
            from app.services.subtitle_tool.subtitle_pack import extract_audio, transcribe

            with tempfile.TemporaryDirectory(prefix="inlook_cosyvoice_prompt_asr_") as temp_dir:
                asr_wav = Path(temp_dir) / "prompt_asr.wav"
                extract_audio(reference_wav, asr_wav)
                segments = transcribe(
                    asr_wav,
                    model_name=get_whisper_model(),
                    language=get_whisper_language(),
                    device=get_whisper_device(),
                    compute_type=get_whisper_compute_type(),
                    beam_size=get_whisper_beam_size(),
                    vad_filter=get_whisper_vad_filter(),
                    initial_prompt="这是一段中文口播参考音频，请准确识别人声内容。",
                )
                return " ".join(segment.text for segment in segments).strip()
        except BaseException:
            logger.warning("cosyvoice prompt_text ASR failed", exc_info=True)
            return ""

    def _cosyvoice_installed(self) -> bool:
        return (
            importlib.util.find_spec("cosyvoice") is not None
            and importlib.util.find_spec("torchaudio") is not None
        )

    def _ensure_imports(self) -> None:
        if self._cosyvoice_class and self._load_wav and self._torchaudio:
            return
        try:
            from cosyvoice.cli.cosyvoice import CosyVoice2  # type: ignore
            from cosyvoice.utils.file_utils import load_wav  # type: ignore
            import torchaudio  # type: ignore
        except ImportError as exc:
            raise AppException(
                error_code.INTERNAL_ERROR,
                "CosyVoice 未安装，请先安装 CosyVoice 及其依赖。",
                data={"errorType": "cosyvoice_not_installed"},
                status_code=500,
            ) from exc
        self._cosyvoice_class = CosyVoice2
        self._load_wav = load_wav
        self._torchaudio = torchaudio

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        self._ensure_imports()
        if not self.model_dir.exists():
            raise AppException(
                error_code.INTERNAL_ERROR,
                "CosyVoice 模型目录不存在，请先下载 CosyVoice2-0.5B。",
                data={"errorType": "cosyvoice_model_missing", "modelDir": str(self.model_dir)},
                status_code=500,
            )
        try:
            self._model = self._cosyvoice_class(
                str(self.model_dir),
                load_jit=False,
                load_trt=False,
                fp16=False,
            )
        except Exception as exc:
            raise AppException(
                error_code.INTERNAL_ERROR,
                "CosyVoice 模型加载失败。",
                data={"errorType": "cosyvoice_load_failed", "modelDir": str(self.model_dir)},
                status_code=500,
            ) from exc
        if not hasattr(self._model, "inference_zero_shot"):
            raise AppException(
                error_code.INTERNAL_ERROR,
                "当前 CosyVoice 模型不支持 zero-shot。",
                data={"errorType": "cosyvoice_zero_shot_not_supported", "modelDir": str(self.model_dir)},
                status_code=500,
            )
        return self._model

    def _synthesize_chunk(
        self,
        *,
        model: Any,
        text: str,
        output_path: Path,
        reference_wav: Path | None,
        prompt_text: str,
    ) -> None:
        if reference_wav is None:
            raise AppException(
                error_code.BAD_REQUEST,
                "CosyVoice POC 当前只验证自定义音色 zero-shot，请提供 reference_audio_path。",
                data={"errorType": "reference_audio_required"},
                status_code=400,
            )
        # Official CosyVoice2 zero-shot examples load prompt speech at 16 kHz.
        # The file itself is normalized to COSYVOICE_SAMPLE_RATE first, then resampled by load_wav.
        prompt_speech_16k = self._load_wav(str(reference_wav), 16000)
        try:
            generated_any = False
            for index, result in enumerate(
                model.inference_zero_shot(text, prompt_text, prompt_speech_16k, stream=False),
                1,
            ):
                speech = result.get("tts_speech") if isinstance(result, dict) else None
                if speech is None:
                    continue
                self._torchaudio.save(str(output_path), speech, int(getattr(model, "sample_rate", self.sample_rate)))
                generated_any = True
                if index >= 1:
                    break
            if not generated_any or not output_path.exists():
                raise RuntimeError("CosyVoice 没有返回有效音频")
        except AppException:
            raise
        except Exception as exc:
            raise AppException(
                error_code.INTERNAL_ERROR,
                "CosyVoice 语音生成失败。",
                data={"errorType": "cosyvoice_synthesis_failed"},
                status_code=500,
            ) from exc

    def _validate_reference_audio(self, audio_path: Path) -> None:
        metadata = probe_audio(audio_path)
        if metadata["duration"] < MIN_REFERENCE_SECONDS:
            raise AppException(
                error_code.BAD_REQUEST,
                "参考音频太短，请提供至少 10 秒以上的清晰人声。",
                data={"errorType": "reference_audio_too_short", "duration": metadata["duration"]},
                status_code=400,
            )
        if metadata["channels"] != 1 or metadata["sampleRate"] != self.sample_rate:
            raise AppException(
                error_code.BAD_REQUEST,
                "参考音频格式不正确，需要 mono PCM wav。",
                data={"errorType": "reference_audio_format_invalid", **metadata},
                status_code=400,
            )
        volume = measure_volume(audio_path)
        if volume["meanVolumeDb"] < LOW_MEAN_VOLUME_DB or volume["maxVolumeDb"] < LOW_MAX_VOLUME_DB:
            raise AppException(
                error_code.BAD_REQUEST,
                "参考音频音量太低，请上传更清晰的人声。",
                data={"errorType": "reference_audio_volume_too_low", **volume},
                status_code=400,
            )


def split_tts_text(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return []
    sentences = [item.strip() for item in re.split(r"(?<=[。！？!?；;])\s*|\n+", normalized) if item.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences or [normalized]:
        if len(sentence) > SHORT_TEXT_MAX_CHARS:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_sentence(sentence))
            continue
        if current and len(current) + len(sentence) > 80:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current}{sentence}" if current else sentence
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk]


def _split_long_sentence(sentence: str) -> list[str]:
    chunks: list[str] = []
    current = ""
    for part in [item for item in re.split(r"(?<=[，,、])", sentence) if item]:
        if current and len(current) + len(part) > 80:
            chunks.append(current)
            current = part
        else:
            current += part
        while len(current) > SHORT_TEXT_MAX_CHARS:
            chunks.append(current[:80])
            current = current[80:]
    if current:
        chunks.append(current)
    return chunks


def concat_wavs(segment_paths: list[Path], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    list_path = output_path.parent / f"{output_path.stem}_segments.txt"
    lines = []
    for path in segment_paths:
        escaped = str(path).replace("'", r"'\''")
        lines.append(f"file '{escaped}'")
    list_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    result = run_command(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(output_path),
        ]
    )
    if result.returncode != 0 or not output_path.exists():
        logger.warning("cosyvoice concat failed: %s", (result.stdout or "")[-1200:])
        raise AppException(
            error_code.INTERNAL_ERROR,
            "CosyVoice 分段音频合并失败。",
            data={"errorType": "cosyvoice_concat_failed"},
            status_code=500,
        )


def probe_audio(audio_path: Path) -> dict[str, Any]:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "format=duration,size:stream=sample_rate,channels",
            "-of",
            "json",
            str(audio_path),
        ]
    )
    if result.returncode != 0:
        raise AppException(
            error_code.BAD_REQUEST,
            "音频读取失败。",
            data={"errorType": "audio_probe_failed"},
            status_code=400,
        )
    payload = json.loads(result.stdout or "{}")
    stream = (payload.get("streams") or [{}])[0]
    format_payload = payload.get("format") or {}
    return {
        "duration": float(format_payload.get("duration") or 0.0),
        "sampleRate": int(stream.get("sample_rate") or 0),
        "channels": int(stream.get("channels") or 0),
        "size": int(format_payload.get("size") or audio_path.stat().st_size),
    }


def measure_volume(audio_path: Path) -> dict[str, float]:
    result = run_command(["ffmpeg", "-i", str(audio_path), "-af", "volumedetect", "-f", "null", "-"])
    output = result.stdout or ""
    mean_match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", output)
    max_match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", output)
    return {
        "meanVolumeDb": float(mean_match.group(1)) if mean_match else -99.0,
        "maxVolumeDb": float(max_match.group(1)) if max_match else -99.0,
    }


def _copy_audio(source_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(source_path.read_bytes())


cosyvoice_engine = CosyVoiceEngine()
