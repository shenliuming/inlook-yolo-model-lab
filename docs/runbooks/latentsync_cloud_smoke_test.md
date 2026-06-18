# LatentSync Cloud Smoke Test

This runbook documents a minimal manual smoke test for sending an exported Template Clip Bank job package to a cloud GPU host, running LatentSync there, and importing the result back into the local runtime.

This document is intentionally manual.

- No automated SSH flow
- No cloud API integration
- No code changes
- No local LatentSync execution

## 1. Pick A Local Job Package

Choose one exported LatentSync job package. Example:

`apps/yolo-api/runtime/template_bank/latentsync_jobs/job_test_002`

## 2. Package The Job Locally

Run:

```bash
tar -czf /tmp/job_test_002.tar.gz \
  -C apps/yolo-api/runtime/template_bank/latentsync_jobs \
  job_test_002
```

Optional quick check:

```bash
ls -lh /tmp/job_test_002.tar.gz
tar -tzf /tmp/job_test_002.tar.gz | head
```

## 3. Upload To The Cloud GPU Host

Replace the SSH port and cloud server IP with the real values:

```bash
scp -P 端口号 /tmp/job_test_002.tar.gz root@云服务器IP:/root/
```

## 4. Extract On The Cloud Host

SSH into the cloud GPU host, then run:

```bash
cd /root/LatentSync
mkdir -p inlook_jobs
tar -xzf /root/job_test_002.tar.gz -C /root/LatentSync/inlook_jobs
```

Optional quick check:

```bash
find /root/LatentSync/inlook_jobs/job_test_002 -maxdepth 3 -type f | sort
```

## 5. Run LatentSync On The Cloud Host

Run:

```bash
bash inlook_jobs/job_test_002/run_latentsync.sh
```

This runbook assumes:

- cloud LatentSync root is `/root/LatentSync`
- uploaded job path is `/root/LatentSync/inlook_jobs/job_test_002`

## 6. Check Cloud Output

Verify that the output file exists:

```bash
ls -lh /root/LatentSync/inlook_jobs/job_test_002/output/
```

Check the output duration:

```bash
ffprobe -v error \
  -show_entries format=duration \
  -of default=nk=1:nw=1 \
  /root/LatentSync/inlook_jobs/job_test_002/output/latentsync_output.mp4
```

Optional deeper probe:

```bash
ffprobe -v error \
  -show_entries stream=index,codec_type,codec_name,avg_frame_rate,nb_frames,width,height \
  -show_entries format=duration,size \
  -of json \
  /root/LatentSync/inlook_jobs/job_test_002/output/latentsync_output.mp4
```

## 7. Download The Result Back Locally

Replace the SSH port and cloud server IP with the real values:

```bash
scp -P 端口号 \
  root@云服务器IP:/root/LatentSync/inlook_jobs/job_test_002/output/latentsync_output.mp4 \
  apps/yolo-api/runtime/template_bank/latentsync_jobs/job_test_002/output/latentsync_output.mp4
```

Optional quick check:

```bash
ls -lh apps/yolo-api/runtime/template_bank/latentsync_jobs/job_test_002/output/latentsync_output.mp4
```

## 8. Import The Result Locally

Run:

```bash
python3 apps/yolo-api/engines/latentsync/template_bank/import_latentsync_result.py \
  --runtime-dir apps/yolo-api/runtime/template_bank \
  --job-dir apps/yolo-api/runtime/template_bank/latentsync_jobs/job_test_002 \
  --result-video apps/yolo-api/runtime/template_bank/latentsync_jobs/job_test_002/output/latentsync_output.mp4
```

This writes:

- `apps/yolo-api/runtime/template_bank/final/final_latentsync_output.mp4`
- `apps/yolo-api/runtime/template_bank/reports/final_qa_report.json`
- `apps/yolo-api/runtime/template_bank/final/final_report.json`

## 9. Check Final Artifacts

Expected local outputs:

- `apps/yolo-api/runtime/template_bank/final/final_latentsync_output.mp4`
- `apps/yolo-api/runtime/template_bank/reports/final_qa_report.json`
- `apps/yolo-api/runtime/template_bank/final/final_report.json`

Recommended checks:

```bash
ls -lh apps/yolo-api/runtime/template_bank/final/final_latentsync_output.mp4
cat apps/yolo-api/runtime/template_bank/reports/final_qa_report.json
cat apps/yolo-api/runtime/template_bank/final/final_report.json
```

## Expected Smoke Test Outcome

The smoke test is considered successful when:

- cloud-side `latentsync_output.mp4` is generated
- local import completes successfully
- `final_qa_report.json` is generated
- final video/audio duration difference is within one frame
- `final_report.json` shows status `imported`
