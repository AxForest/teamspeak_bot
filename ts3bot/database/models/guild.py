import datetime
import logging
import typing

import ts3bot
from sqlalchemy import Column, types
from sqlalchemy.orm import Session, relationship
from ts3bot.database.models.base import Base

if typing.TYPE_CHECKING:
    from sqlalchemy.orm import RelationshipProperty

    from .link_account_guild import LinkAccountGuild


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

    members: "RelationshipProperty[LinkAccountGuild]" = relationship(
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
        session.commit()

        logging.info(f"Deleted {deleted} empty guilds")
