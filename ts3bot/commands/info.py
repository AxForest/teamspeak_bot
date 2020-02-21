import logging
import typing

import requests
import ts3
from sqlalchemy.orm import load_only

from ts3bot import InvalidKeyException, RateLimitException, fetch_api
from ts3bot.bot import Bot
from ts3bot.database import enums, models

MESSAGE_REGEX = "!info \\s*(\\w{8}(-\\w{4}){3}-\\w{20}(-\\w{4}){3}-\\w{12})\\s*"
USAGE = "!info <API-Key>"


def handle(bot: Bot, event: ts3.response.TS3Event, match: typing.Match):
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
            event[0]["invokerid"],
            "info_world",
            i18n_kwargs={
                "user": account.get("name"),
                "world": server.proper_name,
                "guilds": ", ".join([_.name for _ in guilds]),
            },
        )
    except InvalidKeyException:
        logging.info("This seems to be an invalid API key.")
        bot.send_message(event[0]["invokerid"], "invalid_token")
    except (requests.RequestException, RateLimitException):
        logging.exception("Error during API call")
        bot.send_message(event[0]["invokerid"], "error_api")
