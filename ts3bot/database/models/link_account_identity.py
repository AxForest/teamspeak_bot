import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, UniqueConstraint, types
from sqlalchemy.orm import relationship

from ts3bot.database.models.base import Base

if TYPE_CHECKING:
    from .account import Account  # noqa: F401
    from .identity import Identity  # noqa: F401


class LinkAccountIdentity(Base):  # type: ignore
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

    def __str__(self) -> str:
        return (
            f"<LinkAccountIdentity account={self.account.name} "
            f"identity={self.identity.guid} "
            f"is_deleted={self.is_deleted}>"
        )

    def __repr__(self) -> str:
        return str(self)
