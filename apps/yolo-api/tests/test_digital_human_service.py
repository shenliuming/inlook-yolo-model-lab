from __future__ import annotations

from app.services import digital_human_poc_service
from app.services.digital_human.task_service import _project_audio_relative_path


def test_project_audio_relative_path_supports_absolute_project_file_url() -> None:
    project_id = "proj_test_123"
    audio_url = f"http://127.0.0.1:7860/api/v1/studio/projects/{project_id}/files/tts/synthesis/syn_001/output.wav"
    assert _project_audio_relative_path(project_id, audio_url) == "tts/synthesis/syn_001/output.wav"


def test_project_audio_relative_path_returns_empty_for_non_project_url() -> None:
    assert _project_audio_relative_path("proj_test_123", "https://example.com/audio.wav") == ""


class _FakeChanjingClient:
    def list_customised_person(self, *, page: int, page_size: int) -> dict[str, object]:
        return {
            "data": {
                "list": [
                    {
                        "id": "C-ready",
                        "name": "Ready Person",
                        "status": 2,
                        "audio_man_id": "A-ready",
                        "pic_url": "https://example.com/pic.png",
                        "preview_url": "https://example.com/preview.mp4",
                        "width": 720,
                        "height": 1280,
                        "support_4k": False,
                    }
                ]
            }
        }


class _FakeEngine:
    def __init__(self) -> None:
        self.client = _FakeChanjingClient()

    def ensure_access_token(self) -> str:
        return "token"


def test_list_chanjing_persons_marks_remote_status_2_as_ready(monkeypatch) -> None:
    monkeypatch.setattr(digital_human_poc_service, "upsert_digital_human_person", None)
    monkeypatch.setattr(digital_human_poc_service, "list_digital_human_persons", None)

    payload = digital_human_poc_service.list_chanjing_persons(source="api", engine=_FakeEngine())

    assert payload["source"] == "api"
    assert payload["items"][0]["person_id"] == "C-ready"
    assert payload["items"][0]["status"] == "ready"
