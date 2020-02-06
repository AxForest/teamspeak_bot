import configparser
from pathlib import Path

FILE_PATH = (Path(".") / "config.ini").absolute()


class Config:
    config: configparser.ConfigParser
    whitelist_cycle: list

    @staticmethod
    def get(section, option):
        return Config.config.get(section, option)

    @staticmethod
    def has_option(section, option):
        return Config.config.has_option(section, option)

    @staticmethod
    def getboolean(section, option):
        return Config.config.getboolean(section, option)

    @staticmethod
    def _create():
        config = configparser.RawConfigParser(allow_no_value=True)

        # Don't convert values to lowercase
        config.optionxform = lambda o: o

        config["sentry"] = {"dsn": ""}
        config["database"] = {"uri": "sqlite:///db.sqlite3"}
        config["teamspeak"] = {
            "# The API bot's default TS3 channel": None,
            "channel_id": 1,
            "# The virtual server": None,
            "server_id": 2,
            "# Connection details": None,
            "hostname": "localhost:10011",
            "protocol": "telnet",
            "# Channel for the reset sheet": None,
            "sheet_channel_id": 0,
        }
        config["bot_login"] = {
            "# User account for regular bot": None,
            "nickname": "Hallo_Welt",
            "username": "API-Bot",
            "password": "abc",
        }
        config["cycle_login"] = {
            "# User account for re-verification": None,
            "nickname": "Cycle",
            "username": "Cycle",
            "password": "abc",
        }
        config["commands"] = {
            "# Enable/disable commands here": None,
            "guild": True,
            "ignore": True,
            "info": True,
            "list_group_members": True,
            "sheet": True,
            "verify": True,
        }
        config["whitelist_admins"] = {
            "# List of admins/mods, can use !help/!ignore etc": None,
            "V2h5IGhlbGxvIHRoZXJlIQ==": None,
            "R28gc2V0IHlvdXIgYWRtaW4gdWlkcyBoZXJl": None,
        }
        config["whitelist_group_list"] = {
            "# List of groups who are able to use !list": None,
            "Gilden-Admin": None,
        }
        config["whitelist_cycle"] = {
            "# Groups that won't be removed by cycle": None,
            "Server-Admin": None,
        }
        config["legacy"] = {
            "# Which group to assign to unknown users": None,
            "group_id": 13,
            "enabled": False,
        }

        return config

    @staticmethod
    def load():
        if not FILE_PATH.exists():
            config = Config._create()
            # Write config
            with FILE_PATH.open("w") as f:
                config.write(f)
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
        Config.whitelist_cycle = [_[0] for _ in config.items("whitelist_cycle")]
