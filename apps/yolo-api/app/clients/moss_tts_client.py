from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from app.config.settings import (
    get_moss_tts_backend,
    get_moss_tts_execution_provider,
    get_moss_tts_model_dir,
    get_moss_tts_output_filename,
    get_moss_tts_repo_dir,
)
from app.utils.subprocess_utils import stream_command

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class MossTtsClient:
    def __init__(self) -> None:
        self.repo_dir = get_moss_tts_repo_dir()
        self.model_dir = get_moss_tts_model_dir()
        self.default_backend = get_moss_tts_backend()
        self.default_execution_provider = get_moss_tts_execution_provider()
        self.default_output_filename = get_moss_tts_output_filename()

    def infer_script_path(self) -> Path:
        return self.repo_dir / "infer_onnx.py"

    def cli_binary(self) -> str | None:
        return shutil.which("moss-tts-nano")

    def cli_module_path(self) -> Path:
        return self.repo_dir / "moss_tts_nano" / "cli.py"

    def cli_available(self) -> bool:
        return self.cli_binary() is not None or self.cli_module_path().exists()

    def infer_script_exists(self) -> bool:
        return self.infer_script_path().exists()

    def dependency_status(self) -> dict[str, bool]:
        return {
            "onnxruntime": importlib.util.find_spec("onnxruntime") is not None,
            "sentencepiece": importlib.util.find_spec("sentencepiece") is not None,
            "torch": importlib.util.find_spec("torch") is not None,
            "torchaudio": importlib.util.find_spec("torchaudio") is not None,
            "huggingface_hub": importlib.util.find_spec("huggingface_hub") is not None,
            "transformers": importlib.util.find_spec("transformers") is not None,
            "wetextprocessing": importlib.util.find_spec("tn") is not None,
        }

    def health(self) -> dict[str, Any]:
        binary_path = self.cli_binary()
        dependency_status = self.dependency_status()
        required_dependencies_ready = all(
            dependency_status[name]
            for name in ("onnxruntime", "sentencepiece", "torch", "torchaudio", "huggingface_hub", "wetextprocessing")
        )
        ready = (
            self.repo_dir.exists()
            and self.infer_script_exists()
            and self.cli_available()
            and required_dependencies_ready
        )
        if self.model_dir.exists():
            has_model_files = any(path.is_file() for path in self.model_dir.rglob("*"))
            model_hint = "已检测到模型目录"
        else:
            has_model_files = False
            model_hint = "模型目录不存在，首次生成时会尝试下载 ONNX 模型"

        return {
            "status": "ok" if ready else "degraded",
            "engine": "moss-tts-nano",
            "backend": self.default_backend,
            "execution_provider": self.default_execution_provider,
            "repo_dir": str(self.repo_dir),
            "repo_dir_exists": self.repo_dir.exists(),
            "infer_onnx_path": str(self.infer_script_path()),
            "infer_onnx_exists": self.infer_script_exists(),
            "cli_exists": self.cli_available(),
            "cli_binary": binary_path,
            "cli_module_entry": str(self.cli_module_path()),
            "models_dir": str(self.model_dir),
            "models_dir_exists": self.model_dir.exists(),
            "models_present": has_model_files,
            "models_hint": model_hint,
            "dependencies": dependency_status,
            "message": "MOSS-TTS-Nano ONNX health checked",
        }

    def _build_python_env(self) -> dict[str, str]:
        python_path_entries = [str(self.repo_dir), str(BACKEND_DIR)]
        current_pythonpath = os.environ.get("PYTHONPATH", "").strip()
        if current_pythonpath:
            python_path_entries.append(current_pythonpath)
        return {
            "PYTHONPATH": ":".join(python_path_entries),
        }

    def _build_cli_command(
        self,
        *,
        text_path: Path,
        output_path: Path,
        prompt_audio_path: Path | None,
        execution_provider: str,
        voice: str,
        model_dir: Path | None,
    ) -> list[str]:
        binary_path = self.cli_binary()
        if binary_path:
            command = [binary_path, "generate"]
        else:
            command = [sys.executable, "-m", "moss_tts_nano.cli", "generate"]

        command.extend(
            [
                "--backend",
                "onnx",
                "--text-file",
                str(text_path),
                "--output",
                str(output_path),
                "--voice",
                voice,
                "--execution-provider",
                "cuda" if execution_provider == "cuda" else "cpu",
            ]
        )
        if prompt_audio_path:
            command.extend(["--prompt-speech", str(prompt_audio_path)])
        if model_dir:
            command.extend(["--onnx-model-dir", str(model_dir)])
        return command

    def _build_infer_command(
        self,
        *,
        text_path: Path,
        output_path: Path,
        prompt_audio_path: Path | None,
        execution_provider: str,
        voice: str,
        model_dir: Path | None,
    ) -> list[str]:
        command = [
            sys.executable,
            str(self.infer_script_path()),
            "--text-file",
            str(text_path),
            "--output-audio-path",
            str(output_path),
            "--voice",
            voice,
            "--execution-provider",
            "cuda" if execution_provider == "cuda" else "cpu",
        ]
        if prompt_audio_path:
            command.extend(["--prompt-audio-path", str(prompt_audio_path)])
        if model_dir:
            command.extend(["--model-dir", str(model_dir)])
        return command

    def generate(
        self,
        *,
        text_path: Path,
        output_path: Path,
        prompt_audio_path: Path | None,
        execution_provider: str,
        voice: str,
        model_dir: Path | None,
        on_log,
    ) -> dict[str, Any]:
        env = self._build_python_env()
        model_root = model_dir if model_dir and model_dir.exists() else self.model_dir

        attempts: list[dict[str, str]] = []
        commands: list[tuple[str, list[str], dict[str, str]]] = []
        if binary_path := self.cli_binary():
            commands.append(
                (
                    "cli",
                    self._build_cli_command(
                        text_path=text_path,
                        output_path=output_path,
                        prompt_audio_path=prompt_audio_path,
                        execution_provider=execution_provider,
                        voice=voice,
                        model_dir=model_root,
                    ),
                    env,
                )
            )
        if self.infer_script_exists():
            commands.append(
                (
                    "infer_onnx.py",
                    self._build_infer_command(
                        text_path=text_path,
                        output_path=output_path,
                        prompt_audio_path=prompt_audio_path,
                        execution_provider=execution_provider,
                        voice=voice,
                        model_dir=model_root,
                    ),
                    env,
                )
            )
        elif self.cli_module_path().exists():
            commands.append(
                (
                    "cli-module",
                    self._build_cli_command(
                        text_path=text_path,
                        output_path=output_path,
                        prompt_audio_path=prompt_audio_path,
                        execution_provider=execution_provider,
                        voice=voice,
                        model_dir=model_root,
                    ),
                    env,
                )
            )

        if not commands:
            raise RuntimeError("未找到可用的 MOSS-TTS-Nano CLI 或 infer_onnx.py")

        for label, command, command_env in commands:
            on_log(f"[INFO] 尝试使用 {label} 生成语音")
            on_log(f"[CMD] {' '.join(command)}")
            exit_code = stream_command(
                command,
                cwd=self.repo_dir,
                env=command_env,
                on_output=on_log,
            )
            attempts.append({"runner": label, "exit_code": str(exit_code)})
            if exit_code == 0 and output_path.exists():
                return {
                    "ok": True,
                    "runner": label,
                    "output_path": str(output_path),
                    "attempts": attempts,
                }
            on_log(f"[WARN] {label} 执行失败，退出码 {exit_code}")

        raise RuntimeError(
            f"MOSS-TTS-Nano 生成失败：{json.dumps(attempts, ensure_ascii=False)}"
        )


moss_tts_client = MossTtsClient()
