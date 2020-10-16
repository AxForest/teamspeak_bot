import typing

import requests
import ts3
from ts3bot import ApiErrBadData, InvalidKeyException, events, sync_groups
from ts3bot.bot import Bot
from ts3bot.config import Config
from ts3bot.database import enums, models

MESSAGE_REGEX = "!verify +([A-Za-z0-9+/=]+)"
USAGE = "!verify <TS Database ID|TS Unique ID>"


def handle(bot: Bot, event: events.TextMessage, match: typing.Match):
    if event.uid not in Config.whitelist_admin:
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
        bot.send_message(event.id, "user_not_found")
        return

    # Grab user's account
    account = models.Account.get_by_identity(bot.session, cluid)

    if not account:
        bot.send_message(event.id, "verify_no_token")
        return

    try:
        bot.send_message(event.id, "account_updating")
        result = account.update(bot.session)
        if result["transfer"]:
            old_world: enums.World = result["transfer"][0]
            new_world: enums.World = result["transfer"][1]

            bot.send_message(
                event.id,
                "verify_transferred",
                old_world=old_world.proper_name,
                new_world=new_world.proper_name,
            )
        guilds_joined, guilds_left = result["guilds"]

        if len(guilds_joined) > 0 or len(guilds_left) > 0:
            bot.send_message(
                event.id,
                "verify_guild_change",
                guilds_joined=guilds_joined,
                guilds_left=guilds_left,
            )

        # Sync user's groups
        sync_groups(bot, cldbid, account)

        bot.send_message(
            event.id,
            "verify_valid_world",
            user=account.name,
            world=account.world.proper_name,
        )
    except InvalidKeyException:
        bot.send_message(event.id, "invalid_token")

        # Invalidate link
        account.invalidate(bot.session)
        changes = sync_groups(bot, cldbid, account)

        bot.send_message(event.id, "groups_removed", groups=str(changes["removed"]))
    except (requests.RequestException, ApiErrBadData):
        bot.send_message(event.id, "error_api")
