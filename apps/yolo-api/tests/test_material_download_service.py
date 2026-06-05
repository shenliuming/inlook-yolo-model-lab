from __future__ import annotations

import shutil
import unittest
from pathlib import Path
from unittest import mock

from app.common.exceptions import AppException
from app.services.material_download_service import download_material_video
from app.tasks.task_store import init_material_runtime, material_dir, material_inputs_dir, write_material


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, chunks: list[bytes] | None = None):
        self.status_code = status_code
        self._chunks = chunks or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def iter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class MaterialDownloadServiceTest(unittest.TestCase):
    def _cleanup(self, material_id: str) -> None:
        shutil.rmtree(material_dir(material_id), ignore_errors=True)

    def _write_material(self, material_id: str, **overrides) -> None:
        init_material_runtime(material_id)
        payload = {
            "materialId": material_id,
            "materialKey": material_id,
            "sourceType": "douyin",
            "sourceUrl": "https://v.douyin.com/test123/",
            "cacheStatus": "metadata_cached",
            "downloadStatus": "not_downloaded",
            "localFileStatus": "none",
            "video": {
                "url": "https://cdn.example.com/main.mp4",
                "remoteUrl": "https://cdn.example.com/main.mp4",
                "sources": [
                    {"label": "主视频", "url": "https://cdn.example.com/main.mp4"},
                    {"label": "720P", "url": "https://cdn.example.com/fallback.mp4"},
                ],
            },
        }
        payload.update(overrides)
        write_material(material_id, payload)

    def test_case_1_local_ready_extract_would_not_redownload(self) -> None:
        material_id = "mt_step3_case1"
        self.addCleanup(self._cleanup, material_id)
        self._write_material(
            material_id,
            cacheStatus="local_ready",
            downloadStatus="downloaded",
            localFileStatus="exists",
            localVideoPath=str(material_inputs_dir(material_id) / "source.mp4"),
            localVideoUrl=f"/api/v1/materials/{material_id}/files/source.mp4",
        )
        source = material_inputs_dir(material_id) / "source.mp4"
        source.write_bytes(b"x" * (12 * 1024))

        with mock.patch("app.services.material_download_service.httpx.stream") as stream_mock:
            with mock.patch("app.services.material_download_service.ffmpeg_client.probe_video", return_value={"duration": 10.0, "width": 720, "height": 1280}):
                result = download_material_video(material_id)

        self.assertEqual(result["cacheStatus"], "local_ready")
        self.assertEqual(result["downloadStatus"], "downloaded")
        self.assertEqual(result["localFileStatus"], "exists")
        stream_mock.assert_not_called()

    def test_case_2_metadata_cached_downloads_source_mp4(self) -> None:
        material_id = "mt_step3_case2"
        self.addCleanup(self._cleanup, material_id)
        self._write_material(material_id)

        with mock.patch("app.services.material_download_service.httpx.stream", return_value=_FakeResponse(chunks=[b"x" * (12 * 1024)])):
            with mock.patch("app.services.material_download_service.ffmpeg_client.probe_video", return_value={"duration": 12.0, "width": 1080, "height": 1920}):
                result = download_material_video(material_id)

        self.assertTrue((material_inputs_dir(material_id) / "source.mp4").exists())
        self.assertEqual(result["cacheStatus"], "local_ready")
        self.assertEqual(result["downloadStatus"], "downloaded")
        self.assertEqual(result["localFileStatus"], "exists")

    def test_case_3_primary_source_fails_fallback_succeeds(self) -> None:
        material_id = "mt_step3_case3"
        self.addCleanup(self._cleanup, material_id)
        self._write_material(material_id)

        responses = [
            _FakeResponse(status_code=403),
            _FakeResponse(chunks=[b"x" * (12 * 1024)]),
        ]

        def fake_stream(*args, **kwargs):
            return responses.pop(0)

        with mock.patch("app.services.material_download_service.httpx.stream", side_effect=fake_stream):
            with mock.patch("app.services.material_download_service.ffmpeg_client.probe_video", return_value={"duration": 8.0, "width": 720, "height": 1280}):
                result = download_material_video(material_id)

        self.assertEqual(result["cacheStatus"], "local_ready")
        self.assertEqual(result["triedSources"][0]["errorType"], "source_forbidden")
        self.assertEqual(result["triedSources"][-1]["status"], "success")

    def test_case_4_all_sources_fail(self) -> None:
        material_id = "mt_step3_case4"
        self.addCleanup(self._cleanup, material_id)
        self._write_material(material_id)

        with mock.patch("app.services.material_download_service.httpx.stream", side_effect=[_FakeResponse(status_code=403), _FakeResponse(status_code=404)]):
            with self.assertRaises(AppException) as context:
                download_material_video(material_id)

        self.assertEqual(context.exception.data["errorType"], "material_download_failed")
        self.assertEqual(context.exception.data["downloadStatus"], "failed")

    def test_case_5_small_file_retries_next_source(self) -> None:
        material_id = "mt_step3_case5"
        self.addCleanup(self._cleanup, material_id)
        self._write_material(material_id)

        responses = [
            _FakeResponse(chunks=[b"tiny"]),
            _FakeResponse(chunks=[b"x" * (12 * 1024)]),
        ]

        with mock.patch("app.services.material_download_service.httpx.stream", side_effect=lambda *a, **k: responses.pop(0)):
            with mock.patch("app.services.material_download_service.ffmpeg_client.probe_video", return_value={"duration": 6.0, "width": 720, "height": 1280}):
                result = download_material_video(material_id)

        self.assertEqual(result["cacheStatus"], "local_ready")
        self.assertEqual(result["triedSources"][0]["errorType"], "source_invalid")

    def test_case_6_ffprobe_failure_retries_next_source(self) -> None:
        material_id = "mt_step3_case6"
        self.addCleanup(self._cleanup, material_id)
        self._write_material(material_id)

        responses = [
            _FakeResponse(chunks=[b"x" * (12 * 1024)]),
            _FakeResponse(chunks=[b"y" * (12 * 1024)]),
        ]
        probe_results = [
            AppException(50001, "视频源下载失败：ffprobe 校验失败。", status_code=500, data={"errorType": "ffprobe_failed"}),
            {"duration": 9.0, "width": 720, "height": 1280},
        ]

        def fake_probe(_path: Path):
            result = probe_results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with mock.patch("app.services.material_download_service.httpx.stream", side_effect=lambda *a, **k: responses.pop(0)):
            with mock.patch("app.services.material_download_service.ffmpeg_client.probe_video", side_effect=fake_probe):
                result = download_material_video(material_id)

        self.assertEqual(result["cacheStatus"], "local_ready")
        self.assertEqual(result["triedSources"][0]["errorType"], "ffprobe_failed")


if __name__ == "__main__":
    unittest.main()
