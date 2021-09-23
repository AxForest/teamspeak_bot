import datetime
import logging
from typing import Match, Optional, cast

import ts3  # type: ignore
from requests import RequestException
from sqlalchemy.orm.dynamic import AppenderQuery

import ts3bot
from ts3bot import (
    ApiErrBadData,
    Config,
    InvalidKeyException,
    RateLimitException,
    events,
    fetch_api,
    sync_groups,
)
from ts3bot.bot import Bot
from ts3bot.database import enums, models

MESSAGE_REGEX = "\\s*(\\w{8}(-\\w{4}){3}-\\w{20}(-\\w{4}){3}-\\w{12})\\s*"
USAGE = "<API KEY>"
LOG = logging.getLogger("ts3bot.api_key")


def handle(bot: Bot, event: events.TextMessage, match: Match) -> None:
    key = match.group(1)

    # Check with ArenaNet's API
    try:
        account_info = fetch_api("account", api_key=key)

        # Check if one of the guilds is in the alliance
        is_part_of_alliance = (
            bot.session.query(models.Guild)
            .filter(models.Guild.guid.in_(account_info.get("guilds", [])))
            .filter(models.Guild.is_part_of_alliance.is_(True))
            .count()
            > 0
        )

        # One of the guilds is in the alliance
        if is_part_of_alliance:
            account: models.Account = models.Account.get_or_create(
                bot.session, account_info, key
            )
            identity: models.Identity = models.Identity.get_or_create(
                bot.session, event.uid
            )

            # Check if account is registered to anyone
            linked_identity: Optional[
                models.LinkAccountIdentity
            ] = account.valid_identities.one_or_none()

            # Account is already linked
            if linked_identity:
                # Account is linked to another guid
                if linked_identity.identity.guid != event.uid:
                    try:
                        # Get user's DB id
                        cldbid: str = bot.exec_(
                            "clientgetdbidfromuid", cluid=event.uid
                        )[0]["cldbid"]
                    except ts3.TS3Error:
                        LOG.error("Failed to get user's dbid", exc_info=True)
                        bot.send_message(event.id, "error_critical")
                        return

                    force_key_name = f"ts3bot-{cldbid}"

                    # Fetch token info
                    token_info = fetch_api("tokeninfo", api_key=key)

                    # Override registration, same as !register
                    if token_info.get("name", "") == force_key_name:
                        ts3bot.transfer_registration(bot, account, event)

                        LOG.info(
                            "%s (%s) transferred permissions of %s onto themselves.",
                            event.name,
                            event.uid,
                            account_info.get("name"),
                        )
                        return

                    LOG.warning(
                        "%s (%s) tried to use an already registered API key/account. (%s)",
                        event.name,
                        event.uid,
                        account_info.get("name"),
                    )
                    bot.send_message(event.id, "token_in_use", api_name=force_key_name)
                else:  # Account is linked to current guid
                    LOG.info(
                        "User %s (%s) tried to register a second time for whatever reason using %s",
                        event.name,
                        event.uid,
                        account_info.get("name", "Unknown account"),
                    )

                    # Save new API key
                    if account.api_key != key:
                        account.api_key = key
                        account.is_valid = True
                        bot.session.commit()
                        bot.send_message(event.id, "registration_exists")
                        return

                    # Same API key supplied, last check was over 12 minutes ago
                    if (
                        ts3bot.timedelta_hours(
                            datetime.datetime.today() - account.last_check
                        )
                        >= 0.2
                    ):
                        # Update saved account info if same API key was posted again with a reasonable time frame
                        account.update(bot.session)
                        try:
                            # Get user's DB id
                            cldbid = bot.exec_("clientgetdbidfromuid", cluid=event.uid)[
                                0
                            ]["cldbid"]

                            # Sync groups
                            ts3bot.sync_groups(bot, cldbid, account)
                            bot.send_message(event.id, "registration_details_updated")
                        except ts3.TS3Error:
                            # User might not exist in the db
                            LOG.error("Failed to sync user", exc_info=True)
                    else:
                        # Too early
                        bot.send_message(event.id, "registration_too_early")

            else:
                # Otherwise account is not yet linked and can be used

                # Save API key
                account.api_key = key
                account.is_valid = True
                bot.session.commit()

                # Get user's DB id
                cldbid = bot.exec_("clientgetdbidfromuid", cluid=event.uid)[0]["cldbid"]

                # Unlink previous account from identity
                current_account = models.Account.get_by_identity(bot.session, event.uid)
                if current_account:
                    LOG.info("Delinking %s from cldbid:%s", current_account, cldbid)
                    current_account.invalidate(bot.session)

                # Register link between models
                bot.session.add(
                    models.LinkAccountIdentity(account=account, identity=identity)
                )
                bot.session.commit()

                # Add all known guilds to user if enabled
                if Config.getboolean(
                    "guild", "assign_on_register"
                ) and Config.getboolean("guild", "allow_multiple_guilds"):
                    cast(AppenderQuery, account.guilds).filter(
                        models.LinkAccountGuild.id.in_(
                            bot.session.query(models.LinkAccountGuild.id)
                            .join(models.Guild)
                            .filter(models.Guild.group_id.isnot(None))
                            .subquery()
                        )
                    ).update({"is_active": True}, synchronize_session="fetch")
                    bot.session.commit()

                # Sync groups
                sync_groups(bot, cldbid, account)

                LOG.info(
                    "Assigned alliance permissions to %s (%s) using %s",
                    event.name,
                    event.uid,
                    account_info.get("name", "Unknown account"),
                )

                # Was registered with other account previously
                if current_account:
                    bot.send_message(
                        event.id, "registration_update", account=account.name
                    )
                else:
                    bot.send_message(event.id, "welcome_registered")

                    # Tell user about !guild if it's enabled
                    if Config.getboolean("commands", "guild"):
                        if Config.getboolean(
                            "guild", "assign_on_register"
                        ) and Config.getboolean("guild", "allow_multiple_guilds"):
                            bot.send_message(event.id, "welcome_registered_3")
                        else:
                            bot.send_message(event.id, "welcome_registered_2")

        else:
            bot.send_message(
                event.id,
                "invalid_world",
                world=enums.World(account_info.get("world")).proper_name,
            )

    except InvalidKeyException:
        LOG.info("This seems to be an invalid API key.")
        bot.send_message(event.id, "invalid_token_retry")
    except (RateLimitException, RequestException, ApiErrBadData):
        bot.send_message(event.id, "error_api")
