import datetime
import logging
import typing

import requests
import ts3

from ts3bot import InvalidKeyException, RateLimitException, sync_groups
from ts3bot.bot import Bot
from ts3bot.database import models

MESSAGE_REGEX = "!guild *([\\w ]+)?"
USAGE = "!guild [Guild Tag]"


def handle(bot: Bot, event: ts3.response.TS3Event, match: typing.Match):
    cluid = event[0]["invokeruid"]
    cldbid = bot.exec_("clientgetdbidfromuid", cluid=event[0]["invokeruid"])[0][
        "cldbid"
    ]

    # Grab user's account
    account = models.Account.get_by_guid(bot.session, cluid)

    if not account or not account.is_valid:
        bot.send_message(event[0]["invokerid"], "missing_token")
        return

    # Saved account is older than one day or has no guilds
    if (
        datetime.datetime.today() - account.last_check
    ).days >= 1 or account.guilds.count() == 0:
        bot.send_message(event[0]["invokerid"], "account_updating")

        try:
            account.update(bot.session)

            # Sync groups in case the user has left a guild or similar changes
            sync_groups(bot, cldbid, account)
        except InvalidKeyException:
            # Invalidate link
            account.invalidate(bot.session)
            sync_groups(bot, cldbid, account, remove_all=True)

            logging.info("Revoked user's permissions.")
            bot.send_message(event[0]["invokerid"], "invalid_token_admin")
            return
        except (requests.RequestException, RateLimitException):
            logging.exception("Error during API call")
            bot.send_message(event[0]["invokerid"], "error_api")

    # User requested guild removal
    if match.group(1) and match.group(1).lower() == "remove":
        # Remove guilds
        account.guilds.filter(models.LinkAccountGuild.is_active.is_(True)).update(
            {"is_active": False}
        )
        bot.session.commit()

        # Sync groups
        changes = sync_groups(bot, cldbid, account)
        if len(changes["removed"]) > 0:
            bot.send_message(event[0]["invokerid"], "guild_removed")
        else:
            bot.send_message(event[0]["invokerid"], "guild_error")

        return

    available_guilds = account.guilds.join(models.Guild).filter(
        models.Guild.group_id.isnot(None)
    )

    # No guild specified
    if not match.group(1):
        available_guilds = available_guilds.all()
        if len(available_guilds) > 0:
            bot.send_message(
                event[0]["invokerid"],
                "guild_selection",
                guilds="\n- ".join([_.guild.tag for _ in available_guilds]),
            )
        else:
            bot.send_message(event[0]["invokerid"], "guild_unknown")
    else:
        guild = match.group(1).lower()

        selected_guild: typing.Optional[
            models.LinkAccountGuild
        ] = available_guilds.filter(models.Guild.tag.ilike(guild)).one_or_none()

        # Guild not found or user not in guild
        if not selected_guild:
            bot.send_message(event[0]["invokerid"], "guild_invalid_selection")
            return

        # Remove other guilds
        account.guilds.update({"is_active": False})

        # Assign guild
        selected_guild.is_active = True
        bot.session.commit()

        # Sync groups
        changes = sync_groups(bot, cldbid, account)
        if len(changes["added"]) > 0:
            bot.send_message(
                event[0]["invokerid"],
                "guild_set",
                guild=selected_guild.guild.name
            )
        else:
            bot.send_message(event[0]["invokerid"], "guild_error")
