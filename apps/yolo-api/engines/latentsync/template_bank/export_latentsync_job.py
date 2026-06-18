from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a Template Clip Bank result as a LatentSync job package")
    parser.add_argument("--runtime-dir", required=True, help="Template Clip Bank runtime directory")
    parser.add_argument("--job-id", default="", help="Optional override for generated job id")
    parser.add_argument("--latentsync-root", default="/root/LatentSync", help="Cloud LatentSync root directory")
    parser.add_argument("--engine-version", default="LatentSync-1.6", help="LatentSync engine version label")
    parser.add_argument("--inference-steps", type=int, default=20, help="LatentSync inference steps")
    parser.add_argument("--guidance-scale", type=float, default=1.5, help="LatentSync guidance scale")
    parser.add_argument("--enable-deepcache", action="store_true", help="Enable DeepCache in generated config")
    return parser.parse_args()


def _read_optional_json(path: Path) -> dict:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _job_id(override: str) -> str:
    if override:
        return override
    return "job_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def _copy_if_exists(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    input_dir = runtime_dir / "input"
    output_dir = runtime_dir / "output"
    reports_dir = runtime_dir / "reports"
    jobs_dir = runtime_dir / "latentsync_jobs"

    prepared_video = output_dir / "prepared_template.mp4"
    narration_audio = input_dir / "narration.wav"
    script_file = input_dir / "script.txt"
    script_segments = input_dir / "script_segments.json"
    qa_report = reports_dir / "qa_report.json"
    timeline_plan = reports_dir / "timeline_plan.json"
    pipeline_report = reports_dir / "pipeline_report.json"
    candidates_ai_scored = reports_dir / "candidates_ai_scored.json"

    if not prepared_video.exists():
        raise SystemExit(f"Missing prepared template video: {prepared_video}")
    if not narration_audio.exists():
        raise SystemExit(f"Missing narration audio: {narration_audio}")
    if args.inference_steps <= 0:
        raise SystemExit("inference-steps must be > 0")

    job_id = _job_id(args.job_id)
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    job_dir = jobs_dir / job_id
    job_input = job_dir / "input"
    job_output = job_dir / "output"
    job_reports = job_dir / "reports"

    job_input.mkdir(parents=True, exist_ok=True)
    job_output.mkdir(parents=True, exist_ok=True)
    job_reports.mkdir(parents=True, exist_ok=True)

    video_target = job_input / "video.mp4"
    audio_target = job_input / "audio.wav"
    shutil.copy2(prepared_video, video_target)
    shutil.copy2(narration_audio, audio_target)

    qa_exists = _copy_if_exists(qa_report, job_reports / "template_qa_report.json")
    timeline_exists = _copy_if_exists(timeline_plan, job_reports / "timeline_plan.json")
    pipeline_exists = _copy_if_exists(pipeline_report, job_reports / "pipeline_report.json")
    ai_scored_exists = _copy_if_exists(candidates_ai_scored, job_reports / "candidates_ai_scored.json")
    script_segments_exists = _copy_if_exists(script_segments, job_reports / "script_segments.json")
    script_exists = _copy_if_exists(script_file, job_dir / "script.txt")

    job_config = {
        "job_id": job_id,
        "engine": "latentsync",
        "engine_version": args.engine_version,
        "input_video": "input/video.mp4",
        "input_audio": "input/audio.wav",
        "output_video": "output/latentsync_output.mp4",
        "unet_config_path": "configs/unet/stage2_512.yaml",
        "inference_ckpt_path": "checkpoints/latentsync_unet.pt",
        "inference_steps": args.inference_steps,
        "guidance_scale": args.guidance_scale,
        "enable_deepcache": bool(args.enable_deepcache),
        "created_at": created_at,
    }
    _write_json(job_dir / "job_config.json", job_config)

    warnings: list[str] = []
    manifest = {
        "job_id": job_id,
        "status": "exported",
        "source_runtime_dir": str(runtime_dir),
        "files": {
            "input_video": "input/video.mp4",
            "input_audio": "input/audio.wav",
            "script_txt": "script.txt",
            "job_config": "job_config.json",
            "run_script": "run_latentsync.sh",
        },
        "checks": {
            "input_video_exists": video_target.exists(),
            "input_audio_exists": audio_target.exists(),
            "qa_report_exists": qa_exists,
            "timeline_plan_exists": timeline_exists,
            "pipeline_report_exists": pipeline_exists,
            "candidates_ai_scored_exists": ai_scored_exists,
            "script_segments_exists": script_segments_exists,
            "script_txt_exists": script_exists,
        },
        "warnings": warnings,
    }
    _write_json(job_dir / "manifest.json", manifest)

    remote_job_dir = f"{args.latentsync_root.rstrip('/')}/inlook_jobs/{job_id}"
    deepcache_line = '  --enable_deepcache \\\n' if args.enable_deepcache else ""
    run_script = f"""#!/usr/bin/env bash
set -e

cd "{args.latentsync_root.rstrip('/')}"

python -m scripts.inference \\
  --unet_config_path "configs/unet/stage2_512.yaml" \\
  --inference_ckpt_path "checkpoints/latentsync_unet.pt" \\
  --inference_steps {args.inference_steps} \\
  --guidance_scale {args.guidance_scale} \\
{deepcache_line}  --video_path "{remote_job_dir}/input/video.mp4" \\
  --audio_path "{remote_job_dir}/input/audio.wav" \\
  --video_out_path "{remote_job_dir}/output/latentsync_output.mp4"
"""
    run_script_path = job_dir / "run_latentsync.sh"
    _write_text(run_script_path, run_script)
    run_script_path.chmod(0o755)

    readme = f"""# LatentSync Job Package

This job package was exported from Template Clip Bank.

Upload this directory to:

`{remote_job_dir}`

Then run:

```bash
cd {args.latentsync_root.rstrip('/')}
bash inlook_jobs/{job_id}/run_latentsync.sh
```

LatentSync output will be written to:

`inlook_jobs/{job_id}/output/latentsync_output.mp4`
"""
    _write_text(job_dir / "README.md", readme)

    print(f"[DONE] job_dir={job_dir}")
    print(f"[DONE] job_id={job_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
