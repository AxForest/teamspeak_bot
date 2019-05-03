#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import re
from importlib import import_module

import ts3

import commands
import common
import config


class Bot:
    def __init__(self):
        self.commands = []
        # Register commands
        for _ in commands.__all__:
            mod = import_module("commands.{}".format(_))
            mod.REGEX = re.compile(mod.MESSAGE_REGEX)
            logging.info("Registered command.{}".format(_))
            self.commands.append(mod)

        # Connect to TS3
        self.ts3c = ts3.query.TS3ServerConnection(
            "{}://{}:{}@{}".format(
                config.TS3_PROTOCOL,
                config.CLIENT_USER,
                config.CLIENT_PASS,
                config.QUERY_HOST,
            )
        )

        # Select server and change nick
        self.ts3c.exec_("use", sid=config.SERVER_ID)
        self.ts3c.exec_("clientupdate", client_nickname=config.CLIENT_NICK)

        # Subscribe to events
        self.ts3c.exec_("servernotifyregister", event="channel", id=config.CHANNEL_ID)
        self.ts3c.exec_("servernotifyregister", event="textprivate")

        # Move to target channel
        self.own_id = self.ts3c.exec_("clientfind", pattern=config.CLIENT_NICK)[0][
            "clid"
        ]
        self.ts3c.exec_("clientmove", clid=self.own_id, cid=config.CHANNEL_ID)

    def loop(self):
        while True:
            self.ts3c.send_keepalive()
            try:
                event = self.ts3c.wait_for_event(timeout=60)
                # type: ts3.response.TS3Event
            except ts3.query.TS3TimeoutError:
                pass  # Ignore wait timeout
            else:
                # Ignore own events
                if (
                    "invokername" in event[0]
                    and event[0]["invokername"] == config.CLIENT_NICK
                    or "clid" in event[0]
                    and event[0]["clid"] == self.own_id
                ):
                    continue

                self.handle_event(event)

    def handle_event(self, event):
        if event.event == "notifyclientmoved":
            if event[0]["ctid"] == str(config.CHANNEL_ID):
                logging.info("User id:{} joined channel".format(event[0]["clid"]))
                self.send_message(
                    event[0]["clid"],
                    "Willkommen bei der automatischen Registrierung auf dem Kodash-TS. Bitte "
                    "schicken Sie mir Ihren API-Key, welchen Sie hier generieren können: < ["
                    "url=https://account.arena.net/applications]ArenaNet[/url] >",
                )
            else:
                logging.info("User id:{} left channel".format(event[0]["clid"]))
        elif event.event == "notifytextmessage":
            message = event[0]["msg"].strip()
            logging.info(
                "{} ({}): {}".format(
                    event[0]["invokername"], event[0]["invokeruid"], message
                )
            )

            valid_command = False
            for command in self.commands:
                match = command.REGEX.match(message)
                if match:
                    valid_command = True
                    try:
                        command.handle(self, event, match)
                    except ts3.query.TS3QueryError:
                        logging.exception(
                            "Unexpected TS3QueryError in command handler."
                        )
                    break

            if not valid_command:
                self.send_message(
                    event[0]["invokerid"],
                    msg="Sie haben eine ungültige Eingabe getätigt. Bitte versuchen Sie es erneut.",
                )

    def send_message(self, recipient: str, msg: str):
        try:
            logging.info("Response: {}".format(msg))
            self.ts3c.exec_("sendtextmessage", targetmode=1, target=recipient, msg=msg)
        except ts3.query.TS3Error:
            logging.exception(
                "Seems like the user I tried to message vanished into thin air"
            )


if __name__ == "__main__":
    common.init_logger("bot")
    Bot().loop()
