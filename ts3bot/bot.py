import datetime
import logging
import re
import types
from importlib import import_module
from pathlib import Path
from re import Match
from typing import Any, AnyStr, cast

import i18n  # type: ignore
import requests
import ts3  # type: ignore
from sqlalchemy import exc
from sqlalchemy.orm import Session, load_only
from ts3.response import TS3QueryResponse  # type: ignore

import ts3bot
from ts3bot import commands, events
from ts3bot.config import env
from ts3bot.database import models


class Command(types.ModuleType):
    MESSAGE_REGEX: str
    REGEX: re.Pattern
    USAGE: str

    @staticmethod
    def handle(bot: "Bot", event: events.TextMessage, match: Match) -> None:
        pass


class Bot:
    def __init__(
        self, session: Session, connect: bool = True, is_cycle: bool = False
    ) -> None:
        self.users: dict[str, ts3bot.User] = {}
        self.session = session
        self.is_cycle = is_cycle

        if is_cycle:
            self.client_nick = env.cycle_nickname
        else:
            # Register commands
            self.commands: list[Command] = []
            for _ in commands.__commands__:
                # Check if command is *not* in our list
                if _ not in env.commands:
                    logging.info("Skipping command.%s", _)
                    continue

                mod = cast(Command, import_module(f"ts3bot.commands.{_}"))
                mod.REGEX = re.compile(mod.MESSAGE_REGEX)
                logging.info("Registered command.%s", _)
                self.commands.append(mod)

            # Register translation settings
            i18n.set("load_path", [str(Path(__file__).parent / "i18n")])
            i18n.set("filename_format", "{locale}.json")
            i18n.set("enable_memoization", True)
            i18n.set("skip_locale_root_data", True)
            i18n.set("locale", "de")

            self.client_nick = env.bot_nickname

        self.ts3c: ts3.query.TS3ServerConnection | None = None
        self.own_id: int = 0
        self.own_uid: str = ""

        if connect:
            self.connect()

    def connect(self) -> None:
        if self.is_cycle:
            username = env.cycle_username
            password = env.cycle_password
        else:
            username = env.bot_username
            password = env.bot_password

        # Connect to TS3
        self.ts3c = ts3.query.TS3ServerConnection(
            "{}://{}:{}@{}".format(
                env.protocol,
                username,
                password,
                env.host,
            )
        )

        # Select server and change nick
        self.exec_("use", sid=env.server_id)

        current_nick = self.exec_("whoami")
        if current_nick[0]["client_nickname"] != self.client_nick:
            self.exec_("clientupdate", client_nickname=self.client_nick)

        # TODO: Replace clientfind/clientinfo with info from whoami
        self.own_id = self.exec_("clientfind", pattern=self.client_nick)[0]["clid"]
        self.own_uid = self.exec_("clientinfo", clid=self.own_id)[0][
            "client_unique_identifier"
        ]

        if not self.is_cycle:
            # Subscribe to events
            self.exec_("servernotifyregister", event="channel", id=env.channel_id)
            self.exec_("servernotifyregister", event="textprivate")
            self.exec_("servernotifyregister", event="server")

            # Move to target channel
            if current_nick[0]["client_channel_id"] != env.channel_id:
                self.exec_("clientmove", clid=self.own_id, cid=env.channel_id)

    def exec_(self, cmd: str, *options: Any, **params: Any) -> TS3QueryResponse:
        if not self.ts3c:
            raise ConnectionError("Not connected yet.")

        return self.ts3c.exec_(cmd, *options, **params)

    def loop(self) -> None:
        if not self.ts3c:
            raise ConnectionError("Not connected yet.")

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

    def handle_event(self, event: ts3.response.TS3Event) -> None:  # noqa: PLR0912
        evt = events.Event.from_event(event)

        # Drop event silently if invalid
        if not evt or not evt.valid:
            return

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

        if isinstance(evt, events.ClientEnterView):  # User connected/entered view
            # Skip server query and other non-voice clients
            if evt.client_type != "0":
                return

            was_created = self.create_user(evt.id)
            is_known = self.verify_user(evt.uid, evt.database_id, evt.id)

            # Skip next check if user could not be cached
            if not was_created:
                return

            # Message user if total_connections is below n and user is new
            if (
                not is_known
                and evt.id in self.users
                and -1
                < self.users[evt.id].total_connections
                <= env.annoy_total_connections
            ):
                self.send_message(
                    evt.id, "welcome_greet", con_limit=env.annoy_total_connections
                )

        elif isinstance(evt, events.ClientLeftView):
            if evt.id in self.users:
                del self.users[evt.id]
        elif isinstance(evt, events.ClientMoved):
            if evt.channel_id == str(env.channel_id):
                logging.info("User id:%s joined channel", evt.id)
                self.send_message(evt.id, "welcome")
            else:
                logging.info("User id:%s left channel", evt.id)
        elif isinstance(evt, events.TextMessage):
            if not evt.id:
                invoker_id = event[0].get("invokerid")
                if invoker_id:
                    self.send_message(invoker_id, "parsing_error")
                return

            logging.info("Message from %s (%s): %s", evt.name, evt.uid, evt.message)

            valid_command = False
            for command in self.commands:
                match = command.REGEX.match(evt.message)
                if match:
                    valid_command = True
                    try:
                        command.handle(self, evt, match)
                    except ts3.query.TS3QueryError:
                        logging.exception(
                            "Unexpected TS3QueryError in command handler."
                        )
                    break

            if not valid_command:
                self.send_message(evt.id, "invalid_input")
        else:
            logging.warning("Unexpected event: %s", event.data)

    def create_user(self, client_id: str) -> bool:
        """
        Caches the user into our local user list, returns False if an error occured or
        the user left too quickly
        :param client_id:
        :return:
        """
        try:
            info = self.exec_("clientinfo", clid=client_id)
            self.users[client_id] = ts3bot.User(
                id=int(client_id),
                db_id=int(info[0]["client_database_id"]),
                unique_id=info[0]["client_unique_identifier"],
                nickname=info[0].get("client_nickname", "Unknown"),
                country=info[0].get("client_country", ""),
                total_connections=int(info[0].get("client_totalconnections", -1)),
            )
            return True
        except ts3.TS3Error as e:
            if e.args[0].error["id"] == "512":
                # User went away, just ignore
                pass
            else:
                logging.exception("Failed to get client info for user")
        except KeyError:
            logging.exception("Failed to get client info for user")

        return False

    def send_message(
        self,
        recipient: str,
        msg: str,
        is_translation: bool = True,
        **i18n_kwargs: AnyStr | list | int | float,
    ) -> None:
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
            logging.info("Message to %s: %s", recipient, msg)
            self.exec_("sendtextmessage", targetmode=1, target=recipient, msg=msg)
        except ts3.query.TS3Error:
            logging.exception(
                "Seems like the user I tried to message vanished into thin air"
            )

    def verify_user(
        self, client_unique_id: str, client_database_id: str, client_id: str
    ) -> bool:
        """
        Verify a user if they are in a known group, otherwise nothing is done.
        Groups are revoked/updated if necessary

        :param client_unique_id: The client's UUID
        :param client_database_id: The database ID
        :param client_id: The client's temporary ID during the session
        :return: True if the user has/had a known group and False if the user is new
        """

        def revoked(response: str) -> None:
            l_account = cast(models.Account | None, account)
            if l_account:
                l_account.invalidate(self.session)

            changes = ts3bot.sync_groups(
                self, client_database_id, l_account, remove_all=True
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

        known_groups: list[int] = (
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
            + [env.generic_world_id, env.generic_guild_id]
        )

        # Check if user has any known groups
        has_group = False
        has_skip_group = False
        for server_group in server_groups:
            # Has a known server group
            if int(server_group.get("sgid", -1)) in known_groups:
                has_group = True

            # Has a server group that causes the user to be ignored
            if server_group.get("name") in env.join_verification_ignore:
                has_skip_group = True

        # Skip users without any known groups
        if not has_group:
            return False

        # Skip users in whitelisted groups that should be ignored like
        # guests, music bots, etc
        if has_skip_group:
            return True

        # Grab user's account info
        account = models.Account.get_by_identity(self.session, client_unique_id)

        # User does not exist in DB
        if not account:
            revoked("groups_revoked_missing_key")
            return True

        # User was checked, don't check again
        if (
            ts3bot.timedelta_hours(datetime.datetime.today() - account.last_check)
            < env.on_join_hours
        ):
            return True

        logging.debug("Checking %s/%s", account, client_unique_id)

        try:
            account.update(self.session)
            # Sync groups
            ts3bot.sync_groups(self, client_database_id, account)
        except ts3bot.InvalidKeyError:
            revoked("groups_revoked_invalid_key")
        except (
            requests.RequestException,
            ts3bot.RateLimitError,
            ts3bot.ApiErrBadDataError,
        ):
            logging.exception("Error during API call")

        return True
