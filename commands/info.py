import logging
import typing

import requests
import ts3

import common
from bot import Bot
from constants import STRINGS

MESSAGE_REGEX = "!info \\s*(\\w{8}(-\\w{4}){3}-\\w{20}(-\\w{4}){3}-\\w{12})\\s*"
USAGE = "!info <API-Key>"


def handle(bot: Bot, event: ts3.response.TS3Event, match: typing.Match):
    try:
        key = match.group(1)
        account = common.fetch_account(key)
        if account:
            server = account.get("world")

            for _ in SERVERS:
                if _["id"] == account.get("world"):
                    server = _["name"]

            bot.send_message(
                event[0]["invokerid"],
                STRINGS["info_world"].format(account.get("name"), server),
            )
        else:
            logging.info("This seems to be an invalid API key.")
            bot.send_message(event[0]["invokerid"], STRINGS["invalid_token"])
    except (requests.RequestException, common.RateLimitException):
        logging.exception("Error during API call")
        bot.send_message(event[0]["invokerid"], STRINGS["error_api"])


SERVERS = [
    {"id": 1001, "name": "Anvil Rock"},
    {"id": 1002, "name": "Borlis Pass"},
    {"id": 1003, "name": "Yak's Bend"},
    {"id": 1004, "name": "Henge of Denravi"},
    {"id": 1005, "name": "Maguuma"},
    {"id": 1006, "name": "Sorrow's Furnace"},
    {"id": 1007, "name": "Gate of Madness"},
    {"id": 1008, "name": "Jade Quarry"},
    {"id": 1009, "name": "Fort Aspenwood"},
    {"id": 1010, "name": "Ehmry Bay"},
    {"id": 1011, "name": "Stormbluff Isle"},
    {"id": 1012, "name": "Darkhaven"},
    {"id": 1013, "name": "Sanctum of Rall"},
    {"id": 1014, "name": "Crystal Desert"},
    {"id": 1015, "name": "Isle of Janthir"},
    {"id": 1016, "name": "Sea of Sorrows"},
    {"id": 1017, "name": "Tarnished Coast"},
    {"id": 1018, "name": "Northern Shiverpeaks"},
    {"id": 1019, "name": "Blackgate"},
    {"id": 1020, "name": "Ferguson's Crossing"},
    {"id": 1021, "name": "Dragonbrand"},
    {"id": 1022, "name": "Kaineng"},
    {"id": 1023, "name": "Devona's Rest"},
    {"id": 1024, "name": "Eredon Terrace"},
    {"id": 2001, "name": "Fissure of Woe"},
    {"id": 2002, "name": "Desolation"},
    {"id": 2003, "name": "Gandara"},
    {"id": 2004, "name": "Blacktide"},
    {"id": 2005, "name": "Ring of Fire"},
    {"id": 2006, "name": "Underworld"},
    {"id": 2007, "name": "Far Shiverpeaks"},
    {"id": 2008, "name": "Whiteside Ridge"},
    {"id": 2009, "name": "Ruins of Surmia"},
    {"id": 2010, "name": "Seafarer's Rest"},
    {"id": 2011, "name": "Vabbi"},
    {"id": 2012, "name": "Piken Square"},
    {"id": 2013, "name": "Aurora Glade"},
    {"id": 2014, "name": "Gunnar's Hold"},
    {"id": 2101, "name": "Jade Sea [FR]"},
    {"id": 2102, "name": "Fort Ranik [FR]"},
    {"id": 2103, "name": "Augury Rock [FR]"},
    {"id": 2104, "name": "Vizunah Square [FR]"},
    {"id": 2105, "name": "Arborstone [FR]"},
    {"id": 2201, "name": "Kodash [DE]"},
    {"id": 2202, "name": "Riverside [DE]"},
    {"id": 2203, "name": "Elona Reach [DE]"},
    {"id": 2204, "name": "Abaddon's Mouth [DE]"},
    {"id": 2205, "name": "Drakkar Lake [DE]"},
    {"id": 2206, "name": "Miller's Sound [DE]"},
    {"id": 2207, "name": "Dzagonur [DE]"},
    {"id": 2301, "name": "Baruch Bay [SP]"},
]
