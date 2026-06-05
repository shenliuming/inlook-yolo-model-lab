from __future__ import annotations

import shutil
import unittest
from pathlib import Path
from unittest import mock

from app.services import material_service as ms
from app.tasks.task_store import init_material_runtime, material_dir, material_inputs_dir, write_material
from app.utils.url_util import parse_material_input


class MaterialServiceStep2Test(unittest.TestCase):
    def _cleanup(self, material_id: str) -> None:
        shutil.rmtree(material_dir(material_id), ignore_errors=True)

    def test_case_1_same_link_has_same_material_key_and_second_call_hits_cache(self) -> None:
        raw_input = "https://v.douyin.com/w2_bZi78r3k/"
        parsed = parse_material_input(raw_input, "auto")
        material_id = ms.build_material_key(parsed.source_type, parsed.normalized_url)
        self._cleanup(material_id)
        self.addCleanup(self._cleanup, material_id)

        def fake_extract(material_id: str, parsed):
            payload = ms._map_douyin_material(
                material_id=material_id,
                parsed=parsed,
                final_url=parsed.normalized_url,
                aweme_detail={
                    "desc": "测试文案",
                    "author": {"nickname": "测试作者"},
                    "video": {"play_addr": {"url_list": ["https://cdn.example.com/video.mp4"]}, "width": 1080, "height": 1920},
                    "duration": 7400,
                },
                cache_hit=False,
                extractor="copy_pilot",
            )
            return ms._persist_material_metadata(material_id, payload)

        with mock.patch.object(ms.settings, "get_copy_pilot_enabled", return_value=True):
            with mock.patch.object(ms, "_extract_copy_pilot_material", side_effect=fake_extract) as extractor:
                with mock.patch.object(
                    ms,
                    "download_material_video",
                    side_effect=[
                        {"materialId": material_id, "materialKey": material_id, "cacheHit": False},
                        {"materialId": material_id, "materialKey": material_id, "cacheHit": True},
                    ],
                ):
                    first = ms.extract_material(source_type="auto", raw_input=raw_input, raw_url="")
                    second = ms.extract_material(source_type="auto", raw_input=raw_input, raw_url="")

        self.assertEqual(first["materialId"], second["materialId"])
        self.assertEqual(first["materialKey"], second["materialKey"])
        self.assertFalse(first["cacheHit"])
        self.assertTrue(second["cacheHit"])
        extractor.assert_called_once()

    def test_case_2_share_text_and_plain_url_have_same_key(self) -> None:
        share_text = "0.02 复制打开抖音，看看【沈柳名的作品】 https://v.douyin.com/w2_bZi78r3k/ SYZ:/ :0pm 08/20 [S@Y.ZZ](mailto:S@Y.ZZ)"
        plain_url = "https://v.douyin.com/w2_bZi78r3k/"
        parsed_share = parse_material_input(share_text, "auto")
        parsed_plain = parse_material_input(plain_url, "auto")
        self.assertEqual(parsed_share.normalized_url, parsed_plain.normalized_url)
        self.assertEqual(
            ms.build_material_key(parsed_share.source_type, parsed_share.normalized_url),
            ms.build_material_key(parsed_plain.source_type, parsed_plain.normalized_url),
        )

    def test_case_3_different_links_have_different_keys(self) -> None:
        left = parse_material_input("https://v.douyin.com/L5pbfdP/", "auto")
        right = parse_material_input("https://v.douyin.com/L4FJNR3/", "auto")
        self.assertNotEqual(
            ms.build_material_key(left.source_type, left.normalized_url),
            ms.build_material_key(right.source_type, right.normalized_url),
        )

    def test_case_4_material_json_exists_but_source_missing(self) -> None:
        material_id = "mt_case4_missing"
        init_material_runtime(material_id)
        self.addCleanup(self._cleanup, material_id)

        write_material(material_id, {"materialId": material_id, "materialKey": material_id, "downloadStatus": "not_downloaded"})
        metadata_cached = ms.get_material(material_id)
        self.assertTrue(metadata_cached["cacheHit"])
        self.assertEqual(metadata_cached["cacheStatus"], "metadata_cached")
        self.assertEqual(metadata_cached["downloadStatus"], "not_downloaded")
        self.assertEqual(metadata_cached["localFileStatus"], "none")

        write_material(material_id, {"materialId": material_id, "materialKey": material_id, "downloadStatus": "downloaded", "localVideoPath": "old/source.mp4"})
        missing = ms.get_material(material_id)
        self.assertEqual(missing["cacheStatus"], "local_missing")
        self.assertEqual(missing["downloadStatus"], "missing")
        self.assertEqual(missing["localFileStatus"], "missing")

    def test_case_5_small_file_is_invalid(self) -> None:
        material_id = "mt_case5_small"
        init_material_runtime(material_id)
        self.addCleanup(self._cleanup, material_id)
        write_material(material_id, {"materialId": material_id, "materialKey": material_id})
        source = material_inputs_dir(material_id) / "source.mp4"
        source.write_bytes(b"small")

        payload = ms.get_material(material_id)
        self.assertEqual(payload["cacheStatus"], "local_invalid")
        self.assertEqual(payload["downloadStatus"], "failed")
        self.assertEqual(payload["localFileStatus"], "invalid")

    def test_case_6_ffprobe_failure_marks_invalid(self) -> None:
        material_id = "mt_case6_ffprobe"
        init_material_runtime(material_id)
        self.addCleanup(self._cleanup, material_id)
        write_material(material_id, {"materialId": material_id, "materialKey": material_id})
        source = material_inputs_dir(material_id) / "source.mp4"
        source.write_bytes(b"x" * (11 * 1024))

        with mock.patch.object(ms.ffmpeg_client, "probe_video", side_effect=ms.AppException(ms.error_code.INTERNAL_ERROR, "boom", status_code=500)):
            payload = ms.get_material(material_id)

        self.assertEqual(payload["cacheStatus"], "local_invalid")
        self.assertEqual(payload["downloadStatus"], "failed")
        self.assertEqual(payload["localFileStatus"], "invalid")

    def test_case_7_valid_source_is_local_ready(self) -> None:
        material_id = "mt_case7_ready"
        init_material_runtime(material_id)
        self.addCleanup(self._cleanup, material_id)
        write_material(material_id, {"materialId": material_id, "materialKey": material_id})
        source = material_inputs_dir(material_id) / "source.mp4"
        source.write_bytes(b"x" * (11 * 1024))

        with mock.patch.object(ms.ffmpeg_client, "probe_video", return_value={"duration": 14.2, "width": 720, "height": 1280, "fileSize": source.stat().st_size}):
            payload = ms.get_material(material_id)

        self.assertEqual(payload["cacheStatus"], "local_ready")
        self.assertEqual(payload["downloadStatus"], "downloaded")
        self.assertEqual(payload["localFileStatus"], "exists")
        self.assertTrue(str(payload["localVideoUrl"]).endswith("/source.mp4"))


if __name__ == "__main__":
    unittest.main()
