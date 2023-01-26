import logging
from typing import Match

import ts3  # type: ignore
from requests import RequestException

from ts3bot import (
    ApiErrBadDataError,
    InvalidKeyError,
    RateLimitError,
    events,
    fetch_api,
    transfer_registration,
)
from ts3bot.bot import Bot
from ts3bot.config import env
from ts3bot.database import models

MESSAGE_REGEX = "!register (\\d+) (\\w{8}(-\\w{4}){3}-\\w{20}(-\\w{4}){3}-\\w{12})\\s*"
USAGE = "!register <database-id> <api-key>"


def handle(bot: Bot, event: events.TextMessage, match: Match) -> None:
    if event.uid not in env.admin_whitelist:
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

        # Save api key in account
        account.api_key = match.group(2)
        account.is_valid = True
        bot.session.commit()

        transfer_registration(
            bot,
            account,
            event,
            is_admin=True,
            target_identity=identity,
            target_dbid=match.group(1),
        )
    except InvalidKeyError:
        logging.info("This seems to be an invalid API key.")
        bot.send_message(event.id, "invalid_token")
        return
    except (RateLimitError, RequestException, ApiErrBadDataError):
        bot.send_message(event.id, "error_api")
