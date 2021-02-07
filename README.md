# teamspeak_bot
A TeamSpeak bot for assigning server groups based on the user's world in Guild Wars 2.

# Requirements 
* Python 3.8+
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

### Usage of `cycle`
Cycle has additional switches, which allow you to
- only verify users on linked worlds (`--relink`*),
- verify everyone (`--all`*),
- only/also verify users on a certain world (`--world id`**),
- and also include all users currently known to TS3 (`--ts3`**).  

The last option is part of the default behaviour, where first everyone known to 
the TS3 server and then 
all other accounts in the database are checked***.  

These switches allow you to set the linked servers and only verify all related 
users before the relink hits the live servers for a smoother user experience
(e.g. `cycle --relink --world 2201` to verify the new link and remove the 
permissions of the previous link).

*: This will ignore `cycle_hours`  
**: These options can also be combined with `--relink`  
***: Where the last check was more than `cycle_hours` ago

# Updating
- Update dependencies via `pipenv sync`
- Run `pipenv run alembic upgrade heads` to run all migrations

# Notes
- The bot assumes that the guest group is still called `Guest`.
- The world group will always remain, even if a guild is selected.
- The database **HAS TO BE** utf8mb4/utf8mb4_bin or you will encounter strange issues.
- A guild tag must be unique, meaning there cannot be two guilds with the same tag mapped to a server group.