# Commands

## API key
When a regular API key (not JWT) is pasted the bot will try to register the user based on this key.

## !guild (guild-tag)
`!guild` will respond with a list of currently available guilds, or tell the user that none of their guilds are available as server group.  
`!guild guild-tag` will apply the guild group, if it exists, and replace the current world permissions.

## !help (¬)
Shows a short list of all available commands, admin commands are currently also included.

## !ignore api-key (¬)
This will remove all* groups from TS3 identities linked to the GW2 account to allow a new user to register again.
The account/guild data is not removed, however guild groups will have to be selected again.

## !info api-key (¬)
Responds with the account name and a list of guilds with configured TS3 server group.

## !list server-group (¬+)
Returns a list of all users in that server group sorted by the nickname. Groups with over 50 users will not be listed as that has crashed the TS3 server before.

Called `list_group_members` in the config, has an additional whitelist to allow guild leaders to view their guild groups.  
Note that everyone in a whitelisted group will be able to list any group.

## !register database-id api-key (¬)
If the GW2 account is already registered, (generic) world and guild groups are transferred to the new user.
Otherwise the new user is simply registered as always. The new user's registration is overwritten, in case it exists.

## !sheet <ebg, red, green, blue, remove> [note]
Renders a little table in the channel description defined by `sheet_channel_id`.
Each map can have up to 2 leads, notes are up to 20 characters, admins can use a different syntax to set a lead manually.
Removing a lead or setting a note is currently not yet supported for admins.

Admin syntax: `!sheet set <ebg, red, green, blue> [lead name]`

Map | Lead | Note | Date
--- | --- | --- | ---
EBG | User | - | 05.07. 20:47
Red | Red Guard | Bring mesmers | 05.07. 20:47
Green | - | - | -
Blue | - | - | -

## !verify database-id|unique-id (¬)
Forces verification/group synchronisation immediately for specified user.  
Database id or global unique id of users can be either found via ServerQuery (I would recommend [YaTQA](https://yat.qa/)) or with a custom TS3 client theme like [Extended Client Info](https://www.myteamspeak.com/addons/45f5a52a-8e98-4a8b-ab69-0753c8d44617).

---
¬: Command is only available to admins listed in `[whitelist_admin]` in `config.ini`.  
\*: Only world/guild groups and groups listed in `[additional_guild_groups]` will be removed, all others are ignored.