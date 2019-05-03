#!/usr/bin/python3
# -*- coding: utf-8 -*-
import json
import logging
import time

import mysql.connector as msql
import ratelimit
import requests
import ts3

import common
import config


def limit_fetch_account(api_key):
    while True:
        try:
            return common.fetch_account(api_key)
        except ratelimit.RateLimitException as exception:
            logging.info("Ran into the soft API limit, waiting a bit.")
            time.sleep(exception.period_remaining)
        except common.RateLimitException:
            logging.warning("Got rate-limited, waiting 10 minutes.")
            time.sleep(60 * 10)


if __name__ == "__main__":
    logger = common.init_logger("cycle")

    with ts3.query.TS3ServerConnection(
        "{}://{}:{}@{}".format(
            config.TS3_PROTOCOL, config.CYCLE_USER, config.CYCLE_PASS, config.QUERY_HOST
        )
    ) as ts3c:
        ts3c.exec_("use", sid=config.SERVER_ID)
        ts3c.exec_("clientupdate", client_nickname="Bicycle")

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

            # This isn't perfect at all but it works nicely
            cur.execute(
                """
                SELECT
                    SUBSTRING_INDEX( GROUP_CONCAT( DISTINCT `apikey` ORDER BY `timestamp` DESC SEPARATOR ',' ), ',', 1 ),
                    `name`,
                    GROUP_CONCAT( DISTINCT `tsuid` SEPARATOR '$$' )
                FROM
                    `users`
                WHERE
                    `ignored` = FALSE 
                AND (TIMESTAMPDIFF( DAY , now( ) , `last_check` ) <= -7 OR `last_check` IS NULL)
                GROUP BY
                    `name`
                ORDER BY
                    `last_check` ASC
                LIMIT 500
                """
            )
            results = cur.fetchall()

            user_delete = []

            server_ids = [x["id"] for x in config.SERVERS]

            full_len = len(results)
            progress_string = "{0}/{0}".format("{:0" + str(len(str(full_len))) + "d}")

            for counter, row in enumerate(results):
                try:
                    logging.info(
                        (progress_string + " ({:3.0f}%) - Checking {} ({})").format(
                            counter + 1,
                            full_len,
                            (counter + 1) / full_len * 100,
                            row[1],
                            row[0],
                        )
                    )

                    account = limit_fetch_account(row[0])
                    if (
                        not account or account.get("world") not in server_ids
                    ):  # Invalid API key or wrong world
                        tsuids = row[2].split("$$")
                        for tsuid in tsuids:
                            try:
                                cldbid = ts3c.exec_(
                                    "clientgetdbidfromuid", cluid=tsuid
                                )[0]["cldbid"]

                                server_groups = common.remove_roles(ts3c, cldbid)

                                if not account:
                                    reason = "Invalid API key."
                                elif account.get("world") not in server_ids:
                                    reason = "Invalid world: {}".format(
                                        account.get("world")
                                    )
                                else:
                                    reason = "No fucking clue."

                                logging.info(
                                    "Removed {}'s ({}) permissions. Groups: {}. Reason: {}".format(
                                        row[1],
                                        tsuid,
                                        [_["name"] for _ in server_groups],
                                        reason,
                                    )
                                )
                            except (ts3.TS3Error, msql.Error) as err:
                                if (
                                    isinstance(err, ts3.query.TS3QueryError)
                                    and err.args[0].error["id"] == "512"
                                ):
                                    # Client ID doesn't exist on server, whatever
                                    pass
                                else:
                                    logging.exception(
                                        "Failed to remove user's row or permissions"
                                    )
                        user_delete.append(row[1])
                        cur.execute(
                            "DELETE FROM `users` WHERE `name` IN ({})".format(row[1])
                        )
                    else:
                        # TODO: Remove user from guild on update
                        cur.execute(
                            "UPDATE `users` SET `last_check` = CURRENT_TIMESTAMP(), `guilds` = %s "
                            "WHERE `apikey` = %s AND `ignored` = FALSE",
                            (json.dumps(account.get("guilds", [])), row[0]),
                        )
                except requests.RequestException:
                    logging.exception("API seems to be down, skipping execution")
                    msqlc.commit()
                    exit(1)

                msqlc.commit()
        except msql.Error:
            logging.exception("MySQL error.")
        finally:
            if cur:
                cur.close()
            if msqlc:
                msqlc.close()

        # Disconnect gracefully
        ts3c.close()
