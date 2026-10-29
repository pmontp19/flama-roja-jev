# flama-roja-jev

Harness **System One (Jev)** que juga a *Pokémon Flama Roja* (Pokémon FireRed traduït al català per [TraduSquare](https://tradusquare.es/proyectos/pokemon-flama-roja-fulla-verda/)) via **mGBA**, decidint amb preguntes tipades (`Choice`, `Score`, `Noul`) sobre estat estructurat de la memòria del joc.

Aquest harness no usa ReAct ni chain-of-thought: no hi ha cap LLM generant text lliure. El bucle és:

```
mGBA (ROM BPRE) ──> build_state (memòria -> JSON) ──> 1 crida system_one amb 7 preguntes en paral·lel
                                                            │
codi decideix (policy.py): probabilitats calibrades ─────────┘
        │
        └──> botons -> mGBA -> tick
```

## Requisits

- [uv](https://docs.astral.sh/uv/) i Python 3.11 (pinjat a `.python-version`: els wheels de `mgba` només existeixen per 3.10/3.11)
- Una **ROM legal**: necessites el teu propi dump de *Pokémon Edición Rojo Fuego (S)* (BPRE). Aquest projecte no distribueix ROMs.

### Emulador (mGBA)

| Plataforma | Com |
|---|---|
| macOS Apple Silicon | `uv sync && ./scripts/setup-mgba-x64.sh` (compila libmgba x86_64 + bindings i ho enganxa al venv, sota Rosetta) |
| macOS Intel / Linux x86_64 / Linux arm64 | `uv sync` i prou (wheel oficial de `mgba`) |

`setup-mgba-x64.sh` també apingarda els headers d'E-Reader de mgba (l'API de scan depèn de FFMPEG, que desactivem) i afegeix els defines del build al generador de bindings cffi; si mgba canvia el master, torna a executar-lo.

## Instal·lació

```bash
uv sync
./scripts/setup-mgba-x64.sh   # només macOS Apple Silicon
cp .env.example .env          # omple claus i FLAMAROJA_ROM
```

## La ROM en català

1. Fes un dump de la teva cartutx/descàrrega legal de *Pokémon Edición Rojo Fuego (S)* → `bpre_s.gba`
2. Baixa el parche **Pokémon Flama Roja** (v1.2) de [TraduSquare](https://tradusquare.es/proyectos/pokemon-flama-roja-fulla-verda/) (cal login)
3. Aplica'l amb [Flips](https://www.romhacking.net/utilities/240/):
   ```bash
   flips --apply flama-roja.bps bpre_s.gba flama-roja.gba
   ```
   (segons el format del parche, `.ips` o `.bps`)
4. Verifica que els offsets quadren amb el teu dump:
   ```bash
   cp .env.example .env  # i omple FLAMAROJA_ROM
   uv run flamaroja probe --warmup 1500 --screenshot shot.png
   ```
   Si el JSON mostra mapes/partida coherent i el PNG mostra la intro, tens els offsets bé. Les adreces estan verificades contra **FireRed USA 1.0 (BPRE)** ([DataCrystal](https://datacrystal.tcrf.net/wiki/Pok%C3%A9mon_3rd_Generation/Pok%C3%A9mon_FireRed_and_LeafGreen/RAM_map)); les versions EU acostumen a compartir layout, però així ho confirmes empíricament.

Nota divertida: la traducció usa valencià i renomena Pokémon (Deoxys→Alieene, Ho-oh→Sifirén...). Els noms d'espècie del harness són els anglesos oficials; el model rep l'id + nom.

## API keys

Copies `.env.example` → `.env`:

- `TYPESAFE_API_KEY`: early access de [TypeSafe](https://typesafe.ai/) → usa **Jev real** (`backend --backend jev`)
- Sense clau TypeSafe: el mateix workflow corre sobre LLMs amb l'[adapter oficial](https://github.com/typesafe-ai/system-one-adapter-python) (`--backend adapter --provider openai --model gpt-4o-mini`), útil per comparar cost/velocitat/intel·ligència contra Jev

## Ús

```bash
uv sync

# verificar ROM + offsets
uv run flamaroja probe --rom ~/roms/flama-roja.gba --screenshot shot.png

# captura de pantalla
uv run flamaroja screenshot --rom ~/roms/flama-roja.gba --out intro.png

# bucle principal (auto: jev si hi ha TYPESAFE_API_KEY, sinó adapter LLM)
uv run flamaroja run --rom ~/roms/flama-roja.gba --trace trace.jsonl

# mirant-lo en directe + dashboard web amb les decisions de Jev
uv run flamaroja run --save play.ss --window --dashboard

# tot: finestra + dashboard + gravacio mp4
uv run flamaroja run --save play.ss --window --dashboard --record sessio.mp4
```

Save states: fes-ne un primer amb qualsevol eina o afegeix un `emu.save_state()` després del warmup; amb `--save state.ss` starts des d'allà (útil per saltar la intro llarga de FireRed).

## El workflow de decisions (fan-out especulatiu)

Una única crida per tick, amb totes les preguntes barrejades (s'avaluen en paral·lel i aïllades sobre el mateix estat):

| ID | Tipus | Decideix |
|---|---|---|
| `screen_mode` | `Choice` | title/intro/overworld/dialog/battle/menu/unknown |
| `overworld_action` | `Choice` | up/down/left/right/interact/menu/none |
| `dialog_response` | `Choice` | advance (A)/confirm (A)/cancel (B) |
| `battle_plan` | `Choice` | attack/heal/switch/run (el codi tria el millor moviment per dany esperat) |
| `party_critical` | `Noul` | P(primer Pokémon a punt de desmaiar-se) |
| `enemy_threat` | `Score` | harmless..lethal |
| `objective` | `Choice` | story/heal/explore/grind |

El codi (`policy.py`) compon les respostes amb llindars (confidence floor, run si `enemy_threat` alt + `party_critical` alta) i les tradueix a botons. En combat hi ha una màquina d'estats per fases: text = només A (sense cridar el backend), menú d'acció/moviments = navegació amb els cursors reals de memòria (`gActionSelectionCursor`/`gMoveSelectionCursor`, que el joc recorda entre torns) i tria determinista del moviment per dany esperat (`battle_data.py`). Això és exactament la filosofia System One: preguntes atòmiques, lògica al codi; quan vullis canviar comportament, toques un coeficient de `PolicyConfig`, no un prompt.

## Constants de memòria (BPRE)

| Adreça | Què |
|---|---|
| `[0x03005008]` | ptr save block mapa: +0 cam X u16, +2 cam Y u16, +4 map num, +5 map bank |
| `[0x0300500C]` | ptr save block personal: +0 nom (8b, charmap Gen3) |
| `0x02024284` | `gPlayerParty`: 6 × 100b (congelada durant el combat) |
| `0x02023BE4` | `gBattleMons[4]` (0x58b per battler): HP/PP/stats/moviments en viu; 0 = jugador, 1 = enemic |
| `0x02023FF8` | `gActionSelectionCursor` + `gMoveSelectionCursor` (bitfields graella 2x2) |
| `0x02023E8A` | `gBattleOutcome`: 1 guanyat, 2 perdut, 4 fugit |
| `0x03004F30` | `gBattlerControllerFuncs` (IWRAM): funció de control del jugador = fase del combat |
| `0x03000F9C` | flag de fade (transició) |
| `0x02021D18` | string del text box actiu |

El Pokémon Gen3 va xifrat: PID ⊕ OTID com a clau, 4 subestructures de 12b reordenades per `PID % 24` (Growth/Attacks/EVs/Misc). `memory.py` el desencripta i extreu espècie, nivell, HP, estat, moviments i PP.

## Roadmap

- Pathfinding BFS/A\* sobre tiles: Jev tria l'objectiu, el codi camina (la millora més gran)
- Tracking del cursor del _start menu_ i de la bossa/equip en combat (el de batalla ja es llegeix de `gActionSelectionCursor`/`gMoveSelectionCursor`)
- Plans heal/switch amb navegació real de bossa/equip (ara cauen a atacar amb el millor moviment)
- Eleccions d'alta cardinalitat amb el patró 2-etapes (scoring independent + tria) per a objectius com "quina ruta visito"
- Save states automàtics periòdics i re-rolls de decisions amb baixa confiança
- Succés/trace dashboard per repassar decisions amb probabilitats
- Suport *Pokémon Roig* (Red en català) via PyBoy per comparativa Gen 1

## Crèdits

- [pret/pokefirered](https://github.com/pret/pokefirered) (decomp, charmap i layout)
- [DataCrystal RAM map FRLG](https://datacrystal.tcrf.net/wiki/Pok%C3%A9mon_3rd_Generation/Pok%C3%A9mon_FireRed_and_LeafGreen/RAM_map)
- [NousResearch/pokemon-agent](https://github.com/NousResearch/pokemon-agent) (referència de l'API de pygba, MIT)
- [TraduSquare](https://tradusquare.es/proyectos/pokemon-flama-roja-fulla-verda/) (Flama Roja, EyeOfGuill i aimapepinillo)
- [TypeSafe AI](https://typesafe.ai/) (Jev, System One) i [mGBA](https://mgba.io/)
