from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_

from ts3bot.database import enums, models

from ._base import BaseTest, sample_data


class CycleAffectWorldsTest(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.session.add(
            models.Account(
                name="User.1234",
                world=enums.World.KODASH,
                api_key=sample_data.API_KEY_VALID,
                last_check=datetime(2020, 1, 1, 0, 0, 0, 0),
            )
        )
        self.session.add(
            models.Account(
                name="User.7895",
                world=enums.World.ABADDONS_MOUTH,
                api_key=sample_data.API_KEY_VALID,
                last_check=datetime(2020, 1, 2, 0, 0, 0, 0),
            )
        )
        self.session.add(
            models.Account(
                name="User.5417",
                world=enums.World.RIVERSIDE,
                api_key=sample_data.API_KEY_VALID,
                last_check=datetime(2020, 1, 3, 0, 0, 0, 0),
            )
        )
        self.session.add(
            models.Account(
                name="User.3256",
                world=enums.World.ARBORSTONE,
                api_key=sample_data.API_KEY_VALID,
                last_check=datetime(2020, 1, 3, 0, 0, 0, 0),
            )
        )
        self.session.commit()

    def test_is_linked_worlds(self) -> None:
        world = enums.World(enums.World.ABADDONS_MOUTH)

        def bla() -> Any:
            if world:
                return or_(
                    models.WorldGroup.is_linked.is_(True),
                    models.Account.world.is_(world),
                )
            else:
                return models.WorldGroup.is_linked.is_(True)

        accounts = (
            self.session.query(models.Account)
            .join(
                models.WorldGroup,
                models.Account.world == models.WorldGroup.world,
                isouter=True,
            )
            .filter(and_(bla(), models.Account.is_valid.is_(True)))
        )
        self.assertEqual(accounts.count(), 3)

    def test_linked_additional(self) -> None:
        accounts = (
            self.session.query(models.Account)
            .join(models.WorldGroup, models.Account.world == models.WorldGroup.world)
            .filter(
                and_(
                    models.WorldGroup.is_linked.is_(True),
                    models.Account.is_valid.is_(True),
                )
            )
        )
        self.assertEqual(accounts.count(), 2)

    def test_is_all(self) -> None:
        dt = datetime(2020, 1, 3, 0, 0, 0)
        accounts = self.session.query(models.Account).filter(
            and_(
                models.Account.last_check <= dt,
                models.Account.is_valid.is_(True),
            )
        )
        self.assertEqual(accounts.count(), 4)

    def test_regular(self) -> None:
        dt = datetime(2020, 1, 1, 1, 0, 0, 0)
        accounts = self.session.query(models.Account).filter(
            and_(
                models.Account.last_check <= dt - timedelta(hours=1),
                models.Account.is_valid.is_(True),
            )
        )
        self.assertEqual(accounts.count(), 1)
