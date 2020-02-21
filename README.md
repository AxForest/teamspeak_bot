# teamspeak_bot
A TeamSpeak bot for assigning server groups based on the user's world in Guild Wars 2.

# Requirements 
* Python 3.6+
* Python libs listed in [setup.py](setup.py)
#### TS3 Requirements
* Generic guild and world groups to hold the permissions
* At least one server query login

# Installation/Usage
- Run `pip3 install -e .` in the cloned repo/downloaded folder
- Install the correct database flavour (e.g. `sqlalchemy[mysql]==1.3.*`)
    - `sqlalchemy[mysql]` is required for migrating the old database
- Run the bot once via `python3 -m ts3bot` to create an example config
- Set the required info in `config.ini`
- Run the bot inside tmux, screen, or as a service via `python3 -m ts3bot bot`
- Run `python3 -m ts3bot cycle` in regular intervals

# Notes
- The bot assumes that the guest group is still called `Guest`
- The world group will always remain, even if a guild is selected