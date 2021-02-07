import datetime
import typing

from sqlalchemy import Column, types
from sqlalchemy.orm import Session, relationship
from ts3bot.database.models.base import Base

if typing.TYPE_CHECKING:
    from sqlalchemy.orm import RelationshipProperty

    from .link_account_identity import LinkAccountIdentity


class Identity(Base):  # type: ignore
    """
    User's TS identity
    """

    __tablename__ = "identities"
    id = Column(types.Integer, primary_key=True)
    guid = Column(types.String(32), unique=True, nullable=False)

    accounts: "RelationshipProperty[LinkAccountIdentity]" = relationship(
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
