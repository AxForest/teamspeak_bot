import logging.handlers
import os
import sys
import time
import typing
from datetime import timedelta
from pathlib import Path

import requests
import ts3
from pydantic.main import BaseModel
from sqlalchemy.orm import load_only

import ts3bot.bot
import ts3bot.database.models
from ts3bot.config import Config

try:
    # Init version number
    import pkg_resources

    VERSION = pkg_resources.get_distribution("ts3bot").version
except pkg_resources.DistributionNotFound:
    VERSION = "unknown"
# Global session
session = requests.Session()


class NotFoundException(Exception):
    pass


class RateLimitException(Exception):
    pass


class InvalidKeyException(Exception):
    pass


def limit_fetch_api(endpoint: str, api_key: typing.Optional[str] = None, level=0):
    if level >= 3:
        raise RateLimitException("Encountered rate limit after waiting multiple times")

    try:
        return fetch_api(endpoint, api_key)
    except ts3bot.RateLimitException:
        logging.warning("Got rate-limited, waiting 1 minute.")
        time.sleep(60)
        return limit_fetch_api(endpoint, api_key, level=level + 1)


def fetch_api(endpoint: str, api_key: typing.Optional[str] = None):
    """

    :param endpoint: The API (v2) endpoint to request
    :param api_key: Optional api key
    :return: Optional[dict]
    :raises InvalidKeyException An invalid API key was given
    :raises NotFoundException The endpoint was not found
    :raises RateLimitException Rate limit of 600/60s was hit, try again later
    :raises RequestException API on fire
    """
    session.headers.update(
        {
            "User-Agent": f"github/AxForest/teamspeak_bot@{VERSION}",
            "Accept": "application/json",
            "Accept-Language": "en",
            "X-Schema-Version": "2019-12-19T00:00:00.000Z",
        }
    )

    # Set API key
    if api_key:
        session.headers.update({"Authorization": f"Bearer {api_key}"})
    elif "authorization" in session.headers:
        del session.headers["authorization"]

    response = session.get(f"https://api.guildwars2.com/v2/{endpoint}")

    if (
        400 <= response.status_code < 500
        and api_key
        and ("Invalid" in response.text or "invalid" in response.text)
    ):  # Invalid API key
        raise InvalidKeyException()

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        raise NotFoundException()
    elif response.status_code == 429:  # Rate limit
        raise RateLimitException()

    logging.warning(response.text)
    logging.exception("Failed to fetch API")
    raise requests.RequestException()  # API down


def init_logger(name: str, is_test=False):
    if not Path("logs").exists():
        Path("logs").mkdir()

    logger = logging.getLogger()

    if os.environ.get("ENV", "") == "dev":
        level = logging.DEBUG
    else:
        level = logging.INFO

    logger.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    # Only write to file outside of tests
    if not is_test:
        hldr = logging.handlers.TimedRotatingFileHandler(
            "logs/{}.log".format(name), when="W0", encoding="utf-8", backupCount=16
        )

        hldr.setFormatter(fmt)
        logger.addHandler(hldr)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    stream.setLevel(level)
    logger.addHandler(stream)

    sentry_dsn = Config.get("sentry", "dsn")
    if sentry_dsn:
        import sentry_sdk

        def before_send(event, hint):
            if "exc_info" in hint:
                _, exc_value, _ = hint["exc_info"]
                if isinstance(exc_value, KeyboardInterrupt):
                    return None
            return event

        sentry_sdk.init(
            dsn=sentry_dsn,
            before_send=before_send,
            release=VERSION,
            send_default_pii=True,
        )


def timedelta_hours(td: timedelta) -> int:
    """
    Convert a timedelta to full hours, microseconds are ignored
    :param td: The timedelta
    :return: Hours as integer
    """
    return td.days * 24 + td.seconds // 3600


def sync_groups(
    bot: ts3bot.bot.Bot,
    cldbid: str,
    account: typing.Optional[ts3bot.database.models.Account],
    remove_all=False,
    skip_whitelisted=False,
) -> typing.Dict[str, list]:
    def sg_dict(_id, _name):
        return {"sgid": _id, "name": _name}

    def _add_group(group: typing.Dict):
        """
        Adds a user to a group if necessary, updates `server_group_ids`.

        :param group:
        :return:
        """

        if int(group["sgid"]) in server_group_ids:
            return False

        try:
            bot.exec_("servergroupaddclient", sgid=str(group["sgid"]), cldbid=cldbid)
            logging.info("Added user dbid:%s to group %s", cldbid, group["name"])
            server_group_ids.append(int(group["sgid"]))
            group_changes["added"].append(group["name"])
            return True
        except ts3.TS3Error:
            # User most likely doesn't have the group
            logging.exception(
                "Failed to add cldbid:%s to group %s for some reason.",
                cldbid,
                group["name"],
            )

    def _remove_group(group: typing.Dict):
        """
        Removes a user from a group if necessary, updates `server_group_ids`.

        :param group:
        :return:
        """
        if int(group["sgid"]) in server_group_ids:
            try:
                bot.exec_(
                    "servergroupdelclient", sgid=str(group["sgid"]), cldbid=cldbid
                )
                logging.info(
                    "Removed user dbid:%s from group %s", cldbid, group["name"]
                )
                server_group_ids.remove(int(group["sgid"]))
                group_changes["removed"].append(group["name"])
                return True
            except ts3.TS3Error:
                # User most likely doesn't have the group
                logging.exception(
                    "Failed to remove cldbid:%s from group %s for some reason.",
                    cldbid,
                    group["name"],
                )
        return False

    server_groups = bot.exec_("servergroupsbyclientid", cldbid=cldbid)
    server_group_ids = [int(_["sgid"]) for _ in server_groups]

    group_changes: typing.Dict[str, typing.List[str]] = {"removed": [], "added": []}

    # Get groups the user is allowed to have
    if account and account.is_valid and not remove_all:
        valid_guild_group: typing.Optional[
            ts3bot.database.models.LinkAccountGuild
        ] = account.guild_group()
        valid_world_group: typing.Optional[
            ts3bot.database.models.WorldGroup
        ] = account.world_group(bot.session)
    else:
        valid_guild_group = None
        valid_world_group = None

    # Get all valid groups
    world_groups: typing.List[int] = [
        _.group_id
        for _ in bot.session.query(ts3bot.database.models.WorldGroup).options(
            load_only(ts3bot.database.models.WorldGroup.group_id)
        )
    ]
    guild_groups: typing.List[int] = [
        _.group_id
        for _ in bot.session.query(ts3bot.database.models.Guild)
        .filter(ts3bot.database.models.Guild.group_id.isnot(None))
        .options(load_only(ts3bot.database.models.Guild.group_id))
    ]
    generic_world = {
        "sgid": int(Config.get("teamspeak", "generic_world_id")),
        "name": "Generic World",
    }
    generic_guild = {
        "sgid": int(Config.get("teamspeak", "generic_guild_id")),
        "name": "Generic Guild",
    }

    # Remove user from all other known invalid groups
    invalid_groups = []
    for server_group in server_groups:
        sgid = int(server_group["sgid"])
        # Skip known valid groups
        if (
            server_group["name"] == "Guest"
            or sgid == generic_world
            or sgid == generic_guild
            or (valid_guild_group and sgid == valid_guild_group.guild.group_id)
            or (valid_world_group and sgid == valid_world_group.group_id)
        ):
            continue

        # Skip users with whitelisted group
        if skip_whitelisted and server_group.get("name") in Config.whitelist_groups:
            logging.info(
                "Skipping cldbid:%s due to whitelisted group: %s",
                cldbid,
                server_group.get("name"),
            )
            return group_changes

        # Skip unknown groups
        if sgid not in guild_groups and sgid not in world_groups:
            continue

        invalid_groups.append(server_group)

    for server_group in invalid_groups:
        _remove_group(server_group)

    # User has additional guild groups but shouldn't
    if not valid_guild_group:
        for _group in Config.additional_guild_groups:
            for server_group in server_groups:
                if server_group["name"] == _group:
                    _remove_group(server_group)
                    break

    # User is missing generic guild
    if valid_guild_group and generic_guild["sgid"] not in server_group_ids:
        _add_group(generic_guild)

    # User has generic guild but shouldn't
    if generic_guild["sgid"] in server_group_ids and not valid_guild_group:
        _remove_group(generic_guild)

    # User is missing valid guild
    if valid_guild_group and valid_guild_group.guild.group_id not in server_group_ids:
        _add_group(
            sg_dict(valid_guild_group.guild.group_id, valid_guild_group.guild.name)
        )

    # User is missing generic world
    if (
        valid_world_group
        and valid_world_group.is_linked
        and generic_world["sgid"] not in server_group_ids
        and not valid_guild_group
    ):
        _add_group(generic_world)

    # User has generic world but shouldn't
    if generic_world["sgid"] in server_group_ids and (
        not valid_world_group or not valid_world_group.is_linked or valid_guild_group
    ):
        _remove_group(generic_world)

    # User is missing home world
    if valid_world_group and valid_world_group.group_id not in server_group_ids:
        _add_group(
            sg_dict(valid_world_group.group_id, valid_world_group.world.proper_name)
        )

    return group_changes


class User(BaseModel):
    id: int
    db_id: int
    unique_id: str
    nickname: str
    country: str
    total_connections: int

    @property
    def locale(self):
        # TODO: Force locale
        if self.country in ["DE", "AT", "CH"]:
            return "de"
        return "en"
