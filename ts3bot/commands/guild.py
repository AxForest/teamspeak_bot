import datetime
import logging
from re import Match
from typing import cast

import requests
from sqlalchemy.orm.dynamic import AppenderQuery

from ts3bot import (
    ApiErrBadDataError,
    InvalidKeyError,
    RateLimitError,
    events,
    sync_groups,
    timedelta_hours,
)
from ts3bot.bot import Bot
from ts3bot.config import env
from ts3bot.database import models

MESSAGE_REGEX = "!guild *([\\w ]+)?"
USAGE = "!guild [Guild Tag]"


def handle(  # noqa: PLR0912,PLR0915
    bot: Bot, event: events.TextMessage, match: Match
) -> None:
    cldbid = bot.exec_("clientgetdbidfromuid", cluid=event.uid)[0]["cldbid"]

    # Grab user's account
    account = models.Account.get_by_identity(bot.session, event.uid)

    if not account or not account.is_valid:
        bot.send_message(event.id, "missing_token")
        return

    # Saved account is older than x hours or has no guilds
    if (
        timedelta_hours(datetime.datetime.today() - account.last_check)
        >= env.on_join_hours
        or cast(AppenderQuery, account.guilds).count() == 0
    ):
        bot.send_message(event.id, "account_updating")

        try:
            account.update(bot.session)

            # Sync groups in case the user has left a guild or similar changes
            sync_groups(bot, cldbid, account)
        except InvalidKeyError:
            # Invalidate link
            account.invalidate(bot.session)
            sync_groups(bot, cldbid, account, remove_all=True)

            logging.info("Revoked user's permissions.")
            bot.send_message(event.id, "invalid_token_admin")
            return
        except (requests.RequestException, RateLimitError, ApiErrBadDataError):
            logging.exception("Error during API call")
            bot.send_message(event.id, "error_api")

    # User requested guild removal
    if match.group(1) and match.group(1).lower() == "remove":
        # Get active guilds
        has_active_guilds: int = (
            cast(AppenderQuery, account.guilds)
            .join(models.Guild)
            .filter(models.Guild.group_id.isnot(None))
            .filter(models.LinkAccountGuild.is_active.is_(True))
            .count()
        )

        # There are no active guilds, no need to remove anything
        if not has_active_guilds:
            bot.send_message(event.id, "guild_already_removed")
            return

        # Remove guilds
        cast(AppenderQuery, account.guilds).filter(
            models.LinkAccountGuild.is_active.is_(True)
        ).update({"is_active": False})
        bot.session.commit()

        # Sync groups
        changes = sync_groups(bot, cldbid, account)
        if len(changes["removed"]) > 0:
            bot.send_message(event.id, "guild_removed")
        else:
            bot.send_message(event.id, "guild_error")

        return

    available_guilds = (
        cast(AppenderQuery, account.guilds)
        .join(models.Guild)
        .filter(models.Guild.group_id.isnot(None))
    )

    # No guild specified
    if not match.group(1):
        available_guilds = available_guilds.all()
        if len(available_guilds) > 0:
            bot.send_message(
                event.id,
                "guild_selection",
                guilds="\n- ".join([_.guild.tag for _ in available_guilds]),
            )
        else:
            bot.send_message(event.id, "guild_unknown")
    else:
        guild = match.group(1).lower()

        selected_guild: models.LinkAccountGuild | None = available_guilds.filter(
            models.Guild.tag.ilike(guild)
        ).one_or_none()

        # Guild not found or user not in guild
        if not selected_guild:
            bot.send_message(
                event.id, "guild_invalid_selection", timeout=env.on_join_hours
            )
            return

        # Toggle guild
        if selected_guild.is_active:
            selected_guild.is_active = False
        else:
            selected_guild.is_active = True

            # Remove other guilds if only one is allowed
            if not env.allow_multiple_guilds:
                cast(AppenderQuery, account.guilds).filter(
                    models.LinkAccountGuild.id != selected_guild.id
                ).update({"is_active": False})

        bot.session.commit()

        # Sync groups
        changes = sync_groups(bot, cldbid, account)
        if selected_guild.is_active and len(changes["added"]):
            bot.send_message(event.id, "guild_set", guild=selected_guild.guild.name)
        elif not selected_guild.is_active and len(changes["removed"]):
            bot.send_message(
                event.id, "guild_removed_one", guild=selected_guild.guild.name
            )
        else:
            bot.send_message(event.id, "guild_error")
