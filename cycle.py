#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import traceback

import mysql.connector as msql
import requests
import ts3

from common import fetch_account
from config import *

ENABLE_DESTRUCTIVE_ACTIONS = True

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger()

    with ts3.query.TS3ServerConnection(
        "{}://{}:{}@{}".format(TS3_PROTOCOL, CLIENT_USER, CLIENT_PASS, QUERY_HOST)
    ) as ts3c:
        ts3c.exec_("use", sid=SERVER_ID)
        ts3c.exec_("clientupdate", client_nickname=CLIENT_NICK + "_cycle")

        msqlc = None
        cur = None
        try:
            msqlc = msql.connect(
                user=SQL_USER,
                password=SQL_PASS,
                host=SQL_HOST,
                port=SQL_PORT,
                database=SQL_DB,
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
                AND TIMESTAMPDIFF( DAY , now( ) , `timestamp` ) <= -7
                GROUP BY
                    `name` 
                ORDER BY
                    `timestamp` ASC
                """
            )
            results = cur.fetchall()

            user_delete = []
            user_update = []

            server_ids = [x["id"] for x in SERVERS]

            full_len = len(results)
            progress_string = "{0}/{0}".format("{:0" + str(len(str(full_len))) + "d}")

            for counter, row in enumerate(results):
                try:
                    logging.info(
                        (progress_string + " ({:.02f}%) - Checking {} ({})").format(
                            counter, full_len, counter / full_len * 100, row[1], row[0]
                        )
                    )
                    json = fetch_account(row[0])
                    if (
                        not json or json.get("world") not in server_ids
                    ):  # Invalid API key or wrong world
                        tsuids = row[2].split("$$")
                        for tsuid in tsuids:
                            try:
                                cldbid = ts3c.exec_(
                                    "clientgetdbidfromuid", cluid=tsuid
                                )[0]["cldbid"]

                                if ENABLE_DESTRUCTIVE_ACTIONS:
                                    server_groups = ts3c.exec_(
                                        "servergroupsbyclientid", cldbid=cldbid
                                    )

                                    # Remove user from all non-whitelisted groups
                                    for server_group in server_groups:
                                        if server_group["name"] in GROUP_WHITELIST:
                                            continue
                                        try:
                                            ts3c.exec_(
                                                "servergroupdelclient",
                                                sgid=server_group["sgid"],
                                                cldbid=cldbid,
                                            )
                                        except ts3.TS3Error:
                                            # User most likely doesn't have the group
                                            logging.exception(
                                                "Failed to remove user's group for some reason."
                                            )

                                logging.info(
                                    "Removed {}'s ({}) permissions".format(
                                        row[1], tsuid
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
                    else:
                        user_update.append(row[1])
                except requests.RequestException:
                    logging.exception("API seems to be down, skipping execution")
                    exit(1)

            if ENABLE_DESTRUCTIVE_ACTIONS:
                # Delete users
                if len(user_delete) > 0:
                    delete_string = ",".join(["%s"] * len(user_delete))
                    cur.execute(
                        "DELETE FROM `users` WHERE `name` IN ({})".format(
                            delete_string
                        ),
                        user_delete,
                    )
                if len(user_update) > 0:
                    update_string = ",".join(["%s"] * len(user_update))
                    cur.execute(
                        "UPDATE `users` SET `timestamp` = CURRENT_TIMESTAMP WHERE `name` IN ({})".format(
                            update_string
                        ),
                        user_update,
                    )
                msqlc.commit()
        except msql.Error as err:
            logging.error(traceback.print_exc())
        finally:
            if cur:
                cur.close()
            if msqlc:
                msqlc.close()
