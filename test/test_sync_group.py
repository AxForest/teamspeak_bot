import datetime

from ._base import BaseTest  # type: ignore
from ._base import MOCK_RESPONSES, sample_data

from ts3bot import sync_groups, User
from ts3bot.config import env
from ts3bot.database import enums, models


class CommonTest(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        # Add account
        self.account = models.Account(
            name="User.1234",
            world=enums.World.KODASH,
            api_key=sample_data.API_KEY_VALID,
            last_check=datetime.datetime(2020, 1, 1, 0, 0, 0, 0),
        )
        self.session.add(self.account)
        # Add guild
        guild = models.Guild(
            guid="4BBB52AA-D768-4FC6-8EDE-C299F2822F0F",
            name="Arenanet",
            tag="Arenanet",
            group_id=100,
        )
        self.session.add(
            models.Guild(
                guid="4BBB52AA-0000-0000-0000-C299F2822F0F",
                name="BS",
                tag="BS",
                group_id=101,
            )
        )
        self.session.add(guild)
        self.session.commit()

        # Link identity to account
        identity = models.Identity(guid="abc")
        self.session.add(identity)
        self.session.add(
            models.LinkAccountIdentity(account=self.account, identity=identity)
        )

        # Link account to guild
        self.session.add(models.LinkAccountGuild(account=self.account, guild=guild))

        self.session.commit()

    def test_User(self) -> None:
        common_init = {
            "id": 1,
            "db_id": 1,
            "unique_id": "abc",
            "nickname": "User",
            "total_connections": 1,
        }
        user_de = User(country="DE", **common_init)
        self.assertEqual(user_de.locale, "de")

        self.assertEqual(
            repr(user_de),
            "User(id=1, db_id=1, unique_id='abc', nickname='User', country='DE', total_connections=1)",
        )

        user_other = User(country="FR", **common_init)
        self.assertEqual(user_other.locale, "en")

    def test_sync_missing_world(self) -> None:
        MOCK_RESPONSES["servergroupsbyclientid"] = [
            {"name": "Server-Admin", "sgid": "1"}
        ]
        sync_groups(self.bot, "1", self.account)
        self.assertEqual(
            list(self.mock_exec_calls.keys()),
            ["servergroupsbyclientid", "servergroupaddclient"],
        )
        self.assertEqual(len(self.mock_exec_calls["servergroupaddclient"]), 2)
        self.assertEqual(
            self.mock_exec_calls["servergroupaddclient"][0]["params"],
            {"sgid": str(env.generic_world_id), "cldbid": "1"},
        )
        self.assertEqual(
            self.mock_exec_calls["servergroupaddclient"][1]["params"],
            {"sgid": "2201", "cldbid": "1"},
        )

    def test_sync_invalid_guild(self) -> None:
        MOCK_RESPONSES["servergroupsbyclientid"] = [
            {"name": "Server-Admin", "sgid": "1"},
            {"name": "BS", "sgid": "101"},
        ]
        sync_groups(self.bot, "1", self.account)
        self.assertEqual(
            list(self.mock_exec_calls.keys()),
            ["servergroupsbyclientid", "servergroupdelclient", "servergroupaddclient"],
        )

        self.assertEqual(len(self.mock_exec_calls["servergroupdelclient"]), 1)
        self.assertEqual(
            self.mock_exec_calls["servergroupdelclient"][0]["params"],
            {"sgid": "101", "cldbid": "1"},
        )

        self.assertEqual(len(self.mock_exec_calls["servergroupaddclient"]), 2)
        self.assertEqual(
            self.mock_exec_calls["servergroupaddclient"][1]["params"],
            {"sgid": "2201", "cldbid": "1"},
        )
        self.assertEqual(
            self.mock_exec_calls["servergroupaddclient"][0]["params"],
            {"sgid": str(env.generic_world_id), "cldbid": "1"},
        )

    def test_sync_invalid_world(self) -> None:
        account = models.Account(
            name="User.4321",
            world=enums.World.ANVIL_ROCK,
            api_key=sample_data.API_KEY_INVALID_WORLD,
            last_check=datetime.datetime(2020, 1, 1, 0, 0, 0, 0),
        )
        self.session.add(models.WorldGroup(group_id=1001, world=enums.World(1001)))
        self.session.add(account)
        self.session.commit()

        MOCK_RESPONSES["servergroupsbyclientid"] = [
            {
                "name": "Generic World",
                "sgid": str(env.generic_world_id),
            },
            {"name": "Kodash", "sgid": "2201"},
        ]

        sync_groups(self.bot, "1", account)

        # Guild groups should've been removed
        self.assertEqual(len(self.mock_exec_calls["servergroupdelclient"]), 2)
        self.assertEqual(
            self.mock_exec_calls["servergroupdelclient"][0]["params"],
            {"sgid": "2201", "cldbid": "1"},
        )
        self.assertEqual(
            self.mock_exec_calls["servergroupdelclient"][1]["params"],
            {"sgid": str(env.generic_world_id), "cldbid": "1"},
        )

        # World group should've been added
        self.assertEqual(len(self.mock_exec_calls["servergroupaddclient"]), 1)
        self.assertEqual(
            self.mock_exec_calls["servergroupaddclient"][0]["params"],
            {"sgid": "1001", "cldbid": "1"},
        )
