import logging
import unittest
from typing import Any, cast, Dict, List
from unittest.mock import MagicMock

import requests_mock  # type: ignore
import sample_data  # type: ignore

import ts3bot
from ts3bot.bot import Bot
from ts3bot.database import create_session, enums, models
from ts3bot.utils import init_logger

TEST_DATABASE = "sqlite:///:memory:"
# TEST_DATABASE = "sqlite:///test.sqlite3"

MOCK_RESPONSES: Dict[str, List[dict]] = {}


def mock_exec_(
    mock_exec_calls: Dict[str, List[dict]], cmd: str, *options: Any, **params: Any
) -> List[Dict]:
    logging.debug("mock_exec_: %s [%s] {%s}", cmd, options, params)

    # Log calls
    if cmd not in mock_exec_calls:
        mock_exec_calls[cmd] = []
    mock_exec_calls[cmd].append({"options": options, "params": params})

    if cmd in MOCK_RESPONSES:
        # Raise exceptions to verify proper handling
        if isinstance(MOCK_RESPONSES[cmd], Exception):
            raise cast(Exception, MOCK_RESPONSES[cmd])

        return MOCK_RESPONSES[cmd]

    if cmd.startswith("clientgetdbidfromuid"):
        return [{"cldbid": 1}]
    elif cmd == "servergroupdelclient":
        return []
    elif cmd == "servergroupaddclient":
        return []
    elif cmd == "servergroupsbyclientid":
        return []

    raise Exception(f"Unhandled query: {cmd} [{options}] {{{params}}}")


class BaseTest(unittest.TestCase):
    adapter: requests_mock.Adapter

    def setUp(self) -> None:
        # Set up DB and bot
        self.session = create_session(TEST_DATABASE, is_test=True)
        self.bot = Bot(self.session, connect=False)
        self.bot.send_message = MagicMock()  # type: ignore

        # TODO: Setup alliance guilds

        # Log ts3 query calls
        self.mock_exec_calls: Dict[str, List[Dict[str, Any]]] = {}

        def mocker(cmd: str, *options: Any, **params: Any) -> List[dict]:
            return mock_exec_(self.mock_exec_calls, cmd, *options, **params)

        self.bot.exec_ = mocker  # type: ignore

    @classmethod
    def setUpClass(cls) -> None:
        # Set up logger
        init_logger("test", is_test=True)

        requests_mock.mock.case_sensitive = True
        cls.adapter = requests_mock.Adapter(case_sensitive=True)
        ts3bot.session.mount("http://", cls.adapter)
        ts3bot.session.mount("https://", cls.adapter)

        # Register commonly used URI
        cls.adapter.register_uri(
            "GET",
            "https://api.guildwars2.com/v2/account",
            request_headers={"authorization": f"Bearer {sample_data.API_KEY_VALID}"},
            text=sample_data.ACCOUNT,
        )
        cls.adapter.register_uri(
            "GET",
            "https://api.guildwars2.com/v2/guild/4BBB52AA-D768-4FC6-8EDE-C299F2822F0F",
            text=sample_data.ARENANET_GUILD,
        )
