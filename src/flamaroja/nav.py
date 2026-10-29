from __future__ import annotations

from collections import deque

from .memory import CollisionMap, Warp, _textbox_visible, read_npcs, read_pos
from .policy import PolicyConfig

_DIRS = (("down", 0, 1), ("up", 0, -1), ("left", -1, 0), ("right", 1, 0))


def bfs(cmap: CollisionMap, start: tuple[int, int], goal: tuple[int, int]) -> list[str] | None:
    """Cami mes curt en botons fins a goal.

    Les tiles warp usables son desti, mai transit (dispararien). El desti pot ser
    una tile bloquejada si es una porta d'exterior: s'hi entra prement-hi contra.
    """
    warps = {(w.x, w.y) for w in cmap.warps if w.usable}

    def ok(x: int, y: int) -> bool:
        if (x, y) == goal:
            return True
        return not cmap.blocked(x, y) and (x, y) not in warps and (x, y) not in cmap.npcs

    if start == goal:
        return []
    if not ok(*goal):
        return None
    prev: dict[tuple[int, int], tuple[tuple[int, int], str] | None] = {start: None}
    queue: deque[tuple[int, int]] = deque([start])
    while queue:
        cur = queue.popleft()
        for btn, dx, dy in _DIRS:
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in prev or not ok(*nxt):
                continue
            prev[nxt] = (cur, btn)
            if nxt == goal:
                out = []
                while nxt != start:
                    prev_node, prev_btn = prev[nxt]
                    out.append(prev_btn)
                    nxt = prev_node
                return list(reversed(out))
            queue.append(nxt)
    return None


def warp_entry(cmap: CollisionMap, warp: Warp) -> tuple[tuple[int, int], str] | None:
    """Tile on posar-se i botto a premer per activar un warp.

    Tiles pasables: hi vas directe i premses (escales/fletxes) o res (portes walk-on).
    Tiles bloquejades (cases a l'exterior): hi entres prement desde el costat
    pasable (normalment sota la porta) i tornes a premer la mateixa direccio.
    """
    if warp.act:
        # tile adjacent passable des d'on mirar l'objecte; el boto es la direccio cap a ell
        for btn, dx, dy in (("up", 0, 1), ("down", 0, -1), ("right", -1, 0), ("left", 1, 0)):
            if not cmap.blocked(warp.x + dx, warp.y + dy) and cmap.warp_at(warp.x + dx, warp.y + dy) is None:
                return (warp.x + dx, warp.y + dy), btn
        return None
    if not cmap.blocked(warp.x, warp.y):
        return (warp.x, warp.y), warp.press if warp.press is not None else ""
    for btn, dx, dy in (("up", 0, 1), ("down", 0, -1), ("right", -1, 0), ("left", 1, 0)):
        if not cmap.blocked(warp.x + dx, warp.y + dy):
            return (warp.x, warp.y), btn
    return None


class Navigator:
    """Camina fins a una tile objectiu verificant la posicio despres de cada passa.

    Tolera col.lisions i NPCs (reintents), passades llargues (recalcula desde la
    posicio real) i warps (portes walk-on, escales/fletxes amb premsada, portes
    d'exterior bloquejades entrant des de la tile adjacent).
    """

    def __init__(self, emu, cfg: PolicyConfig) -> None:
        self.emu = emu
        self.cfg = cfg
        self.cmap: CollisionMap | None = None
        self.tile: tuple[int, int] = (0, 0)
        self.press: str = ""
        self.warp: Warp | None = None
        self.origin: tuple[int, int] = (0, 0)  # (bank, num) del mapa on neix l'objectiu
        self.stuck = 0
        self.steps = 0

    def active(self) -> bool:
        return self.cmap is not None

    def clear(self) -> None:
        self.cmap = None
        self.warp = None
        self.press = ""
        self.stuck = 0
        self.steps = 0

    def set_goal(self, cmap: CollisionMap, warp: Warp) -> bool:
        entry = warp_entry(cmap, warp)
        if entry is None:
            return False
        stand, press = entry
        x, y, bank, num = read_pos(self.emu)
        if bank < 0 or bfs(cmap, (x, y), stand) is None:
            return False
        self.cmap = cmap
        self.tile = stand
        self.press = press
        self.warp = warp
        self.origin = (bank, num)
        self.stuck = 0
        self.steps = 0
        return True

    def _wait_map_change(self, frames: int = 240) -> str:
        for _ in range(frames // 15):
            self.emu.tick(15)
            _, _, bank, num = read_pos(self.emu)
            if (bank, num) != self.origin:
                return "warped"
        return "blocked"

    def step(self) -> str:
        """Una passa (o entrada de warp). Retorna walking/done/warped/blocked."""
        if self.cmap is None:
            return "blocked"
        x, y, bank, num = read_pos(self.emu)
        if (bank, num) != self.origin:
            return "warped"
        if _textbox_visible(self.emu):  # dialeg (p.ex. NPC que et parla): el bucle principal el tanca
            return "blocked"
        if (x, y) == self.tile:
            if self.warp is None:
                return "done"
            if self.warp.act:
                self.emu.press(self.press, hold=8, settle=20)  # girar cap a l'objecte
                self.emu.press("a", hold=4, settle=60)
                return "done"
            if self.press:
                self.emu.press(self.press, hold=25, settle=30)
            return self._wait_map_change()
        self.cmap.npcs = read_npcs(self.emu)  # les NPCs es mouen: refresca abans de planificar
        path = bfs(self.cmap, (x, y), self.tile)
        if not path:
            return "blocked"
        before = (x, y)
        self.emu.press(path[0], hold=self.cfg.walk_hold, settle=self.cfg.walk_settle)
        x2, y2, _, _ = read_pos(self.emu)
        self.steps += 1
        if (x2, y2) == before:
            self.stuck += 1
            if self.stuck >= 4:
                return "blocked"
        else:
            self.stuck = 0
        return "walking"


MB_TALL_GRASS = 0x02


def grass_tiles(emu, cmap: CollisionMap) -> set[tuple[int, int]]:
    """Tiles d'herba alta lliures del mapa (behavior 0x02), per entrenar."""
    from .memory import _behavior_at

    return {
        (x, y)
        for y in range(cmap.height)
        for x in range(cmap.width)
        if not cmap.blocked(x, y) and _behavior_at(emu, cmap, x, y) == MB_TALL_GRASS
    }


def grind_press(cmap: CollisionMap, grass: set[tuple[int, int]], pos: tuple[int, int], last: tuple[int, int] | None) -> str | None:
    """Seguent boto per entrenar: vaiven entre tiles d'herba adjacents, o cami a l'herba mes propera."""
    x, y = pos
    if pos in grass:
        near = [(b, (x + dx, y + dy)) for b, dx, dy in _DIRS if (x + dx, y + dy) in grass and (x + dx, y + dy) not in cmap.npcs]
        # ponytail: tornar a la tile d'abans si es herba; si no, la primera veina
        back = [b for b, t in near if t == last]
        return (back or [b for b, _ in near] or [None])[0]
    for goal in sorted(grass, key=lambda t: abs(t[0] - x) + abs(t[1] - y))[:8]:
        path = bfs(cmap, pos, goal)
        if path:
            return path[0]
    return None
