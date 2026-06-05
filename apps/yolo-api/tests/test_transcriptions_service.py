from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path
from unittest import mock

from app.services import transcriptions_service as ts
from app.tasks.task_store import init_material_runtime, material_dir, material_inputs_dir, write_material


class TranscriptionsServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.material_id = f"mt_test_{uuid.uuid4().hex[:8]}"
        init_material_runtime(self.material_id)
        self.addCleanup(self._cleanup_material_runtime)

    def _cleanup_material_runtime(self) -> None:
        shutil.rmtree(material_dir(self.material_id), ignore_errors=True)

    def test_resolve_material_video_source_downloads_remote_video_before_ffmpeg(self) -> None:
        write_material(
            self.material_id,
            {
                "materialId": self.material_id,
                "sourceType": "douyin",
                "sourceUrl": "https://v.douyin.com/test123/",
                "finalUrl": "https://www.douyin.com/video/123",
                "video": {
                    "url": "https://cdn.example.com/video.mp4",
                    "remoteUrl": "https://cdn.example.com/video.mp4",
                },
            },
        )

        expected_local_path = material_inputs_dir(self.material_id) / "source.mp4"

        def fake_download_file(platform: str, *, target_url: str, output_path: Path, referer: str = "") -> Path:
            self.assertEqual(platform, "douyin")
            self.assertEqual(target_url, "https://cdn.example.com/video.mp4")
            self.assertEqual(referer, "https://www.douyin.com/video/123")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake-mp4")
            return output_path

        with mock.patch.object(ts.browser_client, "download_file", side_effect=fake_download_file) as download_mock:
            with mock.patch.object(ts, "ffprobe_metadata", return_value={"width": 1080, "height": 1920, "duration": 7.4}):
                source_video, metadata = ts.resolve_material_video_source(self.material_id, download_if_needed=True)

        self.assertEqual(Path(source_video), expected_local_path)
        self.assertTrue(expected_local_path.exists())
        self.assertEqual(metadata["width"], 1080)
        self.assertEqual(metadata["height"], 1920)
        self.assertEqual(metadata["duration"], 7.4)
        download_mock.assert_called_once()

    def test_process_transcription_task_marks_task_failed_when_ffmpeg_raises_system_exit(self) -> None:
        write_material(
            self.material_id,
            {
                "materialId": self.material_id,
                "sourceType": "douyin",
                "title": "测试素材",
                "description": "测试描述",
                "tags": [],
                "video": {
                    "url": "/api/v1/materials/source.mp4",
                },
            },
        )
        local_video = material_inputs_dir(self.material_id) / "source.mp4"
        local_video.write_bytes(b"fake-mp4")

        task_id = ts.build_task_id()
        ts.task_inputs_dir(task_id).mkdir(parents=True, exist_ok=True)
        ts.task_outputs_dir(task_id).mkdir(parents=True, exist_ok=True)
        ts.write_task(
            task_id,
            {
                "task_id": task_id,
                "task_type": "transcription.extract",
                "material_id": self.material_id,
                "status": "pending",
                "stage": "等待执行",
                "progress": 0,
                "message": "转写任务已创建",
                "downloads": ts.build_downloads(task_id),
                "created_at": ts.now(),
                "updated_at": ts.now(),
            },
        )

        with mock.patch.object(ts, "get_asr_provider", return_value="faster_whisper"):
            with mock.patch.object(ts, "resolve_material_video_source", return_value=(local_video, {"width": 1080, "height": 1920, "duration": 7.4})):
                with mock.patch.object(ts, "extract_audio", side_effect=SystemExit("命令执行失败：ffmpeg -y -i local.mp4 ...")):
                    ts.process_transcription_task(
                        task_id,
                        material_id=self.material_id,
                        model="medium",
                        language="zh",
                        device="cpu",
                        compute_type="int8",
                        beam_size=5,
                    )

        task = ts.read_task(task_id)
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["stage"], "失败")
        self.assertIn("命令执行失败：ffmpeg", task["message"])


if __name__ == "__main__":
    unittest.main()
