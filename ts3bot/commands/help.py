import typing

import i18n

from ts3bot import events
from ts3bot.bot import Bot
from ts3bot.config import Config

MESSAGE_REGEX = "!help\\s*"
USAGE = "!help"


def handle(bot: Bot, event: events.TextMessage, _match: typing.Match):
    if event.uid not in Config.whitelist_admin:
        return

    i18n.set("locale", "en")
    message = i18n.t("available_commands")
    for _ in bot.commands:
        if _.USAGE != USAGE:
            message += "\n - {}".format(_.USAGE)

    bot.send_message(event.id, message, is_translation=False)
