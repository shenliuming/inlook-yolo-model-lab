from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RUNTIME_DIR = "apps/yolo-api/runtime/template_bank"
STDIO_TAIL_LIMIT = 4000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full Template Clip Bank MVP-1 pipeline")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR, help="Template Clip Bank runtime directory")
    parser.add_argument("--skip-extract", action="store_true", help="Skip extract_candidates.py")
    parser.add_argument("--skip-sheet", action="store_true", help="Skip make_candidate_sheet.py")
    parser.add_argument("--skip-merge-notes", action="store_true", help="Skip merge_manual_clip_notes.py")
    parser.add_argument("--skip-timeline", action="store_true", help="Skip build_timeline_manual.py")
    parser.add_argument("--skip-render", action="store_true", help="Skip render_prepared_template.py")
    parser.add_argument("--skip-qa", action="store_true", help="Skip qa_report.py")
    parser.add_argument("--run-ai-score", action="store_true", help="Optionally run score_candidates_ai.py")
    parser.add_argument("--use-ai-timeline", action="store_true", help="Use build_timeline_ai.py instead of build_timeline_manual.py")
    parser.add_argument("--use-script-segments", action="store_true", help="Use input/script_segments.json with build_timeline_ai.py")
    parser.add_argument("--build-script-segments", action="store_true", help="Build input/script_segments.json from input/script.txt")
    parser.add_argument("--export-latentsync-job", action="store_true", help="Export a LatentSync job package after QA")
    parser.add_argument("--latentsync-job-id", default="", help="Optional LatentSync job id when exporting")
    parser.add_argument("--latentsync-root", default="/root/LatentSync", help="Cloud LatentSync root directory for exported run script")
    parser.add_argument("--latentsync-engine-version", default="LatentSync-1.6", help="LatentSync engine version label for export")
    parser.add_argument("--latentsync-inference-steps", type=int, default=20, help="LatentSync inference steps for export")
    parser.add_argument("--latentsync-guidance-scale", type=float, default=1.5, help="LatentSync guidance scale for export")
    parser.add_argument("--enable-deepcache", action="store_true", help="Enable DeepCache in exported LatentSync job config")
    parser.add_argument("--import-latentsync-result", action="store_true", help="Import a finished LatentSync output after QA")
    parser.add_argument("--latentsync-job-dir", default="", help="LatentSync job directory for result import")
    parser.add_argument("--latentsync-result-video", default="", help="LatentSync output video for result import")
    return parser.parse_args()


def _iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _tail(text: str, limit: int = STDIO_TAIL_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _run_step(command: list[str], cwd: Path) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    started_at = _iso_now()
    start = time.time()
    result = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True)
    end = time.time()
    finished_at = _iso_now()
    record = {
        "command": command,
        "status": "success" if result.returncode == 0 else "failed",
        "start_time": started_at,
        "end_time": finished_at,
        "duration_seconds": round(end - start, 3),
        "return_code": result.returncode,
        "stdout_tail": _tail(result.stdout or ""),
        "stderr_tail": _tail(result.stderr or ""),
    }
    return result, record


def _skipped_step(step_name: str, reason: str) -> dict[str, Any]:
    now = _iso_now()
    return {
        "step_name": step_name,
        "command": [],
        "status": "skipped",
        "start_time": now,
        "end_time": now,
        "duration_seconds": 0.0,
        "return_code": 0,
        "stdout_tail": reason,
        "stderr_tail": "",
    }


def _write_pipeline_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _validate_inputs(
    runtime_dir: Path,
    *,
    need_template: bool,
    need_narration: bool,
    need_selected: bool,
) -> None:
    missing: list[str] = []
    if need_template and not (runtime_dir / "input" / "template.mp4").exists():
        missing.append("input/template.mp4 not found")
    if need_narration and not (runtime_dir / "input" / "narration.wav").exists():
        missing.append("input/narration.wav not found")
    if need_selected and not (runtime_dir / "input" / "selected_clips.json").exists():
        missing.append("input/selected_clips.json not found")
    if missing:
        raise SystemExit("; ".join(missing))


def _require_ai_scored_candidates(runtime_dir: Path) -> None:
    scored_json = runtime_dir / "reports" / "candidates_ai_scored.json"
    if not scored_json.exists():
        raise SystemExit("candidates_ai_scored.json not found. Run score_candidates_ai.py first or pass --run-ai-score.")


def _require_script_segments(runtime_dir: Path) -> None:
    script_segments = runtime_dir / "input" / "script_segments.json"
    if not script_segments.exists():
        raise SystemExit("input/script_segments.json not found. Create script segments first or remove --use-script-segments.")


def _require_script_txt(runtime_dir: Path) -> None:
    script_txt = runtime_dir / "input" / "script.txt"
    if not script_txt.exists():
        raise SystemExit("input/script.txt not found. Create script.txt first or remove --build-script-segments.")


def _require_import_inputs(job_dir: str, result_video: str) -> None:
    if not job_dir:
        raise SystemExit("--import-latentsync-result requires --latentsync-job-dir.")
    if not result_video:
        raise SystemExit("--import-latentsync-result requires --latentsync-result-video.")


def _ensure_default_enriched(runtime_dir: Path) -> bool:
    reports_dir = runtime_dir / "reports"
    candidates_json = reports_dir / "candidates.json"
    enriched_json = reports_dir / "candidates_enriched.json"
    if enriched_json.exists():
        return False
    if not candidates_json.exists():
        raise SystemExit(f"Missing candidates.json: {candidates_json}")
    shutil.copyfile(candidates_json, enriched_json)
    return True


def _python_supports_template_bank(python_cmd: str) -> bool:
    probe = subprocess.run(
        [python_cmd, "-c", "import cv2, numpy"],
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0


def _select_python(repo_root: Path) -> str:
    candidates: list[str] = []
    venv_python = repo_root / "apps" / "yolo-api" / ".venv" / "bin" / "python"
    if venv_python.exists():
        candidates.append(str(venv_python))
    candidates.append(sys.executable)
    which_python3 = shutil.which("python3")
    if which_python3:
        candidates.append(which_python3)
    candidates.append("/usr/bin/python3")

    checked: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in checked:
            continue
        checked.add(candidate)
        if _python_supports_template_bank(candidate):
            return candidate
    raise SystemExit("No suitable Python interpreter found for Template Clip Bank scripts; cv2/numpy are unavailable.")


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    repo_root = Path.cwd().resolve()
    input_dir = runtime_dir / "input"
    reports_dir = runtime_dir / "reports"
    pipeline_report_path = reports_dir / "pipeline_report.json"
    python_cmd = _select_python(repo_root)

    need_template = not args.skip_extract
    need_narration = not args.skip_timeline or not args.skip_render or not args.skip_qa
    need_selected = (not args.use_ai_timeline) and (not args.skip_timeline or (args.skip_timeline and not args.skip_render))

    warnings: list[str] = []
    steps: list[dict[str, Any]] = []

    try:
        _validate_inputs(
            runtime_dir,
            need_template=need_template,
            need_narration=need_narration,
            need_selected=need_selected,
        )
        if args.use_ai_timeline and not args.run_ai_score:
            _require_ai_scored_candidates(runtime_dir)
        if args.build_script_segments:
            _require_script_txt(runtime_dir)
        if args.use_script_segments:
            if not args.use_ai_timeline:
                raise SystemExit("--use-script-segments requires --use-ai-timeline.")
            if not args.build_script_segments:
                _require_script_segments(runtime_dir)
        if args.import_latentsync_result:
            _require_import_inputs(args.latentsync_job_dir, args.latentsync_result_video)

        manual_notes_path = input_dir / "manual_clip_notes.json"
        if not manual_notes_path.exists():
            warnings.append("manual_clip_notes.json not found; using default empty clip notes.")

        step_specs = [
            ("extract_candidates", SCRIPT_DIR / "extract_candidates.py", args.skip_extract),
            ("make_candidate_sheet", SCRIPT_DIR / "make_candidate_sheet.py", args.skip_sheet),
            ("merge_manual_clip_notes", SCRIPT_DIR / "merge_manual_clip_notes.py", args.skip_merge_notes),
        ]
        if args.use_ai_timeline:
            if args.run_ai_score:
                step_specs.append(("score_candidates_ai", SCRIPT_DIR / "score_candidates_ai.py", False))
            if args.build_script_segments:
                step_specs.append(("build_script_segments_mock", SCRIPT_DIR / "build_script_segments_mock.py", False))
            step_specs.append(("build_timeline_ai", SCRIPT_DIR / "build_timeline_ai.py", args.skip_timeline))
        else:
            step_specs.append(("build_timeline_manual", SCRIPT_DIR / "build_timeline_manual.py", args.skip_timeline))
            if args.run_ai_score:
                step_specs.append(("score_candidates_ai", SCRIPT_DIR / "score_candidates_ai.py", False))
        step_specs.extend(
            [
                ("render_prepared_template", SCRIPT_DIR / "render_prepared_template.py", args.skip_render),
                ("qa_report", SCRIPT_DIR / "qa_report.py", args.skip_qa),
            ]
        )
        if args.export_latentsync_job:
            step_specs.append(("export_latentsync_job", SCRIPT_DIR / "export_latentsync_job.py", False))
        if args.import_latentsync_result:
            step_specs.append(("import_latentsync_result", SCRIPT_DIR / "import_latentsync_result.py", False))

        total_steps = len(step_specs)
        for index, (step_name, script_path, should_skip) in enumerate(step_specs, start=1):
            if should_skip:
                print(f"[{index}/{total_steps}] {step_name} (skipped)")
                steps.append(_skipped_step(step_name, "Skipped by CLI flag."))
                if step_name == "merge_manual_clip_notes" and not args.skip_timeline and not args.use_ai_timeline:
                    created = _ensure_default_enriched(runtime_dir)
                    if created:
                        warnings.append("merge_manual_clip_notes step was skipped; generated default candidates_enriched.json.")
                continue

            if step_name == "merge_manual_clip_notes" and not manual_notes_path.exists():
                print(f"[{index}/{total_steps}] {step_name} (skipped: manual notes missing)")
                steps.append(_skipped_step(step_name, "manual_clip_notes.json not found; using default empty clip notes."))
                _ensure_default_enriched(runtime_dir)
                continue

            command = [python_cmd, str(script_path), "--runtime-dir", str(runtime_dir)]
            if step_name == "build_timeline_ai" and args.use_script_segments:
                command.extend(["--script-segments", str(runtime_dir / "input" / "script_segments.json")])
            if step_name == "export_latentsync_job":
                if args.latentsync_job_id:
                    command.extend(["--job-id", args.latentsync_job_id])
                command.extend(
                    [
                        "--latentsync-root",
                        args.latentsync_root,
                        "--engine-version",
                        args.latentsync_engine_version,
                        "--inference-steps",
                        str(args.latentsync_inference_steps),
                        "--guidance-scale",
                        str(args.latentsync_guidance_scale),
                    ]
                )
                if args.enable_deepcache:
                    command.append("--enable-deepcache")
            if step_name == "import_latentsync_result":
                command.extend(["--job-dir", args.latentsync_job_dir, "--result-video", args.latentsync_result_video])
            print(f"[{index}/{total_steps}] {step_name}")
            result, record = _run_step(command, repo_root)
            record["step_name"] = step_name
            steps.append(record)
            if result.returncode != 0:
                report = {
                    "status": "failed",
                    "runtime_dir": str(runtime_dir),
                    "steps": steps,
                    "outputs": {
                        "prepared_template": "output/prepared_template.mp4",
                        "qa_report": "reports/qa_report.json",
                        "candidate_sheet": "sheets/candidate_sheet.jpg",
                        "ai_scored_candidates": "reports/candidates_ai_scored.json",
                        "timeline_plan": "reports/timeline_plan.json",
                        "script_segments": "input/script_segments.json",
                        "latentsync_jobs": "latentsync_jobs/",
                        "final_video": "final/final_latentsync_output.mp4",
                        "final_qa_report": "reports/final_qa_report.json",
                    },
                    "warnings": warnings,
                }
                _write_pipeline_report(pipeline_report_path, report)
                return result.returncode or 1

        report = {
            "status": "success",
            "runtime_dir": str(runtime_dir),
            "python_executable": python_cmd,
            "steps": steps,
            "outputs": {
                "prepared_template": "output/prepared_template.mp4",
                "qa_report": "reports/qa_report.json",
                "candidate_sheet": "sheets/candidate_sheet.jpg",
                "ai_scored_candidates": "reports/candidates_ai_scored.json",
                "timeline_plan": "reports/timeline_plan.json",
                "script_segments": "input/script_segments.json",
                "latentsync_jobs": "latentsync_jobs/",
                "final_video": "final/final_latentsync_output.mp4",
                "final_qa_report": "reports/final_qa_report.json",
            },
            "warnings": warnings,
        }
        _write_pipeline_report(pipeline_report_path, report)
        print(f"[DONE] pipeline_report={pipeline_report_path}")
        return 0
    except SystemExit as exc:
        report = {
            "status": "failed",
            "runtime_dir": str(runtime_dir),
            "python_executable": python_cmd,
            "steps": steps,
            "outputs": {
                "prepared_template": "output/prepared_template.mp4",
                "qa_report": "reports/qa_report.json",
                "candidate_sheet": "sheets/candidate_sheet.jpg",
                "ai_scored_candidates": "reports/candidates_ai_scored.json",
                "timeline_plan": "reports/timeline_plan.json",
                "script_segments": "input/script_segments.json",
                "latentsync_jobs": "latentsync_jobs/",
                "final_video": "final/final_latentsync_output.mp4",
                "final_qa_report": "reports/final_qa_report.json",
            },
            "warnings": warnings,
            "error": str(exc),
        }
        _write_pipeline_report(pipeline_report_path, report)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
