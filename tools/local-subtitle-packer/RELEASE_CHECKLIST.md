# RELEASE CHECKLIST

Before packaging this local subtitle tool for other people to download, check the following:

## Must Not Be Included

- `.venv/`
- `jobs/`
- `input.mp4`
- `output_subtitled.mp4`
- `output_subtitled.srt`
- `output_subtitled.ass`
- `output_subtitled.txt`
- any other `.mp4 / .mov / .m4a / .mp3 / .wav`
- any generated logs
- any local debug files

## Must Be Included

- `README.md`
- `requirements.txt`
- `start.sh`
- `start.command`
- `start.bat`
- `scripts/subtitle_pack.py`
- `scripts/burn_subtitles.py`
- `scripts/check_env.py`
- `scripts/web_app.py`
- `web/index.html`
- `web/app.js`
- `web/styles.css`
- `examples/example_usage.md`
- `PRODUCTION_WORKFLOW.md`

## Before Release

- Confirm `python scripts/check_env.py` can run
- Confirm `start.sh` can open `http://127.0.0.1:7860`
- Confirm one sample video can generate:
  - `mp4`
  - `srt`
  - `ass`
  - `txt`
- Confirm edited `ass` can be reburned with `burn_subtitles.py`
- Confirm no model files, videos, audios, or outputs are committed
