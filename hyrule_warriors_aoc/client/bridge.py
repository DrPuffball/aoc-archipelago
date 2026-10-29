"""
TCP bridge between the Archipelago client and whatever runs next to the game.

The client listens on 127.0.0.1:38291 (not 38281, Archipelago's own server port). A game-side component (a mod, emulator script or memory
reader) connects to it and exchanges newline-delimited JSON objects. The protocol is documented
in docs/game_side_protocol.md; this module only moves messages.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger("AgeOfCalamity")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 38291
PROTOCOL_VERSION = 1

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


class GameBridge:
    def __init__(self, on_message: MessageHandler, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self._on_message = on_message
        self._host = host
        self._port = port
        self._server: asyncio.AbstractServer | None = None
        self._writer: asyncio.StreamWriter | None = None
        self.on_connect: Callable[[], Awaitable[None]] | None = None

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def start(self) -> None:
        try:
            self._server = await asyncio.start_server(self._handle_client, self._host, self._port)
        except OSError as e:  # port taken (another client still open): the live hook does not need the bridge
            logger.warning("Game-side bridge port %s:%d is in use (%s); continuing without it. If another Age of "
                           "Calamity client is still open, close it.", self._host, self._port, e)
            return
        logger.info("Waiting for the game-side hook on %s:%d", self._host, self._port)

    async def stop(self) -> None:
        if self._writer:
            self._writer.close()
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def send(self, message: dict[str, Any]) -> None:
        if not self.connected:
            return
        assert self._writer is not None
        self._writer.write((json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8"))
        try:
            await self._writer.drain()
        except ConnectionError:
            logger.warning("Lost the game-side hook while sending")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        if self.connected:
            # Only one game at a time; the newest connection replaces the old one.
            assert self._writer is not None
            self._writer.close()
        self._writer = writer
        logger.info("Game-side hook connected")
        try:
            if self.on_connect:
                await self.on_connect()
            while line := await reader.readline():
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Ignoring malformed line from game: %r", line[:200])
                    continue
                if isinstance(message, dict):
                    await self._on_message(message)
        except ConnectionError:
            pass
        finally:
            logger.info("Game-side hook disconnected")
            if self._writer is writer:
                self._writer = None
            writer.close()
