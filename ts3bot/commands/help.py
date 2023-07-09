from re import Match

import i18n  # type: ignore

from ts3bot import events
from ts3bot.bot import Bot
from ts3bot.config import env

MESSAGE_REGEX = "!help\\s*"
USAGE = "!help"


def handle(bot: Bot, event: events.TextMessage, _match: Match) -> None:
    if event.uid not in env.admin_whitelist:
        return

    i18n.set("locale", "en")
    message = i18n.t("available_commands")
    for _ in bot.commands:
        if _.USAGE != USAGE:
            message += f"\n - {_.USAGE}"

    bot.send_message(event.id, message, is_translation=False)
