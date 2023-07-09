import datetime
import re
from re import Match
from typing import Any, cast

from ts3bot import events
from ts3bot.commands.guild import MESSAGE_REGEX, handle
from ts3bot.config import env
from ts3bot.database import enums, models

from ._base import BaseTest, sample_data


class GuildTest(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        # Add account
        account = models.Account(
            name="User.1234",
            world=enums.World.KODASH,
            api_key=sample_data.API_KEY_VALID,
            last_check=datetime.datetime(2020, 1, 1, 0, 0, 0, 0),
        )
        self.session.add(account)
        # Add guild
        guild = models.Guild(
            guid="4BBB52AA-D768-4FC6-8EDE-C299F2822F0F",
            name="Arenanet",
            tag="Arenanet",
            group_id=1,
        )
        self.session.add(guild)
        self.session.commit()

        # Link identity to account
        identity = models.Identity(guid="abc")
        self.session.add(identity)
        self.session.add(models.LinkAccountIdentity(account=account, identity=identity))

        # Link account to guild
        self.session.add(models.LinkAccountGuild(account=account, guild=guild))

        self.session.commit()

    def test_missing_account(self) -> None:
        handle(
            self.bot,
            events.TextMessage(
                id="1",
                uid="def",
                name="a",
                message="!guild Arenanet",
            ),
            cast(Match[Any], re.match(MESSAGE_REGEX, "!guild Arenanet")),
        )
        self.bot.send_message.assert_called_with("1", "missing_token")

    def test_refresh_guilds(self) -> None:
        handle(
            self.bot,
            events.TextMessage(
                id="1",
                uid="abc",
                name="a",
                message="!guild A",
            ),
            cast(Match[Any], re.match(MESSAGE_REGEX, "!guild A")),
        )
        self.bot.send_message.assert_any_call("1", "account_updating")
        self.bot.send_message.assert_any_call(
            "1",
            "guild_invalid_selection",
            timeout=env.on_join_hours,
        )

    def test_list_guilds(self) -> None:
        handle(
            self.bot,
            events.TextMessage(
                id="1",
                uid="abc",
                name="a",
                message="!guild",
            ),
            cast(Match[Any], re.match(MESSAGE_REGEX, "!guild")),
        )
        self.bot.send_message.assert_called_with(
            "1", "guild_selection", guilds="Arenanet"
        )

    def test_update_world(self) -> None:
        handle(
            self.bot,
            events.TextMessage(
                id="1",
                uid="abc",
                name="a",
                message="!guild",
            ),
            cast(Match[Any], re.match(MESSAGE_REGEX, "!guild")),
        )
