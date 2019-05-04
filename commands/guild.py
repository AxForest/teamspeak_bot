import datetime
import logging
import typing
import json

import mysql.connector as msql
import requests
import ts3

import common
import config
from bot import Bot

MESSAGE_REGEX = "!guild *([\\w ]+)?"
USAGE = "!guild [Gildenname]"


def handle(bot: Bot, event: ts3.response.TS3Event, match: typing.Match):
    msqlc = None
    cur = None
    try:
        cluid = event[0]["invokeruid"]
        cldbid = bot.ts3c.exec_("clientgetdbidfromuid", cluid=event[0]["invokeruid"])[
            0
        ]["cldbid"]

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
            """
            SELECT `apikey`, `last_check`, `guilds`, `world`
            FROM `users`
            WHERE `ignored` = FALSE
            AND `tsuid` = %s
            ORDER BY `timestamp`
            LIMIT 1
            """,
            (cluid,),
        )
        row = cur.fetchone()

        if not row:
            bot.send_message(
                event[0]["invokerid"], "Es ist scheinbar kein API-Key hinterlegt!"
            )
            return

        if row[2]:
            guilds = json.loads(row[2])
        else:
            guilds = []

        # Saved account is older than one day, was never checked, or has no guilds
        if (
            not row[1]
            or (datetime.datetime.today() - row[1]).days >= 1
            or len(guilds) == 0
        ):
            logging.info("Fetching user's guilds.")
            # Grab account
            account = common.fetch_account(row[0])

            # API key seems to be invalid, revoke roles
            if not account:
                common.remove_roles(bot.ts3c, cldbid)
                logging.info("Revoked user's permissions.")
                bot.send_message(
                    event[0]["invokerid"],
                    "Der API-Key scheint ungültig zu sein. Bitte wenden Sie sich an einen Admin.",
                )
                return

            guilds = account.get("guilds", [])

            # Save user's guilds
            cur.execute(
                "UPDATE `users` SET `guilds` = %s, `last_check` = CURRENT_TIMESTAMP()"
                "WHERE `ignored` = FALSE AND `tsuid` = %s",
                (json.dumps(guilds), cluid),
            )
            msqlc.commit()

        # No guild specified
        if not match.group(1):
            # Search for possible guilds
            available_guilds = []
            for guild in guilds:
                if guild in config.GUILDS:
                    available_guilds.append(config.GUILDS[guild][0])

            if len(available_guilds) > 0:
                bot.send_message(
                    event[0]["invokerid"],
                    "Die Auswahl geschieht per [b]!guild Gilden-Tag[/b]. "
                    "Folgende Gilden stehen zur Auswahl:\n- {}\nFalls die "
                    "Gilde entfernt werden soll, nutzen Sie [b]!guild remove[/b].".format(
                        "\n- ".join(available_guilds)
                    ),
                )
            else:
                bot.send_message(
                    event[0]["invokerid"],
                    "Scheinbar sind Sie in keiner mir bekannten Gilde.",
                )
        else:
            guild = match.group(1).lower()

            # User requested guild removal
            if guild == "remove":
                common.remove_roles(bot.ts3c, cldbid)
                common.assign_server_role(bot, row[3], event[0]["invokerid"], cldbid)

                bot.send_message(
                    event[0]["invokerid"], "Gilden-Gruppe wurde erfolgreich entfernt."
                )
                return

            guild_info = None
            for c_guild in config.GUILDS:
                if config.GUILDS[c_guild][0].lower() == guild:
                    guild_info = {
                        "guid": c_guild,
                        "name": config.GUILDS[c_guild][0],
                        "id": config.GUILDS[c_guild][1],
                    }

            # Guild not found
            if not guild_info:
                bot.send_message(
                    event[0]["invokerid"],
                    "Diese Gilde kenne ich leider nicht. Eine Auflistung Ihrer mir "
                    "bekannten Gilden erhalten Sie via [b]!guild[/b]",
                )
                return

            if guild_info["guid"] not in guilds:
                bot.send_message(
                    event[0]["invokerid"],
                    "Sie sind nicht in dieser Gilde! Falls dies nicht stimmen sollte, wenden Sie sich an einen "
                    "Admin oder warten sie ca. 24 Stunden, bis die API-Infos aktualisiert wurden.",
                )
                return

            # Remove other roles
            common.remove_roles(bot.ts3c, cldbid)

            # Assign guild
            try:
                bot.ts3c.exec_("servergroupaddclient", sgid=guild_info["id"], cldbid=cldbid)
            except ts3.query.TS3QueryError as err:
                logging.critical("Failed to assign guild group to user.")
                bot.send_message(
                    event[0]["invokerid"],
                    "Beim Setzen der Gruppe ist ein Fehler aufgetreten. "
                    "Bitte versuchen Sie es erneut.",
                )
                return

            bot.send_message(
                event[0]["invokerid"],
                "{} wurde erfolgreich gesetzt.".format(guild_info["name"]),
            )
    except msql.Error:
        logging.exception("MySQL error in !guild.")
    except (requests.RequestException, common.RateLimitException):
        logging.exception("Error during API call")
        bot.send_message(
            event[0]["invokerid"],
            "Fehler beim Abrufen der API. Bitte versuchen Sie später erneut.",
        )
    finally:
        if cur:
            cur.close()
        if msqlc:
            msqlc.close()
