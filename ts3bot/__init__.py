import logging.handlers
import time
from datetime import timedelta
from typing import Any, Literal, TypedDict, cast

import requests
import ts3  # type: ignore
from pydantic.main import BaseModel
from sqlalchemy.orm import load_only

from ts3bot import bot as ts3_bot
from ts3bot import events
from ts3bot.database import models
from ts3bot.utils import VERSION, data_path

# Global session
session = requests.Session()


class NotFoundError(Exception):
    pass


class RateLimitError(Exception):
    pass


class InvalidKeyError(Exception):
    pass


class ApiErrBadDataError(Exception):
    pass


class ServerGroup(TypedDict):
    sgid: int
    name: str


class SyncGroupChanges(TypedDict):
    removed: list[str]
    added: list[str]


def limit_fetch_api(
    endpoint: str,
    api_key: str | None = None,
    level: int = 0,
    exc: Exception | None = None,
) -> dict:
    if level >= 3:
        if isinstance(exc, RateLimitError):
            raise RateLimitError("Encountered rate limit after waiting 3 times.")
        else:
            raise ApiErrBadDataError(
                "Encountered ErrBadData even after retrying 3 times."
            )

    try:
        return fetch_api(endpoint, api_key)
    except ApiErrBadDataError as e:
        logging.warning("Got ErrBadData from API, retrying.")
        return limit_fetch_api(endpoint, api_key, level=level + 1, exc=e)
    except RateLimitError as e:
        logging.warning("Got rate-limited, waiting 1 minute.")
        time.sleep(60)
        return limit_fetch_api(endpoint, api_key, level=level + 1, exc=e)


def fetch_api(endpoint: str, api_key: str | None = None) -> dict[str, Any]:
    """

    :param endpoint: The API (v2) endpoint to request
    :param api_key: Optional api key
    :return: Optional[dict]
    :raises InvalidKeyError An invalid API key was given
    :raises NotFoundError The endpoint was not found
    :raises RateLimitError Rate limit of 600/60s was hit, try again later
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
        raise InvalidKeyError()

    if response.status_code == 400 and "ErrBadData" in response.text:
        raise ApiErrBadDataError()

    if response.status_code == 200:
        return cast(dict[str, Any], response.json())
    elif response.status_code == 404:
        raise NotFoundError()
    elif response.status_code == 429:  # Rate limit
        raise RateLimitError()

    logging.warning(response.text)
    logging.exception("Failed to fetch API")
    raise requests.RequestException()  # API down


def timedelta_hours(td: timedelta) -> float:
    """
    Convert a timedelta to hours with up to two digits after comma.
    Microseconds are ignored.

    :param td: The timedelta
    :return: Hours as float
    """
    return round(td.days * 24 + td.seconds / 3600, 2)


def transfer_registration(  # noqa: PLR0913
    bot: ts3_bot.Bot,
    account: models.Account,
    event: events.TextMessage,
    is_admin: bool = False,
    target_identity: models.Identity | None = None,
    target_dbid: str | None = None,
) -> None:
    """
    Transfers a registration and server/guild groups to the sender of the event or
              the target_guid
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
        target_identity = models.Identity.get_or_create(bot.session, event.uid)

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
    previous_identity: models.LinkAccountIdentity | None = (
        account.valid_identities.one_or_none()
    )

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


def set_client_description(bot: ts3_bot.Bot, clid: str, description: str) -> None:
    """
    Updates client's description to whatever text is specified (limited to 200
    characters)
    """

    try:
        bot.exec_("clientedit", clid=clid, client_description=description[:200])
        logging.info("Set client description of %s to %s", clid, description)
    except ts3.TS3Error:
        # We most likely lack the permission to do that
        logging.exception(
            "Failed to set client_description of %s.",
            clid,
        )


def sync_groups(  # noqa: PLR0912, PLR0915
    bot: ts3_bot.Bot,
    cldbid: str,
    account: models.Account | None,
    remove_all: bool = False,
    skip_whitelisted: bool = False,
) -> SyncGroupChanges:
    from ts3bot.config import env

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
        valid_guild_groups: list[models.LinkAccountGuild] = account.guild_groups()
        valid_world_group: models.WorldGroup | None = account.world_group(bot.session)
    else:
        valid_guild_groups = []
        valid_world_group = None

    valid_guild_group_ids = cast(
        list[int], [g.guild.group_id for g in valid_guild_groups]
    )
    valid_guild_mapper = {g.guild.group_id: g for g in valid_guild_groups}

    # Get all valid groups
    world_groups: list[int] = [
        _.group_id
        for _ in bot.session.query(models.WorldGroup).options(
            load_only(models.WorldGroup.group_id)
        )
    ]
    guild_groups: list[int] = [
        _.group_id
        for _ in bot.session.query(models.Guild)
        .filter(models.Guild.group_id.isnot(None))
        .options(load_only(models.Guild.group_id))
    ]
    generic_world = ServerGroup(sgid=env.generic_world_id, name="Generic World")
    generic_guild = ServerGroup(sgid=env.generic_guild_id, name="Generic Guild")

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
        if (
            skip_whitelisted
            and server_group.get("name") in env.join_verification_ignore
        ):
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
        for _group in env.additional_guild_groups:
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
        if self.country in ["DE", "AT", "CH"]:
            return "de"
        return "en"
