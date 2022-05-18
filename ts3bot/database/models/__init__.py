from typing import Any, Type, TYPE_CHECKING, TypeVar

from sqlalchemy.sql.type_api import TypeEngine

from .account import Account, AccountUpdateDict
from .guild import Guild
from .identity import Identity
from .link_account_guild import LinkAccountGuild
from .link_account_identity import LinkAccountIdentity
from .world_group import WorldGroup

if TYPE_CHECKING:
    T = TypeVar("T")

    class SqlAlchemyEnum(TypeEngine[T]):
        # https://github.com/dropbox/sqlalchemy-stubs/issues/114
        def __init__(self, enum: Type[T], **kwargs: Any) -> None:
            ...
