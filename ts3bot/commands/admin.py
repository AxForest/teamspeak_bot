import argparse
import binascii
import logging
from io import BytesIO
from typing import cast, Match, Optional

import requests
import ts3  # type: ignore
from sqlalchemy import func
from sqlalchemy.exc import MultipleResultsFound  # type: ignore
from ts3.filetransfer import TS3FileTransfer, TS3FileTransferError  # type: ignore
from ts3.query import TS3ServerConnection  # type: ignore

import ts3bot
from ts3bot import cmdparse, events
from ts3bot.bot import Bot
from ts3bot.config import env
from ts3bot.database import models

MESSAGE_REGEX = "!admin\\s* *(\\w+)?"
USAGE = "!admin guild (add|update|remove) <name>"


class Parser(cmdparse.ArgParse):
    def init(self) -> None:
        """Initialises the argparser and all subparsers"""

        subs = self.add_subparsers(dest="cmd")
        subs.add_parser("help")

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

    if args.cmd == "guild":
        _guild(bot, event, args)


def _guild(bot: Bot, event: events.TextMessage, args: argparse.Namespace) -> None:
    guild_name = " ".join(args.name)

    # TODO: Setup way of adding guilds into the alliance

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
            "The guild_group_template isn't set correctly in the guild section of the config.",
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
        except ts3bot.NotFoundException:
            bot.send_message(
                event.id,
                "The API is reporting that this guild vanished, please remove it.",
                is_translation=False,
            )
            return
        except (ts3bot.RateLimitException, requests.RequestException):
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
                    f"Failed to rename guild group, please do so manually.\nGroup {guild.group_id}: {guild.tag}",
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
                f"The guild's name hasn't changed, nothing else to do here.",
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


def _download_emblem(guild_id: str) -> Optional[BytesIO]:
    """Downloads the guild emblem"""

    logging.debug("Fetching guild emblem of %s", guild_id)

    with requests.Session() as sess:
        response = sess.get(f"https://emblem.werdes.net/emblem/{guild_id}/64")

        # Request was unsuccessful
        if response.status_code != 200:
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
) -> Optional[int]:
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
