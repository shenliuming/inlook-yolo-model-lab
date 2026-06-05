from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException

from app.config.paths import OUTPUTS_DIR, REPORTS_DIR


def get_vision_task(task_id: str) -> dict[str, object]:
    report_path = REPORTS_DIR / f"{task_id}.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="未找到视觉识别任务")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    output_path = OUTPUTS_DIR / task_id
    files: list[dict[str, str]] = []
    if output_path.exists():
        for file_path in sorted(path for path in output_path.iterdir() if path.is_file()):
            files.append(
                {
                    "name": file_path.name,
                    "url": f"/api/v1/vision/tasks/{task_id}/files/{file_path.name}",
                }
            )
    files.append({"name": f"{task_id}.json", "url": f"/reports/{task_id}.json"})

    return {
        "task_id": task_id,
        "domain": "vision",
        "type": f"{report.get('type', 'unknown')}_detect",
        "status": "success" if report.get("status") == "finished" else str(report.get("status", "unknown")),
        "message": "识别任务已完成",
        "created_at": str(report.get("start_time", "")),
        "updated_at": str(report.get("end_time", "")),
        "started_at": report.get("start_time"),
        "finished_at": report.get("end_time"),
        "files": files,
        "log_tail": "[DONE] 识别完成\n[INFO] 结果文件已生成",
        "report": report,
    }


def get_vision_task_file_path(task_id: str, filename: str) -> Path:
    target = OUTPUTS_DIR / task_id / filename
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return target

