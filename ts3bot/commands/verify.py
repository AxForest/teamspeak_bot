import typing

import requests
import ts3

from ts3bot import InvalidKeyException, sync_groups
from ts3bot.bot import Bot
from ts3bot.config import Config
from ts3bot.database import enums, models

MESSAGE_REGEX = "!verify +([A-Za-z0-9+/=]+)"
USAGE = "!verify <TS Database ID|TS Unique ID>"


def handle(bot: Bot, event: ts3.response.TS3Event, match: typing.Match):
    if event[0]["invokeruid"] not in Config.whitelist_admin:
        return

    # Grab cluid
    try:
        if match.group(1).isdigit():  # DB id
            user = bot.exec_("clientgetnamefromdbid", cldbid=match.group(1))
            cldbid = match.group(1)
            cluid = user[0]["cluid"]
        else:
            user = bot.exec_("clientgetnamefromuid", cluid=match.group(1))
            cldbid = user[0]["cldbid"]
            cluid = match.group(1)
    except ts3.query.TS3QueryError:
        bot.send_message(event[0]["invokerid"], "verify_not_found")
        return

    # Grab user's account
    account = models.Account.get_by_guid(bot.session, cluid)

    if not account:
        bot.send_message(event[0]["invokerid"], "verify_no_token")
        return

    try:
        bot.send_message(event[0]["invokerid"], "account_updating")
        result = account.update(bot.session)
        if result["transfer"]:
            old_world: enums.World = result["transfer"][0]
            new_world: enums.World = result["transfer"][1]

            bot.send_message(
                event[0]["invokerid"],
                "verify_transferred",
                i18n_kwargs={
                    "old_world": old_world.proper_name,
                    "new_world": new_world.proper_name,
                },
            )
        guilds_joined, guilds_left = result["guilds"]

        if len(guilds_joined) > 0 or len(guilds_left) > 0:
            bot.send_message(
                event[0]["invokerid"],
                "verify_guild_change",
                i18n_kwargs={
                    "guilds_joined": guilds_joined,
                    "guilds_left": guilds_left,
                },
            )

        # Sync user's groups
        sync_groups(bot, cldbid, account)

        bot.send_message(
            event[0]["invokerid"],
            "verify_valid_world",
            i18n_kwargs={"user": account.name, "world": account.world.proper_name},
        )
    except InvalidKeyException:
        bot.send_message(event[0]["invokerid"], "invalid_token")

        # Invalidate link
        account.invalidate(bot.session)
        changes = sync_groups(bot, cldbid, account)

        bot.send_message(
            event[0]["invokerid"],
            "groups_removed",
            i18n_kwargs={"groups": changes["removed"]},
        )
    except requests.RequestException:
        bot.send_message(event[0]["invokerid"], "error_api")
