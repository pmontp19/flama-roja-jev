from __future__ import annotations

import json
from pathlib import Path

NOTE_MAX = 4  # notes per mapa: prou per recordar un cartell, sense inflar el payload


class World:
    """Memoria del harness (el que son les notes a Claude Plays Pokemon).

    Jev nomes respon opcions tipades i no te context entre crides: no pot escriure text lliure.
    Per aixo la memoria s'escriu sola des de la RAM (mapes visitats, d'on venim, text vist)
    i es torna a injectar al payload i als criteris de navegacio.
    """

    def __init__(self, path: str | None = "world.json") -> None:
        self.path = Path(path) if path else None
        self.maps: dict[str, dict] = {}

    @staticmethod
    def key(bank: int, num: int) -> str:
        return f"{bank}/{num}"

    def enter(self, here: tuple[int, int], came_from: tuple[int, int] | None) -> None:
        m = self.maps.setdefault(self.key(*here), {"visits": 0, "from": [], "notes": []})
        m["visits"] += 1
        if came_from is not None and self.key(*came_from) not in m["from"]:
            m["from"].append(self.key(*came_from))
        self._save()

    def note(self, here: tuple[int, int], text: str) -> None:
        m = self.maps.get(self.key(*here))
        text = " ".join(text.split())[:100]
        if m is not None and text and text not in m["notes"] and len(m["notes"]) < NOTE_MAX:
            m["notes"].append(text)
            self._save()

    def visits(self, bank: int, num: int) -> int:
        return self.maps.get(self.key(bank, num), {}).get("visits", 0)

    def tag(self, bank: int, num: int) -> str:
        n = self.visits(bank, num)
        return "never visited" if n == 0 else f"visited {n}x"

    def view(self, here: tuple[int, int], names: dict[tuple[int, int], str]) -> dict:
        m = self.maps.get(self.key(*here), {})
        return {
            "visited_maps": [names.get(tuple(map(int, k.split("/"))), k) for k in self.maps],  # type: ignore[arg-type]
            "here_visits": m.get("visits", 0),
            "here_notes": m.get("notes", []),
        }

    def _save(self) -> None:
        if self.path is not None:
            self.path.write_text(json.dumps(self.maps, indent=1, ensure_ascii=False))
