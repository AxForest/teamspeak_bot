import typing

import i18n
import ts3

from ts3bot.bot import Bot
from ts3bot.config import Config

MESSAGE_REGEX = "!help\\s*"
USAGE = "!help"


def handle(bot: Bot, event: ts3.response.TS3Event, _match: typing.Match):
    if event[0]["invokeruid"] not in Config.whitelist_admin:
        return

    i18n.set("locale", "en")
    message = i18n.t("available_commands")
    for _ in bot.commands:
        if _.USAGE != USAGE:
            message += "\n - {}".format(_.USAGE)

    bot.send_message(event[0]["invokerid"], message, is_translation=False)
