import re
from test._base import BaseTest, sample_data
from typing import Any, cast, Match

import requests_mock  # type: ignore
from ts3.response import TS3Event  # type: ignore

from ts3bot import events
from ts3bot.commands.api_key import handle, MESSAGE_REGEX
from ts3bot.config import env
from ts3bot.database import models


class ApiKeyTest(BaseTest):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        register_uris(cls.adapter)

    def test_invalid_world(self) -> None:
        handle(
            self.bot,
            events.TextMessage(
                id="1",
                uid="def",
                name="invalid_world",
                message=sample_data.API_KEY_INVALID_WORLD,
            ),
            cast(
                Match[Any], re.match(MESSAGE_REGEX, sample_data.API_KEY_INVALID_WORLD)
            ),
        )
        self.bot.send_message.assert_called_with(  # type: ignore
            "1", "invalid_world", world="Anvil Rock"
        )

    def test_first_creation(self) -> None:
        handle(
            self.bot,
            events.TextMessage(
                id="1",
                uid="abc",
                name="Test_User",
                message=sample_data.API_KEY_VALID,
            ),
            cast(Match[Any], re.match(MESSAGE_REGEX, sample_data.API_KEY_VALID)),
        )

        self.assertIsNotNone(
            (
                self.session.query(models.Account)
                .filter(models.Account.name == "User.1234")
                .one_or_none()
            ),
            "Account was not created",
        )

        self.assertIsNotNone(
            self.session.query(models.Identity)
            .filter(models.Identity.guid == "abc")
            .one_or_none(),
            "Identity was not created",
        )

        self.assertEqual(
            self.mock_exec_calls["clientgetdbidfromuid"][0]["params"]["cluid"], "abc"
        )

        self.assertEqual(
            self.mock_exec_calls["servergroupaddclient"][0]["params"],
            {"sgid": env.generic_alliance_id, "cldbid": 1},
            "Generic World was not assigned",
        )
        self.assertEqual(
            self.mock_exec_calls["servergroupaddclient"][1]["params"],
            {"sgid": "2201", "cldbid": 1},
            "Correct world was not assigned",
        )

        # TODO: Check if guild was created

    def test_switch_account(self) -> None:
        # Create valid entry
        handle(
            self.bot,
            events.TextMessage(
                id="1",
                uid="abc",
                name="Test_User",
                message=sample_data.API_KEY_VALID,
            ),
            cast(Match[Any], re.match(MESSAGE_REGEX, sample_data.API_KEY_VALID)),
        )

        self.bot.send_message.assert_called_with("1", "welcome_registered_3")  # type: ignore

        # Create valid entry
        handle(
            self.bot,
            events.TextMessage(
                id="1",
                uid="abc",
                name="Test_User",
                message=sample_data.API_KEY_VALID_OTHER,
            ),
            cast(Match[Any], re.match(MESSAGE_REGEX, sample_data.API_KEY_VALID_OTHER)),
        )

        self.bot.send_message.assert_called_with(  # type: ignore
            "1", "registration_update", account="User.4321"
        )

    def test_already_linked(self) -> None:
        # Create valid entry
        handle(
            self.bot,
            events.TextMessage(
                id="1",
                uid="abc",
                name="Test_User",
                message=sample_data.API_KEY_VALID,
            ),
            cast(Match[Any], re.match(MESSAGE_REGEX, sample_data.API_KEY_VALID)),
        )

        # Try again with different uid
        handle(
            self.bot,
            events.TextMessage(
                id="1",
                uid="def",
                name="Already_linked",
                message=sample_data.API_KEY_VALID,
            ),
            cast(Match[Any], re.match(MESSAGE_REGEX, sample_data.API_KEY_VALID)),
        )
        self.bot.send_message.assert_called_with(  # type: ignore
            "1", "token_in_use", api_name="ts3bot-1"
        )

        # Try again with a correctly named token
        handle(
            self.bot,
            events.TextMessage(
                id="1",
                uid="def",
                name="Already_linked",
                message=sample_data.API_KEY_DUPLICATE,
            ),
            cast(Match[Any], re.match(MESSAGE_REGEX, sample_data.API_KEY_DUPLICATE)),
        )
        self.bot.send_message.assert_called_with(  # type: ignore
            "1", "registration_transferred", account="User.1234"
        )

    def test_linked_to_current_guid(self) -> None:
        # Create valid entry
        handle(
            self.bot,
            events.TextMessage(
                id="1",
                uid="abc",
                name="Test_User",
                message=sample_data.API_KEY_VALID,
            ),
            cast(Match[Any], re.match(MESSAGE_REGEX, sample_data.API_KEY_VALID)),
        )

        # Do it again but with a different key
        handle(
            self.bot,
            events.TextMessage(
                id="2",
                uid="abc",
                name="Test_User",
                message=sample_data.API_KEY_DUPLICATE,
            ),
            cast(Match[Any], re.match(MESSAGE_REGEX, sample_data.API_KEY_DUPLICATE)),
        )

        self.bot.send_message.assert_called_with("2", "registration_exists")  # type: ignore

    def test_invalid_key(self) -> None:
        handle(
            self.bot,
            events.TextMessage(
                id="2",
                uid="abc",
                name="Test_User",
                message=sample_data.API_KEY_INVALID,
            ),
            cast(Match[Any], re.match(MESSAGE_REGEX, sample_data.API_KEY_INVALID)),
        )
        self.bot.send_message.assert_called_with("2", "invalid_token_retry")  # type: ignore

    def test_invalid_response(self) -> None:
        handle(
            self.bot,
            events.TextMessage(
                id="2",
                uid="abc",
                name="Test_User",
                message=sample_data.API_KEY_INVALID_RESPONSE,
            ),
            cast(
                Match[Any],
                re.match(MESSAGE_REGEX, sample_data.API_KEY_INVALID_RESPONSE),
            ),
        )
        self.bot.send_message.assert_called_with("2", "error_api")  # type: ignore


def register_uris(adapter: requests_mock.Adapter) -> None:
    adapter.register_uri(
        "GET",
        "https://api.guildwars2.com/v2/account",
        request_headers={"authorization": f"Bearer {sample_data.API_KEY_DUPLICATE}"},
        text=sample_data.ACCOUNT,
    )
    # Data for other account
    adapter.register_uri(
        "GET",
        "https://api.guildwars2.com/v2/account",
        request_headers={"authorization": f"Bearer {sample_data.API_KEY_VALID_OTHER}"},
        text=sample_data.ACCOUNT_OTHER,
    )

    adapter.register_uri(
        "GET",
        "https://api.guildwars2.com/v2/account",
        request_headers={
            "authorization": f"Bearer {sample_data.API_KEY_INVALID_WORLD}"
        },
        text=sample_data.ACCOUNT_INVALID_WORLD,
    )
    adapter.register_uri(
        "GET",
        "https://api.guildwars2.com/v2/account",
        request_headers={"authorization": f"Bearer {sample_data.API_KEY_INVALID}"},
        text=sample_data.ACCOUNT_INVALID,
        status_code=403,
    )
    adapter.register_uri(
        "GET",
        "https://api.guildwars2.com/v2/account",
        request_headers={
            "authorization": f"Bearer {sample_data.API_KEY_INVALID_RESPONSE}"
        },
        status_code=500,
    )
    # Used for registering a second time
    adapter.register_uri(
        "GET",
        "https://api.guildwars2.com/v2/tokeninfo",
        request_headers={"authorization": f"Bearer {sample_data.API_KEY_VALID}"},
        text="""
            {"id":"00000000-0000-0000-0000-0000000000","name": "some-name",
            "permissions":["progression"]}
            """,
    )
    # Also used for that, but this time the name is correct
    adapter.register_uri(
        "GET",
        "https://api.guildwars2.com/v2/tokeninfo",
        request_headers={"authorization": f"Bearer {sample_data.API_KEY_DUPLICATE}"},
        text="""
            {"id":"00000000-0000-0000-0000-0000000000","name": "ts3bot-1",
            "permissions":["progression"]}
            """,
    )
