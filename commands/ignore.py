# -*- coding: utf-8 -*-

import logging
import typing

import mysql.connector as msql
import requests
import ts3

import common
import config
from bot import Bot

MESSAGE_REGEX = "!ignore +([A-Z0-9\\-]+)"
USAGE = "!ignore <API-KEY>"


def handle(bot: Bot, event: ts3.response.TS3Event, match: typing.Match):
    if event[0]["invokeruid"] not in config.WHITELIST["ADMIN"]:
        return

    msqlc = None
    cur = None
    try:
        json = common.fetch_account(match.group(1))
        if not json:
            logging.info("This seems to be an invalid API key.")
            bot.send_message(event[0]["invokerid"], "Ungültiger API-Key.")
            return

        msqlc = msql.connect(
            user=config.SQL_USER,
            password=config.SQL_PASS,
            host=config.SQL_HOST,
            port=config.SQL_PORT,
            database=config.SQL_DB,
        )
        cur = msqlc.cursor()

        # Grab distinct TS unique IDs
        cur.execute(
            "SELECT DISTINCT `tsuid` FROM `users` "
            "WHERE `ignored` = FALSE AND (`apikey` = %s OR `name` = %s)",
            (match.group(1), json.get("name")),
        )
        server_groups = []
        results = cur.fetchall()
        for result in results:
            try:
                cldbid = bot.ts3c.exec_("clientgetdbidfromuid", cluid=result[0])[0][
                    "cldbid"
                ]
                server_groups = common.remove_roles(bot.ts3c, cldbid, use_whitelist=False)
            except ts3.TS3Error:
                # User might not exist in the db, whatever
                pass

        cur.execute(
            "UPDATE `users` SET `ignored` = TRUE "
            "WHERE `ignored` = FALSE AND (`apikey` = %s OR `name` = %s)",
            (match.group(1), json.get("name")),
        )
        msqlc.commit()

        logging.info(
            "{} ({}) marked previous instances of {} as ignored".format(
                event[0]["invokername"], event[0]["invokeruid"], match.group(1)
            )
        )
        bot.send_message(
            event[0]["invokerid"],
            "Done! Rechte von {} vorherigen Nutzern entzogen. Gruppen: {}".format(
                len(results), [_["name"] for _ in server_groups]
            ),
        )
    except msql.Error as err:
        logging.exception("Failed to mark api key {} as ignored".format(match.group(1)))
        raise err
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
