from __future__ import annotations

from dataclasses import dataclass

from .battle_data import best_move
from .decisions import Decisions
from .memory import GameState

_DIALOG_NAV = {
    "advance": ("a",),
    "confirm": ("a",),
    "cancel": ("b",),
}


@dataclass(frozen=True)
class Press:
    button: str
    hold: int = 2
    settle: int = 20


@dataclass(frozen=True)
class PolicyConfig:
    confidence_floor: float = 0.35
    run_when_lethal_and_critical: bool = True
    lethal_threat: float = 1.75
    critical_hp: float = 0.85
    walk_hold: int = 18  # una passa dura 16 frames; 18 la completa sense doblar gairebé mai
    walk_settle: int = 15
    tap_hold: int = 2
    tap_settle: int = 20


def _taps(seq: tuple[str, ...], cfg: PolicyConfig) -> list[Press]:
    return [Press(button=b, hold=cfg.tap_hold, settle=cfg.tap_settle) for b in seq]


def _nav_grid(cur: int, target: int) -> tuple[str, ...]:
    """Prementades per anar del cursor (bitfield 2x2: bit0=col dreta, bit1=fila baixa) al desti.

    Mimifica HandleInputChoose{Action,Move}: right/left commuten bit0, down/up bit1.
    """
    presses = []
    if (cur & 1) != (target & 1):
        presses.append("right" if target & 1 else "left")
    if (cur & 2) != (target & 2):
        presses.append("down" if target & 2 else "up")
    return tuple(presses)


# menu d'accio: LLUITA=0, BOLSA=1, EQUIP=2, FUGIR=3 (mateix bitfield que el cursor)
ACTION_FIGHT, ACTION_RUN = 0, 3


def _battle_plan(gs: GameState, dec: Decisions, cfg: PolicyConfig) -> tuple[str, ...]:
    """Sequencia de botons per aquest cicle de combat, segons la fase i el pla de Jev.

    Jev nomes tria el pla d'alt nivell (attack/heal/switch/run); el moviment concret
    el decideix el codi per dany esperat. ponytail: heal/switch encara no tenen
    navegacio de bossa/equip, cauen a atacar amb el millor moviment.
    """
    if gs.battle_phase == "action":
        plan = dec.battle if dec.battle_confidence >= cfg.confidence_floor else "attack"
        lethal = (
            cfg.run_when_lethal_and_critical
            and plan == "attack"
            and dec.enemy_threat >= cfg.lethal_threat
            and dec.hp_critical >= cfg.critical_hp
        )
        target = ACTION_RUN if (plan == "run" or lethal) else ACTION_FIGHT
        return _nav_grid(gs.battle_action_cursor, target) + ("a",)
    if gs.battle_phase == "move":
        if dec.battle == "run" and dec.battle_confidence >= cfg.confidence_floor:
            return ("b",)  # torna al menu d'accio; FUGIR es tria alla
        player, enemy = gs.battle_player, gs.battle_enemy
        if player is None or enemy is None:
            return ("b",)
        target = best_move(player, enemy)
        return _nav_grid(gs.battle_move_cursor, target) + ("a",)
    # fase text (o cutscene/animacio): avanca amb A; prompts de final (apendre moviment,
    # evolucio, diners/exp) queden al valor per defecte del cursor, que es "No"
    return ("a",)


def plan(gs: GameState, dec: Decisions, cfg: PolicyConfig) -> list[Press]:
    if gs.fading:
        return []

    if gs.battle_active:
        return _taps(_battle_plan(gs, dec, cfg), cfg)

    if dec.screen_mode == "dialog" or (dec.screen_mode in ("menu", "unknown") and gs.dialog_text):
        response = dec.dialog if dec.dialog_confidence >= cfg.confidence_floor else "advance"
        return _taps(_DIALOG_NAV.get(response, ("a",)), cfg)

    if dec.screen_mode == "overworld":
        if dec.overworld_confidence < cfg.confidence_floor:
            return []
        if dec.overworld in ("up", "down", "left", "right"):
            return [
                Press(
                    button=dec.overworld,
                    hold=cfg.walk_hold,
                    settle=cfg.walk_settle,
                )
            ]
        if dec.overworld == "interact":
            return _taps(("a",), cfg)
        if dec.overworld == "menu":
            return _taps(("start",), cfg)
        return []

    return []
