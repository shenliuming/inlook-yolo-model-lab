from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.digital_human_poc_service import (
    list_chanjing_common_audios,
    list_chanjing_common_persons,
    list_chanjing_custom_persons,
)


def _extract_items(payload: dict) -> list[dict]:
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("list", "items", "records"):
            if isinstance(data.get(key), list):
                return [item for item in data[key] if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="List Chanjing common/custom persons or common audios.")
    parser.add_argument("--type", required=True, choices=["custom", "common", "audio"])
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=20)
    args = parser.parse_args()

    if args.type == "custom":
        payload = list_chanjing_custom_persons(page=args.page, page_size=args.page_size)
    elif args.type == "common":
        payload = list_chanjing_common_persons(page=args.page, size=args.page_size)
    else:
        payload = list_chanjing_common_audios(page=args.page, size=args.page_size)
    items = _extract_items(payload)
    for item in items:
        line = {
            "person_id": item.get("id") or item.get("person_id"),
            "name": item.get("name"),
            "status": item.get("status"),
            "audio_man_id": item.get("audio_man_id"),
            "preview_url": item.get("preview_url"),
            "width": item.get("width"),
            "height": item.get("height"),
            "figures": item.get("figures"),
            "audio_preview": item.get("audio_preview"),
        }
        print(json.dumps(line, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
