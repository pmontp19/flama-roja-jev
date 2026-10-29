from __future__ import annotations

"""Dades estàtiques mínimes de combat (Gen 3) per calcular dany determinista.

Noms anglesos com a species.py. Cobertura: moves primerencs de FRLG i tipus
d'espècies de Kanto primerenques; el que falta es tracta com a neutre/sense poder.
"""

TYPE_NAMES = (
    "Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost",
    "Steel", "?", "Fire", "Water", "Grass", "Electric", "Psychic", "Ice",
    "Dragon", "Dark",
)

# tipus especials = ids >= 10 (Fire..Dark); fisics = 0..8 (Normal..Steel); 9 = Mystery
SPECIAL_TYPES = frozenset(range(10, 18))

# id -> (nom, tipus, poder); poder -1 = dany fix = nivell de l'atacant
MOVES: dict[int, tuple[str, int, int]] = {
    1: ("Pound", 0, 40), 2: ("Karate Chop", 1, 50), 3: ("Double Slap", 0, 15),
    5: ("Mega Punch", 0, 80), 6: ("Pay Day", 0, 40), 7: ("Fire Punch", 10, 75),
    8: ("Ice Punch", 15, 75), 9: ("Thunder Punch", 13, 75), 10: ("Scratch", 0, 40),
    11: ("Vice Grip", 0, 55), 13: ("Razor Wind", 0, 80), 14: ("Swords Dance", 0, 0),
    15: ("Cut", 0, 50), 16: ("Gust", 2, 40), 17: ("Wing Attack", 2, 60),
    19: ("Fly", 2, 70), 20: ("Bind", 0, 15), 21: ("Slam", 0, 80),
    22: ("Vine Whip", 12, 35), 23: ("Stomp", 0, 65), 24: ("Double Kick", 1, 30),
    25: ("Mega Kick", 0, 120), 26: ("Jump Kick", 1, 70), 27: ("Rolling Kick", 1, 60),
    28: ("Sand Attack", 4, 0), 29: ("Headbutt", 0, 70), 30: ("Horn Attack", 0, 65),
    31: ("Fury Attack", 0, 15), 33: ("Tackle", 0, 35), 34: ("Body Slam", 0, 85),
    35: ("Wrap", 0, 15), 36: ("Take Down", 0, 90), 37: ("Thrash", 0, 90),
    38: ("Double Edge", 0, 120), 39: ("Tail Whip", 0, 0), 40: ("Poison Sting", 3, 15),
    41: ("Twineedle", 6, 25), 42: ("Pin Missile", 6, 14), 43: ("Leer", 0, 0),
    44: ("Bite", 17, 60), 45: ("Growl", 0, 0), 46: ("Roar", 0, 0),
    47: ("Sing", 0, 0), 48: ("Supersonic", 0, 0), 49: ("Sonic Boom", 0, -2),
    51: ("Acid", 3, 40), 52: ("Ember", 10, 40), 53: ("Flamethrower", 10, 95),
    55: ("Water Gun", 11, 40), 56: ("Hydro Pump", 11, 120), 57: ("Surf", 11, 95),
    58: ("Ice Beam", 15, 95), 59: ("Blizzard", 15, 120), 60: ("Psybeam", 14, 65),
    61: ("Bubble Beam", 11, 65), 62: ("Aurora Beam", 15, 65), 63: ("Hyper Beam", 0, 150),
    64: ("Peck", 2, 35), 65: ("Drill Peck", 2, 80), 66: ("Submission", 1, 80),
    67: ("Low Kick", 1, 50), 69: ("Seismic Toss", 1, -1), 70: ("Strength", 0, 80),
    71: ("Absorb", 12, 20), 72: ("Mega Drain", 12, 40), 73: ("Leech Seed", 12, 0),
    74: ("Growth", 0, 0), 75: ("Razor Leaf", 12, 55), 76: ("Solar Beam", 12, 120),
    77: ("Poison Powder", 3, 0), 78: ("Stun Spore", 12, 0), 79: ("Sleep Powder", 12, 0),
    80: ("Petal Dance", 12, 70), 81: ("String Shot", 6, 0), 82: ("Dragon Rage", 16, -3),
    83: ("Fire Spin", 10, 15), 84: ("Thunder Shock", 13, 40), 85: ("Thunder Bolt", 13, 95),
    86: ("Thunder Wave", 13, 0), 87: ("Thunder", 13, 120), 88: ("Rock Throw", 5, 50),
    89: ("Earthquake", 4, 100), 91: ("Dig", 4, 60), 92: ("Toxic", 3, 0),
    93: ("Confusion", 14, 50), 94: ("Psychic", 14, 90), 95: ("Hypnosis", 14, 0),
    96: ("Meditate", 14, 0), 97: ("Agility", 14, 0), 98: ("Quick Attack", 0, 40),
    99: ("Rage", 0, 20), 100: ("Teleport", 14, 0), 101: ("Night Shade", 7, -1),
    102: ("Mimic", 0, 0), 103: ("Screech", 0, 0), 104: ("Double Team", 0, 0),
    105: ("Recover", 0, 0), 106: ("Harden", 0, 0), 107: ("Minimize", 0, 0),
    108: ("Smokescreen", 0, 0), 109: ("Confuse Ray", 7, 0), 110: ("Withdraw", 11, 0),
    111: ("Defense Curl", 0, 0), 113: ("Light Screen", 14, 0), 114: ("Haze", 15, 0),
    115: ("Reflect", 14, 0), 116: ("Focus Energy", 0, 0), 118: ("Metronome", 0, 0),
    120: ("Self Destruct", 0, 130), 122: ("Lick", 7, 20), 123: ("Smog", 3, 20),
    124: ("Sludge", 3, 65), 125: ("Bone Club", 4, 65), 126: ("Fire Blast", 10, 120),
    127: ("Waterfall", 11, 80), 129: ("Swift", 0, 60), 130: ("Skull Bash", 11, 100),
    132: ("Constrict", 0, 10), 135: ("Soft Boiled", 0, 0), 136: ("High Jump Kick", 1, 85),
    137: ("Glare", 0, 0), 138: ("Dream Eater", 14, 100), 141: ("Leech Life", 6, 20),
    143: ("Sky Attack", 2, 140), 145: ("Bubble", 11, 20), 147: ("Spore", 12, 0),
    148: ("Flash", 0, 0), 149: ("Psywave", 14, -1), 150: ("Splash", 0, 0),
    152: ("Crabhammer", 11, 90), 153: ("Explosion", 0, 250), 154: ("Fury Swipes", 0, 18),
    155: ("Bonemerang", 4, 50), 156: ("Rest", 14, 0), 157: ("Rock Slide", 5, 75),
    158: ("Hyper Fang", 0, 80), 163: ("Slash", 0, 70), 164: ("Substitute", 0, 0),
    165: ("Struggle", 0, 50), 168: ("Thief", 17, 40), 173: ("Flail", 0, -1),
    175: ("Aeroblast", 2, 100), 179: ("Powder Snow", 15, 40), 180: ("Protect", 0, 0),
    181: ("Mach Punch", 1, 40), 182: ("Feint Attack", 17, 60), 185: ("Sludge Bomb", 3, 90),
    186: ("Mud Slap", 4, 20), 189: ("Zap Cannon", 13, 100), 193: ("Icy Wind", 15, 55),
    196: ("Outrage", 16, 90), 198: ("Steel Wing", 8, 70), 203: ("Return", 0, 102),
    205: ("Frustration", 0, 102), 206: ("Safeguard", 0, 0), 207: ("Pain Split", 0, 0),
    209: ("Magnitude", 4, 70), 210: ("Dynamic Punch", 1, 100), 211: ("Megahorn", 6, 120),
    212: ("Dragon Breath", 16, 60), 215: ("Pursuit", 17, 40), 216: ("Rapid Spin", 0, 20),
    218: ("Iron Tail", 8, 100), 219: ("Metal Claw", 8, 50), 220: ("Vital Throw", 1, 70),
    226: ("Rock Smash", 1, 20), 228: ("Pursuit", 17, 60), 232: ("Metal Sound", 8, 0),
    233: ("Iron Defense", 8, 0), 235: ("Synthesis", 12, 0), 239: ("Twister", 16, 40),
    240: ("Rain Dance", 11, 0), 241: ("Sunny Day", 10, 0), 244: ("Bonemerang", 4, 50),
    249: ("Rock Tomb", 5, 50), 250: ("Water Pulse", 11, 60), 253: ("Covet", 0, 40),
    256: ("Gust", 2, 40), 257: ("Flatter", 17, 0), 258: ("Will O Wisp", 10, 0),
    263: ("Facade", 0, 70), 264: ("Focus Punch", 1, 150), 267: ("Nature Power", 0, 0),
    269: ("Taunt", 17, 0), 270: ("Helping Hand", 0, 0), 280: ("Knock Off", 17, 20),
    282: ("Endeavor", 0, -1), 283: ("Skill Swap", 14, 0), 287: ("Refresh", 0, 0),
    289: ("Snatch", 17, 0), 290: ("Secret Power", 0, 70), 291: ("Dive", 11, 60),
    292: ("Arm Thrust", 1, 15), 295: ("Rock Blast", 5, 25), 297: ("Poison Tail", 3, 50),
    298: ("Covet", 0, 60), 299: ("Blaze Kick", 10, 85), 300: ("Bulk Up", 1, 0),
    302: ("Aerial Ace", 2, 60), 303: ("Iron Defense", 8, 0), 308: ("Hyper Voice", 0, 90),
    310: ("Astonish", 7, 30), 311: ("Weather Ball", 0, 50), 312: ("Aromatherapy", 12, 0),
    313: ("Fake Tears", 17, 0), 314: ("Air Cutter", 2, 55), 316: ("Rock Tomb", 5, 50),
    317: ("Silver Wind", 6, 60), 318: ("Grass Whistle", 12, 0), 319: ("Tickle", 0, 0),
    320: ("Cosmic Power", 14, 0), 324: ("Signal Beam", 6, 75), 325: ("Shadow Punch", 7, 60),
    326: ("Extrasensory", 14, 80), 328: ("Sky Uppercut", 1, 85), 329: ("Sand Tomb", 4, 15),
    330: ("Sheer Cold", 15, -1), 331: ("Muddy Water", 11, 95), 332: ("Bullet Seed", 12, 10),
    333: ("Aerial Ace", 2, 60), 334: ("Icicle Spear", 15, 10), 335: ("Iron Defense", 8, 0),
    338: ("Covet", 0, 40), 339: ("Magical Leaf", 12, 60), 341: ("Mud Shot", 4, 55),
    342: ("Poison Fang", 3, 50), 344: ("Volt Tackle", 13, 120), 345: ("Magical Leaf", 12, 60),
    347: ("Water Sport", 11, 0), 348: ("Calm Mind", 14, 0), 349: ("Leaf Blade", 12, 90),
    350: ("Dragon Dance", 16, 0), 351: ("Shock Wave", 13, 60), 352: ("Water Pulse", 11, 60),
    353: ("Doom Desire", 8, 120), 354: ("Psycho Boost", 14, 140),
}

# (tipus atac, tipus defensa) -> multiplicador; només efectivitats != 1 (Gen 3)
TYPE_CHART: dict[tuple[int, int], float] = {
    (0, 5): 0.5, (0, 8): 0.5, (0, 7): 0.0,
    (1, 0): 2.0, (1, 5): 2.0, (1, 8): 2.0, (1, 15): 2.0, (1, 17): 2.0,
    (1, 2): 0.5, (1, 3): 0.5, (1, 6): 0.5, (1, 14): 0.5, (1, 7): 0.0,
    (2, 1): 2.0, (2, 6): 2.0, (2, 12): 2.0, (2, 5): 0.5, (2, 8): 0.5, (2, 13): 0.5,
    (3, 12): 2.0, (3, 3): 0.5, (3, 4): 0.5, (3, 5): 0.5, (3, 7): 0.5, (3, 8): 0.0,
    (4, 3): 2.0, (4, 5): 2.0, (4, 8): 2.0, (4, 10): 2.0, (4, 13): 2.0,
    (4, 6): 0.5, (4, 12): 0.5, (4, 2): 0.0,
    (5, 2): 2.0, (5, 6): 2.0, (5, 10): 2.0, (5, 15): 2.0,
    (5, 1): 0.5, (5, 4): 0.5, (5, 8): 0.5,
    (6, 12): 2.0, (6, 14): 2.0, (6, 17): 2.0, (6, 1): 0.5, (6, 2): 0.5,
    (6, 3): 0.5, (6, 7): 0.5, (6, 8): 0.5, (6, 10): 0.5,
    (7, 7): 2.0, (7, 14): 2.0, (7, 17): 0.5, (7, 0): 0.0, (7, 8): 0.5,
    (8, 5): 2.0, (8, 15): 2.0, (8, 8): 0.5, (8, 10): 0.5, (8, 11): 0.5, (8, 13): 0.5,
    (10, 6): 2.0, (10, 8): 2.0, (10, 12): 2.0, (10, 15): 2.0,
    (10, 5): 0.5, (10, 10): 0.5, (10, 11): 0.5, (10, 16): 0.5,
    (11, 4): 2.0, (11, 5): 2.0, (11, 10): 2.0, (11, 11): 0.5, (11, 12): 0.5, (11, 16): 0.5,
    (12, 4): 2.0, (12, 5): 2.0, (12, 11): 2.0, (12, 2): 0.5, (12, 3): 0.5,
    (12, 6): 0.5, (12, 8): 0.5, (12, 10): 0.5, (12, 12): 0.5, (12, 16): 0.5,
    (13, 2): 2.0, (13, 11): 2.0, (13, 4): 0.0, (13, 12): 0.5, (13, 13): 0.5, (13, 16): 0.5,
    (14, 1): 2.0, (14, 3): 2.0, (14, 8): 0.5, (14, 14): 0.5, (14, 17): 0.0,
    (15, 2): 2.0, (15, 4): 2.0, (15, 12): 2.0, (15, 16): 2.0,
    (15, 8): 0.5, (15, 10): 0.5, (15, 11): 0.5, (15, 15): 0.5,
    (16, 16): 2.0, (16, 8): 0.5,
    (17, 7): 2.0, (17, 14): 2.0, (17, 1): 0.5, (17, 17): 0.5, (17, 8): 0.5,
}

# id espècie -> (tipus1, tipus2); Kanto primerenc, la resta es presumeix neutre
SPECIES_TYPES: dict[int, tuple[int, int]] = {
    1: (12, 3), 2: (12, 3), 3: (12, 3), 4: (10, 10), 5: (10, 10), 6: (10, 2),
    7: (11, 11), 8: (11, 11), 9: (11, 11), 10: (6, 6), 11: (6, 6), 12: (6, 2),
    13: (6, 3), 14: (6, 3), 15: (6, 3), 16: (2, 0), 17: (2, 0), 18: (2, 0),
    19: (0, 0), 20: (0, 0), 21: (2, 0), 22: (2, 0), 23: (3, 3), 24: (3, 3),
    25: (13, 13), 26: (13, 13), 27: (4, 4), 28: (4, 4), 29: (3, 3), 30: (3, 3),
    31: (3, 4), 32: (3, 3), 33: (3, 3), 34: (3, 4), 35: (0, 0), 36: (0, 0),
    37: (10, 10), 38: (10, 10), 39: (0, 0), 40: (0, 0), 41: (3, 2), 42: (3, 2),
    43: (12, 3), 44: (12, 3), 45: (12, 3), 46: (6, 12), 47: (6, 12), 48: (6, 3),
    49: (6, 3), 50: (4, 4), 51: (4, 4), 52: (0, 0), 53: (0, 0), 54: (11, 14),
    55: (11, 14), 56: (1, 1), 57: (1, 1), 58: (10, 10), 59: (10, 10), 60: (11, 11),
    61: (11, 11), 62: (11, 1), 63: (14, 14), 64: (14, 14), 65: (14, 14),
    66: (1, 1), 67: (1, 1), 68: (1, 1), 69: (12, 3), 70: (12, 3), 71: (12, 3),
    72: (11, 3), 73: (11, 3), 74: (5, 4), 75: (5, 4), 76: (5, 4), 77: (10, 10),
    78: (10, 10), 79: (11, 14), 80: (11, 14), 81: (13, 8), 82: (13, 8),
    83: (2, 0), 84: (2, 0), 85: (2, 0), 86: (15, 15), 87: (15, 11), 88: (3, 3),
    89: (3, 3), 90: (11, 11), 91: (11, 15), 92: (7, 3), 93: (7, 3), 94: (7, 3),
    95: (5, 4), 96: (14, 14), 97: (14, 14), 98: (11, 11), 99: (11, 11),
    100: (13, 13), 101: (13, 13), 102: (12, 14), 103: (12, 14), 104: (4, 4),
    105: (4, 4), 106: (1, 1), 107: (1, 1), 108: (0, 0), 109: (3, 3), 110: (3, 3),
    111: (4, 5), 112: (4, 5), 113: (0, 0), 114: (12, 12), 115: (0, 0),
    116: (11, 11), 117: (11, 11), 118: (11, 11), 119: (11, 11), 120: (11, 11),
    121: (11, 14), 122: (14, 3), 123: (6, 2), 124: (15, 14), 125: (13, 13),
    126: (10, 10), 127: (6, 6), 128: (0, 0), 129: (11, 11), 130: (11, 2),
    131: (11, 15), 132: (0, 0), 133: (0, 0), 143: (0, 0), 147: (16, 16),
    148: (16, 16), 149: (16, 2),
}


def move_name(move_id: int) -> str:
    return MOVES.get(move_id, (f"Move#{move_id}",))[0]


def move_type(move_id: int) -> int:
    return MOVES.get(move_id, ("", 0, 0))[1]


def move_power(move_id: int) -> int:
    return MOVES.get(move_id, ("", 0, 0))[2]


def species_types(species_id: int, fallback: tuple[int, int] | None = None) -> tuple[int, int]:
    if species_id in SPECIES_TYPES:
        return SPECIES_TYPES[species_id]
    return fallback if fallback is not None else (0, 0)


def effectiveness(move_type: int, def_types: tuple[int, int]) -> float:
    return TYPE_CHART.get((move_type, def_types[0]), 1.0) * TYPE_CHART.get((move_type, def_types[1]), 1.0)


def expected_damage(atk_mon, def_mon, move_id: int) -> int:
    """Dany esperat determinista (sense crits/aleatorietat/buffs d'estat).

    Formula Gen 3 simplificada: ((2*niv/5+2) * poder * A/D)/50 + 2, amb STAB i
    efectivitat de tipus. Moves amb PP 0 no compten (el caller els filtra).
    """
    power = move_power(move_id)
    mtype = move_type(move_id)
    atk_types = species_types(atk_mon.species_id, tuple(atk_mon.types))
    def_types = species_types(def_mon.species_id, tuple(def_mon.types))
    if power == 0:
        return 0
    if power == -1:  # dany fix = nivell (Seismic Toss, Night Shade...)
        return atk_mon.level
    if power == -2:  # Sonic Boom
        return 20
    if power == -3:  # Dragon Rage
        return 40
    special = mtype in SPECIAL_TYPES
    a = atk_mon.sp_attack if special else atk_mon.attack
    d = def_mon.sp_defense if special else def_mon.defense
    base = ((2 * atk_mon.level // 5 + 2) * power * a // d) // 50 + 2
    stab = 1.5 if mtype in atk_types else 1.0
    eff = effectiveness(mtype, def_types)
    return int(base * stab * eff)


def best_move(mon, enemy) -> int:
    """Índex (0..3) del moviment amb més dany esperat; empat -> el primer amb PP.

    Si cap fa dany (només estat), el primer amb PP: algo hem de fer.
    """
    moves = list(mon.moves)
    usable = [i for i in range(4) if moves[i] != 0 and mon.pp[i] > 0]
    if not usable:
        return 0
    damages = {i: expected_damage(mon, enemy, moves[i]) for i in usable}
    best = max(damages.values())
    if best > 0:
        return min(i for i in usable if damages[i] == best)
    return usable[0]
