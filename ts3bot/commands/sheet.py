import datetime
import json
import typing
from pathlib import Path

import ts3

import config
from ts3bot import Bot

MESSAGE_REGEX = "!sheet\\s* (\\w+)(.*)"
USAGE = "!sheet <ebg,red,green,blue,reset,remove> [note]"
STATE_FILE = Path("sheet.json")


def handle(bot: Bot, event: ts3.response.TS3Event, match: typing.Match):
    if not hasattr(config, "SHEET_CHANNEL_ID"):
        return

    current_state = {"EBG": [], "Rot": [], "Grün": [], "Blau": []}

    if (
        match.group(1) == "reset"
        and event[0]["invokeruid"] in config.WHITELIST["ADMIN"]
    ):
        pass
    elif match.group(1) in ["ebg", "red", "green", "blue", "r", "g", "b", "remove"]:
        if STATE_FILE.exists():
            current_state = json.loads(STATE_FILE.read_text())

        # Remove old entry
        current_state = _remove_lead(current_state, event[0]["invokeruid"])

        if match.group(1) != "remove":
            # Add user to groups
            _map = {
                "ebg": "EBG",
                "red": "Rot",
                "green": "Grün",
                "blue": "Blau",
                "r": "Rot",
                "g": "Grün",
                "b": "Blau",
            }

            # Only allow two leads per map
            if len(current_state[_map[match.group(1).lower()]]) >= 2:
                bot.send_message(event[0]["invokerid"], "sheet_map_full")
                return

            current_state[_map[match.group(1).lower()]].append(
                {
                    "lead": f"[URL=client://0/{event[0]['invokeruid']}]{event[0]['invokername']}[/URL]",
                    "note": (match.group(2) or "").strip()[0:20],
                    "date": _tidy_date(),
                }
            )
    else:
        bot.send_message(event[0]["invokerid"], "invalid_input")
        return

    desc = "[table][tr][td] | Map | [/td][td] | Lead | [/td][td] | Note | [/td][td] | Date | [/td][/tr]"
    for _map, leads in current_state.items():
        if len(leads) == 0:
            desc += f"[tr][td]{_map}[/td][td]-[/td][td]-[/td][td]-[/td][/tr]"
            continue

        for lead in leads:
            desc += f"[tr][td]{_map}[/td][td]{lead['lead']}[/td][td]{_encode(lead['note'])}[/td][td]{lead['date']}[/td][/tr]"

    desc += (
        f"[/table]\n[hr]Last change: {_tidy_date()}\n\n"
        "Usage:\n"
        "- !sheet red/green/blue (note)\t—\tRegister your lead with an optional note (20 characters).\n"
        "- !sheet remove\t—\tRemove the lead"
    )
    bot.ts3c.exec_("channeledit", cid=config.SHEET_CHANNEL_ID, channel_description=desc)
    bot.send_message(event[0]["invokerid"], "sheet_changed")

    STATE_FILE.write_text(json.dumps(current_state))


def _tidy_date(date: datetime.datetime = None):
    if not date:
        date = datetime.datetime.now()
    return date.strftime("%d.%m. %H:%M")


def _remove_lead(maps: typing.Dict, uid: str):
    new_leads = {}
    for _map, leads in maps.items():
        new_leads[_map] = []
        for lead in leads:
            if uid not in lead["lead"]:
                new_leads[_map].append(lead)
    return new_leads


def _encode(s: str):
    return s.replace("[", "\\[").replace("]", "\\]")
