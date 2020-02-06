import typing

import ts3

import config
from ts3bot import Bot

MESSAGE_REGEX = "!list +([\\w ]+)"
USAGE = "!list <TS Group>"


def handle(bot: Bot, event: ts3.response.TS3Event, match: typing.Match):
    cldbid = bot.ts3c.exec_("clientgetdbidfromuid", cluid=event[0]["invokeruid"])[0][
        "cldbid"
    ]
    user_groups = bot.ts3c.exec_("servergroupsbyclientid", cldbid=cldbid)
    allowed = False

    for group in user_groups:
        if group["name"] in config.WHITELIST["GROUP_LIST"]:
            allowed = True
            break

    # User doesn't have any whitelisted groups
    if not allowed:
        return

    groups = bot.ts3c.exec_("servergrouplist")
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
        bot.send_message(event[0]["invokerid"], "list_not_found")
        return

    members = bot.ts3c.exec_("servergroupclientlist", "names", sgid=group["sgid"])

    members = sorted(members, key=lambda _: _["client_nickname"])

    if len(members) >= 50:
        bot.send_message(event[0]["invokerid"], "list_50_users")
        return

    text_groups = [""]
    index = 0
    for member in members:
        member_text = "\n- [URL=client://0/{}]{}[/URL]".format(
            member["client_unique_identifier"], member["client_nickname"]
        )
        if len(text_groups[index]) + len(bytes(member_text, "utf-8")) >= 1024:
            index += 1
            text_groups.append("")

        text_groups[index] += member_text

    bot.send_message(
        event[0]["invokerid"],
        "list_users",
        i18n_kwargs={"amount": len(members), "role": group["name"]},
    )
    for _ in text_groups:
        bot.send_message(event[0]["invokerid"], _, is_translation=False)
