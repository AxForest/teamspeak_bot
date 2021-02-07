import logging
import typing

from sqlalchemy import Column, ForeignKey, and_, types
from sqlalchemy.orm import Session, relationship
from ts3bot.database.models.base import Base

if typing.TYPE_CHECKING:
    from sqlalchemy.orm import RelationshipProperty

    from .account import Account
    from .guild import Guild


class LinkAccountGuild(Base):  # type: ignore
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
    is_leader = Column(
        types.Boolean,
        default=False,
        nullable=False,
        doc="Whether the user has leader permission in this guild",
    )
    is_active = Column(
        types.Boolean,
        default=False,
        nullable=False,
        doc="Whether the group should be assigned",
    )

    account: "RelationshipProperty[Account]" = relationship(
        "Account", back_populates="guilds", cascade="all, delete"
    )
    guild: "RelationshipProperty[Guild]" = relationship(
        "Guild", back_populates="members", cascade="all, delete"
    )

    def __str__(self):
        return f"<LinkAccountGuild account={self.account.name} guild={self.guild.name} is_leader={self.is_leader}>"

    def __repr__(self):
        return str(self)

    @staticmethod
    def get_or_create(
        session: Session, account: "Account", guild: "Guild", is_leader: bool
    ):
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
