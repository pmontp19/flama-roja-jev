"""Memoria del harness: visites, notes, etiquetes als criteris de navegacio i payload."""
from flamaroja.decisions import MAP_NAMES, build_questions, state_payload
from flamaroja.memory import GameState
from flamaroja.world import World

w = World(None)
assert w.tag(3, 2) == "never visited"
w.enter((3, 1), None)
w.enter((3, 2), (3, 1))
w.enter((3, 2), (6, 0))
w.note((3, 2), "PEWTER CITY\n  POKéMON GYM  LEADER: BROCK")
w.note((3, 2), "PEWTER CITY POKéMON GYM LEADER: BROCK")  # duplicat
assert w.visits(3, 2) == 2 and w.tag(3, 2) == "visited 2x"
assert w.maps["3/2"]["from"] == ["3/1", "6/0"]
v = w.view((3, 2), MAP_NAMES)
assert v["visited_maps"] == ["Viridian City", "Pewter City"], v
assert v["here_notes"] == ["PEWTER CITY POKéMON GYM LEADER: BROCK"], v
assert "nav_destination" in build_questions(None, None, w)
assert state_payload(GameState(), w, "x")["last_action"] == "x" and state_payload(GameState(), w)["last_action"] == "none yet"
print("PASS: memoria del harness (visites, notes, vista)")
