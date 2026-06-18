#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from pathlib import Path


URL_RE = re.compile(r"https?://[^\s，。；;]+", re.IGNORECASE)


def extract_first_url(text: str) -> str | None:
    match = URL_RE.search(text or "")
    if not match:
        return None
    url = match.group(0).strip()
    # Remove common trailing punctuation copied from share text.
    return url.rstrip(").,，。；;！!？?")


def detect_platform_from_url(url: str) -> str:
    lower = (url or "").lower()
    if "bilibili.com" in lower or "b23.tv" in lower or re.search(r"\bbv[0-9a-z]{10}\b", lower):
        return "bilibili"
    if "douyin.com" in lower or "iesdouyin.com" in lower:
        return "douyin"
    if "weixin.qq.com" in lower or "channels.weixin.qq.com" in lower:
        return "wechat_channels"
    if "youtube.com" in lower or "youtu.be" in lower:
        return "youtube"
    return "unknown"


def detect_platform_from_input(path: str | Path) -> str:
    return "local"
