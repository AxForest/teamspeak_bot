import enum

WORLDS = {
    1001: "Anvil Rock",
    1002: "Borlis Pass",
    1003: "Yak's Bend",
    1004: "Henge of Denravi",
    1005: "Maguuma",
    1006: "Sorrow's Furnace",
    1007: "Gate of Madness",
    1008: "Jade Quarry",
    1009: "Fort Aspenwood",
    1010: "Ehmry Bay",
    1011: "Stormbluff Isle",
    1012: "Darkhaven",
    1013: "Sanctum of Rall",
    1014: "Crystal Desert",
    1015: "Isle of Janthir",
    1016: "Sea of Sorrows",
    1017: "Tarnished Coast",
    1018: "Northern Shiverpeaks",
    1019: "Blackgate",
    1020: "Ferguson's Crossing",
    1021: "Dragonbrand",
    1022: "Kaineng",
    1023: "Devona's Rest",
    1024: "Eredon Terrace",
    2001: "Fissure of Woe",
    2002: "Desolation",
    2003: "Gandara",
    2004: "Blacktide",
    2005: "Ring of Fire",
    2006: "Underworld",
    2007: "Far Shiverpeaks",
    2008: "Whiteside Ridge",
    2009: "Ruins of Surmia",
    2010: "Seafarer's Rest",
    2011: "Vabbi",
    2012: "Piken Square",
    2013: "Aurora Glade",
    2014: "Gunnar's Hold",
    2101: "Jade Sea [FR]",
    2102: "Fort Ranik [FR]",
    2103: "Augury Rock [FR]",
    2104: "Vizunah Square [FR]",
    2105: "Arborstone [FR]",
    2201: "Kodash [DE]",
    2202: "Riverside [DE]",
    2203: "Elona Reach [DE]",
    2204: "Abaddon's Mouth [DE]",
    2205: "Drakkar Lake [DE]",
    2206: "Miller's Sound [DE]",
    2207: "Dzagonur [DE]",
    2301: "Baruch Bay [SP]",
}


class World(enum.Enum):
    # NA
    ANVIL_ROCK: int = 1001
    BORLIS_PASS: int = 1002
    YAKS_BEND: int = 1003
    HENGE_OF_DENRAVI: int = 1004
    MAGUUMA: int = 1005
    SORROWS_FURNACE: int = 1006
    GATE_OF_MADNESS: int = 1007
    JADE_QUARRY: int = 1008
    FORT_ASPENWOOD: int = 1009
    EHMRY_BAY: int = 1010
    STORMBLUFF_ISLE: int = 1011
    DARKHAVEN: int = 1012
    SANCTUM_OF_RALL: int = 1013
    CRYSTAL_DESERT: int = 1014
    ISLE_OF_JANTHIR: int = 1015
    SEA_OF_SORROWS: int = 1016
    TARNISHED_COAST: int = 1017
    NORTHERN_SHIVERPEAKS: int = 1018
    BLACKGATE: int = 1019
    FERGUSONS_CROSSING: int = 1020
    DRAGONBRAND: int = 1021
    KAINENG: int = 1022
    DEVONAS_REST: int = 1023
    EREDON_TERRACE: int = 1024

    # EU
    FISSURE_OF_WOE: int = 2001
    DESOLATION: int = 2002
    GANDARA: int = 2003
    BLACKTIDE: int = 2004
    RING_OF_FIRE: int = 2005
    UNDERWORLD: int = 2006
    FAR_SHIVERPEAKS: int = 2007
    WHITESIDE_RIDGE: int = 2008
    RUINS_OF_SURMIA: int = 2009
    SEAFARERS_REST: int = 2010
    VABBI: int = 2011
    PIKEN_SQUARE: int = 2012
    AURORA_GLADE: int = 2013
    GUNNARS_HOLD: int = 2014
    # French
    JADE_SEA: int = 2101
    FORT_RANIK: int = 2102
    AUGURY_ROCK: int = 2103
    VIZUNAH_SQUARE: int = 2104
    ARBORSTONE: int = 2105
    # German
    KODASH: int = 2201
    RIVERSIDE: int = 2202
    ELONA_REACH: int = 2203
    ABADDONS_MOUTH: int = 2204
    DRAKKAR_LAKE: int = 2205
    MILLERS_SOUND: int = 2206
    DZAGONUR: int = 2207
    # Spanish
    BARUCH_BAY: int = 2301

    @property
    def proper_name(self) -> str:
        return WORLDS[self.value]
