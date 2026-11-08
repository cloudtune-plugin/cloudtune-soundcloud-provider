import asyncio
import socket
from unittest.mock import MagicMock

import pytest

import cloudtune_soundcloud_provider.provider as module
from cloudtune_soundcloud_provider import SoundCloudProvider


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Tests must not make network requests")
    # Windows builds asyncio's internal socketpair over loopback TCP.
    # Construct only the event loop before reinstating the network guard;
    # no provider code or callbacks run during loop construction.
    original_new_loop = asyncio.events.new_event_loop
    original_connect = socket.socket.connect

    def new_loop():
        with monkeypatch.context() as context:
            context.setattr(socket.socket, "connect", original_connect)
            return original_new_loop()

    monkeypatch.setattr(asyncio.events, "new_event_loop", new_loop)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


@pytest.fixture
def provider():
    return SoundCloudProvider(settings={}, secrets={})


@pytest.fixture
def extractor(monkeypatch):
    factory = MagicMock()
    factory.return_value.__enter__.return_value = factory.return_value
    monkeypatch.setattr(module, "YoutubeDL", factory)
    return factory
