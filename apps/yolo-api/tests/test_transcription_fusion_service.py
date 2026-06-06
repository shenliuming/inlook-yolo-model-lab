from __future__ import annotations

import unittest

from app.services.transcription_fusion_service import (
    apply_asr_corrections,
    build_final_text_from_asr_ocr,
)


class TranscriptionFusionServiceTest(unittest.TestCase):
    def test_apply_asr_corrections_keeps_raw_asr_separate(self) -> None:
        corrected, applied = apply_asr_corrections("OpenI 让 XGB Plus 免费，评论区试料")

        self.assertIn("OpenAI", corrected)
        self.assertIn("ChatGPT Plus", corrected)
        self.assertIn("私聊", corrected)
        self.assertGreaterEqual(len(applied), 3)

    def test_ocr_primary_when_coverage_is_high(self) -> None:
        ocr_segments = [
            {"start": float(index), "end": float(index + 1), "text": f"第{index}句 ChatGPT Plus 字幕"}
            for index in range(6)
        ]
        ocr_text = "\n".join(segment["text"] for segment in ocr_segments)

        result = build_final_text_from_asr_ocr(
            asr_text="最近都在传 OpenAI 让 XG PLUS 免费了",
            asr_segments=[{"start": 0.0, "end": 6.0, "text": "最近都在传 OpenAI 让 XG PLUS 免费了"}],
            corrected_asr_text="最近都在传 OpenAI 让 ChatGPT Plus 免费了",
            ocr_text=ocr_text,
            ocr_segments=ocr_segments,
            ocr_status="success",
        )

        self.assertEqual(result.fusionSource, "ocr_primary")
        self.assertIn("ChatGPT Plus", result.finalText)
        self.assertEqual(result.fusionStats["replacedSegmentCount"], 6)

    def test_ocr_skipped_falls_back_to_corrected_asr(self) -> None:
        corrected, _ = apply_asr_corrections("你在评论区回复XGBT，我会试料给你")

        result = build_final_text_from_asr_ocr(
            asr_text="你在评论区回复XGBT，我会试料给你",
            asr_segments=[{"start": 0.0, "end": 3.0, "text": "你在评论区回复XGBT，我会试料给你"}],
            corrected_asr_text=corrected,
            ocr_text="",
            ocr_segments=[],
            ocr_status="skipped",
        )

        self.assertEqual(result.fusionSource, "asr_only")
        self.assertIn("ChatGPT", result.finalText)
        self.assertIn("私聊", result.finalText)
        self.assertIn("OCR 未可用", "".join(result.warnings))

    def test_time_overlap_uses_ocr_segment_for_subtitle_correction(self) -> None:
        corrected, _ = apply_asr_corrections("马尔他军兵在完成AI数码课程之后")

        result = build_final_text_from_asr_ocr(
            asr_text="马尔他军兵在完成AI数码课程之后",
            asr_segments=[{"start": 3.2, "end": 5.8, "text": "马尔他军兵在完成AI数码课程之后"}],
            corrected_asr_text=corrected,
            ocr_text="马耳他居民在完成 AI 数字课程之后",
            ocr_segments=[
                {
                    "start": 3.0,
                    "end": 6.0,
                    "text": "马耳他居民在完成 AI 数字课程之后",
                    "confidence": 0.91,
                }
            ],
            ocr_status="success",
        )

        self.assertEqual(result.fusionSource, "asr_ocr_fusion")
        self.assertIn("马耳他居民", result.finalText)
        self.assertIn("AI 数字课程", result.finalText)
        self.assertEqual(result.fusionStats["replacedSegmentCount"], 1)


if __name__ == "__main__":
    unittest.main()
