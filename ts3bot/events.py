"""
Since TS3 loves to send partial events, these classes provide some abstraction
and somewhat sane defaults
"""

import logging
from typing import Optional

import ts3  # type: ignore
from pydantic import BaseModel

LOG = logging.getLogger("ts3bot.events")


class Event(BaseModel):
    valid: bool = True

    @staticmethod
    def from_event(event: ts3.response.TS3Event) -> Optional["Event"]:
        if event.event == "notifytextmessage":
            return TextMessage.from_event(event)
        elif event.event == "notifycliententerview":
            return ClientEnterView.from_event(event)
        elif event.event == "notifyclientleftview":
            return ClientLeftView.from_event(event)
        elif event.event == "notifyclientmoved":
            return ClientMoved.from_event(event)

        LOG.critical("Got unknown TS3Event: %s", event.data)
        raise NotImplementedError(event.event)


class ClientEnterView(Event):
    client_type: str = ""
    database_id: str = ""
    id: str = ""
    uid: str = ""

    @staticmethod
    def from_event(event: ts3.response.TS3Event) -> Optional["ClientEnterView"]:
        try:
            return ClientEnterView(
                id=event[0]["clid"],
                database_id=event[0]["client_database_id"],
                uid=event[0]["client_unique_identifier"],
                client_type=event[0].get("client_type", "42"),
            )
        except KeyError:
            LOG.warning("Partial event from TS: %s", event.data)
            return ClientEnterView(valid=False)


class ClientLeftView(Event):
    id: str = ""

    @staticmethod
    def from_event(event: ts3.response.TS3Event) -> Optional["ClientLeftView"]:
        try:
            return ClientLeftView(id=event[0]["clid"])
        except KeyError:
            LOG.warning("Partial event from TS: %s", event.data)
            return ClientLeftView(valid=False)


class ClientMoved(Event):
    id: str = ""
    channel_id: str = ""

    @staticmethod
    def from_event(event: ts3.response.TS3Event) -> Optional["ClientMoved"]:
        try:
            return ClientMoved(id=event[0]["clid"], channel_id=event[0].get("ctid", -1))
        except KeyError:
            LOG.warning("Partial event from TS: %s", event.data)
        return ClientMoved(valid=False)


class TextMessage(Event):
    message: str = ""
    id: str = ""
    uid: str = ""
    name: str = ""

    @staticmethod
    def from_event(event: ts3.response.TS3Event) -> Optional["TextMessage"]:
        try:
            return TextMessage(
                id=event[0]["invokerid"],
                uid=event[0]["invokeruid"],
                name=event[0]["invokername"],
                message=event[0]["msg"].strip(),
            )
        except KeyError:
            LOG.warning("Partial event from TS: %s", event.data)
            return TextMessage(valid=False)
