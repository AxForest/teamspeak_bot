import configparser
import logging
from typing import cast, Dict, List

from ts3bot.utils import data_path

FILE_PATH = data_path("config.ini")

# TODO: Switch to pydantic.BaseSettings


class Config:
    config: configparser.RawConfigParser
    additional_guild_groups: List[str]
    whitelist_admin: List[str]
    whitelist_group_list: List[str]
    whitelist_groups: List[str]

    @staticmethod
    def get(section: str, option: str) -> str:
        return Config.config.get(section, option)

    @staticmethod
    def getint(section: str, option: str) -> int:
        return int(Config.config.get(section, option))

    @staticmethod
    def getfloat(section: str, option: str) -> float:
        return float(Config.config.get(section, option))

    @staticmethod
    def has_option(section: str, option: str) -> bool:
        return Config.config.has_option(section, option)

    @staticmethod
    def getboolean(section: str, option: str) -> bool:
        return Config.config.getboolean(section, option)

    # noinspection PyTypeChecker
    @staticmethod
    def _create() -> configparser.RawConfigParser:
        config = configparser.RawConfigParser(allow_no_value=True)

        # Don't convert values to lowercase
        config.optionxform = lambda o: o  # type: ignore

        # The casts are fun workarounds for invalid typings.
        config["sentry"] = {"dsn": ""}
        config["database"] = {"uri": f"sqlite:///{str(data_path('db.sqlite3'))}"}
        config["teamspeak"] = cast(
            Dict[str, str],
            {
                "# The API bot's default TS3 channel": None,
                "channel_id": 1,
                "# The virtual server": None,
                "server_id": 2,
                "# Connection details": None,
                "hostname": "localhost:10011",
                "protocol": "telnet",
                "# Channel for the reset sheet": None,
                "sheet_channel_id": 97,
                "# Generic world group (holds the permissions)": None,
                "generic_world_id": 99,
                "# Generic guild group": None,
                "generic_guild_id": 98,
                "# How many times users should be told to register on connect": None,
                "annoy_total_connections": 5,
                "# Whether to put account name in the client description": None,
                "set_client_description_to_ign": False,
            },
        )
        config["bot_login"] = cast(
            Dict[str, str],
            {
                "# User account for regular bot": None,
                "nickname": "Hallo_Welt",
                "username": "API-Bot",
                "password": "abc",
            },
        )
        config["cycle_login"] = cast(
            Dict[str, str],
            {
                "# User account for re-verification": None,
                "nickname": "Cycle",
                "username": "Cycle",
                "password": "abc",
            },
        )
        config["commands"] = cast(
            Dict[str, str],
            {
                "# Enable/disable commands here": None,
                "api_key": True,
                "admin": True,
                "guild": True,
                "ignore": True,
                "info": True,
                "list_group_members": True,
                "register": True,
                "sheet": True,
                "verify": True,
            },
        )
        config["additional_guild_groups"] = cast(
            Dict[str, str],
            {
                "# Groups which be removed when guild is changed": None,
                "Gilden-Leader": None,
                "Gilden-Officer": None,
            },
        )
        config["whitelist_admin"] = cast(
            Dict[str, str],
            {
                "# List of admins/mods, can use !help/!ignore etc": None,
                "# Separated by comma, spaces will be ignored": None,
                "uids": "V2h5IGhlbGxvIHRoZXJlIQ==, R28gc2V0IHlvdXIgYWRtaW4gdWlkcyBoZXJl",
            },
        )
        config["whitelist_group_list"] = cast(
            Dict[str, str],
            {
                "# List of groups who are able to use !list": None,
                "Gilden-Admin": None,
            },
        )
        config["whitelist_groups"] = cast(
            Dict[str, str],
            {
                "# List of groups whose members should be ignored during join verification": None,
                "Guest": None,
            },
        )
        config["verify"] = cast(
            Dict[str, str],
            {
                "# How long users should not be checked again in cycle and on join": None,
                "cycle_hours": 48,
                "on_join_hours": 24,
            },
        )
        config["guild"] = cast(
            Dict[str, str],
            {
                "# Whether to allow multiple guilds on a user": None,
                "allow_multiple_guilds": True,
                "# Assign guild tags automatically on register, only available if allow_multiple_guilds is enabled": None,
                "assign_on_register": True,
                "# Guild group template ID, used for creation of new guild groups": None,
                "guild_group_template": None,
            },
        )

        return config

    @staticmethod
    def load(is_test: bool = False) -> None:
        if is_test:
            config = Config._create()
        else:
            if not FILE_PATH.exists():
                config = Config._create()
                # Write config
                with FILE_PATH.open("w") as f:
                    config.write(f)

                logging.info("Config was initialized, please edit it.")
                exit(0)
            else:
                # Read config, will use defaults if value is not found
                config = Config._create()
                config.read(FILE_PATH)

                # Clean up items and remove comments
                for section in config.sections():
                    for item_key, _ in config.items(section):
                        if item_key.startswith("#") or item_key.startswith(";"):
                            config.remove_option(section, item_key)

        Config.config = config
        Config.additional_guild_groups = [
            _[0].strip() for _ in config.items("additional_guild_groups")
        ]
        Config.whitelist_admin = [
            _.strip() for _ in config.get("whitelist_admin", "uids").split(",")
        ]
        Config.whitelist_group_list = [
            _[0].strip() for _ in config.items("whitelist_group_list")
        ]
        Config.whitelist_groups = [
            _[0].strip() for _ in config.items("whitelist_groups")
        ]
