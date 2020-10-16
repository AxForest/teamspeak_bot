import datetime
import json
import re
import typing
from pathlib import Path

from ts3bot import events
from ts3bot.bot import Bot
from ts3bot.config import Config

MESSAGE_REGEX = "!sheet\\s* (\\w+)(.*)"
USAGE = "!sheet <ebg,red,green,blue,remove> [note]"
STATE_FILE = Path("sheet.json")

COMMAND_MAPPING = {
    "ebg": "EBG",
    "red": "Red",
    "green": "Green",
    "blue": "Blue",
    "r": "Red",
    "g": "Green",
    "b": "Blue",
}


def handle(bot: Bot, event: events.TextMessage, match: typing.Match):
    sheet_channel_id = Config.get("teamspeak", "sheet_channel_id")
    if sheet_channel_id == 0:
        return

    current_state = {"EBG": [], "Red": [], "Green": [], "Blue": []}

    if match.group(1) == "help" and event.uid in Config.whitelist_admin:
        bot.send_message(
            event.id,
            "!sheet <ebg,red,green,blue,remove,reset>\n!sheet set <ebg,red,green,blue,remove> <name>",
            is_translation=False,
        )
        return

    if match.group(1) == "reset" and event.uid in Config.whitelist_admin:
        pass  # Don't load the current file, just use the defaults
    elif match.group(1) == "set" and event.uid in Config.whitelist_admin:
        # Force-set an entry
        match = re.match(
            "!sheet set (ebg|red|green|blue|r|g|b|remove) (.*)",
            event.message.strip(),
        )
        if not match:
            bot.send_message(event.id, "invalid_input")
            return

        if STATE_FILE.exists():
            current_state = json.loads(STATE_FILE.read_text())

        if match.group(1) == "remove":
            current_state = _remove_lead(current_state, name_field=match.group(2))
        else:
            # Add new entry
            current_state = _add_lead(
                current_state,
                wvw_map=match.group(1),
                note="",
                name=match.group(2),
            )
            if not current_state:
                bot.send_message(event.id, "sheet_map_full")
                return

    elif match.group(1) in ["ebg", "red", "green", "blue", "r", "g", "b", "remove"]:
        if STATE_FILE.exists():
            current_state = json.loads(STATE_FILE.read_text())

        if match.group(1) == "remove":
            current_state = _remove_lead(current_state, uid=event.uid)
        else:
            current_state = _add_lead(
                current_state,
                wvw_map=match.group(1),
                note=match.group(2),
                uid=event.uid,
                name=event.name,
            )
            if not current_state:
                bot.send_message(event.id, "sheet_map_full")
                return
    else:
        bot.send_message(event.id, "invalid_input")
        return

    # Build new table
    desc = "[table][tr][td] | Map | [/td][td] | Lead | [/td][td] | Note | [/td][td] | Date | [/td][/tr]"
    for _map, leads in current_state.items():
        if len(leads) == 0:
            desc += f"[tr][td]{_map}[/td][td]-[/td][td]-[/td][td]-[/td][/tr]"
            continue

        for lead in leads:
            desc += (
                f"[tr][td]{_map}[/td][td]{lead['lead']}[/td][td]{_encode(lead['note'])}[/td]"
                f"[td]{lead['date']}[/td][/tr]"
            )

    desc += (
        f"[/table]\n[hr]Last change: {_tidy_date()}\n\n"
        f"Link to bot: [URL=client://0/{bot.own_uid}]{Config.get('bot_login', 'nickname')}[/URL]\n"  # Add link to self
        "Usage:\n"
        "- !sheet red/green/blue (note)\t—\tRegister your lead with an optional note (20 characters).\n"
        "- !sheet remove\t—\tRemove the lead"
    )
    bot.exec_("channeledit", cid=sheet_channel_id, channel_description=desc)
    bot.send_message(event.id, "sheet_changed")

    STATE_FILE.write_text(json.dumps(current_state))


def _tidy_date(date: datetime.datetime = None):
    if not date:
        date = datetime.datetime.now()
    return date.strftime("%d.%m. %H:%M")


def _add_lead(
    maps: typing.Dict,
    wvw_map: str,
    note: str,
    name: str,
    uid: typing.Optional[str] = None,
) -> typing.Optional[typing.Dict]:
    mapping = COMMAND_MAPPING[wvw_map]

    lead = f"[URL=client://0/{uid}]{name}[/URL]" if uid else name

    # Remove leads with the same name
    maps = _remove_lead(maps, name_field=lead)

    # Only allow two leads per map
    if len(maps[mapping]) >= 2:
        return None

    maps[mapping].append(
        {"lead": lead, "note": note.strip()[0:20], "date": _tidy_date()}
    )
    return maps


def _remove_lead(
    maps: typing.Dict,
    name_field: typing.Optional[str] = None,
    uid: typing.Optional[str] = None,
):
    def compare(_lead):
        if uid:
            return uid not in _lead["lead"]

        return name_field != _lead["lead"]

    new_leads: typing.Dict[str, typing.List[typing.Dict[str, str]]] = {}
    for _map, leads in maps.items():
        new_leads[_map] = []
        for lead in leads:
            if compare(lead):
                new_leads[_map].append(lead)
    return new_leads


def _encode(s: str):
    return s.replace("[", "\\[").replace("]", "\\]")
