from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app.common.exceptions import AppException
from app.services import transcriptions_service as ts
from app.tasks.task_store import init_material_runtime, material_dir, material_inputs_dir, material_outputs_dir, write_material


class TranscriptionsServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.material_id = f"mt_test_{uuid.uuid4().hex[:8]}"
        init_material_runtime(self.material_id)
        write_material(
            self.material_id,
            {
                "materialId": self.material_id,
                "materialKey": self.material_id,
                "sourceType": "douyin",
                "title": "测试素材",
                "description": "这是一段测试口播",
                "tags": ["测试"],
                "video": {
                    "url": "/api/v1/materials/source.mp4",
                },
            },
        )
        self.addCleanup(self._cleanup_material_runtime)

    def _cleanup_material_runtime(self) -> None:
        shutil.rmtree(material_dir(self.material_id), ignore_errors=True)

    def test_create_transcription_task_returns_success_and_writes_material_outputs(self) -> None:
        local_video = material_inputs_dir(self.material_id) / "source.mp4"
        local_video.write_bytes(b"fake-mp4-data")

        def fake_extract_audio(input_file: Path, output_wav: Path) -> None:
            output_wav.parent.mkdir(parents=True, exist_ok=True)
            output_wav.write_bytes(b"fake-wav")

        segments = [
            SimpleNamespace(start=0.0, end=1.2, text="你好，欢迎来到 INLOOK Studio"),
            SimpleNamespace(start=1.2, end=2.4, text="这是一次真实转写测试"),
        ]

        with mock.patch.object(ts.ffmpeg_client, "probe_video", return_value={"width": 720, "height": 1280, "duration": 12.3}):
            with mock.patch.object(ts, "get_asr_provider", return_value="faster_whisper"):
                with mock.patch.object(ts, "extract_audio", side_effect=fake_extract_audio):
                    with mock.patch.object(ts, "transcribe", return_value=segments):
                        result = ts.create_transcription_task(
                            material_id=self.material_id,
                            model="medium",
                            language="zh",
                            device="cpu",
                            compute_type="int8",
                            beam_size=5,
                        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["progress"], 100)
        self.assertEqual(result["materialId"], self.material_id)
        self.assertEqual(result["materialKey"], self.material_id)
        self.assertEqual(result["engine"], "faster_whisper")
        self.assertEqual(result["model"], "medium")
        self.assertEqual(result["language"], "zh")
        self.assertEqual(result["correctedAsrText"], "")
        self.assertIn("真实转写测试", result["finalText"])
        self.assertEqual(result["transcript"], result["finalText"])
        self.assertTrue((material_outputs_dir(self.material_id) / "audio.wav").exists())
        self.assertTrue((material_outputs_dir(self.material_id) / "asr_text.txt").exists())
        self.assertTrue((material_outputs_dir(self.material_id) / "asr_segments.json").exists())
        self.assertTrue((material_outputs_dir(self.material_id) / "final_transcript.txt").exists())
        self.assertTrue((material_outputs_dir(self.material_id) / "transcript.txt").exists())
        self.assertTrue((material_outputs_dir(self.material_id) / "subtitles.srt").exists())
        self.assertTrue((material_outputs_dir(self.material_id) / "subtitles.vtt").exists())
        self.assertTrue((material_outputs_dir(self.material_id) / "transcription_result.json").exists())

    def test_create_transcription_task_raises_when_source_video_missing(self) -> None:
        with self.assertRaises(AppException) as ctx:
            ts.create_transcription_task(
                material_id=self.material_id,
                model="medium",
                language="zh",
                device="cpu",
                compute_type="int8",
                beam_size=5,
            )

        self.assertEqual(ctx.exception.data["errorType"], "source_mp4_missing")
        self.assertIn("本地视频不存在", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
