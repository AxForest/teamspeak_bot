import datetime
import logging
from typing import TYPE_CHECKING, List, Optional, Tuple, TypedDict, cast

import requests
from sqlalchemy import Column, and_, or_, types
from sqlalchemy.orm import Session, relationship
from sqlalchemy.orm.dynamic import AppenderQuery

import ts3bot
from ts3bot.database import enums
from ts3bot.database.models.base import Base

from .guild import Guild
from .identity import Identity
from .world_group import WorldGroup
from .link_account_guild import LinkAccountGuild
from .link_account_identity import LinkAccountIdentity

if TYPE_CHECKING:
    from ts3bot.database.models import SqlAlchemyEnum as Enum
else:
    from sqlalchemy import Enum

AccountUpdateDict = TypedDict(
    "AccountUpdateDict",
    {
        "transfer": List[enums.World],
        "guilds": Tuple[List[str], List[str]],
    },
)


class Account(Base):  # type: ignore
    """
    User's GW2 account
    """

    __tablename__ = "accounts"

    id = Column(types.Integer, primary_key=True)
    # TODO: Make non-NULL after GUID migration
    guid = Column(types.String(36), unique=True, nullable=True)
    name = Column(types.String(41), unique=True, nullable=False)
    world = Column(Enum(enums.World), nullable=False)
    api_key = Column(types.String(72), nullable=False)

    guilds = relationship(
        "LinkAccountGuild", lazy="dynamic", back_populates="account", uselist=True
    )

    identities = relationship(
        "LinkAccountIdentity", lazy="dynamic", back_populates="account", uselist=True
    )

    is_valid = Column(types.Boolean, default=True, nullable=False)
    retries = Column(types.Integer, default=0, nullable=False)

    last_check = Column(types.DateTime, default=datetime.datetime.now, nullable=False)
    created_at = Column(types.DateTime, default=datetime.datetime.now, nullable=False)

    def __str__(self) -> str:
        return f"<Account name={self.name} world={self.world}>"

    def __repr__(self) -> str:
        return str(self)

    def world_group(self, session: Session) -> Optional["WorldGroup"]:
        return (
            session.query(WorldGroup)
            .filter(WorldGroup.world == self.world)
            .one_or_none()
        )

    def guild_groups(self) -> List["LinkAccountGuild"]:
        return cast(
            List["LinkAccountGuild"],
            cast(AppenderQuery, self.guilds)
            .join(Guild)
            .filter(
                and_(Guild.group_id.isnot(None), LinkAccountGuild.is_active.is_(True))
            )
            .all(),
        )

    @staticmethod
    def get_by_identity(session: Session, guid: str) -> Optional["Account"]:
        return cast(
            Optional["Account"],
            session.query(Account)
            .join(LinkAccountIdentity)
            .join(Identity)
            .filter(LinkAccountIdentity.is_deleted.is_(False))
            .filter(Identity.guid == guid)
            .one_or_none(),
        )

    @staticmethod
    def get_by_api_info(session: Session, guid: str, name: str) -> Optional["Account"]:
        # TODO: Remove name after GUID migration
        return (
            session.query(Account)
            .filter(or_(Account.guid == guid, Account.name == name))
            .one_or_none()
        )

    @staticmethod
    def get_or_create(session: Session, account_info: dict, api_key: str) -> "Account":
        """
        Returns an Account instance, the account is created if necessary
        """
        # Get account by guid or name
        instance = Account.get_by_api_info(
            session, guid=account_info.get("id", ""), name=account_info.get("name", "")
        )
        if not instance:
            instance = cast(Account, Account.create(account_info, api_key))
            session.add(instance)

            # Create guilds if necessary
            for guid in account_info.get("guilds", []):
                try:
                    guild = Guild.get_or_create(session, guid)
                    is_leader = guid in account_info.get("guild_leader", [])
                    LinkAccountGuild.get_or_create(session, instance, guild, is_leader)
                except (ts3bot.RateLimitException, requests.RequestException):
                    logging.warning("Failed to request guild info", exc_info=True)
            session.commit()
        return instance

    @staticmethod
    def create(account_info: dict, api_key: str) -> "Account":
        """
        Returns an instance based on given information
        """
        return Account(
            guid=account_info.get("id", ""),
            name=account_info.get("name", ""),
            world=enums.World(account_info.get("world")),
            api_key=api_key,
        )

    @property
    def valid_identities(self) -> AppenderQuery:
        return cast(AppenderQuery, self.identities).filter(
            LinkAccountIdentity.is_deleted.is_(False)
        )

    def invalidate(self, session: Session) -> None:
        """
        Removes identity associations and resets guild group
        :param session:
        :return:
        """
        self.valid_identities.update(
            {"deleted_at": datetime.datetime.now(), "is_deleted": True}
        )
        cast(AppenderQuery, self.guilds).update({"is_active": False})

        session.commit()

    def update(self, session: Session) -> AccountUpdateDict:
        """
        Updates and saves an accounts's detail
        :raises InvalidKeyException
        :raises RateLimitException
        :raises RequestException
        """
        logging.info("Updating account record for %s", self.name)

        result: AccountUpdateDict = AccountUpdateDict(transfer=[], guilds=([], []))

        try:
            account_info = ts3bot.limit_fetch_api("account", api_key=self.api_key)

            # TODO: Remove after GUID migration is done
            if not self.guid:
                self.guid = account_info.get("id", "UNKNOWN")

            # Update world
            new_world = cast(enums.World, enums.World(account_info.get("world")))
            if new_world != self.world:
                result["transfer"] = [self.world, new_world]

                logging.info(
                    "%s transferred from %s to %s",
                    self.name,
                    self.world.proper_name,
                    new_world.proper_name,
                )
                self.world = new_world

            # Update name, changes rarely
            new_name = account_info.get("name")
            if new_name != self.name:
                logging.info("%s got renamed to %s", self.name, new_name)

            # Update guilds
            account_guilds = account_info.get("guilds", [])
            guids_joined: List[str] = []
            links_left: List[int] = []
            guilds_left: List[str] = []
            old_guilds: List[str] = []

            # Collect left guilds
            link_guild: LinkAccountGuild
            for link_guild in cast(AppenderQuery, self.guilds):
                old_guilds.append(link_guild.guild.guid)

                if link_guild.guild.guid not in account_guilds:
                    links_left.append(link_guild.id)
                    guilds_left.append(link_guild.guild.name)

            # Collect new guilds
            guild_guid: str
            for guild_guid in account_guilds:
                if guild_guid not in old_guilds:
                    guids_joined.append(guild_guid)

            # Process guild leaves
            if len(links_left) > 0:
                session.query(LinkAccountGuild).filter(
                    LinkAccountGuild.id.in_(links_left)
                ).delete(synchronize_session="fetch")

            # Process guild joins
            guilds_joined = []
            for guild_guid in guids_joined:
                guild = Guild.get_or_create(session, guild_guid)
                guilds_joined.append(guild.name)
                is_leader = guild.guid in account_info.get("guild_leader", [])
                LinkAccountGuild.get_or_create(session, self, guild, is_leader)

            # Process all current guilds for leader status
            for link_guild in self.guilds:
                # Skip new guilds
                if link_guild.guild.guid in guids_joined:
                    continue

                # Update leader status
                link_guild.is_leader = link_guild.guild.guid in account_info.get(
                    "guild_leader", []
                )

            result["guilds"] = (guilds_joined, guilds_left)

            if len(guilds_joined) > 0:
                logging.info("%s joined new guilds: %s", self.name, guilds_joined)
            if len(guilds_left) > 0:
                logging.info("%s left guilds: %s", self.name, guilds_left)

            self.last_check = datetime.datetime.now()
            self.is_valid = True
            if self.retries > 0:
                logging.info(
                    "%s was valid again after %s retries.", self.name, self.retries
                )
                self.retries = 0
        except ts3bot.InvalidKeyException:
            if self.retries >= 3:
                self.is_valid = False
                logging.info(
                    "%s was invalid after 3 retries, marking as invalid.", self.name
                )
                raise
            else:
                logging.info(
                    "%s was invalid in this attempt, increasing counter to %s",
                    self.name,
                    self.retries + 1,
                )
                self.retries += 1
        finally:
            session.commit()

        return result
