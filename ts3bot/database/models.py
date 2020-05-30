import datetime
import logging
import typing

import requests
from sqlalchemy import Column, ForeignKey, UniqueConstraint, types, and_, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, joinedload
from sqlalchemy.orm.dynamic import AppenderQuery

import ts3bot
from ts3bot.database import enums

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)
Base = declarative_base(metadata=metadata)


class Identity(Base):
    """
    User's TS identity
    """

    __tablename__ = "identities"
    id = Column(types.Integer, primary_key=True)
    guid = Column(types.String(32), unique=True, nullable=False)

    accounts: AppenderQuery = relationship(
        "LinkAccountIdentity", lazy="dynamic", back_populates="identity"
    )

    created_at = Column(types.DateTime, default=datetime.datetime.now, nullable=False)

    def __str__(self):
        return f"<Identity guid={self.guid}>"

    def __repr__(self):
        return str(self)

    @staticmethod
    def get_or_create(session: Session, guid: str):
        """
        Returns an Identity instance, it is created if necessary
        """
        instance = session.query(Identity).filter(Identity.guid == guid).one_or_none()
        if not instance:
            instance = Identity(guid=guid)
            session.add(instance)
            session.commit()
        return instance


class Guild(Base):
    """
    GW2 guilds
    """

    __tablename__ = "guilds"

    id = Column(types.Integer, primary_key=True)
    guid = Column(types.String(36), unique=True, nullable=False)
    name = Column(types.String(255), nullable=False)  # Should be considered unique
    tag = Column(types.String(32), nullable=False)

    # TS3 group id
    group_id = Column(types.Integer, nullable=True)

    members: AppenderQuery = relationship(
        "LinkAccountGuild", lazy="dynamic", back_populates="guild"
    )
    created_at = Column(types.DateTime, default=datetime.datetime.now, nullable=False)

    def __str__(self):
        return f"<Guild guid={self.guid} name={self.name} tag={self.tag}>"

    def __repr__(self):
        return str(self)

    @staticmethod
    def get_or_create(session: Session, guid: str, group_id: int = None) -> "Guild":
        """
        Returns existing or inserted instance
        :param session: The current database session
        :param guid: The guild's GUID
        :param group_id: The guild's TS3 group_id, can be empty
        """
        instance = session.query(Guild).filter_by(guid=guid).one_or_none()
        if not instance:
            logging.debug("Creating guild %s", guid)
            instance = Guild.create(guid, group_id=group_id)
            session.add(instance)
            session.commit()
        else:
            if group_id:
                instance.group_id = group_id
            session.commit()

        return instance

    @staticmethod
    def create(guid: str, group_id: int = None):
        """
        Retrieves guild details from the API and returns an instance or None if the guild was not found
        :exception NotFoundException
        :exception RateLimitException
        :exception requests.RequestException
        """
        data = ts3bot.fetch_api(f"guild/{guid}")
        return Guild(
            guid=guid,
            name=data.get("name", "undefined"),
            tag=data.get("tag", "undefined"),
            group_id=group_id,
        )

    @staticmethod
    def cleanup(session: Session):
        """
        Removes all guilds without players
        :param session:
        :return:
        """
        deleted = (
            session.query(Guild)
            .filter(
                Guild.id.notin_(
                    session.query(LinkAccountGuild.guild_id)
                    .group_by(LinkAccountGuild.guild_id)
                    .subquery()
                )
            )
            .delete(synchronize_session="fetch")
        )

        logging.info(f"Deleted {deleted} empty guilds")


class Account(Base):
    """
    User's GW2 account
    """

    __tablename__ = "accounts"

    id = Column(types.Integer, primary_key=True)
    name = Column(types.String(41), unique=True, nullable=False)
    world: typing.Union[enums.World, int, str] = Column(
        types.Enum(enums.World), nullable=False
    )
    api_key = Column(types.String(72), nullable=False)

    guilds: AppenderQuery = relationship(
        "LinkAccountGuild", lazy="dynamic", back_populates="account"
    )

    identities: AppenderQuery = relationship(
        "LinkAccountIdentity", lazy="dynamic", back_populates="account"
    )

    is_valid = Column(types.Boolean, default=True, nullable=False)

    last_check = Column(types.DateTime, default=datetime.datetime.now, nullable=False)
    created_at = Column(types.DateTime, default=datetime.datetime.now, nullable=False)

    def __str__(self):
        return f"<Account name={self.name} world={self.world}>"

    def __repr__(self):
        return str(self)

    def world_group(self, session: Session) -> typing.Optional["WorldGroup"]:
        return (
            session.query(WorldGroup)
            .filter(WorldGroup.world == self.world)
            .one_or_none()
        )

    def guild_group(self) -> typing.Optional["LinkAccountGuild"]:
        # TODO: Introduce setting to allow multiple guild tags
        return (
            self.guilds.join(Guild)
            .filter(
                and_(Guild.group_id.isnot(None), LinkAccountGuild.is_active.is_(True))
            )
            .first()
        )

    @staticmethod
    def get_by_guid(session: Session, guid: str) -> typing.Optional["Account"]:
        return (
            session.query(Account)
            .join(LinkAccountIdentity)
            .join(Identity)
            .filter(LinkAccountIdentity.is_deleted.is_(False))
            .filter(Identity.guid == guid)
            .one_or_none()
        )

    @staticmethod
    def get_or_create(session: Session, account_info: dict, api_key: str):
        """
        Returns an Account instance, the account is created if necessary
        """
        instance = (
            session.query(Account)
            .filter(Account.name == account_info.get("name"))
            .one_or_none()
        )
        if not instance:
            instance = Account.create(account_info, api_key)
            session.add(instance)

            # Create guilds if necessary
            for guid in account_info.get("guilds", []):
                try:
                    guild = Guild.get_or_create(session, guid)
                    LinkAccountGuild.get_or_create(session, instance, guild)
                except (ts3bot.RateLimitException, requests.RequestException):
                    logging.warning("Failed to request guild info", exc_info=True)
            session.commit()
        return instance

    @staticmethod
    def create(account_info: dict, api_key: str):
        """
        Returns an instance based on given information
        """
        return Account(
            name=account_info.get("name"),
            world=enums.World(account_info.get("world")),
            api_key=api_key,
        )

    @property
    def valid_identities(self) -> AppenderQuery:
        return self.identities.filter(LinkAccountIdentity.is_deleted.is_(False))

    def invalidate(self, session: Session):
        """
        Removes identity associations and resets guild group
        :param session:
        :return:
        """
        self.valid_identities.update(
            {"deleted_at": datetime.datetime.now(), "is_deleted": True}
        )
        self.guilds.update({"is_active": False})

        session.commit()

    def update(self, session: Session) -> typing.Dict:
        """
        Updates and saves an accounts's detail
        :raises InvalidKeyException
        :raises RateLimitException
        :raises RequestException
        """
        logging.info("Updating account record for %s", self.name)

        result = {"transfer": None, "guilds": None}

        try:
            account_info = ts3bot.limit_fetch_api("account", api_key=self.api_key)

            # Update world
            new_world = enums.World(account_info.get("world"))
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
            guids_joined: typing.List[str] = []
            links_left: typing.List[int] = []
            guilds_left: typing.List[str] = []
            old_guilds: typing.List[str] = []

            # Collect left guilds
            link_guild: LinkAccountGuild
            for link_guild in self.guilds:
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
                LinkAccountGuild.get_or_create(session, self, guild)

            result["guilds"] = [guilds_joined, guilds_left]

            if len(guilds_joined) > 0:
                logging.info("%s joined new guilds: %s", self.name, guilds_joined)
            if len(guilds_left) > 0:
                logging.info("%s left guilds: %s", self.name, guilds_left)

            self.last_check = datetime.datetime.now()
            self.is_valid = True
        except ts3bot.InvalidKeyException:
            self.is_valid = False
            session.commit()
            raise

        session.commit()

        return result


# region TS groups
class WorldGroup(Base):
    __tablename__ = "groups_world"

    id = Column(types.Integer, primary_key=True)
    group_id = Column(types.Integer, unique=True, nullable=False)
    world: enums.World = Column(types.Enum(enums.World), unique=True, nullable=False)
    is_linked: bool = Column(
        types.Boolean,
        nullable=False,
        default=False,
        doc="Whether the world shall get the generic permissions",
    )

    def __str__(self):
        return f"<WorldGroup group_id={self.group_id} world={self.world.proper_name} is_linked={self.is_linked}>"

    def __repr__(self):
        return str(self)


# endregion

# region Many-to-Many relationships
class LinkAccountGuild(Base):
    """
    Relationship between accounts and guilds
    """

    __tablename__ = "link_account_guild"

    id = Column(types.Integer, primary_key=True)
    account_id = Column(
        types.Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    guild_id = Column(
        types.Integer, ForeignKey("guilds.id", ondelete="CASCADE"), nullable=False
    )
    is_active = Column(
        types.Boolean,
        default=False,
        nullable=False,
        doc="Whether the group should be assigned",
    )

    account = relationship("Account", back_populates="guilds", cascade="all, delete")
    guild = relationship("Guild", back_populates="members", cascade="all, delete")

    def __str__(self):
        return f"<LinkAccountGuild account={self.account.name} guild={self.guild.name}>"

    def __repr__(self):
        return str(self)

    @staticmethod
    def get_or_create(session: Session, account: Account, guild: Guild):
        instance = (
            session.query(LinkAccountGuild)
            .filter(
                and_(
                    LinkAccountGuild.account == account, LinkAccountGuild.guild == guild
                )
            )
            .one_or_none()
        )
        if not instance:
            logging.debug("Linking %s to %s", account.name, guild.name)
            instance = LinkAccountGuild(account=account, guild=guild)
            session.add(instance)
            session.commit()
        return instance


class LinkAccountIdentity(Base):
    """
    Relationship between TS3 identity and GW2 account
    """

    __tablename__ = "link_identity_account"

    # Prevent identity/account being registered multiple times
    __table_args__ = (
        UniqueConstraint("account_id", "is_deleted", "deleted_at"),
        UniqueConstraint("identity_id", "is_deleted", "deleted_at"),
    )

    id = Column(types.Integer, primary_key=True)
    account_id = Column(
        types.Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    identity_id = Column(
        types.Integer, ForeignKey("identities.id", ondelete="CASCADE"), nullable=False
    )

    account = relationship(
        "Account", back_populates="identities", cascade="all, delete"
    )
    identity = relationship(
        "Identity", back_populates="accounts", cascade="all, delete"
    )

    # Workaround for NULL and unique
    is_deleted = Column(types.Boolean, default=False, nullable=False)

    created_at = Column(types.DateTime, default=datetime.datetime.now, nullable=False)
    deleted_at = Column(types.DateTime, nullable=True)

    def __str__(self):
        return (
            f"<LinkAccountIdentity account={self.account.name} identity={self.identity.guid} "
            f"is_deleted={self.is_deleted}>"
        )

    def __repr__(self):
        return str(self)


# endregion
