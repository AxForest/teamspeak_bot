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

MESSAGE_REGEX = "!verify +([A-Za-z0-9+/=]+)"
USAGE = "!verify <TS Database ID|TS Unique ID>"


def handle(bot: Bot, event: ts3.response.TS3Event, match: typing.Match):
    if event[0]["invokeruid"] not in config.WHITELIST["ADMIN"]:
        return

    msqlc = None
    cur = None
    try:
        # Grab cluid
        try:
            if match.group(1).isdigit():  # DB id
                user = bot.ts3c.exec_("clientgetnamefromdbid", cldbid=match.group(1))
                cldbid = match.group(1)
                cluid = user[0]["cluid"]
            else:
                user = bot.ts3c.exec_("clientgetnamefromuid", cluid=match.group(1))
                cldbid = user[0]["cldbid"]
                cluid = match.group(1)
        except ts3.query.TS3QueryError:
            bot.send_message(event[0]["invokerid"], "verify_not_found")
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
            "SELECT `apikey` FROM `users` WHERE `ignored` = FALSE AND `tsuid` = %s ORDER BY `timestamp` DESC LIMIT 1",
            (cluid,),
        )
        row = cur.fetchone()

        if not row:
            bot.send_message(event[0]["invokerid"], "verify_no_token")
            return

        # Grab account
        account = common.fetch_account(row[0])
        if not account:
            bot.send_message(event[0]["invokerid"], "invalid_token")
            removed_groups = common.remove_roles(bot.ts3c, cldbid)
            bot.send_message(
                event[0]["invokerid"],
                "roles_removed",
                i18n_kwargs={"roles": removed_groups},
            )
            return
        world = account.get("world")

        # Grab server info from config
        server = common.find_world(world)

        # Server wasn't found in config
        if not server:
            removed_groups = common.remove_roles(bot.ts3c, cldbid)
            bot.send_message(
                event[0]["invokerid"],
                "verify_invalid_world",
                i18n_kwargs={
                    "world": common.world_name_from_id(world),
                    "roles": removed_groups,
                },
            )
        else:
            cur.execute(
                "UPDATE `users` SET `last_check` = CURRENT_TIMESTAMP, `guilds` = %s "
                "WHERE `apikey` = %s AND `ignored` = FALSE",
                (json.dumps(account.get("guilds", [])), row[0]),
            )
            msqlc.commit()
            bot.send_message(
                event[0]["invokerid"],
                "verify_valid_world",
                i18n_kwargs={"user": account.get("name"), "world": server["name"]},
            )
    except msql.Error:
        logging.exception("MySQL error in !verify.")
    except (requests.RequestException, common.RateLimitException):
        logging.exception("Error during API call")
        bot.send_message(event[0]["invokerid"], "error_api")
    finally:
        if cur:
            cur.close()
        if msqlc:
            msqlc.close()
