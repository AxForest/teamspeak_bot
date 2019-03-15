import typing

import ts3

import config
from bot import Bot

MESSAGE_REGEX = "!help\\s*"
USAGE = "!help"


def handle(bot: Bot, event: ts3.response.TS3Event, _match: typing.Match):
    if event[0]["invokeruid"] not in config.WHITELIST["ADMIN"]:
        return

    message = "\nVerfügbare Befehle:"
    for _ in bot.commands:
        if _.USAGE != USAGE:
            message += "\n - {}".format(_.USAGE)

    bot.send_message(event[0]["invokerid"], message)
