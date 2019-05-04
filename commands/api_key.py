import json
import logging
import typing

import mysql.connector as msql
import requests
import ts3

import common
import config
from bot import Bot

MESSAGE_REGEX = "\\s*(\\w{8}(-\\w{4}){3}-\\w{20}(-\\w{4}){3}-\\w{12})\\s*"
USAGE = "<API-KEY>"


def handle(bot: Bot, event: ts3.response.TS3Event, match: typing.Match):
    key = match.group(1)

    # Check with ArenaNet's API
    try:
        account = common.fetch_account(key)
        if not account:
            logging.info("This seems to be an invalid API key.")
            bot.send_message(
                event[0]["invokerid"],
                "Der API-Key scheint ungültig zu sein. Bitte versuchen Sie es erneut.",
            )
            return
        world = account.get("world")

        # Grab server info from config
        server = None
        for s in config.SERVERS:
            if s["id"] == world:
                server = s
                break

        # World is in config
        if server:
            msqlc = None
            cur = None
            try:
                msqlc = msql.connect(
                    user=config.SQL_USER,
                    password=config.SQL_PASS,
                    host=config.SQL_HOST,
                    port=config.SQL_PORT,
                    database=config.SQL_DB,
                )
                cur = msqlc.cursor()

                # Check if API key/account was user previously by another uid
                cur.execute(
                    "SELECT COUNT(`id`), `name` FROM `users` WHERE `tsuid` != %s AND "
                    " (`apikey` = %s OR `name` = %s) AND `ignored` is FALSE",
                    (event[0]["invokeruid"], key, account.get("name")),
                )
                result = cur.fetchone()
                if result[0] > 0:  # Key is already registered
                    logging.warning(
                        "{} ({}) tried to use an already registered API key/account. ({})".format(
                            event[0]["invokername"],
                            event[0]["invokeruid"],
                            account.get("name"),
                        )
                    )
                    bot.send_message(
                        event[0]["invokerid"],
                        "Dieser API-Key/Account ist bereits auf einen anderen Nutzer registiert. "
                        "Bitte kontaktieren Sie einen Admin.",
                    )
                    return

                # Mark previous encounters using the same tsuid and account as ignored
                cur.execute(
                    "UPDATE `users` SET `ignored` = TRUE WHERE `tsuid` = %s AND `apikey` = %s",
                    (event[0]["invokeruid"], key),
                )
                # Save API key and user info in database
                cur.execute(
                    "INSERT INTO `users` (`name`, `world`, `apikey`, `tsuid`, `last_check`, `guilds`)"
                    "VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP(), %s)",
                    (
                        account.get("name"),
                        world,
                        key,
                        event[0]["invokeruid"],
                        json.dumps(account.get("guilds", [])),
                    ),
                )

                msqlc.commit()

                cldbid = bot.ts3c.exec_(
                    "clientgetdbidfromuid", cluid=event[0]["invokeruid"]
                )[0]["cldbid"]

                # Check if user has the legacy role
                server_groups = bot.ts3c.exec_("servergroupsbyclientid", cldbid=cldbid)
                is_legacy = False
                for group in server_groups:
                    if group["sgid"] == config.LEGACY_ANNOYANCE_GROUP:
                        is_legacy = True
                        break

                # Remove legacy group
                if is_legacy:
                    logging.info(
                        "Removed legacy group from user_db:{} ({})".format(
                            cldbid, event[0]["invokeruid"]
                        )
                    )
                    bot.ts3c.exec_(
                        "servergroupdelclient",
                        sgid=config.LEGACY_ANNOYANCE_GROUP,
                        cldbid=cldbid,
                    )

                # Assign configured role if user is not a legacy user
                if not is_legacy:
                    bot.ts3c.exec_(
                        "servergroupaddclient", sgid=server["group_id"], cldbid=cldbid
                    )
                logging.info(
                    "Assigned world {} to {} ({}) using {}".format(
                        server["name"],
                        event[0]["invokername"],
                        event[0]["invokeruid"],
                        account.get("name", "Unknown account"),
                    )
                )
                bot.send_message(
                    event[0]["invokerid"],
                    "Willkommen auf dem Kodash-TS! Um alle Channels sehen zu können, verbinden Sie erneut, oder "
                    "klicken sie auf die Sprechblase mit dem Auge über der Channel-Liste.",
                )
                bot.send_message(
                    event[0]["invokerid"],
                    "Falls Sie zu einer Gilde gehören, die hier eine Servergruppe hat, kann diese per [b]!guild[/b] "
                    "gewählt werden.",
                )

            except (ts3.TS3Error, msql.Error) as err:
                if (
                    isinstance(err, ts3.query.TS3QueryError)
                    and err.args[0].error["id"] == "2561"
                ):
                    logging.info(
                        "User {} ({}) registered a second time for whatever reason using {}".format(
                            event[0]["invokername"],
                            event[0]["invokeruid"],
                            account.get("name", "Unknown account"),
                        )
                    )
                    bot.send_message(
                        event[0]["invokerid"],
                        "Sie haben bereits die passende Servergruppe!",
                    )
                else:
                    logging.exception(
                        "Failed to assign server group to user uid:{}".format(
                            event[0]["invokeruid"]
                        )
                    )
                    bot.send_message(
                        event[0]["invokerid"],
                        "Fehler beim Speichern des API-Keys. Bitte kontaktieren Sie einen Admin.",
                    )
            finally:
                if cur:
                    cur.close()
                if msqlc:
                    msqlc.close()
        else:  # Invalid world on API
            logging.warning(
                "User {} ({}) is currently on world {} and tried to register using {}.".format(
                    event[0]["invokername"],
                    event[0]["invokeruid"],
                    world,
                    account.get("name", "Unknown account"),
                )
            )
            bot.send_message(
                event[0]["invokerid"],
                "Sie haben eine andere Welt gewählt. Falls sie vor kurzer Zeit "
                "ihre Heimatwelt gewechselt haben, versuchen Sie es in 24 Stunden "
                "erneut. Spion!",
            )
    except (
        requests.RequestException,
        common.RateLimitException,
    ):  # API seems to be down
        bot.send_message(
            event[0]["invokerid"],
            "Fehler beim Abfragen der API. Bitte versuchen Sie es später erneut oder wenden Sie sich an "
            "einen Admin.",
        )
