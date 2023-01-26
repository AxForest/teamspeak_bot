from typing import Match, cast

from ts3bot import events
from ts3bot.bot import Bot
from ts3bot.config import env

MESSAGE_REGEX = "!list +([\\w\\- ]+)"
USAGE = "!list <TS Group>"

MAX_MEMBER_AMOUNT = 50
MAX_MESSAGE_SIZE = 1024


def handle(bot: Bot, event: events.TextMessage, match: Match) -> None:
    cldbid = bot.exec_("clientgetdbidfromuid", cluid=event.uid)[0]["cldbid"]
    user_groups = bot.exec_("servergroupsbyclientid", cldbid=cldbid)
    allowed = False

    if event.uid in env.admin_whitelist:
        allowed = True
    else:
        for group in user_groups:
            if group["name"] in env.list_whitelist:
                allowed = True
                break

    # User doesn't have any whitelisted groups
    if not allowed:
        return

    groups = bot.exec_("servergrouplist")
    group = None
    search_group = match.group(1).strip()
    for _ in groups:
        if _["type"] != "1":  # Regular type, neither template nor query
            continue

        if _["name"] == search_group:
            group = _
            break

    # Group not found
    if group is None:
        bot.send_message(event.id, "list_not_found")
        return

    members = bot.exec_("servergroupclientlist", "names", sgid=group["sgid"])

    members = sorted(members, key=lambda x: cast(str, _.get("client_nickname", "")))

    if len(members) >= MAX_MEMBER_AMOUNT:
        bot.send_message(event.id, "list_50_users")
        return

    text_groups = [""]
    index = 0
    for member in members:
        member_text = "\n- [URL=client://0/{}]{}[/URL]".format(
            member["client_unique_identifier"], member["client_nickname"]
        )
        if (
            len(text_groups[index]) + len(bytes(member_text, "utf-8"))
            >= MAX_MESSAGE_SIZE
        ):
            index += 1
            text_groups.append("")

        text_groups[index] += member_text

    bot.send_message(event.id, "list_users", amount=len(members), group=group["name"])
    for _ in text_groups:
        bot.send_message(event.id, _, is_translation=False)
