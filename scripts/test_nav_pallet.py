from __future__ import annotations

"""Test E2E de navegacio per tiles, sense LLM.

Des de play.ss (habitacio del jugador, mapa 4/1) ha de sortir per les escales,
travessar la casa (4/0) i arribar a l'exterior de Pallet Town (3/0) nomes amb
pathfinding i l'executor de passes. Falla (SystemExit) si no hi arriba.

Us: uv run python scripts/test_nav_pallet.py [--rom roms/flama-roja.gba]
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flamaroja.decisions import nav_options
from flamaroja.emulator import GbaEmulator
from flamaroja.memory import CollisionMap, Warp, read_map, read_pos, read_state
from flamaroja.nav import Navigator, bfs
from flamaroja.policy import PolicyConfig


def test_bfs_sintetic() -> None:
    # habitacio 5x4 amb un mur central i una porta a la dreta
    cm = CollisionMap(width=5, height=4, xs=5 + 14, ys=4 + 14, grid=[0] * (19 * 18))
    for y in range(4):
        for x in range(5):
            if x == 2 and y != 3:
                cm.grid[(y + 7) * cm.xs + (x + 7)] = 0x0C00  # mur
    cm.warps.append(Warp(x=4, y=1, dest_bank=0, dest_map=0, dest_warp=0))
    path = bfs(cm, (0, 0), (4, 1))
    assert path is not None, "bfs ha de trobar camí voltant el mur fins la porta"
    assert path[0] == "down", "primer ha de baixar per esquivar el mur"
    x, y = 0, 0
    for btn in path:
        dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[btn]
        x, y = x + dx, y + dy
    assert (x, y) == (4, 1)
    # regio tancada amb murs a tots els costats: inaccessible
    for wx, wy in ((3, 1), (5, 1), (4, 0), (4, 2)):
        cm.grid[(wy + 7) * cm.xs + (wx + 7)] = 0x0C00
    assert bfs(cm, (0, 0), (4, 1)) is None, "regio tancada: inassolible"
    print("bfs sintetic: OK")


def run_nav(emu: GbaEmulator, nav: Navigator, cmap: CollisionMap, warp: Warp, limit: int = 400) -> tuple[int, int]:
    assert nav.set_goal(cmap, warp), f"objectiu inassolible: ({warp.x},{warp.y})"
    for _ in range(limit):
        status = nav.step()
        if status == "warped":
            x, y, bank, num = read_pos(emu)
            print(f"  warp fet -> mapa {bank}/{num} pos({x},{y}) en {nav.steps} passes")
            nav.clear()
            return bank, num
        if status == "blocked":
            raise SystemExit(f"navegacio bloquejada cap a ({warp.x},{warp.y})")
    raise SystemExit(f"timeouts de navegacio cap a ({warp.x},{warp.y})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", default=os.environ.get("FLAMAROJA_ROM") or str(ROOT / "roms/flama-roja.gba"))
    parser.add_argument("--save", default=str(ROOT / "play.ss"))
    parser.add_argument("--shot", default="/tmp/drive2/test_pallet.png")
    args = parser.parse_args()

    test_bfs_sintetic()

    emu = GbaEmulator(args.rom)
    emu.tick(60)
    emu.load_state(args.save)
    gs = read_state(emu, frame=emu.frame)
    print(f"inici: {gs.summary()}")
    assert (gs.map_bank, gs.map_number) == (4, 1), "el save state hauria de ser a l'habitacio (4/1)"
    assert gs.cmap is not None and (gs.cmap.width, gs.cmap.height) == (12, 9), "habitacio 12x9"
    assert gs.facing, "facing del jugador hauria de ser llegible"

    for _ in range(20):  # el save comenca amb un quadre de text obert: el bucle principal el tanca amb A
        if not read_state(emu, frame=emu.frame).dialog_text:
            break
        emu.press("a", hold=4, settle=40)
    gs = read_state(emu, frame=emu.frame)
    cmap = gs.cmap

    nav = Navigator(emu, PolicyConfig())

    # 1) habitacio -> escales (stair warp directional DOWN_LEFT, behavior 0x6F)
    cmap = gs.cmap
    print("\nmapa habitacio:")
    for row in cmap.rows():
        print(f"  {row}")
    escalas = [w for w in cmap.warps if w.usable and (w.dest_bank, w.dest_map) == (4, 0)]
    assert escalas, "l'habitacio hauria de tenir les escales usables cap a la casa (4/0)"
    bank, num = run_nav(emu, nav, cmap, escalas[0])
    assert (bank, num) == (4, 0), f"esperava casa 4/0, soc a {bank}/{num}"

    # 2) casa 1F -> porta cap a l'exterior (3/0)
    emu.tick(120)
    cmap = read_map(emu)
    assert cmap is not None, "casa 1F hauria de tenir mapa"
    print(f"\ncasa 1F {cmap.width}x{cmap.height}, warps: {[(w.x, w.y, w.dest_bank, w.dest_map) for w in cmap.warps]}")
    portes = [w for w in cmap.warps if w.usable and (w.dest_bank, w.dest_map) == (3, 0)]
    assert portes, "la casa hauria de tenir porta usable cap a Pallet (3/0)"
    bank, num = run_nav(emu, nav, cmap, portes[0])
    assert (bank, num) == (3, 0), f"esperava Pallet Town 3/0, soc a {bank}/{num}"

    # 3) exterior: camina unes passes cap al centre per confirmar control
    emu.tick(240)
    cmap = read_map(emu)
    assert cmap is not None and cmap.width > 14, "Pallet Town hauria de ser un mapa exterior gran"
    x, y, bank, num = read_pos(emu)
    print(f"\nexterior: mapa {bank}/{num} {cmap.width}x{cmap.height} pos({x},{y})")
    gs = read_state(emu, frame=emu.frame)
    print(f"estat final: {gs.summary()}")
    # sortides per connexio (nord = Ruta 1) i anti-ping-pong: no ofereix la casa d'on venim
    assert any(w.edge == "up" and (w.dest_bank, w.dest_map) == (3, 19) for w in gs.warps), "falta la sortida nord a Ruta 1"
    assert all((w.dest_bank, w.dest_map) != (4, 0) for w in nav_options(gs, (4, 0))), "no ha d'oferir tornar a casa"
    if args.shot:
        emu.screen().resize((480, 320)).save(args.shot)
        print(f"captura: {args.shot}")
    emu.close()
    print("\nPASS: habitacio -> escales -> casa -> Pallet Town per codi")


if __name__ == "__main__":
    main()
