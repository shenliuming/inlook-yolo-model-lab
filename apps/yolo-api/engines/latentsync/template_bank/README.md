# Template Clip Bank MVP

Template Clip Bank prepares a reusable real-person template video for later
LatentSync lip-sync generation.

The MVP takes a 60-120 second `input/template.mp4`, slices it into reusable
candidate clips, supports human notes or mock AI scoring, builds a timeline that
roughly matches `input/narration.wav`, renders `output/prepared_template.mp4`,
runs local QA, and can export/import a LatentSync job package.

Main chain:

```text
script.txt
-> script_segments.json
-> candidates_ai_scored.json
-> timeline_plan.json
-> prepared_template.mp4
-> qa_report.json
-> export_latentsync_job
-> import_latentsync_result
```

## Runtime Layout

Default runtime directory:

```text
apps/yolo-api/runtime/template_bank
```

Expected subdirectories:

- `input/`: `template.mp4`, `narration.wav`, `script.txt`, manual selections, manual notes
- `candidates/`: sliced candidate clips
- `sheets/`: per-clip preview sheets and paginated overview sheets
- `reports/`: candidate metadata, timeline, pipeline, and QA reports
- `output/`: `prepared_template.mp4`
- `latentsync_jobs/`: exported cloud job packages
- `final/`: imported LatentSync result and final report

## Scripts

- `extract_candidates.py`: sliding-window clip extraction
- `make_candidate_sheet.py`: six-frame preview sheets and overview pages
- `merge_manual_clip_notes.py`: merge `manual_clip_notes.json` into candidates
- `build_script_segments_mock.py`: split `script.txt` by punctuation and allocate durations from `narration.wav`
- `score_candidates_ai.py`: mock scoring provider that fixes the future vision-model contract
- `build_timeline_manual.py`: build `timeline_plan.json` from `selected_clips.json`
- `build_timeline_ai.py`: build score-only or script-aware mock AI timeline
- `render_prepared_template.py`: render `prepared_template.mp4` from `timeline_plan.json`
- `qa_report.py`: validate local prepared video against narration and timeline
- `export_latentsync_job.py`: package prepared video/audio/context for cloud LatentSync
- `import_latentsync_result.py`: import a finished `latentsync_output.mp4`
- `run_pipeline.py`: standard orchestration wrapper

## Standard Runs

Manual selected-clip route:

```bash
python3 apps/yolo-api/engines/latentsync/template_bank/run_pipeline.py \
  --runtime-dir apps/yolo-api/runtime/template_bank
```

Mock AI + script-aware route:

```bash
python3 apps/yolo-api/engines/latentsync/template_bank/run_pipeline.py \
  --runtime-dir apps/yolo-api/runtime/template_bank \
  --build-script-segments \
  --run-ai-score \
  --use-ai-timeline \
  --use-script-segments
```

Mock AI + script-aware route with LatentSync export:

```bash
python3 apps/yolo-api/engines/latentsync/template_bank/run_pipeline.py \
  --runtime-dir apps/yolo-api/runtime/template_bank \
  --build-script-segments \
  --run-ai-score \
  --use-ai-timeline \
  --use-script-segments \
  --export-latentsync-job \
  --latentsync-job-id job_test_002 \
  --enable-deepcache
```

Useful export tuning flags:

- `--latentsync-job-id`
- `--latentsync-root`
- `--latentsync-engine-version`
- `--latentsync-inference-steps`
- `--latentsync-guidance-scale`
- `--enable-deepcache`

Import a finished cloud result:

```bash
python3 apps/yolo-api/engines/latentsync/template_bank/run_pipeline.py \
  --runtime-dir apps/yolo-api/runtime/template_bank \
  --import-latentsync-result \
  --latentsync-job-dir apps/yolo-api/runtime/template_bank/latentsync_jobs/job_test_002 \
  --latentsync-result-video apps/yolo-api/runtime/template_bank/latentsync_jobs/job_test_002/output/latentsync_output.mp4
```

## Current Limits

- `score_candidates_ai.py` is still a mock provider, not a real visual model.
- `build_timeline_ai.py` is still rule-based, not an LLM planner.
- `prepared_template.mp4` is hard-cut concatenation; crossfade and beat-level transitions are not implemented.
- Cloud execution is packaged and documented, but upload, remote run, polling, and download are still manual.

See `docs/template_clip_bank_handoff.md` and
`docs/runbooks/latentsync_cloud_smoke_test.md` for the latest handoff and cloud
smoke-test workflow.
