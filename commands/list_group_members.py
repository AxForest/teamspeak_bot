import typing

import ts3

import config
from bot import Bot

MESSAGE_REGEX = "!list +([\\w ]+)"
USAGE = "!list <TS-Gruppe>"


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
        bot.send_message(event[0]["invokerid"], "Gruppe nicht gefunden!")
        return

    members = bot.ts3c.exec_("servergroupclientlist", "names", sgid=group["sgid"])

    members = sorted(members, key=lambda _: _['client_nickname'])

    text_groups = ["\nEs sind {} Member in {}:".format(len(members), group["name"])]
    index = 0
    for member in members:
        member_text = "\n- [URL=client://0/{}]{}[/URL]".format(
            member["client_unique_identifier"], member["client_nickname"]
        )
        if len(text_groups[index]) + len(bytes(member_text, "utf-8")) >= 1024:
            index += 1
            text_groups.append("")

        text_groups[index] += member_text

    for _ in text_groups:
        bot.send_message(event[0]["invokerid"], _)
