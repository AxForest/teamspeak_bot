import datetime
import logging
from re import Match
from typing import cast

import ts3  # type: ignore
from requests import RequestException
from sqlalchemy.orm.dynamic import AppenderQuery

import ts3bot
from ts3bot import (
    ApiErrBadDataError,
    InvalidKeyError,
    RateLimitError,
    events,
    fetch_api,
    sync_groups,
)
from ts3bot.bot import Bot
from ts3bot.config import env
from ts3bot.database import enums, models

MESSAGE_REGEX = "\\s*(\\w{8}(-\\w{4}){3}-\\w{20}(-\\w{4}){3}-\\w{12})\\s*"
USAGE = "<API KEY>"


def handle(  # noqa: PLR0912,PLR0915
    bot: Bot, event: events.TextMessage, match: Match
) -> None:
    key = match.group(1)

    # Check with ArenaNet's API
    try:
        account_info = fetch_api("account", api_key=key)

        # Grab server info from database
        server_group: models.WorldGroup | None = (
            bot.session.query(models.WorldGroup)
            .filter(models.WorldGroup.world == enums.World(account_info.get("world")))
            .one_or_none()
        )

        # World is linked to a group
        if server_group:
            account: models.Account = models.Account.get_or_create(
                bot.session, account_info, key
            )
            identity: models.Identity = models.Identity.get_or_create(
                bot.session, event.uid
            )

            # Check if account is registered to anyone
            linked_identity: models.LinkAccountIdentity | None = (
                account.valid_identities.one_or_none()
            )

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
                        logging.error("Failed to get user's dbid", exc_info=True)
                        bot.send_message(event.id, "error_critical")
                        return

                    force_key_name = f"ts3bot-{cldbid}"

                    # Fetch token info
                    token_info = fetch_api("tokeninfo", api_key=key)

                    # Override registration, same as !register
                    if token_info.get("name", "").strip() == force_key_name:
                        ts3bot.transfer_registration(bot, account, event)

                        logging.info(
                            "%s (%s) transferred permissions of %s onto themselves.",
                            event.name,
                            event.uid,
                            account_info.get("name"),
                        )
                        return

                    logging.warning(
                        (
                            "%s (%s) tried to use an already registered "
                            "API key/account. (%s)"
                        ),
                        event.name,
                        event.uid,
                        account_info.get("name"),
                    )
                    bot.send_message(event.id, "token_in_use", api_name=force_key_name)
                else:  # Account is linked to current guid
                    logging.info(
                        (
                            "User %s (%s) tried to register a second time for "
                            "whatever reason using %s"
                        ),
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
                        >= 0.2  # noqa: PLR2004
                    ):
                        # Update saved account info if same API key was posted again
                        # within a reasonable time frame
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
                            logging.error("Failed to sync user", exc_info=True)
                    else:
                        # Too early
                        bot.send_message(event.id, "registration_too_early")

                    # Set description to IGN
                    if env.set_client_description_to_ign:
                        ts3bot.set_client_description(bot, event.id, account.name)

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
                    logging.info("Delinking %s from cldbid:%s", current_account, cldbid)
                    current_account.invalidate(bot.session)

                # Register link between models
                bot.session.add(
                    models.LinkAccountIdentity(account=account, identity=identity)
                )
                bot.session.commit()

                # Add all known guilds to user if enabled
                if env.assign_guild_on_register and env.allow_multiple_guilds:
                    cast(AppenderQuery, account.guilds).filter(
                        models.LinkAccountGuild.id.in_(
                            bot.session.query(models.LinkAccountGuild.id)
                            .join(models.Guild)
                            .filter(models.Guild.group_id.isnot(None))
                            .subquery()
                            .select()
                        )
                    ).update({"is_active": True}, synchronize_session="fetch")
                    bot.session.commit()

                # Sync groups
                sync_groups(bot, cldbid, account)

                logging.info(
                    "Assigned world %s to %s (%s) using %s",
                    server_group.world.name,
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
                    if "guild" in env.commands:
                        if env.assign_guild_on_register and env.allow_multiple_guilds:
                            bot.send_message(event.id, "welcome_registered_3")
                        else:
                            bot.send_message(event.id, "welcome_registered_2")

                # Set description to IGN
                if env.set_client_description_to_ign:
                    ts3bot.set_client_description(bot, event.id, account.name)
        else:
            bot.send_message(
                event.id,
                "invalid_world",
                world=enums.World(account_info.get("world")).proper_name,
            )

    except InvalidKeyError:
        logging.info("This seems to be an invalid API key.")
        bot.send_message(event.id, "invalid_token_retry")
    except (RateLimitError, RequestException, ApiErrBadDataError):
        bot.send_message(event.id, "error_api")
