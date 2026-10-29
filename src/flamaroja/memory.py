from __future__ import annotations

import struct
from dataclasses import dataclass, field

from .charmap import decode_text

# BPRS (Rojo Fuego ES / Flama Roja): punters IWRAM -0xB0 respecte BPRE (verificat amb el nom del jugador);
# party/enemic com BPRE (party verificada amb l'OT del primer Pokemon)
IWRAM_MAP_BLOCK_PTR = 0x03004F58
IWRAM_PLAYER_BLOCK_PTR = 0x03004F5C
IWRAM_FADE = 0x03000F9C
EWRAM_MESSAGE = 0x02021D18
EWRAM_PARTY = 0x02024284

# mapa BPRS: adreces verificades empiricament des de play.ss (veure scripts/test_nav_pallet.py);
# atenccio: no segueixen del tot el desplacament -0xB0/+0xC dels punters de dalt
EWRAM_MAP_HEADER = 0x02036DFC    # gMapHeader: +0 layout*, +4 events*, +8 scripts*
IWRAM_VMAP = 0x03004F90          # VMap: {s32 xs, s32 ys, u16* graella}, la dada apunta a EWRAM
EWRAM_OBJECT_EVENTS = 0x02036E38  # gObjectEvents[16] de 0x24 bytes, jugador = slot amb isPlayer
IWRAM_CALLBACK2 = 0x03003044     # gMain.callback2; BATTLE_MAIN_CB2 mentre hi ha combat
BATTLE_MAIN_CB2 = 0x08011071
MAP_OFFSET = 7                   # la graella VMap te borda de 7: coords mapa + 7

# combat BPRS (verificat empiricament des de battle1.ss, veure scripts/test_battle.py):
# gBattleMons es la font de veritat en viu (HP/PP/stats); la copia de party/enemic no s'actualitza
BATTLE_MON_SIZE = 0x58           # struct BattlePokemon (pret/pokefirered)
EWRAM_GBATTLEMONS = 0x02023BE4   # gBattleMons[4]: battler 0 jugador, 1 enemic
EWRAM_BATTLE_OUTCOME = 0x02023E8A  # gBattleOutcome: 0 en curs, 1 guanyat, 2 perdut, 4 fugit
EWRAM_ACTION_CURSOR = 0x02023FF8  # gActionSelectionCursor[4], bitfield: bit0 col dreta (Bossa), bit1 fila baixa: LLUITA0 BOLSA1 EQUIP2 FUGIR3
EWRAM_MOVE_CURSOR = 0x02023FFC    # gMoveSelectionCursor[4], mateix bitfield: mov1..4 com a graella 2x2
IWRAM_CONTROLLER_FUNCS = 0x03004F30  # gBattlerControllerFuncs[4] (BPRS = BPRE -0xB0); [0] = jugador
CTRL_ACTION_MENU = (0x080E7949, 0x0802E3BD)  # HandleInputChooseAction: (BPRS base, Flama Roja 1.2); el pedaç mou el codi
CTRL_MOVE_MENU = (0x080E7C95, 0x0802E995)    # HandleInputChooseMove: (BPRS base, Flama Roja 1.2)

# objectes interactuables coneguts (gfx de l'object event -> descripcio)
OBJECT_LABELS = {
    0x5C: "Poké Ball on Oak's table holding a starter Pokémon (pick one)",
    0x47: "Professor Oak (talk to deliver the parcel)",
    0x58: "Mom (talk to heal the team)",
}
SB1_FLAGS = 0x0EE0  # flags del saveblock1 (FRLG); un object amb flag activa esta amagat

# behaviors de metatile que ens interessen (pret/constants/metatile_behaviors.h)
MB_WALK_ON_WARPS = (0x60, 0x61, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x6B, 0x71)
STAIR_WARP_WEST = (0x6D, 0x6F)   # escales directionals: cal premsar left des de la tile
STAIR_WARP_EAST = (0x6C, 0x6E)   # cal premsar right
ARROW_WARP_PRESS = {0x62: "right", 0x63: "left", 0x64: "up", 0x65: "down"}

PARTY_MON_SIZE = 100
PARTY_SLOTS = 6

_FACING = ("", "down", "up", "left", "right")  # DIR_NONE, DIR_SOUTH..DIR_EAST del decomp

SUBSTRUCT_PERMUTATIONS = (
    "GAEM", "GAME", "GEAM", "GEMA", "GMAE", "GMEA",
    "AGEM", "AGME", "AEGM", "AEMG", "AMGE", "AMEG",
    "EGAM", "EGMA", "EAGM", "EAMG", "EMGA", "EMAG",
    "MGAE", "MGEA", "MAGE", "MAEG", "MEGA", "MEAG",
)


@dataclass
class Mon:
    personality: int = 0
    ot_id: int = 0
    nickname: str = ""
    species_id: int = 0
    level: int = 0
    hp: int = 0
    max_hp: int = 0
    status: int = 0
    experience: int = 0
    moves: list[int] = field(default_factory=list)
    pp: list[int] = field(default_factory=list)

    @property
    def species(self) -> str:
        from .species import species_name

        return species_name(self.species_id)

    def to_dict(self) -> dict[str, object]:
        return {
            "species": self.species,
            "species_id": self.species_id,
            "nickname": self.nickname,
            "level": self.level,
            "current_hp": self.hp,
            "max_hp": self.max_hp,
            "status": self.status,
            "experience": self.experience,
            "moves": self.moves,
            "pp": self.pp,
        }


@dataclass
class BattleMon:
    """struct BattlePokemon de gBattleMons (en viu durant el combat)."""

    species_id: int = 0
    level: int = 0
    hp: int = 0
    max_hp: int = 0
    attack: int = 0
    defense: int = 0
    speed: int = 0
    sp_attack: int = 0
    sp_defense: int = 0
    moves: list[int] = field(default_factory=list)
    pp: list[int] = field(default_factory=list)
    types: tuple[int, int] = (0, 0)
    status1: int = 0

    @property
    def species(self) -> str:
        from .species import species_name

        return species_name(self.species_id)

    def to_dict(self) -> dict[str, object]:
        from .battle_data import TYPE_NAMES, move_name, species_types

        t1, t2 = species_types(self.species_id, self.types)
        return {
            "species": self.species,
            "species_id": self.species_id,
            "level": self.level,
            "current_hp": self.hp,
            "max_hp": self.max_hp,
            "status1": self.status1,
            "types": [TYPE_NAMES[t1], TYPE_NAMES[t2] if t2 else None],
            "stats": {
                "attack": self.attack, "defense": self.defense, "speed": self.speed,
                "sp_attack": self.sp_attack, "sp_defense": self.sp_defense,
            },
            "moves": [
                {"id": m, "name": move_name(m), "pp": p} if m else None
                for m, p in zip(self.moves, self.pp)
            ],
        }


@dataclass
class Warp:
    x: int
    y: int
    dest_bank: int
    dest_map: int
    dest_warp: int
    behavior: int = 0  # behavior del metatile sota la porta/escales
    act: bool = False  # objecte amb qui interactuar (A des d'una tile adjacent), no una sortida
    label: str = ""  # descripcio humana per al model
    edge: str = ""  # sortida per connexio de mapa: boto a premer a la vora (up/down/left/right)

    @property
    def press(self) -> str | None:
        if self.edge:
            return self.edge
        # com activar el warp un cop som a la tile: escales/fletxes demanen premsada
        if self.behavior in STAIR_WARP_WEST:
            return "left"
        if self.behavior in STAIR_WARP_EAST:
            return "right"
        return ARROW_WARP_PRESS.get(self.behavior)

    @property
    def usable(self) -> bool:
        # behavior 0 = punt d'aterratge d'un warp desti, no una sortida; les tiles
        # bloquejades amb behavior (portes de cases a l'exterior) si que son sortides
        return self.behavior != 0

    def to_dict(self) -> dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "dest_bank": self.dest_bank,
            "dest_map": self.dest_map,
            "dest_warp": self.dest_warp,
            "behavior": self.behavior,
        }


@dataclass
class CollisionMap:
    width: int = 0
    height: int = 0
    xs: int = 0  # stride de la graella VMap (inclou connexions de mapa)
    ys: int = 0
    grid: list[int] = field(default_factory=list)
    warps: list[Warp] = field(default_factory=list)
    npcs: set[tuple[int, int]] = field(default_factory=set)  # tiles ocupades per altres object events
    prim_attrs: int = 0  # ptrs ROM a metatile_attributes (per behaviors)
    sec_attrs: int = 0

    def blocked(self, x: int, y: int) -> bool:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return True
        gx, gy = x + MAP_OFFSET, y + MAP_OFFSET
        if gx >= self.xs or gy >= self.ys:
            return True
        return (self.grid[gy * self.xs + gx] & 0x0C00) != 0

    def warp_at(self, x: int, y: int) -> Warp | None:
        for w in self.warps:
            if (w.x, w.y) == (x, y):
                return w
        return None

    def rows(self) -> list[str]:
        # mapa visual: # bloquejat, . lliure, + warp
        out = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                if self.warp_at(x, y) is not None:
                    row.append("+")
                elif self.blocked(x, y):
                    row.append("#")
                else:
                    row.append(".")
            out.append("".join(row))
        return out


@dataclass
class GameState:
    frame: int = 0
    map_bank: int = 0
    map_number: int = 0
    camera_x: int = 0
    camera_y: int = 0
    player_name: str = ""
    facing: str = ""
    party: list[Mon] = field(default_factory=list)
    battle_active: bool = False
    battle_phase: str = ""        # "action" | "move" | "text" (qualsevol altra cosa: avanca amb A)
    battle_player: BattleMon | None = None
    battle_enemy: BattleMon | None = None
    battle_action_cursor: int = -1  # bitfield LLUITA/BOLSA/EQUIP/FUGIR, nomes valid a "action"
    battle_move_cursor: int = -1    # bitfield mov1..4, nomes valid a "move"
    battle_outcome: int = 0         # gBattleOutcome: 1 guanyat, 2 perdut, 4 fugit
    has_parcel: bool = False       # Oak's Parcel (item 349) a la butxaca d'objectes clau
    badges: int = 0               # medalles de gimnas (flags de sistema 0x820..0x827)
    parcel_delivered: bool = False  # el paquet ja s'ha vist i ja no hi es (el posa cli.py, es memoria de sessio)
    fading: bool = False
    dialog_text: str = ""
    cmap: CollisionMap | None = None  # mapa de col·lisio actual (None si no hi ha overworld)

    @property
    def warps(self) -> list[Warp]:
        return self.cmap.warps if self.cmap is not None else []

    def summary(self) -> str:
        enemy = ""
        if self.battle_active and self.battle_enemy is not None:
            enemy = f" enemy={self.battle_enemy.species} Lv{self.battle_enemy.level} {self.battle_enemy.hp}/{self.battle_enemy.max_hp}HP"
            if self.battle_phase:
                enemy += f" [{self.battle_phase}]"
        dims = f"{self.cmap.width}x{self.cmap.height} " if self.cmap is not None else ""
        return (
            f"map {self.map_bank}/{self.map_number} {dims}pos({self.camera_x},{self.camera_y}) "
            f"face={self.facing or '?'} party={len(self.party)} battle={'Y' if self.battle_active else 'N'}{enemy} "
            f"dialog='{self.dialog_text[:40]}'"
        )


def _decrypt_block(pid: int, ot_id: int, data: bytes) -> dict[str, bytes]:
    key = (pid ^ ot_id) & 0xFFFFFFFF
    words = struct.unpack("<12I", data)
    plain = struct.pack("<12I", *[(w ^ key) & 0xFFFFFFFF for w in words])
    order = SUBSTRUCT_PERMUTATIONS[pid % 24]
    return {order[i]: plain[i * 12 : (i + 1) * 12] for i in range(4)}


def parse_mon(raw: bytes) -> Mon | None:
    if len(raw) < PARTY_MON_SIZE:
        return None
    pid = int.from_bytes(raw[0:4], "little")
    ot_id = int.from_bytes(raw[4:8], "little")
    if pid == 0 or pid == 0xFFFFFFFF:
        return None
    mon = Mon(personality=pid, ot_id=ot_id)
    mon.nickname = decode_text(raw[8:18])
    sub = _decrypt_block(pid, ot_id, raw[0x20:0x50])
    growth = sub["G"]
    attacks = sub["A"]
    mon.species_id = int.from_bytes(growth[0:2], "little")
    mon.experience = int.from_bytes(growth[4:8], "little")
    mon.moves = [int.from_bytes(attacks[i * 2 : i * 2 + 2], "little") for i in range(4)]
    mon.pp = list(attacks[8:12])
    mon.status = int.from_bytes(raw[0x50:0x54], "little")
    mon.level = raw[0x54]
    # struct Pokemon: status+0x50, level+0x54, mail+0x55, hp+0x56, maxHP+0x58 (abans llegiem 0x58 com a hp: era maxHP)
    mon.hp = int.from_bytes(raw[0x56:0x58], "little")
    mon.max_hp = int.from_bytes(raw[0x58:0x5A], "little")
    return mon


def parse_battle_mon(raw: bytes) -> BattleMon | None:
    """struct BattlePokemon: species+0, stats +2..+0xB, moves+0xC, statStages+0x18,
    types+0x21/0x22, pp+0x24, hp+0x28, level+0x2A, maxHP+0x2C, status1+0x4C."""
    if len(raw) < BATTLE_MON_SIZE:
        return None
    species_id = int.from_bytes(raw[0x00:0x02], "little")
    if species_id == 0:
        return None
    atk, dfn, spd, spa, spd2 = struct.unpack_from("<5H", raw, 0x02)
    moves = list(struct.unpack_from("<4H", raw, 0x0C))
    pp = list(raw[0x24:0x28])
    hp = int.from_bytes(raw[0x28:0x2A], "little")
    max_hp = int.from_bytes(raw[0x2C:0x2E], "little")
    if not (0 < max_hp <= 1500 and hp <= max_hp and 0 < raw[0x2A] <= 100):
        return None
    return BattleMon(
        species_id=species_id,
        level=raw[0x2A],
        hp=hp,
        max_hp=max_hp,
        attack=atk,
        defense=dfn,
        speed=spd,
        sp_attack=spa,
        sp_defense=spd2,
        moves=moves,
        pp=pp,
        types=(raw[0x21], raw[0x22]),
        status1=int.from_bytes(raw[0x4C:0x50], "little"),
    )


def battle_phase(emu) -> str:
    """Fase del controlador del jugador: menu d'accio, menu de moviments o text."""
    c = emu.read_u32(IWRAM_CONTROLLER_FUNCS)
    if c in CTRL_ACTION_MENU:
        return "action"
    if c in CTRL_MOVE_MENU:
        return "move"
    return "text"


def read_battle(emu) -> tuple[BattleMon | None, BattleMon | None]:
    return (
        parse_battle_mon(emu.read_range(EWRAM_GBATTLEMONS, BATTLE_MON_SIZE)),
        parse_battle_mon(emu.read_range(EWRAM_GBATTLEMONS + BATTLE_MON_SIZE, BATTLE_MON_SIZE)),
    )


def _textbox_visible(emu) -> bool:
    import numpy as np

    # vora del quadre (blava per dialegs, grisa per cartells): una linia horitzontal llarga a la franja
    # inferior (el blanc no serveix: el terra d'alguns interiors, com el laboratori, es gairebe blanc)
    screen = np.asarray(emu.screen())
    # pantalla negra amb text blanc (missatge de whiteout): sense vora de quadre
    if (screen == 0).all(axis=2).mean() > 0.85 and (screen == 255).all(axis=2).mean() > 0.005:
        return True
    strip = screen[108:140]
    return any((strip == c).all(axis=2).sum(axis=1).max() > 100 for c in ((74, 115, 165), (107, 115, 123)))


def read_pos(emu) -> tuple[int, int, int, int]:
    """(x, y, bank, num) del jugador sense parsejar la party ni la pantalla."""
    ptr = emu.read_u32(IWRAM_MAP_BLOCK_PTR)
    if not (0x02000000 <= ptr < 0x03010000):
        return (-1, -1, -1, -1)
    x, y = struct.unpack("<hh", emu.read_range(ptr, 4))
    bank, num = emu.read_range(ptr + 4, 2)
    return x, y, bank, num


def _behavior_at(emu, cm: CollisionMap, x: int, y: int) -> int:
    # behavior = metatile_attributes (ROM, u32 per metatile) & 0x1FF; primari < 640 (NUM_METATILES_IN_PRIMARY de FRLG)
    gx, gy = x + MAP_OFFSET, y + MAP_OFFSET
    if gx >= cm.xs or gy >= cm.ys:
        return 0
    mt = cm.grid[gy * cm.xs + gx] & 0x03FF
    ptr = None
    if mt < 640:
        ptr = cm.prim_attrs
        idx = mt
    else:
        ptr = cm.sec_attrs
        idx = mt - 640
    if not ptr or not (0x08000000 <= ptr < 0x09000000):
        return 0
    return emu.read_u32(ptr + idx * 4) & 0x1FF


def read_map(emu) -> CollisionMap | None:
    """Llegeix el mapa de col·lisio: VMap (graella viva) + warps del gMapHeader."""
    layout = emu.read_u32(EWRAM_MAP_HEADER)
    events = emu.read_u32(EWRAM_MAP_HEADER + 4)
    if not (0x08000000 <= layout < 0x09000000 and 0x08000000 <= events < 0x09000000):
        return None
    cm = CollisionMap()
    cm.width, cm.height = struct.unpack("<ii", emu.read_range(layout, 8))
    if not (0 < cm.width <= 250 and 0 < cm.height <= 250):
        return None
    prim, sec = emu.read_u32(layout + 0x10), emu.read_u32(layout + 0x14)
    if 0x08000000 <= prim < 0x09000000:
        cm.prim_attrs = emu.read_u32(prim + 0x14)
    if 0x08000000 <= sec < 0x09000000:
        cm.sec_attrs = emu.read_u32(sec + 0x14)
    cm.xs, cm.ys, mp = struct.unpack("<iiI", emu.read_range(IWRAM_VMAP, 12))
    if not (0x02000000 <= mp < 0x03010000 and cm.xs >= cm.width + MAP_OFFSET and cm.ys >= cm.height + MAP_OFFSET):
        return None
    cm.grid = list(struct.unpack(f"<{cm.xs * cm.ys}H", emu.read_range(mp, cm.xs * cm.ys * 2)))
    # events: 4 comptadors + 4 punters (objectes, warps, coordEvents, bgEvents)
    _, warp_count, _, _ = emu.read_range(events, 4)
    if warp_count:
        warps_ptr = emu.read_u32(events + 8)
        if 0x08000000 <= warps_ptr < 0x09000000:
            for i in range(min(warp_count, 16)):
                raw = emu.read_range(warps_ptr + i * 8, 8)
                wx, wy = struct.unpack("<hh", raw[:4])
                _, dw, dn, db = raw[4:]
                w = Warp(x=wx, y=wy, dest_bank=db, dest_map=dn, dest_warp=dw)
                w.behavior = _behavior_at(emu, cm, wx, wy)
                cm.warps.append(w)
    cm.npcs = read_npcs(emu)
    _read_connections(emu, cm)
    _read_objects(emu, cm)
    return cm


def read_npcs(emu) -> set[tuple[int, int]]:
    """Tiles ocupades per object events actius que no son el jugador (coords gObjectEvents = mapa + 7)."""
    out: set[tuple[int, int]] = set()
    for slot in range(16):
        o = emu.read_range(EWRAM_OBJECT_EVENTS + slot * 0x24, 0x24)
        if o[0] & 1 and not o[2] & 1:
            x, y = struct.unpack("<hh", o[0x10:0x14])
            out.add((x - MAP_OFFSET, y - MAP_OFFSET))
    return out


def read_facing(emu) -> str:
    # busca l'object event del jugador (isPlayer, actiu) entre els 16 slots
    for slot in range(16):
        o = emu.read_range(EWRAM_OBJECT_EVENTS + slot * 0x24, 0x24)
        if o[0] & 1 and o[2] & 1:
            d = o[0x18] & 0xF
            return _FACING[d] if d < len(_FACING) else ""
    return ""


_CONN_DIR = {1: "down", 2: "up", 3: "left", 4: "right"}


def _read_connections(emu, cm: CollisionMap) -> None:
    """Connexions del gMapHeader (+0x0C) com a sortides: tile passable de la vora mes propera al centre."""
    conn = emu.read_u32(EWRAM_MAP_HEADER + 0x0C)
    if not 0x08000000 <= conn < 0x09000000:
        return
    count, ptr = struct.unpack("<II", emu.read_range(conn, 8))
    if not (0 < count <= 8 and 0x08000000 <= ptr < 0x09000000):
        return
    for i in range(count):
        d, _, group, num = struct.unpack("<BxxxiBBxx", emu.read_range(ptr + i * 12, 12))
        btn = _CONN_DIR.get(d)
        if btn is None:
            continue
        if btn in ("up", "down"):
            y = 0 if btn == "up" else cm.height - 1
            tiles = [(x, y) for x in range(cm.width)]
            mid = cm.width / 2
        else:
            x = 0 if btn == "left" else cm.width - 1
            tiles = [(x, y) for y in range(cm.height)]
            mid = cm.height / 2
        free = [t for t in tiles if not cm.blocked(*t) and cm.warp_at(*t) is None]
        if not free:
            continue
        x, y = min(free, key=lambda t: abs((t[0] if btn in ("up", "down") else t[1]) - mid))
        cm.warps.append(Warp(x=x, y=y, dest_bank=group, dest_map=num, dest_warp=-1, behavior=0xFF, edge=btn))


def _flag_set(emu, flag: int) -> bool:
    sb1 = emu.read_u32(IWRAM_MAP_BLOCK_PTR)
    if flag == 0 or not 0x02000000 <= sb1 < 0x03010000:
        return False
    return bool(emu.read_u8(sb1 + SB1_FLAGS + flag // 8) >> (flag % 8) & 1)


def _read_objects(emu, cm: CollisionMap) -> None:
    """Object events amb etiqueta coneguda i visibles, com a objectius d'interaccio."""
    events = emu.read_u32(EWRAM_MAP_HEADER + 4)
    count = emu.read_u8(events)
    ptr = emu.read_u32(events + 4)
    if not (0 < count <= 64 and 0x08000000 <= ptr < 0x09000000):
        return
    for i in range(count):
        raw = emu.read_range(ptr + i * 24, 24)
        label = OBJECT_LABELS.get(raw[1])
        x, y = struct.unpack("<hh", raw[4:8])
        flag = struct.unpack("<H", raw[20:22])[0]
        if label and not _flag_set(emu, flag):
            cm.warps.append(Warp(x=x, y=y, dest_bank=-1, dest_map=-1, dest_warp=-1, behavior=0xFE, act=True, label=label))


def read_state(emu, frame: int = 0) -> GameState:
    gs = GameState(frame=frame)
    map_ptr = emu.read_u32(IWRAM_MAP_BLOCK_PTR)
    if 0x02000000 <= map_ptr < 0x03010000:
        gs.camera_x = emu.read_u16(map_ptr + 0x0000)
        gs.camera_y = emu.read_u16(map_ptr + 0x0002)
        gs.map_bank = emu.read_u8(map_ptr + 0x0004)
        gs.map_number = emu.read_u8(map_ptr + 0x0005)
        keys = emu.read_range(map_ptr + 0x03B8, 0x78)  # key items FRLG: 30 x (u16 item, u16 qty)
        gs.has_parcel = any(keys[i] | keys[i + 1] << 8 == 349 for i in range(0, 0x78, 4))
    player_ptr = emu.read_u32(IWRAM_PLAYER_BLOCK_PTR)
    if 0x02000000 <= player_ptr < 0x03010000:
        gs.player_name = decode_text(emu.read_range(player_ptr, 8))
    gs.cmap = read_map(emu)
    gs.badges = sum(_flag_set(emu, 0x820 + i) for i in range(8))
    gs.facing = read_facing(emu)
    for slot in range(PARTY_SLOTS):
        mon = parse_mon(emu.read_range(EWRAM_PARTY + slot * PARTY_MON_SIZE, PARTY_MON_SIZE))
        if mon is not None:
            gs.party.append(mon)
    # estat de combat en viu desde gBattleMons; la copia de party/enemic queda congelada
    if emu.read_u32(IWRAM_CALLBACK2) == BATTLE_MAIN_CB2:
        gs.battle_active = True
        gs.battle_phase = battle_phase(emu)
        gs.battle_player, gs.battle_enemy = read_battle(emu)
        gs.battle_action_cursor = emu.read_u8(EWRAM_ACTION_CURSOR)
        gs.battle_move_cursor = emu.read_u8(EWRAM_MOVE_CURSOR)
        gs.battle_outcome = emu.read_u8(EWRAM_BATTLE_OUTCOME)
    # ponytail: flag de fade de BPRE no existeix a BPRS (llegia sempre 1 i bloquejava la policy); desactivat
    gs.fading = False
    # el buffer de text de l'overworld no s'esborra i durant el combat es queda estancat:
    # nomes el llegim fora de combat i quan el quadre blanc es visible
    if not gs.battle_active and _textbox_visible(emu):
        gs.dialog_text = decode_text(emu.read_range(EWRAM_MESSAGE, 200))
    return gs
