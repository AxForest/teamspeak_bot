import logging
import typing
from operator import or_

import ts3

from ts3bot import InvalidKeyException, events, fetch_api, sync_groups
from ts3bot.bot import Bot
from ts3bot.config import Config
from ts3bot.database import models

MESSAGE_REGEX = "!ignore +([A-Z0-9\\-]+)"
USAGE = "!ignore <API KEY>"


def handle(bot: Bot, event: events.TextMessage, match: typing.Match):
    if event.uid not in Config.whitelist_admin:
        return

    try:
        json = fetch_api("account", api_key=match.group(1))
        account = models.Account.get_by_api_info(
            bot.session, guid=json.get("id"), name=json.get("name")
        )

        # Account does not exist
        if not account:
            logging.info("User was not registered.")
            bot.send_message(event.id, "account_unknown", account=json.get("name"))
            return

        # Get previous identity
        previous_identity: typing.Optional[
            models.LinkAccountIdentity
        ] = account.valid_identities.one_or_none()

        # Remove previous links
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
    except InvalidKeyException:
        logging.info("This seems to be an invalid API key.")
        bot.send_message(event.id, "invalid_token")
        return
