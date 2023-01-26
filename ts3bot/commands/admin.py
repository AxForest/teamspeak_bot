import argparse
import binascii
import logging
from io import BytesIO
from typing import Match, Optional, cast

import requests
import ts3  # type: ignore
from sqlalchemy import func
from sqlalchemy.exc import MultipleResultsFound
from ts3.filetransfer import TS3FileTransfer, TS3FileTransferError  # type: ignore
from ts3.query import TS3ServerConnection  # type: ignore

import ts3bot
from ts3bot import cmdparse, events
from ts3bot.bot import Bot
from ts3bot.config import env
from ts3bot.database import enums, models

MESSAGE_REGEX = "!admin\\s* *(\\w+)?"
USAGE = "!admin <link (create|add|remove) <world_id>, guild (add|update|remove) <name>>"


class Parser(cmdparse.ArgParse):
    def init(self) -> None:
        """Initialises the argparser and all subparsers"""

        subs = self.add_subparsers(dest="cmd")
        subs.add_parser("help")

        link = subs.add_parser("link")
        link_choice = link.add_subparsers(dest="choice", required=False)

        link_create = link_choice.add_parser("create")
        link_create.add_argument(
            "world_id", type=enums.World, action=cmdparse.EnumAction
        )
        link_create.add_argument("group_id", type=int)

        link_add = link_choice.add_parser("add")
        link_add.add_argument("world_id", type=enums.World, action=cmdparse.EnumAction)

        link_rm = link_choice.add_parser("remove", aliases=["rm"])
        link_rm.add_argument("world_id", type=enums.World, action=cmdparse.EnumAction)

        guild = subs.add_parser("guild")
        guild_choice = guild.add_subparsers(dest="choice", required=True)

        guild_add = guild_choice.add_parser("add")
        guild_add.add_argument("name", type=str, nargs="+")

        guild_add = guild_choice.add_parser("update")
        guild_add.add_argument("name", type=str, nargs="+")

        guild_add = guild_choice.add_parser("remove")
        guild_add.add_argument("name", type=str, nargs="+")

    @property
    def usage_help(self) -> str:
        """Returns the usage string"""
        return (
            "\nRetrieve the current linking and world groups:"
            "\n\t!admin link"
            "\n"
            "\nRegister or update a world's TS3 group:"
            "\n\t!admin link create <world_id> <group_id>"
            "\n"
            "\nUpdate the current linking:"
            "\n\t!admin link add <world_id>"
            "\n\t!admin link remove <world_id>"
            "\n"
            "\nCreate a new guild group based on the configured permission template"
            "\n\t!admin guild add <name>"
            "\n"
            "\nUpdate a guild's name or logo"
            "\n\t!admin guild update <name>"
            "\n"
            "\nRemoves the guild group from the server"
            "\n\t!admin guild remove <name>"
        )


def handle(bot: Bot, event: events.TextMessage, _match: Match) -> None:
    if event.uid not in env.admin_whitelist:
        return

    parser = Parser(prog="!admin")
    parser.init()

    try:
        args = parser.parse_event(event)
    except cmdparse.WorldError:
        bot.send_message(event.id, "Invalid input for world_id.")
        return
    except (cmdparse.UsageError, argparse.ArgumentError) as e:
        bot.send_message(event.id, str(e))
        return

    if args.cmd in [None, "help"]:
        bot.send_message(event.id, parser.usage_help, is_translation=False)
        return

    if args.cmd == "link":
        _linking(bot, event, args)
    elif args.cmd == "guild":
        _guild(bot, event, args)


def _linking(bot: Bot, event: events.TextMessage, args: argparse.Namespace) -> None:
    """Creates a WorldGroup or sets the linking status on said group"""

    # Create or update the linking's TS3 group ID
    if args.choice == "create":
        _filter = cast(
            Optional[models.WorldGroup],
            bot.session.query(models.WorldGroup)
            .filter(models.WorldGroup.world == args.world_id)
            .one_or_none(),
        )

        # Check if server group exists
        try:
            bot.exec_("servergrouppermlist", sgid=args.group_id)
        except ts3.query.TS3QueryError:
            bot.send_message(
                event.id, "This guild group does not exist.", is_translation=False
            )
            return

        # Check if world ID is taken already
        if (
            wg_instance := cast(
                Optional[models.WorldGroup],
                bot.session.query(models.WorldGroup)
                .filter(models.WorldGroup.group_id == args.group_id)
                .one_or_none(),
            )
        ) is not None:
            bot.send_message(
                event.id,
                (
                    "This TS3 group ID is already taken "
                    f"by {wg_instance.world.proper_name}."
                ),
                is_translation=False,
            )
            return

        # Create new world group
        if _filter is None:
            bot.session.add(
                models.WorldGroup(group_id=args.group_id, world=args.world_id)
            )
            bot.session.commit()
        else:
            # Update world group
            _filter.group_id = args.group_id
            bot.session.commit()

        logging.info(
            "Created new WorldGroup for %s (%s) as requested by %s",
            args.world_id,
            args.group_id,
            event.uid,
        )
        bot.send_message(
            event.id,
            (
                "World group successfully updated/created for "
                f"{args.world_id.proper_name} ({args.group_id})."
            ),
        )

    # Add/remove a server to/from our linking
    elif args.choice in ["add", "remove", "rm"]:
        _filter = cast(
            Optional[models.WorldGroup],
            bot.session.query(models.WorldGroup)
            .filter(models.WorldGroup.world == args.world_id)
            .one_or_none(),
        )

        # No world group found
        if _filter is None:
            bot.send_message(
                event.id,
                f"Could not found a world group for {args.world_id.proper_name}.\n"
                f"Create it via !admin link create {args.world_id.value} <group_id>.",
                is_translation=False,
            )
            return

        # World is linked already, ignore add
        if _filter.is_linked and args.choice == "add":
            bot.send_message(
                event.id,
                f"{args.world_id.proper_name} is already set to linked.",
                is_translation=False,
            )
            return
        # World is not linked, ignore remove
        elif not _filter.is_linked and args.choice in ["remove", "rm"]:
            bot.send_message(
                event.id,
                f"{args.world_id.proper_name} is not set as linked.",
                is_translation=False,
            )
            return

        # Set world linking status
        _filter.is_linked = args.choice == "add"
        bot.session.commit()
        bot.send_message(
            event.id,
            f"{args.world_id.proper_name} was updated to linked = {_filter.is_linked}.",
        )
        logging.info(
            "Set WorldGroup for %s to linked=%s as requested by %s",
            args.world_id,
            _filter.is_linked,
            event.uid,
        )

    # Print currently linked worlds
    else:
        linked_worlds = (
            bot.session.query(models.WorldGroup)
            .filter(models.WorldGroup.is_linked.is_(True))
            .all()
        )
        unlinked_worlds = (
            bot.session.query(models.WorldGroup)
            .filter(models.WorldGroup.is_linked.is_(False))
            .all()
        )

        # Print linked worlds
        if len(linked_worlds) > 0:
            bot.send_message(
                event.id,
                "\nThe following worlds are set as linked:\n- "
                + "\n- ".join(
                    f"{x.world.proper_name} (id: {x.world.value}, group: {x.group_id})"
                    for x in linked_worlds
                ),
                is_translation=False,
            )
        else:
            bot.send_message(
                event.id,
                "There's no linked world set up currently",
                is_translation=False,
            )

        # Print other worlds
        if len(unlinked_worlds) > 0:
            bot.send_message(
                event.id,
                "\nThe following worlds are set up with a group ID:\n- "
                + "\n- ".join(
                    f"{x.world.proper_name} (id: {x.world.value}, group: {x.group_id})"
                    for x in unlinked_worlds
                ),
                is_translation=False,
            )
        elif len(unlinked_worlds) == 0 and len(linked_worlds) == 0:
            bot.send_message(
                event.id,
                "There are no world groups set up currently. Create one via "
                "!admin link create <world_id> <group_id>",
                is_translation=False,
            )


def _guild(bot: Bot, event: events.TextMessage, args: argparse.Namespace) -> None:
    guild_name = " ".join(args.name)

    try:
        guild = cast(
            Optional[models.Guild],
            bot.session.query(models.Guild)
            .filter(func.lower(models.Guild.name) == guild_name.lower())
            .one_or_none(),
        )
    except MultipleResultsFound:
        bot.send_message(
            event.id,
            "Found multiple guilds with that name, please yell at your database admin.",
            is_translation=False,
        )
        return

    # Nobody is registered with that guild
    if guild is None:
        bot.send_message(
            event.id,
            f"The guild {guild_name} does not exist in my database.",
            is_translation=False,
        )
        return

    # Check if guild group template is set
    if not env.guild_group_template:
        bot.send_message(
            event.id,
            (
                "The guild_group_template isn't set correctly "
                "in the guild section of the config."
            ),
            is_translation=False,
        )
        return

    # Add guild group
    if args.choice == "add":
        try:
            response = bot.exec_(
                "servergroupcopy",
                ssgid=env.guild_group_template,
                tsgid=0,
                name=guild.tag,
                type=1,
            )
        except ts3.query.TS3QueryError as e:
            # Probably duplicate entry
            if e.args[0].error["id"] == "1282":
                bot.send_message(
                    event.id,
                    f"Guild group {guild.tag} already exists",
                    is_translation=False,
                )
            else:
                logging.exception("Failed to create new guild group")

            return

        new_group_id = response.parsed[0].get("sgid")
        if new_group_id is None:
            logging.critical(
                "Failed to parse sgid from servergroupcopy response: %s",
                response.parsed,
            )
            bot.send_message(
                event.id,
                "Creation of guild group failed, please delete it manually "
                "(if it exists) and try again",
                is_translation=False,
            )
            return

        guild.group_id = new_group_id
        bot.session.commit()

        logging.info(
            "Created new guild group %s (%s) for %s as requested by %s",
            guild.tag,
            guild.group_id,
            guild.name,
            event.uid,
        )

        bot.send_message(
            event.id, "Guild group has been created successfully.", is_translation=False
        )

        # Fetch and set guild emblem
        if (emblem := _download_emblem(guild.guid)) is not None and (
            icon_name := _upload_file(bot.ts3c, emblem, guild.guid)
        ) is not None:
            try:
                bot.exec_(
                    "servergroupaddperm",
                    sgid=new_group_id,
                    permsid="i_icon_id",
                    permvalue=icon_name,
                    permnegated=0,
                    permskip=0,
                )
                bot.send_message(event.id, "Guild emblem was set as well.")
            except ts3.query.TS3QueryError:
                logging.exception("Failed to set guild icon.")
                bot.send_message(event.id, "Failed to set guild emblem.")

    # Update guild name/tag/emblem
    elif args.choice == "update":
        # No group ID, nothing to do here
        if guild.group_id is None:
            bot.send_message(
                event.id,
                "This guild has no TS3 group ID, was it added?",
                is_translation=False,
            )
            return

        # Store old name for later comparison
        old_tag = guild.tag

        # Update guild data
        try:
            guild.update(bot.session)
        except ts3bot.NotFoundError:
            bot.send_message(
                event.id,
                "The API is reporting that this guild vanished, please remove it.",
                is_translation=False,
            )
            return
        except (ts3bot.RateLimitError, requests.RequestException):
            logging.exception("Failed to retrieve guild data")
            bot.send_message(
                event.id, "Failed to retrieve guild data, try again later."
            )
            return

        # Fetch and set guild emblem
        if (emblem := _download_emblem(guild.guid)) is not None and (
            icon_name := _upload_file(bot.ts3c, emblem, guild.guid)
        ) is not None:
            try:
                bot.exec_(
                    "servergroupaddperm",
                    sgid=guild.group_id,
                    permsid="i_icon_id",
                    permvalue=icon_name,
                    permnegated=0,
                    permskip=0,
                )
                bot.send_message(
                    event.id, "Guild emblem was updated.", is_translation=False
                )
            except ts3.query.TS3QueryError:
                logging.exception("Failed to set guild icon.")
                bot.send_message(
                    event.id, "Failed to set guild emblem.", is_translation=False
                )

        if old_tag != guild.tag:
            try:
                bot.exec_("servergrouprename", sgid=guild.group_id, name=guild.tag)
            except ts3.query.TS3QueryError:
                logging.exception(
                    "Failed to rename guild %s to %s.", guild.group_id, guild.tag
                )
                bot.send_message(
                    event.id,
                    (
                        "Failed to rename guild group, please do so manually.\n"
                        f"Group {guild.group_id}: {guild.tag}"
                    ),
                    is_translation=False,
                )
                return

            bot.send_message(
                event.id,
                f"Updated guild group {guild.group_id} to {guild.tag} successfully.",
                is_translation=False,
            )
        else:
            bot.send_message(
                event.id,
                "The guild's name hasn't changed, nothing else to do here.",
                is_translation=False,
            )

    # Remove guild group
    elif args.choice == "remove":
        try:
            bot.exec_("servergroupdel", sgid=guild.group_id, force=1)
        except ts3.query.TS3QueryError as e:
            if e.args[0].error["id"] == "2560":
                bot.send_message(
                    event.id,
                    "Server group was already removed, deleting link in database.",
                    is_translation=False,
                )
            else:
                logging.exception("Failed to remove server group.")
                bot.send_message(
                    event.id, "Failed to remove server group.", is_translation=False
                )
                return

        bot.send_message(
            event.id, "Guild group has been removed and unlinked.", is_translation=False
        )

        guild.group_id = None
        bot.session.commit()

        logging.info(
            "Removed guild group of %s as requested by %s", guild.name, event.uid
        )


def _download_emblem(guild_id: str) -> BytesIO | None:
    """Downloads the guild emblem"""

    logging.debug("Fetching guild emblem of %s", guild_id)

    with requests.Session() as sess:
        response = sess.get(f"https://emblem.werdes.net/emblem/{guild_id}/64")

        # Request was unsuccessful
        if response.status_code != 200:  # noqa: PLR2004
            logging.warning(
                "Failed to download emblem for %s, response was %s",
                guild_id,
                response.status_code,
            )
            return None

        # Check for Emblem-Status header
        # https://github.com/werdes/Gw2_GuildEmblems/issues/2
        if response.headers.get("Emblem-Status") != "OK":
            logging.info("No emblem found or server-side error")
            return None

        return BytesIO(response.content)


def _upload_file(
    ts3c: TS3ServerConnection, icon_file: BytesIO, guild_id: str
) -> int | None:
    """Uploads an image file to the TS3 server, returning the file's hash"""

    icon_hash = binascii.crc32(guild_id.encode("utf-8"))
    icon_name = f"/icon_{icon_hash}"
    ft = TS3FileTransfer(ts3c)

    try:
        ft.init_upload(input_file=icon_file, name=icon_name, cid=0)
        return icon_hash
    except (TS3FileTransferError, NameError, KeyError):
        logging.exception("Failed to upload guild emblem to server.")

    return None
