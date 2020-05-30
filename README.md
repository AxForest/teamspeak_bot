# teamspeak_bot
A TeamSpeak bot for assigning server groups based on the user's world in Guild Wars 2.

# Requirements 
* Python 3.6+
* Python libs listed in [Pipfile](Pipfile)
* pipenv or boredom
#### TS3 Requirements
* Generic guild and world groups to hold the permissions
* At least one server query login

# Installation/Usage
- Run `pipenv install` in the cloned repo/downloaded folder (or install everything by hand)
- Install the correct database flavour (e.g. `sqlalchemy[mysql]==1.3.*`)
    - Note: `sqlalchemy[mysql]` is required for migrating the old database
- Run the bot once via `pipenv run python -m ts3bot` to create an example config
- Set the required info in `config.ini`
- Run the bot inside tmux, screen, or as a service via `pipenv run python -m ts3bot bot`
- Run `pipenv run python -m ts3bot cycle` in regular intervals

# Updating
- Update dependencies via `pipenv sync`
- Run `pipenv run alembic upgrade heads` to run all migrations

# Notes
- The bot assumes that the guest group is still called `Guest`.
- The world group will always remain, even if a guild is selected.
- The database **HAS TO BE** utf8mb4/utf8mb4_bin or you will encounter strange issues.