import argparse
import enum
from typing import TYPE_CHECKING, Any, NoReturn

from ts3bot import events

if TYPE_CHECKING:
    from argparse import _SubParsersAction  # noqa


class UsageError(Exception):
    """General usage error"""


class WorldError(UsageError):
    """Invalid World ID"""


class ArgumentError(argparse.ArgumentError):
    """General argument error, e.g. missing or invalid"""

    def __str__(self) -> str:
        return self.message


class ArgParse(argparse.ArgumentParser):
    """
    Modified :py:class:`argparse.ArgumentParser` to raise specific errors per
    field and not quit.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        """Init shim to disable help on all sub parsers"""

        kwargs["add_help"] = False

        super().__init__(*args, **kwargs)

    def add_subparsers(self, **kwargs: Any) -> "_SubParsersAction":
        """
        Shim to overwrite parser_class, causing all sub parsers to have the
        same error handling
        """

        # Overwrite parser_class with this class
        kwargs["parser_class"] = type(self)

        return super().add_subparsers(**kwargs)

    def error(self, message: str) -> NoReturn:
        """Raises :py:class:`UsageError` instead of quitting"""

        raise UsageError(message)

    def _check_value(self, action: argparse.Action, value: Any) -> None:
        """
        Raises specific exception or default :py:class::`argparse.ArgumentError`
        """

        # converted value must be one of the choices (if specified)
        if action.choices is not None and value not in action.choices:
            # Raise world error if invalid world was used
            if action.dest == "world_id":
                raise WorldError()

            raise ArgumentError(
                action,
                (
                    f"Invalid choice: {value} "
                    f"(valid options: {', '.join(map(repr, action.choices))})"
                ),
            )

    def parse_event(self, event: events.TextMessage) -> argparse.Namespace:
        clear_message = event.message.replace(self.prog, "").strip()

        # No argument specified
        # .split would result in ['']
        if len(clear_message) == 0:
            return self.parse_args([])

        return self.parse_args(clear_message.split(" "))


class EnumAction(argparse.Action):
    """
    Argparse action for handling Enums

    Source: https://stackoverflow.com/a/60750535
    Author: https://stackoverflow.com/users/334972/tim

    Modified to (only) handle integer enums
    """

    def __init__(self, **kwargs: Any):
        # Pop off the type value
        enum_type = kwargs.pop("type", None)

        # Ensure an Enum subclass is provided
        if enum_type is None:
            raise ValueError("type must be assigned an Enum when using EnumAction")
        if not issubclass(enum_type, enum.Enum):
            raise TypeError("type must be an Enum when using EnumAction")

        # Generate choices from the enum
        kwargs.setdefault("choices", tuple(str(e.value) for e in enum_type))

        super().__init__(**kwargs)

        self._enum = enum_type

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        """Convert value back into an enum"""

        value = self._enum(int(values))
        setattr(namespace, self.dest, value)
