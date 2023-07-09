import datetime
import json
import re
from collections.abc import ItemsView
from re import Match
from typing import Literal, TypedDict, cast

from ts3bot import events
from ts3bot.bot import Bot
from ts3bot.config import env
from ts3bot.utils import data_path

MESSAGE_REGEX = "!sheet\\s* (\\w+)(.*)"
USAGE = "!sheet <ebg,red,green,blue,remove> [note]"
STATE_FILE = data_path("sheet.json")
MAX_LEADS_PER_MAP = 2


class LeadDict(TypedDict):
    lead: str
    note: str
    date: str


IterType = ItemsView[Literal["EBG", "Red", "Green", "Blue"], list[LeadDict]]


class CommandingDict(TypedDict):
    EBG: list[LeadDict]
    Red: list[LeadDict]
    Green: list[LeadDict]
    Blue: list[LeadDict]


def handle(bot: Bot, event: events.TextMessage, match: Match) -> None:  # noqa: PLR0912
    if not env.sheet_channel_id:
        return

    current_state: CommandingDict = {"EBG": [], "Red": [], "Green": [], "Blue": []}

    if match.group(1) == "help" and event.uid in env.admin_whitelist:
        bot.send_message(
            event.id,
            (
                "!sheet <ebg,red,green,blue,remove,reset>\n"
                "!sheet set <ebg,red,green,blue,remove> <name>"
            ),
            is_translation=False,
        )
        return

    if match.group(1) == "reset" and event.uid in env.admin_whitelist:
        pass  # Don't load the current file, just use the defaults
    elif match.group(1) == "set" and event.uid in env.admin_whitelist:
        # Force-set an entry
        _match = re.match(
            "!sheet set (ebg|red|green|blue|r|g|b|remove) (.*)",
            event.message.strip(),
        )
        if not _match:
            bot.send_message(event.id, "invalid_input")
            return

        if STATE_FILE.exists():
            current_state = cast(CommandingDict, json.loads(STATE_FILE.read_text()))

        if _match.group(1) == "remove":
            current_state = _remove_lead(current_state, name_field=_match.group(2))
        else:
            # Add new entry
            new_state = _add_lead(
                current_state,
                wvw_map=_match.group(1),
                note="",
                name=_match.group(2),
            )
            if not new_state:
                bot.send_message(event.id, "sheet_map_full")
                return
            current_state = new_state

    elif match.group(1) in ["ebg", "red", "green", "blue", "r", "g", "b", "remove"]:
        if STATE_FILE.exists():
            current_state = json.loads(STATE_FILE.read_text())

        if match.group(1) == "remove":
            current_state = _remove_lead(current_state, uid=event.uid)
        else:
            new_state = _add_lead(
                current_state,
                wvw_map=match.group(1),
                note=match.group(2),
                uid=event.uid,
                name=event.name,
            )
            if not new_state:
                bot.send_message(event.id, "sheet_map_full")
                return
            current_state = new_state
    else:
        bot.send_message(event.id, "invalid_input")
        return

    # Build new table
    desc = (
        "[table][tr][td] | Map | [/td][td] | Lead | [/td][td] | Note | "
        "[/td][td] | Date | [/td][/tr]"
    )
    for _map, leads in cast(IterType, current_state.items()):
        if len(leads) == 0:
            desc += f"[tr][td]{_map}[/td][td]-[/td][td]-[/td][td]-[/td][/tr]"
            continue

        for lead in leads:
            desc += (
                f"[tr][td]{_map}[/td][td]{lead['lead']}"
                f"[/td][td]{_encode(lead['note'])}[/td]"
                f"[td]{lead['date']}[/td][/tr]"
            )

    desc += (
        f"[/table]\n[hr]Last change: {_tidy_date()}\n\n"
        # Add link to self
        f"Link to bot: [URL=client://0/{bot.own_uid}]{env.bot_nickname}[/URL]\n"
        "Usage:\n"
        "- !sheet red/green/blue (note)\t—\tRegister your lead with an optional "
        "note (20 characters).\n"
        "- !sheet remove\t—\tRemove the lead"
    )
    bot.exec_("channeledit", cid=env.sheet_channel_id, channel_description=desc)
    bot.send_message(event.id, "sheet_changed")

    STATE_FILE.write_text(json.dumps(current_state))


def _tidy_date(date: datetime.datetime = None) -> str:
    if not date:
        date = datetime.datetime.now()
    return date.strftime("%d.%m. %H:%M")


def _add_lead(
    maps: CommandingDict,
    wvw_map: str,
    note: str,
    name: str,
    uid: str | None = None,
) -> CommandingDict | None:
    mapping = _get_key(wvw_map)

    lead = f"[URL=client://0/{uid}]{name}[/URL]" if uid else name

    # Remove leads with the same name
    maps = _remove_lead(maps, name_field=lead)

    # Only allow two leads per map
    if len(maps[mapping]) >= MAX_LEADS_PER_MAP:
        return None

    maps[mapping].append(
        {"lead": lead, "note": note.strip()[0:20], "date": _tidy_date()}
    )
    return maps


def _remove_lead(
    maps: CommandingDict,
    name_field: str | None = None,
    uid: str | None = None,
) -> CommandingDict:
    def compare(_lead: LeadDict) -> bool:
        if uid:
            return uid not in _lead["lead"]

        return name_field != _lead["lead"]

    new_leads: CommandingDict = {"EBG": [], "Red": [], "Green": [], "Blue": []}
    for _map, leads in cast(IterType, maps.items()):
        new_leads[_map] = []
        for lead in leads:
            if compare(lead):
                new_leads[_map].append(lead)
    return new_leads


def _get_key(input_key: str) -> Literal["EBG", "Red", "Green", "Blue"]:
    if input_key == "ebg":
        return "EBG"
    elif input_key in ["red", "r"]:
        return "Red"
    elif input_key in ["green", "g"]:
        return "Green"

    return "Blue"  # This is filtered in handle(), it's fine this way


def _encode(s: str) -> str:
    return s.replace("[", "\\[").replace("]", "\\]")
