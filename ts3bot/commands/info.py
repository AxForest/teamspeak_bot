import logging
from typing import Match

import requests
from sqlalchemy.orm import load_only

from ts3bot import (
    ApiErrBadData,
    InvalidKeyException,
    RateLimitException,
    events,
    fetch_api,
)
from ts3bot.bot import Bot
from ts3bot.database import enums, models

MESSAGE_REGEX = "!info \\s*(\\w{8}(-\\w{4}){3}-\\w{20}(-\\w{4}){3}-\\w{12})\\s*"
USAGE = "!info <API-Key>"


def handle(bot: Bot, event: events.TextMessage, match: Match) -> None:
    try:
        account = fetch_api("account", api_key=match.group(1))
        server = enums.World(account.get("world"))

        guilds = (
            bot.session.query(models.Guild)
            .filter(models.Guild.guid.in_(account.get("guilds", [])))
            .filter(models.Guild.group_id.isnot(None))
            .options(load_only(models.Guild.name))
        )

        bot.send_message(
            event.id,
            "info_world",
            user=account.get("name", "Unknown.0000"),
            world=server.proper_name,
            guilds=", ".join([_.name for _ in guilds]),
        )
    except InvalidKeyException:
        logging.info("This seems to be an invalid API key.")
        bot.send_message(event.id, "invalid_token")
    except (requests.RequestException, RateLimitException, ApiErrBadData):
        logging.exception("Error during API call")
        bot.send_message(event.id, "error_api")
