import logging
import typing

import ts3
from requests import RequestException

from ts3bot import (
    InvalidKeyException,
    RateLimitException,
    events,
    fetch_api,
    sync_groups,
)
from ts3bot.bot import Bot
from ts3bot.config import Config
from ts3bot.database import models

MESSAGE_REGEX = "!register (\\d+) (\\w{8}(-\\w{4}){3}-\\w{20}(-\\w{4}){3}-\\w{12})\\s*"
USAGE = "!register <database-id> <api-key>"


def handle(bot: Bot, event: events.TextMessage, match: typing.Match):
    if event.uid not in Config.whitelist_admin:
        return

    # Grab client_uid
    try:
        user = bot.exec_("clientgetnamefromdbid", cldbid=match.group(1))
        client_uid = user[0]["cluid"]
    except ts3.query.TS3QueryError:
        bot.send_message(event.id, "user_not_found")
        return

    try:
        json = fetch_api("account", api_key=match.group(2))
        account = models.Account.get_or_create(bot.session, json, match.group(2))
        identity: models.Identity = models.Identity.get_or_create(
            bot.session, client_uid
        )

        # Get current guild group
        guild_group = account.guild_group()

        # Get previous identity
        previous_identity: typing.Optional[
            models.LinkAccountIdentity
        ] = account.valid_identities.one_or_none()

        # Remove previous identities, keep guild groups intact
        account.invalidate(bot.session)

        if previous_identity:
            # Get cldbid and sync groups
            try:
                cldbid = bot.exec_(
                    "clientgetdbidfromuid", cluid=previous_identity.identity.guid
                )[0]["cldbid"]

                result = sync_groups(bot, cldbid, account, remove_all=True)

                logging.info(
                    "%s (%s) marked previous links of %s as ignored",
                    event.name,
                    event.uid,
                    account.name,
                )

                bot.send_message(
                    event.id, "groups_revoked", amount="1", groups=result["removed"],
                )
            except ts3.TS3Error:
                # User might not exist in the db
                logging.info("Failed to remove groups from user", exc_info=True)
        else:
            bot.send_message(event.id, "groups_revoked", amount="0", groups=[])

        # Save api key in account
        account.api_key = match.group(2)
        account.is_valid = True

        # Remove new identity's link
        other_account = models.Account.get_by_identity(bot.session, identity.guid)
        if other_account:
            other_account.invalidate(bot.session)

        # Transfer roles to new identity
        bot.session.add(models.LinkAccountIdentity(account=account, identity=identity))

        # Add guild group
        if guild_group:
            guild_group.is_active = True

        bot.session.commit()

        # Sync groups
        sync_groups(bot, match.group(1), account)

        logging.info(
            "Transferred groups of %s to cldbid:%s",
            json.get("name", "Unknown account"),
            match.group(1),
        )

        bot.send_message(
            event.id, "register_transfer", account=account.name,
        )

    except InvalidKeyException:
        logging.info("This seems to be an invalid API key.")
        bot.send_message(event.id, "invalid_token")
        return
    except (RateLimitException, RequestException):
        bot.send_message(event.id, "error_api")
