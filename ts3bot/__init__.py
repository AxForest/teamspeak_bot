import logging.handlers
import os
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypedDict, cast

import requests
import ts3  # type: ignore
from pydantic.main import BaseModel
from sqlalchemy.orm import load_only

from ts3bot import bot as ts3_bot
from ts3bot import events
from ts3bot.config import Config
from ts3bot.database import models

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


class ApiErrBadData(Exception):
    pass


ServerGroup = TypedDict("ServerGroup", {"sgid": int, "name": str})
SyncGroupChanges = TypedDict(
    "SyncGroupChanges", {"removed": List[str], "added": List[str]}
)


def limit_fetch_api(
    endpoint: str,
    api_key: Optional[str] = None,
    level: int = 0,
    exc: Exception = None,
) -> Dict:
    if level >= 3:
        if isinstance(exc, RateLimitException):
            raise RateLimitException("Encountered rate limit after waiting 3 times.")
        else:
            raise ApiErrBadData("Encountered ErrBadData even after retrying 3 times.")

    try:
        return fetch_api(endpoint, api_key)
    except ApiErrBadData as e:
        logging.warning("Got ErrBadData from API, retrying.")
        return limit_fetch_api(endpoint, api_key, level=level + 1, exc=e)
    except RateLimitException as e:
        logging.warning("Got rate-limited, waiting 1 minute.")
        time.sleep(60)
        return limit_fetch_api(endpoint, api_key, level=level + 1, exc=e)


def fetch_api(endpoint: str, api_key: Optional[str] = None) -> Dict[str, Any]:
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

    if response.status_code == 400 and "ErrBadData" in response.text:
        raise ApiErrBadData()

    if response.status_code == 200:
        return cast(Dict[str, Any], response.json())
    elif response.status_code == 404:
        raise NotFoundException()
    elif response.status_code == 429:  # Rate limit
        raise RateLimitException()

    logging.warning(response.text)
    logging.exception("Failed to fetch API")
    raise requests.RequestException()  # API down


def init_logger(name: str, is_test: bool = False) -> None:
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
        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.sqlalchemy import (
            SqlalchemyIntegration,
        )  # type: ignore

        def before_send(event: Any, hint: Any) -> Any:
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
            integrations=[SqlalchemyIntegration()],
        )


def timedelta_hours(td: timedelta) -> float:
    """
    Convert a timedelta to hours with up to two digits after comma.
    Microseconds are ignored.

    :param td: The timedelta
    :return: Hours as float
    """
    return round(td.days * 24 + td.seconds / 3600, 2)


def transfer_registration(
    bot: ts3_bot.Bot,
    account: models.Account,
    event: events.TextMessage,
    is_admin: bool = False,
    target_identity: Optional[models.Identity] = None,
    target_dbid: Optional[str] = None,
) -> None:
    """
    Transfers a registration and server/guild groups to the sender of the event or the target_guid
    :param bot: The current bot instance
    :param account: The account that should be re-registered for the target user
    :param event: The sender of the text message, usually the one who gets permissions
    :param is_admin: Whether the sender is an admin
    :param target_identity: To override the user who gets the permissions
    :param target_dbid: The target's database id, usually sourced from the event
    :return:
    """

    # Get identity from event if necessary
    if not target_identity:
        # TODO: Remove workaround once mypy gets its shit together https://github.com/python/mypy/pull/9956
        target_identity = cast(
            models.Identity, models.Identity.get_or_create(bot.session, event.uid)
        )

    # Get database id if necessary
    if not target_dbid:
        try:
            target_dbid = cast(
                str, bot.exec_("clientgetdbidfromuid", cluid=event.uid)[0]["cldbid"]
            )
        except ts3.TS3Error:
            # User might not exist in the db
            logging.exception("Failed to get database id from event's user")
            bot.send_message(event.id, "error_critical")
            return

    # Get current guild groups to save them for later use
    guild_groups = account.guild_groups()

    # Get previous identity
    previous_identity: Optional[
        models.LinkAccountIdentity
    ] = account.valid_identities.one_or_none()

    # Remove previous identities, also removes guild groups
    account.invalidate(bot.session)

    # Account is currently registered, sync groups with old identity
    if previous_identity:
        # Get cldbid and sync groups
        try:
            cldbid = bot.exec_(
                "clientgetdbidfromuid", cluid=previous_identity.identity.guid
            )[0]["cldbid"]

            result = sync_groups(bot, cldbid, account, remove_all=True)

            logging.info(
                "Removed previous links of %s as ignored during transfer to %s",
                account.name,
                target_identity.guid,
            )

            if is_admin:
                bot.send_message(
                    event.id, "groups_revoked", amount="1", groups=result["removed"]
                )
        except ts3.TS3Error:
            # User might not exist in the db
            logging.info("Failed to remove groups from user", exc_info=True)

    # Invalidate target identity's link, if it exists
    other_account = models.Account.get_by_identity(bot.session, target_identity.guid)
    if other_account:
        other_account.invalidate(bot.session)

    # Transfer roles to new identity
    bot.session.add(
        models.LinkAccountIdentity(account=account, identity=target_identity)
    )

    # Add guild group
    if guild_groups:
        bot.session.query(models.LinkAccountGuild).filter(
            models.LinkAccountGuild.id.in_([g.id for g in guild_groups])
        ).update({"is_active": True})

    bot.session.commit()

    # Sync group
    sync_groups(bot, target_dbid, account)

    logging.info("Transferred groups of %s to cldbid:%s", account.name, target_dbid)

    bot.send_message(
        event.id,
        "registration_transferred",
        account=account.name,
    )


def sync_groups(
    bot: ts3_bot.Bot,
    cldbid: str,
    account: Optional[models.Account],
    remove_all: bool = False,
    skip_whitelisted: bool = False,
) -> SyncGroupChanges:
    def _add_group(group: ServerGroup) -> bool:
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

        except ts3.TS3Error:
            # User most likely doesn't have the group
            logging.exception(
                "Failed to add cldbid:%s to group %s for some reason.",
                cldbid,
                group["name"],
            )
        return True

    def _remove_group(group: ServerGroup) -> bool:
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

    group_changes: SyncGroupChanges = {"removed": [], "added": []}

    # Get groups the user is allowed to have
    if account and account.is_valid and not remove_all:
        valid_guild_groups: List[models.LinkAccountGuild] = account.guild_groups()
        valid_world_group: Optional[models.WorldGroup] = account.world_group(
            bot.session
        )
    else:
        valid_guild_groups = []
        valid_world_group = None

    valid_guild_group_ids = cast(
        List[int], [g.guild.group_id for g in valid_guild_groups]
    )
    valid_guild_mapper = {g.guild.group_id: g for g in valid_guild_groups}

    # Get all valid groups
    world_groups: List[int] = [
        _.group_id
        for _ in bot.session.query(models.WorldGroup).options(
            load_only(models.WorldGroup.group_id)
        )
    ]
    guild_groups: List[int] = [
        _.group_id
        for _ in bot.session.query(models.Guild)
        .filter(models.Guild.group_id.isnot(None))
        .options(load_only(models.Guild.group_id))
    ]
    generic_world = ServerGroup(
        sgid=int(Config.get("teamspeak", "generic_world_id")),
        name="Generic World",
    )
    generic_guild = ServerGroup(
        sgid=int(Config.get("teamspeak", "generic_guild_id")), name="Generic Guild"
    )

    # Remove user from all other known invalid groups
    invalid_groups = []
    for server_group in server_groups:
        sgid = int(server_group["sgid"])
        # Skip known valid groups
        if (
            server_group["name"] == "Guest"
            or sgid == generic_world
            or sgid == generic_guild
            or (len(valid_guild_groups) > 0 and sgid in valid_guild_group_ids)
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
    if len(valid_guild_group_ids) == 0:
        for _group in Config.additional_guild_groups:
            for server_group in server_groups:
                if server_group["name"] == _group:
                    _remove_group(server_group)
                    break

    # User is missing generic guild
    if len(valid_guild_group_ids) > 0 and generic_guild["sgid"] not in server_group_ids:
        _add_group(generic_guild)

    # User has generic guild but shouldn't
    if len(valid_guild_group_ids) == 0 and generic_guild["sgid"] in server_group_ids:
        _remove_group(generic_guild)

    # Sync guild groups
    left_guilds = [
        gid
        for gid in server_group_ids
        if gid in guild_groups and gid not in valid_guild_group_ids
    ]  # Guilds that shouldn't be applied to the user
    joined_guilds = [
        gid for gid in valid_guild_group_ids if gid not in server_group_ids
    ]  # Guild that are missing in the user's group list

    # Remove guilds that should not be applied
    if len(guild_groups) > 0:
        for group_id in left_guilds:
            _remove_group(
                ServerGroup(sgid=group_id, name=valid_guild_mapper[group_id].guild.name)
            )

    # Join guilds
    if len(valid_guild_group_ids) > 0:
        for group_id in joined_guilds:
            _add_group(
                ServerGroup(sgid=group_id, name=valid_guild_mapper[group_id].guild.name)
            )

    # User is missing generic world
    if (
        valid_world_group
        and valid_world_group.is_linked
        and generic_world["sgid"] not in server_group_ids
        and len(valid_guild_group_ids) == 0
    ):
        _add_group(generic_world)

    # User has generic world but shouldn't
    if generic_world["sgid"] in server_group_ids and (
        not valid_world_group
        or not valid_world_group.is_linked
        or len(valid_guild_group_ids) > 0
    ):
        _remove_group(generic_world)

    # User is missing home world
    if valid_world_group and valid_world_group.group_id not in server_group_ids:
        _add_group(
            ServerGroup(
                sgid=valid_world_group.group_id,
                name=valid_world_group.world.proper_name,
            )
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
    def locale(self) -> Literal["de", "en"]:
        # TODO: Force locale
        if self.country in ["DE", "AT", "CH"]:
            return "de"
        return "en"
