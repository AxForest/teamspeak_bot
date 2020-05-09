import datetime
import logging
import re
import typing
from importlib import import_module
from pathlib import Path

import i18n
import requests
import ts3
from sqlalchemy import exc
from sqlalchemy.orm import Session, load_only, sessionmaker

import ts3bot
from ts3bot import commands
from ts3bot.config import Config
from ts3bot.database import models


class Bot:
    def __init__(self, session: Session, connect=True, is_cycle: bool = False):
        self.users: typing.Dict[str, ts3bot.User] = {}
        self.session = session
        self.is_cycle = is_cycle

        if is_cycle:
            self.client_nick = Config.get("cycle_login", "nickname")
            self.channel_id = None
        else:
            # Register commands
            self.commands = []
            for _ in commands.__all__:
                if Config.has_option("commands", _) and not Config.getboolean(
                    "commands", _
                ):
                    logging.info("Skipping command.%s", _)
                    continue

                mod = import_module(f"ts3bot.commands.{_}")
                mod.REGEX = re.compile(mod.MESSAGE_REGEX)
                logging.info("Registered command.%s", _)
                self.commands.append(mod)

            # Register translation settings
            i18n.set("load_path", [str(Path(__file__).parent / "i18n")])
            i18n.set("filename_format", "{locale}.json")
            i18n.set("enable_memoization", True)
            i18n.set("skip_locale_root_data", True)
            i18n.set("locale", "de")

            self.client_nick = Config.get("bot_login", "nickname")

        self.channel_id = Config.get("teamspeak", "channel_id")
        self.ts3c: typing.Optional[ts3.query.TS3ServerConnection] = None
        self.own_id: int = 0

        if connect:
            self.connect()

    def connect(self):
        if self.is_cycle:
            username = Config.get("cycle_login", "username")
            password = Config.get("cycle_login", "password")
        else:
            username = Config.get("bot_login", "username")
            password = Config.get("bot_login", "password")

        # Connect to TS3
        self.ts3c = ts3.query.TS3ServerConnection(
            "{}://{}:{}@{}".format(
                Config.get("teamspeak", "protocol"),
                username,
                password,
                Config.get("teamspeak", "hostname"),
            )
        )

        # Select server and change nick
        self.exec_("use", sid=Config.get("teamspeak", "server_id"))

        current_nick = self.exec_("whoami")
        if current_nick[0]["client_nickname"] != self.client_nick:
            self.exec_("clientupdate", client_nickname=self.client_nick)

        self.own_id: int = self.exec_("clientfind", pattern=self.client_nick)[0]["clid"]

        if not self.is_cycle:
            # Subscribe to events
            self.exec_("servernotifyregister", event="channel", id=self.channel_id)
            self.exec_("servernotifyregister", event="textprivate")
            self.exec_("servernotifyregister", event="server")

            # Move to target channel
            self.exec_("clientmove", clid=self.own_id, cid=self.channel_id)

    def exec_(self, cmd: str, *options, **params):
        return self.ts3c.exec_(cmd, *options, **params)

    def loop(self):
        while True:
            self.ts3c.send_keepalive()
            try:
                event: ts3.response.TS3Event = self.ts3c.wait_for_event(timeout=60)
            except ts3.query.TS3TimeoutError:
                pass  # Ignore wait timeout
            else:
                # Ignore own events
                if (
                    "invokername" in event[0]
                    and event[0]["invokername"] == self.client_nick
                    or "clid" in event[0]
                    and event[0]["clid"] == self.own_id
                ):
                    continue

                self.handle_event(event)

    def handle_event(self, event: ts3.response.TS3Event):
        # Got an event where the DB is relevant
        if event.event in ["notifycliententerview", "notifytextmessage"]:
            try:
                # Skip check when using SQLite
                if self.session.bind.name != "sqlite":
                    self.session.execute("SELECT VERSION()")
            except exc.DBAPIError as e:
                if e.connection_invalidated:
                    logging.debug("Database connection was invalidated")
                else:
                    raise
            finally:
                # Close session anyway to force-use a new connection
                self.session.close()

        if event.event == "notifycliententerview":  # User connected/entered view
            # Skip server query and other non-voice clients
            if event[0].get("client_type", 42) != "0":
                return

            clid = event[0].get("clid")
            if not clid:
                return

            self.create_user(clid)

            self.verify_user(
                event[0]["client_unique_identifier"],
                event[0]["client_database_id"],
                clid,
            )
        elif event.event == "notifyclientleftview":
            clid = event[0].get("clid")
            if clid in self.users:
                del self.users[clid]
        elif event.event == "notifyclientmoved":
            if event[0].get("ctid") == str(self.channel_id):
                logging.info("User id:%s joined channel", event[0].get("clid"))
                self.send_message(event[0].get("clid"), "welcome")
            else:
                logging.info("User id:%s left channel", event[0]["clid"])
        elif event.event == "notifytextmessage":
            message = event[0]["msg"].strip()
            logging.info(
                "%s (%s): %s", event[0]["invokername"], event[0]["invokeruid"], message
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
                self.send_message(event[0]["invokerid"], "invalid_input")

    def create_user(self, client_id: str):
        info = self.exec_("clientinfo", clid=client_id)
        self.users[client_id] = ts3bot.User(
            id=int(client_id),
            db_id=int(info[0]["client_database_id"]),
            unique_id=info[0]["client_unique_identifier"],
            nickname=info[0]["client_nickname"],
            country=info[0]["client_country"],
            total_connections=int(info[0]["client_totalconnections"]),
        )

    def send_message(
        self,
        recipient: str,
        msg: str,
        is_translation: bool = True,
        **i18n_kwargs: typing.AnyStr,
    ):
        if not recipient:
            logging.error("Got invalid recipient %s", recipient)
            return

        if is_translation:
            # Look up user's locale
            if recipient not in self.users:
                self.create_user(recipient)

            i18n.set("locale", self.users[recipient].locale)

            msg = i18n.t(msg, **i18n_kwargs)

        try:
            logging.info("Response: %s", msg)
            self.exec_("sendtextmessage", targetmode=1, target=recipient, msg=msg)
        except ts3.query.TS3Error:
            logging.exception(
                "Seems like the user I tried to message vanished into thin air"
            )

    def verify_user(
        self, client_unique_id: str, client_database_id: str, client_id: str
    ):
        def revoked(response: str):
            if account:
                account.invalidate(self.session)

            changes = ts3bot.sync_groups(
                self, client_database_id, account, remove_all=True
            )

            reason = "unknown reason"
            if response == "groups_revoked_missing_key":
                reason = "missing API key"
            elif response == "groups_revoked_invalid_key":
                reason = "invalid API key"

            logging.info(
                "Revoked user's (cldbid:%s) groups (%s) due to %s.",
                client_database_id,
                changes["removed"],
                reason,
            )
            self.send_message(client_id, response)

        # Get all current groups
        server_groups = self.exec_("servergroupsbyclientid", cldbid=client_database_id)

        known_groups: typing.List[int] = (
            [
                _.group_id
                for _ in self.session.query(ts3bot.database.models.WorldGroup).options(
                    load_only(ts3bot.database.models.WorldGroup.group_id)
                )
            ]
            + [
                _.group_id
                for _ in self.session.query(ts3bot.database.models.Guild)
                .filter(ts3bot.database.models.Guild.group_id.isnot(None))
                .options(load_only(ts3bot.database.models.Guild.group_id))
            ]
            + [
                int(Config.get("teamspeak", "generic_world_id")),
                int(Config.get("teamspeak", "generic_guild_id")),
            ]
        )

        # Check if user has any known groups
        has_group = False
        has_skip_group = False
        for server_group in server_groups:
            if int(server_group.get("sgid", -1)) in known_groups:
                has_group = True
            if server_group.get("name") in Config.whitelist_groups:
                has_skip_group = True

        # Skip users without any known groups or in skip group
        # Skip group = Whitelisted groups on users that should be ignored like
        # guests, music bots, etc
        if not has_group or has_skip_group:
            return

        # Grab user's account info
        account = models.Account.get_by_guid(self.session, client_unique_id)

        # User does not exist in DB
        if not account:
            revoked("groups_revoked_missing_key")
            return

        # User was checked today, don't check again
        if (datetime.datetime.today() - account.last_check).days < 1:
            return

        logging.debug("Checking %s/%s", account, client_unique_id)

        try:
            account.update(self.session)
            # Sync groups
            ts3bot.sync_groups(self, client_database_id, account)
        except ts3bot.InvalidKeyException:
            revoked("groups_revoked_invalid_key")
        except (requests.RequestException, ts3bot.RateLimitException):
            logging.exception("Error during API call")
            return
