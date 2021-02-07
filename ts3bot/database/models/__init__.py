import typing

from sqlalchemy.sql.type_api import TypeEngine

from .account import Account, AccountUpdateDict
from .guild import Guild
from .identity import Identity
from .link_account_guild import LinkAccountGuild
from .link_account_identity import LinkAccountIdentity
from .world_group import WorldGroup

if typing.TYPE_CHECKING:
    T = typing.TypeVar("T")

    class SqlAlchemyEnum(TypeEngine[T]):
        # https://github.com/dropbox/sqlalchemy-stubs/issues/114
        def __init__(self, enum: typing.Type[T], **kwargs: typing.Any) -> None:
            ...
