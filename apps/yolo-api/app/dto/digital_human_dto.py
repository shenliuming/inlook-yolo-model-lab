from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DigitalHumanGenerateRequestDTO(BaseModel):
    templateId: str | None = Field(default=None, max_length=160)
    script: str = Field(default="", max_length=10000)
    voiceMode: Literal["inlook_tts", "upload_audio", "provider_auto"] = "provider_auto"
    audioTaskId: str | None = Field(default=None, max_length=160)
    audioPath: str | None = Field(default=None, max_length=2000)
    audioUrl: str | None = Field(default=None, max_length=2000)
    workflowId: str | None = Field(default=None, max_length=160)
    projectId: str | None = Field(default=None, max_length=160)
    mode: str = Field(default="talking_head", max_length=80)
    avatarId: str | None = Field(default=None, max_length=120)
    personId: str | None = Field(default=None, max_length=120)
    audioId: str | None = Field(default=None, max_length=160)
    audioManId: str | None = Field(default=None, max_length=120)
    screenWidth: int | None = Field(default=None, ge=1)
    screenHeight: int | None = Field(default=None, ge=1)
    personWidth: int | None = Field(default=None, ge=1)
    personHeight: int | None = Field(default=None, ge=1)
    model: int | None = Field(default=None, ge=0)
    resolutionRate: int | None = Field(default=None, ge=0)


class ChanjingPocCreateRequestDTO(BaseModel):
    person_id: str = Field(min_length=1, max_length=120)
    audio_type: str = Field(default="audio", pattern="^(audio|tts)$")
    text: str | None = Field(default=None, max_length=10000)
    wav_url: str | None = Field(default=None, max_length=1000)
    audio_man_id: str | None = Field(default=None, max_length=120)
    figure_type: str | None = Field(default=None, max_length=120)
    screen_width: int = Field(default=1080, ge=1)
    screen_height: int = Field(default=1920, ge=1)
    model: int = Field(default=0)
    add_compliance_watermark: bool = Field(default=False)


class ChanjingTrainingPocRequestDTO(BaseModel):
    local_video_path: str = Field(min_length=1, max_length=2000)
    name: str = Field(min_length=1, max_length=200)
    train_type: str = Field(default="both", pattern="^(voice|figure|both)$")
    callback: str = Field(default="", max_length=1000)
    error_skip: bool = Field(default=False)
    resolution_rate: int = Field(default=0)
    language: str = Field(default="cn", max_length=32)
    version: str = Field(default="1.0", max_length=32)
    auth_text: str | None = Field(default=None, max_length=500)
    auth_video_file_id: str | None = Field(default=None, max_length=120)


class ChanjingVideoPocRequestDTO(BaseModel):
    person_id: str = Field(min_length=1, max_length=120)
    audio_type: str = Field(default="audio", pattern="^(audio|tts)$")
    text: str | None = Field(default=None, max_length=10000)
    wav_url: str | None = Field(default=None, max_length=2000)
    audio_file_id: str | None = Field(default=None, max_length=120)
    audio_man_id: str | None = Field(default=None, max_length=120)
    figure_type: str | None = Field(default=None, max_length=120)
    screen_width: int = Field(default=1080, ge=1)
    screen_height: int = Field(default=1920, ge=1)
    person_x: int = Field(default=0)
    person_y: int = Field(default=0)
    person_width: int | None = Field(default=None, ge=1)
    person_height: int | None = Field(default=None, ge=1)
    model: int = Field(default=0)
    resolution_rate: int = Field(default=0)
    add_compliance_watermark: bool = Field(default=False)
    hide_subtitle: bool = Field(default=False)
    bg_color: str | None = Field(default=None, max_length=64)


class ChanjingFullPocRequestDTO(BaseModel):
    local_video_path: str = Field(min_length=1, max_length=2000)
    name: str = Field(min_length=1, max_length=200)
    train_type: str = Field(default="both", pattern="^(voice|figure|both)$")
    callback: str = Field(default="", max_length=1000)
    error_skip: bool = Field(default=False)
    resolution_rate: int = Field(default=0)
    language: str = Field(default="cn", max_length=32)
    version: str = Field(default="1.0", max_length=32)
    auth_text: str | None = Field(default=None, max_length=500)
    auth_video_file_id: str | None = Field(default=None, max_length=120)
    audio_type: str = Field(default="audio", pattern="^(audio|tts)$")
    text: str | None = Field(default=None, max_length=10000)
    wav_url: str | None = Field(default=None, max_length=2000)
    audio_file_id: str | None = Field(default=None, max_length=120)
    audio_man_id: str | None = Field(default=None, max_length=120)
    figure_type: str | None = Field(default=None, max_length=120)
    screen_width: int = Field(default=1080, ge=1)
    screen_height: int = Field(default=1920, ge=1)
    person_x: int = Field(default=0)
    person_y: int = Field(default=0)
    person_width: int | None = Field(default=None, ge=1)
    person_height: int | None = Field(default=None, ge=1)
    model: int = Field(default=0)
    add_compliance_watermark: bool = Field(default=False)
    hide_subtitle: bool = Field(default=False)
    bg_color: str | None = Field(default=None, max_length=64)
