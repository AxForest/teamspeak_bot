import typing

import ts3

import config
from bot import Bot

MESSAGE_REGEX = "!list +([\\w ]+)"
USAGE = "!list <TS-Gruppe>"


def handle(bot: Bot, event: ts3.response.TS3Event, match: typing.Match):
    if event[0]["invokeruid"] not in config.WHITELIST["GROUP_LIST"]:
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

    text_groups = ["\nEs sind {} Member in {}:".format(len(members), group["name"])]
    index = 0
    for member in members:
        member_text = "\n- [URL=client://0/{}]{}[/URL]".format(
            member["client_unique_identifier"], member["client_nickname"]
        )
        if len(text_groups[index]) + len(member_text) >= 1024:
            index += 1
            text_groups[index] = ""

        text_groups[index] += member_text

    for _ in text_groups:
        bot.send_message(event[0]["invokerid"], _)

    bot.send_message(event[0]["invokerid"], "Und das wär'n dann alle.")
