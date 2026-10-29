from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from typesafe_sdk import Choice, Noul, Score

from .memory import GameState
from .world import World

SCREEN_MODES = ("title", "intro", "overworld", "dialog", "battle", "menu", "unknown")
OVERWORLD_ACTIONS = ("up", "down", "left", "right", "interact", "menu", "none")
DIALOG_RESPONSES = ("advance", "confirm", "cancel")
BATTLE_PLANS = ("attack", "heal", "switch", "run")
OBJECTIVES = ("story", "heal", "explore", "grind")


@dataclass
class Decisions:
    screen_mode: str = "unknown"
    screen_confidence: float = 0.0
    overworld: str = "none"
    overworld_confidence: float = 0.0
    dialog: str = "advance"
    dialog_confidence: float = 0.0
    battle: str = "attack"
    battle_confidence: float = 0.0
    nav_destination: str = "none"
    nav_confidence: float = 0.0
    objective: str = "explore"
    objective_confidence: float = 0.0
    hp_critical: float = 0.0
    enemy_threat: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


class DecisionBackend(Protocol):
    def system_one(self, state: Any, questions: dict[str, Any]) -> Any: ...


def make_backend(kind: str) -> DecisionBackend:
    if kind == "jev":
        from typesafe_sdk import TypeSafeClient

        return TypeSafeClient()
    if kind == "adapter":
        from system_one_adapter import SystemOneAdapterClient

        return SystemOneAdapterClient(
            structured_outputs=True,
            llm_answer_mode="probabilities",
            normalize_probabilities=True,
        )
    raise ValueError(f"backend desconegut: {kind}")


def state_payload(gs: GameState, world: World | None = None, last: str = "") -> dict[str, Any]:
    cmap = gs.cmap
    map_info: dict[str, Any] = {
        "bank": gs.map_bank,
        "number": gs.map_number,
        "camera_x": gs.camera_x,
        "camera_y": gs.camera_y,
    }
    if cmap is not None:
        map_info["width"] = cmap.width
        map_info["height"] = cmap.height
        map_info["warps"] = [w.to_dict() for w in cmap.warps]
        # graella compacta per contextualitzar ( '#' mur, '.' lliure, '+' warp )
        if cmap.width <= 60 and cmap.height <= 40:
            map_info["grid"] = cmap.rows()
    if gs.battle_active:
        battle: dict[str, Any] = {
            "active": True,
            "phase": gs.battle_phase,  # "action"/"move" = cal decidir; "text" = nomes avanca
            "outcome": gs.battle_outcome,
            "player": gs.battle_player.to_dict() if gs.battle_player else None,
            "enemy": gs.battle_enemy.to_dict() if gs.battle_enemy else None,
        }
    else:
        battle = {"active": False}
    return {
        "map": map_info,
        "player": {"name": gs.player_name, "facing": gs.facing},
        "party": [mon.to_dict() for mon in gs.party],
        "has_oaks_parcel": gs.has_parcel,
        "oaks_parcel_delivered": gs.parcel_delivered,
        "badges": gs.badges,
        "last_action": last or "none yet",  # fil de continuitat: Jev no recorda la crida anterior
        "battle": battle,
        "dialog": {"text": gs.dialog_text[:400]},
        "signals": {"fading": gs.fading, "frame": gs.frame},
        **({"memory": world.view((gs.map_bank, gs.map_number), MAP_NAMES)} if world is not None else {}),
    }


# noms de mapes FRLG (bank, num) coneguts; la resta es mostren com bank/num
MAP_NAMES = {
    (3, 0): "Pallet Town",
    (3, 19): "Route 1 (north of Pallet Town, tall grass)",
    (3, 39): "Route 21 (south sea route)",
    (4, 0): "player's house 1F",
    (4, 1): "player's room",
    (4, 2): "rival's house",
    (4, 3): "Professor Oak's lab",
    (3, 1): "Viridian City",
    (3, 2): "Pewter City",
    (3, 20): "Route 2 (north of Viridian City)",
    (3, 41): "Route 22 (west of Viridian City)",
    (5, 0): "Viridian house",
    (5, 1): "Viridian Gym (locked early)",
    (5, 2): "Viridian house (school)",
    (5, 3): "Viridian Poké Mart",
    (5, 4): "Viridian Pokémon Center (heals the team)",
    # grup 6 = interiors de Pewter (ordre de pokefirered, sense verificar en viu)
    (6, 0): "Pewter Museum 1F",
    (6, 1): "Pewter Museum 2F",
    (6, 2): "Pewter Gym (Brock, Rock-type leader)",
    (6, 3): "Pewter Poké Mart",
    (6, 4): "Pewter house",
    (6, 5): "Pewter Pokémon Center (heals the team)",
    (6, 6): "Pewter Pokémon Center 2F",
    (6, 7): "Pewter house",
}

QUEST = (
    "Quest: get the first Pokémon. Oak stops the player when entering the tall grass of Route 1 "
    "(north of Pallet Town) and takes them to his lab. Do not wander into houses; "
    "never go back to the map just left. In Oak's lab, pick one starter Poké Ball (press A on it, confirm with yes)."
)


QUEST_PARCEL = (
    "Quest: Oak's Pokédex errand. The old man blocks Route 2 north of Viridian City until the parcel is delivered. "
    "If `has_oaks_parcel` is false: go to the Viridian Poké Mart in Viridian City (the clerk hands over Oak's Parcel). "
    "If true: walk back south to Pallet Town (Route 1) and enter Professor Oak's lab to deliver it. "
    "Never go to Route 2 before that. Ignore the Pokémon Center and tall grass detours."
)


QUEST_NORTH = (
    "Quest: Oak's parcel is delivered and the Pokédex obtained. Head north: Viridian City, Route 2, Viridian Forest, "
    "Pewter City. Do not enter houses on the way. In Pewter City the goal is the Pewter Gym: beat Brock for the first badge "
    "(`badges` 0 -> 1); prefer doors marked never visited. Once `badges` >= 1 go east via Route 3."
)


def nav_options(gs: GameState | None, came_from: tuple[int, int] | None = None, world: World | None = None) -> list:
    """Sortides usables del mapa, sense la del mapa d'on venim (evita el ping-pong casa/exterior)."""
    warps = [w for w in (gs.warps if gs is not None else []) if w.usable]
    if gs is not None:
        # ponytail: els flags d'objecte amagat no funcionen; boles nomes sense equip, Oak nomes amb el paquet, Brock nomes al seu gimnas
        here = (gs.map_bank, gs.map_number)
        warps = [w for w in warps if not w.act or (gs.has_parcel and here == (4, 3) if "Oak (" in w.label else here == (6, 2) and not gs.badges if "Brock" in w.label else not gs.party)]
    if gs is not None and world is not None:
        warps = [w for w in warps if not world.banned((gs.map_bank, gs.map_number), w.x, w.y)] or warps
    kept = [w for w in warps if (w.dest_bank, w.dest_map) != came_from]
    return kept or warps


def build_questions(gs: GameState | None = None, came_from: tuple[int, int] | None = None, world: World | None = None) -> dict[str, Choice | Noul | Score]:
    warps = nav_options(gs, came_from, world)
    nav_criteria: dict[str, str] = {
        "none": "No warp destination in this map; movement will be handled directly",
    }
    for i, w in enumerate(warps):
        kind = "warp"
        if w.press is not None:
            kind = "stairs" if w.behavior > 0x6B else "door exit"
        if w.edge:
            kind = f"map edge going {w.edge}"
        if w.act:
            nav_criteria[f"warp_{i}"] = f"walk next to it and press A: {w.label} at ({w.x},{w.y})"
            continue
        dest = MAP_NAMES.get((w.dest_bank, w.dest_map), f"map {w.dest_bank}/{w.dest_map}")
        seen = f" ({world.tag(w.dest_bank, w.dest_map)})" if world is not None else ""
        nav_criteria[f"warp_{i}"] = f"{kind} at ({w.x},{w.y}) leading to {dest}{seen}"
    questions: dict[str, Choice | Noul | Score] = {
        "screen_mode": Choice(
            instructions="Which game screen is currently active? Judge from `map`, `battle.active`, `dialog.text` and `signals`.",
            criteria={
                "title": "Title screen or game intro menus",
                "intro": "New game intro, naming screen or scripted cutscene",
                "overworld": "Player is free to walk in the field",
                "dialog": "A text box or conversation is open and waiting for input",
                "battle": "A Pokémon battle is happening",
                "menu": "A pause menu or submenu is open",
                "unknown": "Cannot be determined from this state",
            },
        ),
        "overworld_action": Choice(
            instructions="If `screen_mode` is `overworld`, which single action should the player take now to make story progress?",
            criteria={
                "up": "Walk one tile north",
                "down": "Walk one tile south",
                "left": "Walk one tile west",
                "right": "Walk one tile east",
                "interact": "Press A on the tile the player faces (NPC, sign, item)",
                "menu": "Open the pause menu (START)",
                "none": "Stay still and wait",
            },
        ),
        "dialog_response": Choice(
            instructions="If a dialog is open (`dialog.text` non-empty), how should we respond to it?",
            criteria={
                "advance": "Just advance the text (press A)",
                "confirm": "Choose the highlighted affirmative option (press A on yes)",
                "cancel": "Decline or dismiss the dialog (press B)",
            },
        ),
        "battle_plan": Choice(
            instructions=(
                "If `battle.active` is true and `battle.phase` is `action` or `move`, what is the high-level plan "
                "for this turn? You only pick the plan: deterministic code chooses the exact move (highest expected "
                "damage from `battle.player.moves` against `battle.enemy.types`), navigates the real menu cursors "
                "and executes it. During `battle.phase` = `text` no decision is needed."
            ),
            criteria={
                "attack": "Fight with the best move (code computes expected damage per move and picks the best)",
                "heal": "Restore HP with an item first (ponytail: bag navigation not implemented, code falls back to attacking)",
                "switch": "Send out a different party Pokémon (ponytail: party menu navigation not implemented, code falls back to attacking)",
                "run": "Flee the battle (fails against trainers)",
            },
        ),
        "nav_destination": Choice(
            instructions=(
                "If `screen_mode` is `overworld` and `map.warps` is non-empty, which destination should the player "
                "navigate to? Code pathfinds and walks there; you only pick the destination. " + (QUEST_NORTH if gs is not None and gs.parcel_delivered else QUEST_PARCEL if gs is not None and gs.party else QUEST)
            ),
            criteria=nav_criteria,
        ),
        "party_critical": Noul(
            instructions=(
                "Is the active Pokémon close to fainting? In battle use `battle.player.current_hp` vs `battle.player.max_hp`; "
                "outside battle use `party[0]`."
            ),
        ),
        "enemy_threat": Score(
            instructions="If `battle.active` is true, how dangerous is `battle.enemy` (see its level, types, moves and stats) to our active Pokémon right now?",
            criteria=[
                "Harmless: cannot meaningfully damage us soon",
                "Moderate: can chip us down over several turns",
                "Lethal: can knock out our Pokémon in one or two turns",
            ],
        ),
        "objective": Choice(
            instructions="Which objective should drive the next movement decisions?",
            criteria={
                "story": "Advance the main quest",
                "heal": "Reach a Pokémon Center and heal the party",
                "explore": "Explore unvisited areas",
                "grind": "Battle wild Pokémon to strengthen the party",
            },
        ),
    }
    return questions


def extract_decisions(response: Any) -> Decisions:
    a = response.answers
    nav = a.get("nav_destination")
    return Decisions(
        screen_mode=str(a["screen_mode"].choice),
        screen_confidence=float(a["screen_mode"].confidence or 0.0),
        overworld=str(a["overworld_action"].choice),
        overworld_confidence=float(a["overworld_action"].confidence or 0.0),
        dialog=str(a["dialog_response"].choice),
        dialog_confidence=float(a["dialog_response"].confidence or 0.0),
        battle=str(a["battle_plan"].choice),
        battle_confidence=float(a["battle_plan"].confidence or 0.0),
        nav_destination=str(nav.choice) if nav is not None else "none",
        nav_confidence=float(nav.confidence or 0.0) if nav is not None else 0.0,
        objective=str(a["objective"].choice),
        objective_confidence=float(a["objective"].confidence or 0.0),
        hp_critical=float(a["party_critical"].noul),
        enemy_threat=float(a["enemy_threat"].score),
        raw={"probabilities": {k: getattr(v, "probabilities", None) for k, v in a.items()}},
    )
