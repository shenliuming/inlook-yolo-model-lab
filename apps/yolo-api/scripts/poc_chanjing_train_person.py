from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.digital_human_poc_service import create_chanjing_training_poc_job, poll_chanjing_training_poc_job


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a customised Chanjing digital human from a local template video.")
    parser.add_argument("--video", required=True, help="Local template video path")
    parser.add_argument("--name", required=True, help="Person name")
    parser.add_argument("--train-type", default="both", choices=["voice", "figure", "both"])
    parser.add_argument("--callback", default="")
    parser.add_argument("--error-skip", action="store_true")
    parser.add_argument("--resolution-rate", type=int, default=0)
    parser.add_argument("--language", default="cn")
    parser.add_argument("--version", default="1.0")
    parser.add_argument("--poll-interval", type=int, default=30)
    args = parser.parse_args()

    job = create_chanjing_training_poc_job(
        {
            "local_video_path": args.video,
            "name": args.name,
            "train_type": args.train_type,
            "callback": args.callback,
            "error_skip": args.error_skip,
            "resolution_rate": args.resolution_rate,
            "language": args.language,
            "version": args.version,
        }
    )
    print(json.dumps(job, ensure_ascii=False, indent=2))
    while job.get("status") == "training":
        time.sleep(max(1, args.poll_interval))
        job = poll_chanjing_training_poc_job(str(job["job_id"]))
        print(json.dumps(job, ensure_ascii=False, indent=2))
    return 0 if job.get("status") == "training_succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
