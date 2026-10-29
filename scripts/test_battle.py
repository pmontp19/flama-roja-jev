from __future__ import annotations

"""Test E2E de combat sense LLM: la policy sola ha de guanyar el combat del rival.

Des de battle1.ss (intro del combat rival Bulbasaur nv5 vs Squirtle nv5) juga amb
pla fixe 'attack' fins que battle_active=False. Verifica que:
- les fases (text/action/move) i els cursors reals es llegeixen,
- l'HP en viu de gBattleMons baixa (jugador i enemic),
- la navegacio del cursor segueix l'estat real (forcem el cursor a moviment 2 i
  la policy ha de tornar al millor moviment), i
- el combat acaba amb outcome=1 (guanyat) i els prompts de final es passen.

Si /tmp/drive2/battle1.ss no existeix, el recrea des de starter.ss caminant fins
al rival (com scripts de /tmp/drive2). Us:
    uv run python scripts/test_battle.py [--rom roms/flama-roja.gba]
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flamaroja.battle_data import best_move, expected_damage
from flamaroja.decisions import Decisions
from flamaroja.emulator import GbaEmulator
from flamaroja.memory import BattleMon, GameState, read_pos, read_state
from flamaroja.nav import bfs
from flamaroja.policy import PolicyConfig, plan

BATTLE1 = "/tmp/drive2/battle1.ss"


def test_policy_unit() -> None:
    """Politica de combat i calcul de dany, sense emulador."""
    cfg = PolicyConfig()

    def mk(phase: str, cur_a: int = 0, cur_m: int = 0) -> GameState:
        return GameState(
            battle_active=True,
            battle_phase=phase,
            battle_action_cursor=cur_a,
            battle_move_cursor=cur_m,
            battle_player=BattleMon(
                species_id=7, level=5, hp=20, max_hp=20, attack=11, defense=12,
                speed=10, sp_attack=10, sp_defense=12, moves=[33, 39, 0, 0],
                pp=[35, 30, 0, 0], types=(11, 11),
            ),
            battle_enemy=BattleMon(
                species_id=1, level=5, hp=19, max_hp=19, attack=9, defense=9,
                speed=9, sp_attack=11, sp_defense=9, moves=[33, 45, 0, 0],
                pp=[35, 40, 0, 0], types=(12, 3),
            ),
        )

    def seq(gs: GameState, dec: Decisions) -> str:
        return "+".join(p.button for p in plan(gs, dec, cfg))

    atk = Decisions(battle="attack", battle_confidence=1.0)
    flee = Decisions(battle="run", battle_confidence=1.0)
    weak = Decisions(battle="attack", battle_confidence=0.1)
    lethal = Decisions(battle="attack", battle_confidence=1.0, enemy_threat=2.0, hp_critical=0.9)
    heal = Decisions(battle="heal", battle_confidence=1.0)

    assert seq(mk("text"), atk) == "a"
    assert seq(mk("action", 0), atk) == "a"
    assert seq(mk("action", 3), atk) == "left+up+a"
    assert seq(mk("action", 0), flee) == "right+down+a"
    assert seq(mk("action", 2), flee) == "right+a"
    assert seq(mk("action", 0), weak) == "a"  # confianca baixa: pla per defecte = attack
    assert seq(mk("action", 1), heal) == "left+a"  # heal sense navegacio de bossa: ataca
    assert seq(mk("action", 0), lethal) == "right+down+a"  # amenaca letal + party critica: fuig
    assert seq(mk("move", 0, 0), atk) == "a"
    assert seq(mk("move", 0, 1), atk) == "left+a"  # el cursor recordat era al mov 2: hi torna
    assert seq(mk("move", 0, 1), flee) == "b"  # fugir es decideix al menu d'accio

    gs = mk("move")
    assert expected_damage(gs.battle_player, gs.battle_enemy, 33) == 5  # Pla
    assert expected_damage(gs.battle_player, gs.battle_enemy, 39) == 0  # Cua (estat)
    assert expected_damage(gs.battle_player, gs.battle_enemy, 52) == 10  # Bras vs Planta/Verí x2
    assert best_move(gs.battle_player, gs.battle_enemy) == 0
    gs.battle_player.pp = [0, 30, 0, 0]
    assert best_move(gs.battle_player, gs.battle_enemy) == 1  # sense PP al millor: l'altre
    print("policy/battle_data unit: OK")


def make_battle1(emu: GbaEmulator, starter: str) -> None:
    """Recrea battle1.ss: camina fins al rival del laboratori i deixa que comenci el combat."""
    emu.load_state(starter)
    emu.tick(3)
    for _ in range(12):
        x, y, _b, _n = read_pos(emu)
        gs = read_state(emu, frame=emu.frame)
        if gs.battle_active:
            break
        path = bfs(gs.cmap, (x, y), (6, 11))
        if not path:
            break
        emu.press(path[0], hold=18, settle=15)
    for _ in range(80):
        gs = read_state(emu, frame=emu.frame)
        if gs.battle_active:
            break
        emu.press("a", hold=4, settle=40)
    emu.tick(200)
    gs = read_state(emu, frame=emu.frame)
    assert gs.battle_active, "no s'ha pogut iniciar el combat del rival des de starter.ss"
    Path(BATTLE1).parent.mkdir(parents=True, exist_ok=True)
    emu.save_state(BATTLE1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", default=os.environ.get("FLAMAROJA_ROM") or str(ROOT / "roms/flama-roja.gba"))
    parser.add_argument("--save", default=BATTLE1)
    parser.add_argument("--starter", default=str(ROOT / "starter.ss"))
    parser.add_argument("--max-cycles", type=int, default=900)
    args = parser.parse_args()

    test_policy_unit()

    emu = GbaEmulator(args.rom)
    emu.tick(60)
    if Path(args.save).is_file():
        emu.load_state(args.save)
    else:
        print(f"{args.save} no trobat: el recreo des de {args.starter}")
        make_battle1(emu, args.starter)
        if args.save != BATTLE1:
            emu.load_state(args.save)
    emu.tick(3)

    gs = read_state(emu, frame=emu.frame)
    assert gs.battle_active, "el save state hauria de ser dins del combat"
    assert gs.battle_player is not None and gs.battle_enemy is not None, "gBattleMons hauria de donar els dos mons"
    print(f"inici: jo {gs.battle_player.species} nv{gs.battle_player.level} {gs.battle_player.hp}/{gs.battle_player.max_hp}HP "
          f"vs {gs.battle_enemy.species} nv{gs.battle_enemy.level} {gs.battle_enemy.hp}/{gs.battle_enemy.max_hp}HP, "
          f"fase={gs.battle_phase or '?'}")
    start_enemy_hp = gs.battle_enemy.hp
    dec = Decisions(battle="attack", battle_confidence=1.0)
    cfg = PolicyConfig()

    phases: set[str] = set()
    min_player_hp = gs.battle_player.hp
    min_enemy_hp = start_enemy_hp
    outcome_seen = 0  # gBattleOutcome es neteja poc despres de tancar el combat: el capturarem en viu
    saw_recover_left = False  # la policy ha de corregir el cursor mogut a ma
    perturbed = False
    cycles = 0
    for cycle in range(args.max_cycles):
        gs = read_state(emu, frame=emu.frame)
        if not gs.battle_active:
            break
        phases.add(gs.battle_phase)
        outcome_seen = max(outcome_seen, gs.battle_outcome)
        if gs.battle_player is not None and gs.battle_enemy is not None:
            min_player_hp = min(min_player_hp, gs.battle_player.hp)
            min_enemy_hp = min(min_enemy_hp, gs.battle_enemy.hp)
        # una vegada: mou el cursor de moviment a ma (mov 2); la policy hi ha de tornar
        if not perturbed and gs.battle_phase == "move":
            emu.press("right", hold=2, settle=30)
            gs = read_state(emu, frame=emu.frame)
            assert gs.battle_move_cursor == 1, f"cursor de moviments hauria de ser 1, es {gs.battle_move_cursor}"
            perturbed = True
        presses = plan(gs, dec, cfg)
        assert presses, "la policy no hauria de quedar-se sense accions en combat"
        if perturbed and not saw_recover_left and gs.battle_phase == "move":
            saw_recover_left = presses[0].button == "left"
        for p in presses:
            emu.press(p.button, p.hold, p.settle)
        cycles += 1
    else:
        raise SystemExit(f"FAIL: el combat no acaba en {args.max_cycles} cicles")

    gs = read_state(emu, frame=emu.frame)
    outcome = outcome_seen
    print(f"fi en {cycles} cicles: outcome={outcome} party_hp={[(m.species, m.hp, m.max_hp) for m in gs.party]}")
    print(f"fases vistes: {sorted(phases)} | min hp jugador={min_player_hp} enemic={min_enemy_hp}")
    assert "action" in phases and "move" in phases and "text" in phases, f"fases llegides malament: {phases}"
    assert min_enemy_hp < start_enemy_hp, "l'HP de l'enemic (gBattleMons) hauria d'haver baixat"
    assert min_player_hp < gs.party[0].max_hp or min_enemy_hp == 0, "cap canvi d'HP llegit en viu"
    assert perturbed and saw_recover_left, "la policy hauria de navegar des del cursor real (left per tornar al mov 1)"
    assert outcome == 1, f"outcome esperat 1 (guanyat), es {outcome}"
    assert not gs.battle_active
    emu.close()
    print("\nPASS: combat complet guanyat per codi (sense LLM), cursors i HP en viu verificats")


if __name__ == "__main__":
    main()
