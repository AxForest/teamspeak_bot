from typing import TYPE_CHECKING

from sqlalchemy import Column, types

from ts3bot.database import enums
from ts3bot.database.models.base import Base

if TYPE_CHECKING:
    from . import SqlAlchemyEnum as Enum
else:
    from sqlalchemy import Enum


class WorldGroup(Base):  # type: ignore
    __tablename__ = "groups_world"

    id = Column(types.Integer, primary_key=True)
    group_id = Column(types.Integer, unique=True, nullable=False)
    world = Column(Enum(enums.World), unique=True, nullable=False)
    is_linked = Column(
        types.Boolean,
        nullable=False,
        default=False,
        doc="Whether the world shall get the generic permissions",
    )

    def __str__(self) -> str:
        return (
            f"<WorldGroup group_id={self.group_id} "
            f"world={self.world.proper_name} "
            f"is_linked={self.is_linked}>"
        )

    def __repr__(self) -> str:
        return str(self)
