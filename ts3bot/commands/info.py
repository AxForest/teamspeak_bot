import logging
import typing

import requests
import ts3

import config
from ts3bot import Bot, common

MESSAGE_REGEX = "!info \\s*(\\w{8}(-\\w{4}){3}-\\w{20}(-\\w{4}){3}-\\w{12})\\s*"
USAGE = "!info <API-Key>"


def handle(bot: Bot, event: ts3.response.TS3Event, match: typing.Match):
    try:
        key = match.group(1)
        account = common.fetch_account(key)
        if account:
            server = common.world_name_from_id(account.get("world"))

            guilds = []
            for _ in account.get("guilds"):
                if _ in config.GUILDS:
                    guilds.append(config.GUILDS[_][0])

            bot.send_message(
                event[0]["invokerid"],
                "info_world",
                i18n_kwargs={
                    "user": account.get("name"),
                    "world": server,
                    "guilds": guilds,
                },
            )
        else:
            logging.info("This seems to be an invalid API key.")
            bot.send_message(event[0]["invokerid"], "invalid_token")
    except (requests.RequestException, common.RateLimitException):
        logging.exception("Error during API call")
        bot.send_message(event[0]["invokerid"], "error_api")