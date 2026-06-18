from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.digital_human_poc_service import create_chanjing_full_poc_job, poll_chanjing_full_poc_job


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full Chanjing POC flow: upload, train, synthesize, download.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--train-type", default="both", choices=["voice", "figure", "both"])
    parser.add_argument("--audio-type", required=True, choices=["audio", "tts"])
    parser.add_argument("--wav-url", default="")
    parser.add_argument("--audio-file-id", default="")
    parser.add_argument("--text", default="")
    parser.add_argument("--audio-man-id", default="")
    parser.add_argument("--screen-width", type=int, default=1080)
    parser.add_argument("--screen-height", type=int, default=1920)
    parser.add_argument("--model", type=int, default=0)
    parser.add_argument("--resolution-rate", type=int, default=0)
    parser.add_argument("--poll-interval", type=int, default=10)
    args = parser.parse_args()

    job = create_chanjing_full_poc_job(
        {
            "local_video_path": args.video,
            "name": args.name,
            "train_type": args.train_type,
            "audio_type": args.audio_type,
            "wav_url": args.wav_url,
            "audio_file_id": args.audio_file_id,
            "text": args.text,
            "audio_man_id": args.audio_man_id,
            "screen_width": args.screen_width,
            "screen_height": args.screen_height,
            "model": args.model,
            "resolution_rate": args.resolution_rate,
        }
    )
    print(json.dumps(job, ensure_ascii=False, indent=2))
    while job.get("status") not in {"succeeded", "failed", "training_failed", "failed_param", "failed_server"}:
        time.sleep(max(1, args.poll_interval))
        job = poll_chanjing_full_poc_job(str(job["job_id"]))
        print(json.dumps(job, ensure_ascii=False, indent=2))
    return 0 if job.get("status") == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
