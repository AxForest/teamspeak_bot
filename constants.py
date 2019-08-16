STRINGS = {
    "already_registered": "Sie haben bereits die passende Servergruppe!",
    "available_commands": "\nVerfügbare Befehle:",
    "error_api": (
        "Fehler beim Abfragen der API. Bitte versuchen Sie es später erneut oder wenden Sie sich an "
        "einen Admin."
    ),
    "error_saving": "Fehler beim Speichern des API-Keys. Bitte kontaktieren Sie einen Admin.",
    "groups_revoked": "Done! Rechte von {} vorherigen Nutzern entzogen. Gruppen: {}",
    "groups_removed": "Folgende Gruppen wurden entfernt: {}",
    "guild_error": (
        "Beim Setzen der Gruppe ist ein Fehler aufgetreten. "
        "Bitte versuchen Sie es erneut."
    ),
    "guild_invalid_selection": (
        "Diese Gilde kenne ich leider nicht. Eine Auflistung Ihrer mir "
        "bekannten Gilden erhalten Sie via [b]!guild[/b]"
    ),
    "guild_not_in_guild": (
        "Sie sind nicht in dieser Gilde! Falls dies nicht stimmen sollte, wenden Sie sich an einen "
        "Admin oder warten sie ca. 24 Stunden, bis die API-Infos aktualisiert wurden."
    ),
    "guild_removed": "Gilden-Gruppe wurde erfolgreich entfernt.",
    "guild_selection": (
        "Die Auswahl geschieht per [b]!guild Gilden-Tag[/b]. "
        "Folgende Gilden stehen zur Auswahl:\n- {}\nFalls die "
        "Gilde entfernt werden soll, nutzen Sie [b]!guild remove[/b]."
    ),
    "guild_set": "{} wurde erfolgreich gesetzt.",
    "guild_unknown": "Scheinbar sind Sie in keiner mir bekannten Gilde.",
    "info_world": "Key ist gültig für {} auf Welt {}. Der Nutzer ist in folgenden bekannten Gilden: {}",
    "invalid_input": "Sie haben eine ungültige Eingabe getätigt. Bitte versuchen Sie es erneut.",
    "invalid_token": "Ungültiger API-Key.",
    "invalid_token_admin": "Der API-Key scheint ungültig zu sein. Bitte wenden Sie sich an einen Admin.",
    "invalid_token_retry": "Der API-Key scheint ungültig zu sein. Bitte versuchen Sie es erneut.",
    "invalid_world": (
        "Sie haben eine andere Welt gewählt. Falls sie vor kurzer Zeit "
        "ihre Heimatwelt gewechselt haben, versuchen Sie es in 24 Stunden "
        "erneut. Spion!"
    ),
    "legacy_removed": "Legacy-Gruppe erfolgreich entfernt.",
    "list_users": "\nEs sind {} Member in {}:",
    "list_50_users": (
        "Die Gruppe hat mehr als 50 Nutzer, Auflisten ist für "
        "Gruppen solcher Größe deaktiviert."
    ),
    "list_not_found": "Gruppe nicht gefunden!",
    "missing_token": "Es ist scheinbar kein API-Key hinterlegt!",
    "token_in_use": (
        "Dieser API-Key/Account ist bereits auf einen anderen Nutzer registiert. "
        "Bitte kontaktieren Sie einen Admin."
    ),
    "unknown_server": (
        "Der aktuell hinterlegte Server konnt nicht zugeordnet werden. "
        "Bitte wenden Sie sich an einen Admin."
    ),
    "verify_invalid_world": (
        "Der Nutzer ist derzeit auf einem unbekannten Server: {}. "
        "Folgende Gruppen wurden entfernt: {}"
    ),
    "verify_no_token": "User hat scheinbar keinen API-Key hinterlegt!",
    "verify_not_found": "User nicht gefunden!",
    "verify_valid_world": "Der Nutzer sieht sauber aus, hinterlegter Account ({}) ist auf {}.",
    "welcome": (
        "Willkommen bei der automatischen Registrierung auf dem Kodash-TS. "
        "Bitte schicken Sie mir Ihren API-Key, welchen Sie hier generieren können: "
        "[url]https://account.arena.net/applications[/url]"
    ),
    "welcome_registered": (
        "Willkommen auf dem Kodash-TS! Um alle Channels sehen zu können, verbinden Sie erneut, oder "
        "klicken sie auf die Sprechblase mit dem Auge über der Channel-Liste."
    ),
    "welcome_registered_2": (
        "Falls Sie zu einer Gilde gehören, die hier eine Servergruppe hat, kann diese per [b]!guild[/b] "
        "gewählt werden."
    ),
}

SERVERS = [
    {"id": 1001, "name": "Anvil Rock"},
    {"id": 1002, "name": "Borlis Pass"},
    {"id": 1003, "name": "Yak's Bend"},
    {"id": 1004, "name": "Henge of Denravi"},
    {"id": 1005, "name": "Maguuma"},
    {"id": 1006, "name": "Sorrow's Furnace"},
    {"id": 1007, "name": "Gate of Madness"},
    {"id": 1008, "name": "Jade Quarry"},
    {"id": 1009, "name": "Fort Aspenwood"},
    {"id": 1010, "name": "Ehmry Bay"},
    {"id": 1011, "name": "Stormbluff Isle"},
    {"id": 1012, "name": "Darkhaven"},
    {"id": 1013, "name": "Sanctum of Rall"},
    {"id": 1014, "name": "Crystal Desert"},
    {"id": 1015, "name": "Isle of Janthir"},
    {"id": 1016, "name": "Sea of Sorrows"},
    {"id": 1017, "name": "Tarnished Coast"},
    {"id": 1018, "name": "Northern Shiverpeaks"},
    {"id": 1019, "name": "Blackgate"},
    {"id": 1020, "name": "Ferguson's Crossing"},
    {"id": 1021, "name": "Dragonbrand"},
    {"id": 1022, "name": "Kaineng"},
    {"id": 1023, "name": "Devona's Rest"},
    {"id": 1024, "name": "Eredon Terrace"},
    {"id": 2001, "name": "Fissure of Woe"},
    {"id": 2002, "name": "Desolation"},
    {"id": 2003, "name": "Gandara"},
    {"id": 2004, "name": "Blacktide"},
    {"id": 2005, "name": "Ring of Fire"},
    {"id": 2006, "name": "Underworld"},
    {"id": 2007, "name": "Far Shiverpeaks"},
    {"id": 2008, "name": "Whiteside Ridge"},
    {"id": 2009, "name": "Ruins of Surmia"},
    {"id": 2010, "name": "Seafarer's Rest"},
    {"id": 2011, "name": "Vabbi"},
    {"id": 2012, "name": "Piken Square"},
    {"id": 2013, "name": "Aurora Glade"},
    {"id": 2014, "name": "Gunnar's Hold"},
    {"id": 2101, "name": "Jade Sea [FR]"},
    {"id": 2102, "name": "Fort Ranik [FR]"},
    {"id": 2103, "name": "Augury Rock [FR]"},
    {"id": 2104, "name": "Vizunah Square [FR]"},
    {"id": 2105, "name": "Arborstone [FR]"},
    {"id": 2201, "name": "Kodash [DE]"},
    {"id": 2202, "name": "Riverside [DE]"},
    {"id": 2203, "name": "Elona Reach [DE]"},
    {"id": 2204, "name": "Abaddon's Mouth [DE]"},
    {"id": 2205, "name": "Drakkar Lake [DE]"},
    {"id": 2206, "name": "Miller's Sound [DE]"},
    {"id": 2207, "name": "Dzagonur [DE]"},
    {"id": 2301, "name": "Baruch Bay [SP]"},
]
