import re
from typing import Any, Literal, Optional, TYPE_CHECKING

import pydantic

if TYPE_CHECKING:
    from pydantic.typing import CallableGenerator


class _TS3Address(str):
    """
    Partial UK postcode validation. Note: this is just an example, and is not
    intended for use in production; in particular this does NOT guarantee
    a postcode exists, just that it has a valid format.
    """

    @classmethod
    def __get_validators__(cls) -> "CallableGenerator":
        yield cls.validate

    @classmethod
    def validate(cls, v: Any) -> "_TS3Address":
        if not isinstance(v, str):
            raise TypeError("String required")

        # Only do dumb validation with one expected colon and a port
        m = re.fullmatch(r"^[\w\d.]+:\d+$", v)
        if not m:
            raise ValueError(
                "Invalid format, expected a domain/IP and a port separated by a colon."
            )

        return cls(v)

    def __repr__(self) -> str:
        return f"TS3Address({super().__repr__()})"


class Environment(pydantic.BaseSettings):
    class Config:
        env_file = "ts3bot.env"
        env_file_encoding = "utf-8"

        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str) -> Any:
            if field_name in [
                "commands",
                "additional_guild_groups",
                "admin_whitelist",
                "list_whitelist",
                "join_verification_ignore",
            ]:
                if raw_val in ["", None]:
                    return []
                return [v.strip() for v in raw_val.split(",") if v.strip()]

            return cls.json_loads(raw_val)  # type: ignore

    sentry_dsn: Optional[str] = None
    database_uri: str

    # Teamspeak connection settings
    # Default channel, joined automatically
    channel_id: int
    server_id: int
    host: _TS3Address
    protocol: Literal["telnet", "ssh"] = "telnet"

    # Channel for the reset sheet
    sheet_channel_id: Optional[int]

    # Generic World/Guild groups
    generic_world_id: int
    generic_guild_id: int

    # Amount of times users should be told to register on connect
    annoy_total_connections: int = 5

    # Whether to put account name in the client description
    set_client_description_to_ign: bool = False

    # Normal bot credentials
    bot_nickname: str
    bot_username: str
    bot_password: str

    # Verfication cronjob credentials
    cycle_nickname: Optional[str]
    cycle_username: Optional[str]
    cycle_password: Optional[str]

    # List of commands that should be loaded
    commands: list[str] = [
        "api_key",
        "admin",
        "guild",
        "ignore",
        "info",
        "list_group_members",
        "register",
        "sheet",
        "verify",
    ]

    # List of groups that should be removed when the guild group is changed by the user
    additional_guild_groups: list[str] = []

    # List of admins that are able to use !help/!ignore etc
    admin_whitelist: list[str] = []

    # List of user groups that are able to use !list
    list_whitelist: list[str] = []

    # List of groups whose member should be ignored during join verification
    join_verification_ignore: list[str] = ["Guest"]

    # How long users should not be checked again in the cronjob or on join
    cycle_hours: float = 48
    on_join_hours: float = 24

    # Allow users to have multiple guilds
    allow_multiple_guilds: bool = False
    # Assign guild tags automatically on register, requires allow_multiple_guilds
    assign_guild_on_register: bool = False

    # Guild group template for !admin guild add
    guild_group_template: Optional[int]

    # Invalid API retry amount
    retry_invalid_api_key: int = 5


env = Environment()
