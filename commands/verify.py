# -*- coding: utf-8 -*-

import json
import logging
import typing

import mysql.connector as msql
import requests
import ts3

import common
import config
from bot import Bot

MESSAGE_REGEX = "!verify +(\\d+)"
USAGE = "!verify <TS-Datenbank-ID>"


def handle(bot: Bot, event: ts3.response.TS3Event, match: typing.Match):
    if event[0]["invokeruid"] not in config.WHITELIST["ADMIN"]:
        return

    msqlc = None
    cur = None
    try:
        # Grab cluid
        try:
            user = bot.ts3c.exec_("clientgetnamefromdbid", cldbid=match.group(1))
            cluid = user[0]["cluid"]
        except ts3.query.TS3QueryError:
            bot.send_message(event[0]["invokerid"], "User nicht gefunden!")
            return

        # Connect to MySQL
        msqlc = msql.connect(
            user=config.SQL_USER,
            password=config.SQL_PASS,
            host=config.SQL_HOST,
            port=config.SQL_PORT,
            database=config.SQL_DB,
        )
        cur = msqlc.cursor()

        # Grab user's latest API key
        cur.execute(
            "SELECT `apikey` FROM `users` WHERE `ignored` = FALSE AND `tsuid` = %s ORDER BY `timestamp` LIMIT 1",
            (cluid,),
        )
        row = cur.fetchone()

        if not row:
            bot.send_message(
                event[0]["invokerid"], "User hat scheinbar keinen API-Key hinterlegt!"
            )
            return

        # Grab account
        account = common.fetch_account(row[0])
        if not account:
            bot.send_message(
                event[0]["invokerid"], msg="Der API-Key scheint ungültig zu sein."
            )
            return
        world = account.get("world")

        # Grab server info from config
        server = None
        for s in config.SERVERS:
            if s["id"] == world:
                server = s
                break

        # Server wasn't found in config
        if not server:
            server_groups = common.remove_roles(bot.ts3c, match.group(1))
            bot.send_message(
                event[0]["invokerid"],
                msg="Der Nutzer ist derzeit auf einem unbekannten Server: {}. Folgende Gruppen wurden entfernt: {}".format(
                    world,
                    [_["name"] for _ in server_groups]
                ),
            )
        else:
            cur.execute(
                "UPDATE `users` SET `last_check` = CURRENT_TIMESTAMP, `guilds` = %s WHERE `apikey` = %s AND `ignored` = FALSE",
                (json.dumps(account.get("guilds", [])), row[0]),
            )
            bot.send_message(
                event[0]["invokerid"],
                msg="Der Nutzer sieht sauber aus, hinterlegter Account ({}) ist auf {}.".format(
                    account.get("name"), server["name"]
                ),
            )
    except msql.Error:
        logging.exception("MySQL error in !verify.")
    except (requests.RequestException, common.RateLimitException):
        logging.exception("Error during API call")
        bot.send_message(
            event[0]["invokerid"],
            "Fehler beim Abrufen der API. Bitte versuche es später erneut.",
        )
    finally:
        if cur:
            cur.close()
        if msqlc:
            msqlc.close()