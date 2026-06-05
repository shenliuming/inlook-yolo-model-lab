from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from app.clients.browser_client import BrowserClient, BrowserSession


class BrowserClientTest(unittest.TestCase):
    def test_runtime_session_reopens_when_visible_session_belongs_to_other_thread(self) -> None:
        client = BrowserClient()
        closed: list[str] = []

        foreign_session = BrowserSession(
            platform="douyin",
            playwright=SimpleNamespace(stop=lambda: closed.append("playwright")),
            context=SimpleNamespace(close=lambda: closed.append("context"), pages=[]),
            thread_id=999999,
        )
        client._sessions["douyin:visible"] = foreign_session

        replacement = object()
        with mock.patch.object(client, "start_persistent_browser", return_value=replacement) as starter:
            session = client._get_runtime_session("douyin")

        self.assertIs(session, replacement)
        self.assertNotIn("douyin:visible", client._sessions)
        self.assertEqual(closed, ["context", "playwright"])
        starter.assert_called_once_with("douyin", headless=True)


if __name__ == "__main__":
    unittest.main()
