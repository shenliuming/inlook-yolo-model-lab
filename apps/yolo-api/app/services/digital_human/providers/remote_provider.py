from __future__ import annotations

from .local_provider import LocalDigitalHumanProvider


class RemoteDigitalHumanProvider(LocalDigitalHumanProvider):
    code = "external_provider"
