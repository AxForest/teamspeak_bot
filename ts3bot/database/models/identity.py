import datetime
from typing import cast, TYPE_CHECKING

from sqlalchemy import Column, types
from sqlalchemy.orm import relationship, Session

from ts3bot.database.models.base import Base

if TYPE_CHECKING:
    from .link_account_identity import LinkAccountIdentity  # noqa: F401


class Identity(Base):  # type: ignore
    """
    User's TS identity
    """

    __tablename__ = "identities"
    id = Column(types.Integer, primary_key=True)
    guid = Column(types.String(32), unique=True, nullable=False)

    accounts = relationship(
        "LinkAccountIdentity", lazy="dynamic", back_populates="identity"
    )

    created_at = Column(types.DateTime, default=datetime.datetime.now, nullable=False)

    def __str__(self) -> str:
        return f"<Identity guid={self.guid}>"

    def __repr__(self) -> str:
        return str(self)

    @staticmethod
    def get_or_create(session: Session, guid: str) -> "Identity":
        """
        Returns an Identity instance, it is created if necessary
        """
        instance = session.query(Identity).filter(Identity.guid == guid).one_or_none()
        if not instance:
            instance = Identity(guid=guid)
            session.add(instance)
            session.commit()
        return cast("Identity", instance)
