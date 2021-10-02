import logging.handlers
import os
import sys
from pathlib import Path
from typing import Any, Union

import ts3  # type: ignore

try:
    # Init version number
    import pkg_resources

    VERSION = pkg_resources.get_distribution("ts3bot").version
except pkg_resources.DistributionNotFound:
    VERSION = "unknown"


def data_path(path: Union[Path, str], is_folder: bool = False) -> Path:
    """Return a valid local data path, docker-aware"""

    if os.environ.get("RUNNING_IN_DOCKER", False):
        _path = Path("/data") / path
    else:
        _path = Path.cwd() / "data" / path

    folder = _path
    if not is_folder:
        folder = _path.parent

    # Create folders if necessarey
    if not folder.exists():
        os.makedirs(folder, exist_ok=True)

    return _path


def init_logger(name: str, is_test: bool = False) -> None:
    from ts3bot.config import Config

    log_folder = data_path("logs", is_folder=True)

    logger = logging.getLogger()

    if os.environ.get("ENV", "") == "dev":
        level = logging.DEBUG
    else:
        level = logging.INFO

    logger.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    # Only write to file outside of tests
    if not is_test:
        hldr = logging.handlers.TimedRotatingFileHandler(
            str(log_folder / f"{name}.log"), when="W0", encoding="utf-8", backupCount=16
        )

        hldr.setFormatter(fmt)
        logger.addHandler(hldr)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    stream.setLevel(level)
    logger.addHandler(stream)

    sentry_dsn = Config.get("sentry", "dsn")
    if sentry_dsn:
        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.sqlalchemy import (
            SqlalchemyIntegration,
        )  # type: ignore

        def before_send(event: Any, hint: Any) -> Any:
            if "exc_info" in hint:
                _, exc_value, _ = hint["exc_info"]
                if isinstance(exc_value, KeyboardInterrupt):
                    return None
            return event

        sentry_sdk.init(
            dsn=sentry_dsn,
            before_send=before_send,
            release=VERSION,
            send_default_pii=True,
            integrations=[SqlalchemyIntegration()],
        )
