from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.services import ocr_subtitle_service as ocr


class OcrSubtitleServiceTest(unittest.TestCase):
    def test_missing_ocr_dependency_is_skipped_and_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "outputs"
            video_path = Path(tmpdir) / "source.mp4"
            video_path.write_bytes(b"fake-video")

            with mock.patch.object(ocr, "_load_ocr_engine", return_value=None):
                result = ocr.extract_ocr_subtitles(video_path, output_dir)

            self.assertEqual(result.ocrStatus, "skipped")
            self.assertEqual(result.ocrText, "")
            self.assertTrue((output_dir / "ocr_text.txt").exists())
            self.assertTrue((output_dir / "ocr_subtitles.json").exists())
            self.assertIn("OCR 依赖未安装", "".join(result.warnings))


if __name__ == "__main__":
    unittest.main()
