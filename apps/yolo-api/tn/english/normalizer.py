from __future__ import annotations

import re


class Normalizer:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    def normalize(self, text: str) -> str:
        value = str(text or "").strip()
        return re.sub(r"\s+", " ", value)
