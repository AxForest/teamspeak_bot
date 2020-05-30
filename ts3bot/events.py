"""
Since TS3 loves to send partial events, these classes provide some abstraction
and somewhat sane defaults
"""

import logging
import typing

import ts3
from pydantic import BaseModel


class Event(BaseModel):
    @staticmethod
    def from_event(event: ts3.response.TS3Event) -> typing.Optional["Event"]:
        if event.event == "notifytextmessage":
            return TextMessage.from_event(event)
        elif event.event == "notifycliententerview":
            return ClientEnterView.from_event(event)
        elif event.event == "notifyclientleftview":
            return ClientLeftView.from_event(event)
        elif event.event == "notifyclientmoved":
            return ClientMoved.from_event(event)

        raise NotImplementedError


class ClientEnterView(Event):
    client_type: str = "42"
    database_id: str = None
    id: str = None
    uid: str = None

    @staticmethod
    def from_event(event: ts3.response.TS3Event) -> typing.Optional["ClientEnterView"]:
        try:
            return ClientEnterView(
                id=event[0]["clid"],
                database_id=event[0]["client_database_id"],
                uid=event[0]["client_unique_identifier"],
                client_type=event[0].get("client_type", "42"),
            )
        except KeyError:
            logging.warning("Partial event from TS: %s", event.data)
            return ClientEnterView()


class ClientLeftView(Event):
    id: str = None

    @staticmethod
    def from_event(event: ts3.response.TS3Event) -> typing.Optional["ClientLeftView"]:
        try:
            return ClientLeftView(id=event[0]["clid"])
        except KeyError:
            logging.warning("Partial event from TS: %s", event.data)
            return ClientLeftView()


class ClientMoved(Event):
    id: str = None
    channel_id: str = None

    @staticmethod
    def from_event(event: ts3.response.TS3Event) -> typing.Optional["ClientMoved"]:
        try:
            return ClientMoved(id=event[0]["clid"], channel_id=event[0].get("ctid", -1))
        except KeyError:
            logging.warning("Partial event from TS: %s", event.data)
        return ClientMoved()


class TextMessage(Event):
    message: str = None
    id: str = None
    uid: str = None
    name: str = None

    @staticmethod
    def from_event(event: ts3.response.TS3Event) -> typing.Optional["TextMessage"]:
        try:
            return TextMessage(
                id=event[0]["invokerid"],
                uid=event[0]["invokeruid"],
                name=event[0]["invokername"],
                message=event[0]["msg"].strip(),
            )
        except KeyError:
            logging.warning("Partial event from TS: %s", event.data)
            return TextMessage()
