import datetime
import logging
from typing import TYPE_CHECKING, cast

from sqlalchemy import Column, types
from sqlalchemy.orm import Session, relationship
from sqlalchemy.sql import expression

import ts3bot
from ts3bot.database.models.base import Base

if TYPE_CHECKING:
    from .link_account_guild import LinkAccountGuild

LOG = logging.getLogger("ts3bot.models.guild")


class Guild(Base):  # type: ignore
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
    is_part_of_alliance = Column(
        types.Boolean, server_default=expression.false(), nullable=False
    )

    members = relationship("LinkAccountGuild", lazy="dynamic", back_populates="guild")
    created_at = Column(types.DateTime, default=datetime.datetime.now, nullable=False)

    def __str__(self) -> str:
        return f"<Guild guid={self.guid} name={self.name} tag={self.tag}>"

    def __repr__(self) -> str:
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
            LOG.debug("Creating guild %s", guid)
            instance = Guild.create(guid, group_id=group_id)
            session.add(instance)
            session.commit()
        else:
            if group_id:
                instance.group_id = group_id
            session.commit()

        return cast(Guild, instance)

    @staticmethod
    def create(guid: str, group_id: int = None) -> "Guild":
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
    def cleanup(session: Session) -> None:
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
        session.commit()

        LOG.info(f"Deleted {deleted} empty guilds")
