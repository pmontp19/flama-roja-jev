from __future__ import annotations

import argparse
import json
import os
import subprocess
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

from .decisions import (
    Decisions,
    build_questions,
    extract_decisions,
    make_backend,
    nav_options,
    state_payload,
)
from .emulator import GbaEmulator
from .memory import read_pos, read_state
from .nav import Navigator, grass_tiles, grind_press
from .policy import PolicyConfig, plan
from .trace import JsonlTrace
from .world import World

GRIND_LEVEL = 9  # nivell minim abans de seguir la historia
# ponytail: ruta cap a casa (la mare cura l'equip) escrita a ma, com TOWARD_GRASS
TOWARD_HOME = {(3, 19): (3, 0), (3, 1): (3, 19), (3, 20): (3, 1), (5, 4): (3, 1), (5, 3): (3, 1)}
# ponytail: ruta cap a l'herba de la Ruta 1 escrita a ma (mapa actual -> seguent mapa); un graf de mapes si cal mes
TOWARD_GRASS = {
    (4, 0): (3, 0), (4, 1): (4, 0), (4, 2): (3, 0), (4, 3): (3, 0),
    (3, 0): (3, 19), (3, 39): (3, 0), (3, 1): (3, 19), (5, 0): (3, 1), (5, 1): (3, 1),
    (5, 2): (3, 1), (5, 3): (3, 1), (5, 4): (3, 1),
}


def _resolve_rom(args: argparse.Namespace) -> str:
    rom = getattr(args, "rom", None) or os.environ.get("FLAMAROJA_ROM")
    if not rom:
        raise SystemExit("Cal --rom o la variable FLAMAROJA_ROM")
    return rom


class VideoRecorder:
    def __init__(self, path: str, fps: int = 30) -> None:
        self.proc = subprocess.Popen(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-s",
                "240x160",
                "-r",
                str(fps),
                "-i",
                "-",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-vf",
                "scale=720:480:flags=neighbor",
                path,
            ],
            stdin=subprocess.PIPE,
        )

    def write(self, frame) -> None:
        self.proc.stdin.write(frame.tobytes())

    def close(self) -> None:
        self.proc.stdin.close()
        self.proc.wait()


def _boot(args: argparse.Namespace) -> GbaEmulator:
    emu = GbaEmulator(
        _resolve_rom(args),
        getattr(args, "sav", None),
        window=getattr(args, "window", False),
    )
    emu.tick(60)
    save = getattr(args, "save", None)
    if save:
        if not Path(save).is_file():
            raise SystemExit(
                f"Save state no trobat: {save}. Crea'l amb 'flamaroja boot' (cal un .sav amb partida iniciada)."
            )
        emu.load_state(save)
    return emu


def _saveblock_ready(emu: GbaEmulator) -> bool:
    ptr = emu.read_u32(0x03005008)
    return 0x02000000 <= ptr < 0x03010000


def cmd_boot(args: argparse.Namespace) -> None:
    emu = GbaEmulator(
        _resolve_rom(args),
        getattr(args, "sav", None),
        window=getattr(args, "window", False),
    )
    emu.tick(600)
    emu.press("start", hold=2, settle=30)
    emu.press("a", hold=2, settle=60)
    emu.press("a", hold=2, settle=120)
    for _ in range(20):
        if _saveblock_ready(emu):
            break
        emu.press("a", hold=2, settle=60)
    emu.tick(120)
    if not _saveblock_ready(emu):
        raise SystemExit(
            "No s'ha arribat a l'overworld. Necessites un .sav amb partida iniciada: "
            "jugues la intro manualment en mGBA amb la mateixa ROM i deses a joc "
            "(el .sav queda al costat de la ROM), despres torna a provar amb --sav."
        )
    gs = read_state(emu, frame=emu.frame)
    emu.save_state(args.out)
    print(f"boot ok: {gs.summary()}")
    print(f"save state: {args.out}")
    emu.close()


def _pick_backend(args: argparse.Namespace) -> str:
    kind = args.backend
    if kind == "auto":
        kind = "jev" if os.environ.get("TYPESAFE_API_KEY") else "adapter"
    return kind


def _ask(backend: str, client, provider: str | None, model: str | None, payload, questions):
    if backend == "jev":
        return client.system_one(state=payload, questions=questions)
    return client.system_one(payload, questions, provider=provider, model=model)


def cmd_probe(args: argparse.Namespace) -> None:
    emu = _boot(args)
    emu.tick(args.warmup)
    gs = read_state(emu, frame=emu.frame)
    print(f"rom: titol={emu.title!r} code={emu.game_code!r}")
    print(json.dumps(state_payload(gs), indent=2, ensure_ascii=False))
    print(f"summary: {gs.summary()}")
    out = getattr(args, "screenshot", None)
    if out:
        emu.screen().save(out)
        print(f"screenshot: {out}")
    emu.close()


def cmd_screenshot(args: argparse.Namespace) -> None:
    emu = _boot(args)
    emu.tick(args.warmup)
    emu.screen().save(args.out)
    print(f"screenshot: {args.out}")
    emu.close()


def cmd_run(args: argparse.Namespace) -> None:
    backend_kind = _pick_backend(args)
    client = make_backend(backend_kind)
    cfg = PolicyConfig()
    trace = JsonlTrace(args.trace)
    emu = _boot(args)
    recorder = VideoRecorder(args.record) if args.record else None
    dashboard = None
    if args.dashboard:
        from .dashboard import Dashboard

        model_label = "jev-latest" if backend_kind == "jev" else args.model
        dashboard = Dashboard(backend_kind, model_label, args.port)
        dashboard.start()
        print(f"dashboard: http://127.0.0.1:{args.port}")
    if recorder is not None or dashboard is not None:
        counter = {"n": 0}

        def hook() -> None:
            counter["n"] += 1
            if counter["n"] % 2 == 0:
                frame = emu.screen()
                if recorder is not None:
                    recorder.write(frame)
                if dashboard is not None:
                    dashboard.publish_frame(frame)

        emu.frame_hook = hook
    model_label = "jev-latest" if backend_kind == "jev" else args.model
    print(f"backend={backend_kind} provider={args.provider} model={model_label} trace={args.trace}")
    if recorder is not None:
        print(f"record: {args.record}")
    started = time.time()
    job: dict[str, object] = {}

    def worker(payload: dict, questions: dict) -> None:
        try:
            job["response"] = _ask(backend_kind, client, args.provider, args.model, payload, questions)
        except Exception as exc:
            job["error"] = exc

    try:
        nav = Navigator(emu, cfg)
        cur_map: tuple[int, int] | None = None
        came_from: tuple[int, int] | None = None
        grass_cache: dict[tuple[int, int], set[tuple[int, int]]] = {}
        grind_last: tuple[int, int] | None = None
        grind_steps = 0
        grind_target = GRIND_LEVEL
        lost = False
        grind_still = 0
        visited: set[tuple[int, int]] = set()
        world = World(args.memory)
        last = ""
        calls = {"jev": 0, "code": 0}  # qui decideix: crides a Jev vs cicles resolts per codi
        blocked_n = 0
        idle = 0  # cicles overworld seguits sense desti de navegacio fiable
        for cycle in range(args.ticks):
            gs = read_state(emu, frame=emu.frame)
            calls["code"] += 1
            if cycle and cycle % 200 == 0:
                print(f"[{cycle:06d}] decisions: jev={calls['jev']} codi={calls['code']}", flush=True)
            here = (gs.map_bank, gs.map_number)
            if here not in visited:  # instantania de la primera visita a cada mapa: punt de partida per depurar
                Path("maps").mkdir(exist_ok=True)
                emu.save_state(f"maps/{here[0]}_{here[1]}.ss")
            visited.add(here)
            if not gs.battle_active:
                lost = False
            elif gs.battle_outcome == 2 and not lost:  # hem perdut: entrena 2 nivells mes abans de tornar a provar
                lost, grind_target = True, min(grind_target + 2, 30)
            if here != cur_map:
                came_from, cur_map = cur_map, here
                world.enter(here, came_from)
            if gs.dialog_text and not gs.battle_active:
                world.note(here, gs.dialog_text)

            # navegacio activa: camina sense gastar crides LLM
            if nav.active():
                status = nav.step()
                x, y, bank, num = read_pos(emu)
                line = (
                    f"[{cycle:06d} f={emu.frame}] nav {status} goal={nav.tile} "
                    f"map {bank}/{num} pos({x},{y})"
                )
                print(line, flush=True)
                trace.log(
                    {
                        "cycle": cycle,
                        "frame": emu.frame,
                        "nav": {
                            "status": status,
                            "goal": list(nav.tile),
                            "warp": nav.warp.to_dict() if nav.warp else None,
                            "steps": nav.steps,
                            "stuck": nav.stuck,
                        },
                    }
                )
                blocked_n = blocked_n + 1 if status == "blocked" else 0 if status in ("warped", "done") else blocked_n
                if blocked_n == 6:  # encallat de debò: deixa l'estat per reproduir-ho
                    emu.save_state("stuck.ss")
                    emu.screen().save("stuck.png")
                if blocked_n == 12 and nav.warp is not None:  # ni el menu: la sortida no es assolible, no la tornis a proposar
                    world.ban(here, nav.warp.x, nav.warp.y)
                if blocked_n and blocked_n % 6 == 0:  # un menu (p.ex. aprendre moviment) absorbeix els botons: B cancela, A confirma
                    for b in ("b", "b", "a"):
                        emu.press(b, hold=4, settle=40)
                if status in ("done", "warped", "blocked"):
                    last = f"walked toward tile {tuple(nav.tile)}: {status}, now in map {bank}/{num}"
                    nav.clear()
                emu.tick(15)
                continue

            # fase text de combat: la policy nomes avanca amb A, no gastis crides al backend
            if gs.battle_active and gs.battle_phase != "action" and gs.battle_phase != "move":
                presses = plan(gs, Decisions(), cfg)
                for p in presses:
                    emu.press(p.button, p.hold, p.settle)
                emu.tick(15)
                if cycle % 20 == 0:
                    print(f"[{cycle:06d} f={emu.frame}] battle text -> " + "+".join(p.button for p in presses), flush=True)
                trace.log(
                    {
                        "cycle": cycle,
                        "frame": emu.frame,
                        "battle_text": True,
                        "presses": [{"button": p.button} for p in presses],
                    }
                )
                continue

            # HP baix fora de combat: torna a casa i que la mare et curi (el whiteout tambe cura, pero costa diners)
            if gs.party and gs.cmap is not None and not gs.battle_active and not gs.dialog_text and gs.party[0].hp < 0.4 * gs.party[0].max_hp:
                if here == (4, 0):
                    mom = next((w for w in gs.warps if w.act and "Mom" in w.label), None)
                    if mom is not None and nav.set_goal(gs.cmap, mom):
                        continue
                nxt = (3, 0) if here in ((4, 1), (4, 2), (4, 3)) else (4, 0) if here == (3, 0) else TOWARD_HOME.get(here)
                door = next((w for w in gs.warps if w.usable and (w.dest_bank, w.dest_map) == nxt), None)
                if door is not None and nav.set_goal(gs.cmap, door):
                    continue

            # entrenament: Squirtle nv5 no aguanta el bosc; vaiven a l'herba fins al nivell objectiu, sense LLM
            if (
                gs.party
                and gs.party[0].level < grind_target
                and gs.cmap is not None
                and not gs.battle_active
                and not gs.dialog_text
            ):
                grass = grass_cache.setdefault(here, grass_tiles(emu, gs.cmap))
                pos = read_pos(emu)[:2]
                btn = grind_press(gs.cmap, grass, pos, grind_last) if grass else None
                if not grass:  # sense herba aqui: camina cap a la Ruta 1
                    nxt = TOWARD_GRASS.get(here)
                    door = next((w for w in gs.warps if w.usable and (w.dest_bank, w.dest_map) == nxt), None)
                    if door is not None and nav.set_goal(gs.cmap, door):
                        continue
                grind_still = grind_still + 1 if pos == grind_last else 0
                if grind_still >= 8:  # no es mou: un menu (p.ex. aprendre moviment) s'ha quedat obert; B cancela, A confirma
                    for b in ("b", "b", "a"):
                        emu.press(b, hold=4, settle=40)
                    grind_still = 0
                    continue
                if btn is not None:
                    grind_last = pos
                    emu.press(btn, hold=cfg.walk_hold, settle=cfg.walk_settle)
                    grind_steps += 1
                    if grind_steps % 40 == 1:
                        print(f"[{cycle:06d} f={emu.frame}] grind nv{gs.party[0].level}/{grind_target} HP {gs.party[0].hp}/{gs.party[0].max_hp} map {here} pos{pos}", flush=True)
                    continue

            payload = state_payload(gs, world, last)
            calls["jev"] += 1
            calls["code"] -= 1
            questions = build_questions(gs, came_from, world)
            job.clear()
            thread = threading.Thread(target=worker, args=(payload, questions), daemon=True)
            thread.start()
            while thread.is_alive():
                emu.tick(30)
            thread.join()
            if "error" in job:
                raise job["error"]
            response = job["response"]
            dec = extract_decisions(response)
            if gs.dialog_text and not gs.battle_active and dec.screen_mode != "dialog":
                dec.screen_mode, dec.dialog = "dialog", "advance"  # ponytail: caixa de text visible = dialeg, el model s'equivoca amb avisos d'objectes

            # objectiu de navegacio triat pel model: el codi fa el cami
            goal = None
            if (
                dec.screen_mode == "overworld"
                and gs.cmap is not None
                and dec.nav_destination.startswith("warp_")
                and dec.nav_confidence >= cfg.confidence_floor
            ):
                usable = nav_options(gs, came_from, world)
                try:
                    idx = int(dec.nav_destination.removeprefix("warp_"))
                    goal = usable[idx]
                except (ValueError, IndexError):
                    goal = None
            if goal is not None and not nav.set_goal(gs.cmap, goal):
                goal = None  # el desti triat no es assolible (p.ex. altra part del mapa)
            if dec.screen_mode == "overworld" and gs.cmap is not None and goal is None:
                idle += 1
                if idle == 8:  # sense sortida fiable: deixa l'estat per reproduir-ho
                    emu.save_state("idle.ss")
                    emu.screen().save("idle.png")
                if idle >= 2:  # ponytail: si el model dubta, explora: sortida cap al nord, mapes nous, mes probable
                    scores = (dec.raw.get("probabilities") or {}).get("nav_destination") or {}
                    usable = nav_options(gs, came_from, world)

                    goal = next((w for _, w in sorted(enumerate(usable), key=lambda it: (0 if (it[1].dest_bank, it[1].dest_map) == (6, 2) and not gs.badges else 1, 0 if gs.parcel_delivered and it[1].edge == "up" else 1, world.visits(it[1].dest_bank, it[1].dest_map), -(scores.get(f"warp_{it[0]}") or 0.0))) if nav.set_goal(gs.cmap, w)), None)
            else:
                idle = 0
            if goal is not None and nav.set_goal(gs.cmap, goal):
                idle = 0
                line = (
                    f"[{cycle:06d} f={emu.frame}] {gs.summary()} | mode={dec.screen_mode} "
                    f"nav_goal=warp({goal.x},{goal.y})->{goal.dest_bank}/{goal.dest_map} obj={dec.objective}"
                )
                print(line, flush=True)
                trace.log(
                    {
                        "cycle": cycle,
                        "frame": emu.frame,
                        "nav_goal": goal.to_dict(),
                        "decisions": {"objective": dec.objective},
                    }
                )
                continue

            presses = plan(gs, dec, cfg)
            last = f"mode {dec.screen_mode}, pressed {'+'.join(p.button for p in presses) or 'nothing'}"
            for p in presses:
                emu.press(p.button, p.hold, p.settle)
            if not presses:
                emu.tick(30)
            latency_ms = round((time.time() - started) * 1000)
            usage = getattr(response, "usage", None)
            usage_pair = None
            if usage is not None:
                usage_pair = (
                    getattr(usage, "input_tokens", None) or getattr(usage, "input_tokens_total", 0),
                    getattr(usage, "output_tokens", None) or getattr(usage, "output_tokens_total", 0),
                )
            line = f"[{cycle:06d} f={emu.frame}] {gs.summary()} | mode={dec.screen_mode} ow={dec.overworld} nav={dec.nav_destination} dlg={dec.dialog} bat={dec.battle} obj={dec.objective} -> {'+'.join(p.button for p in presses) or 'wait'}"
            print(line, flush=True)
            probs = dec.raw.get("probabilities") or {}
            decisions_view = [
                ["screen_mode", "choice", "pantalla", dec.screen_mode, probs.get("screen_mode")],
                ["overworld_action", "choice", "accio overworld", dec.overworld, probs.get("overworld_action")],
                ["nav_destination", "choice", "desti navegacio", dec.nav_destination, probs.get("nav_destination")],
                ["dialog_response", "choice", "resposta dialog", dec.dialog, probs.get("dialog_response")],
                ["battle_plan", "choice", "pla batalla", dec.battle, probs.get("battle_plan")],
                ["objective", "choice", "objectiu", dec.objective, probs.get("objective")],
                ["party_critical", "noul", "party critica", dec.hp_critical, None],
                ["enemy_threat", "score", "amenaça enemic", dec.enemy_threat, None],
            ]
            presses_view = [{"button": p.button, "hold": p.hold, "settle": p.settle} for p in presses]
            trace.log(
                {
                    "cycle": cycle,
                    "frame": emu.frame,
                    "wall_ms": latency_ms,
                    "state": payload,
                    "decisions": {
                        "screen_mode": dec.screen_mode,
                        "screen_confidence": dec.screen_confidence,
                        "overworld": dec.overworld,
                        "overworld_confidence": dec.overworld_confidence,
                        "nav_destination": dec.nav_destination,
                        "nav_confidence": dec.nav_confidence,
                        "dialog": dec.dialog,
                        "dialog_confidence": dec.dialog_confidence,
                        "battle": dec.battle,
                        "battle_confidence": dec.battle_confidence,
                        "objective": dec.objective,
                        "hp_critical": dec.hp_critical,
                        "enemy_threat": dec.enemy_threat,
                        "probabilities": probs,
                    },
                    "presses": presses_view,
                }
            )
            if dashboard is not None:
                dashboard.publish(
                    cycle=cycle,
                    frame=emu.frame,
                    latency_ms=latency_ms,
                    usage=usage_pair,
                    state=payload,
                    decisions=decisions_view,
                    presses=presses_view,
                    line=line,
                )
    except KeyboardInterrupt:
        print("\naturat per l'usuari")
    finally:
        trace.close()
        if recorder is not None:
            recorder.close()
        if dashboard is not None:
            dashboard.stop()
        emu.close()


def cmd_play(args: argparse.Namespace) -> None:
    import pygame

    emu = GbaEmulator(_resolve_rom(args), getattr(args, "sav", None), window=True)
    clock = pygame.time.Clock()
    print(
        "controls: fletxes=d-pad X=A Z=B A=L S=R RETURN=start BACKSPACE=select ESC=sortir i desar\n"
        f"en sortir es desara el save state a: {args.out}"
    )
    try:
        while True:
            emu.tick(1)
            clock.tick(60)
    except KeyboardInterrupt:
        pass
    emu.save_state(args.out)
    print(f"save state desat: {args.out}")
    emu.close()


def cmd_smoke(args: argparse.Namespace) -> None:
    backend_kind = _pick_backend(args)
    client = make_backend(backend_kind)
    state = {
        "map": {"bank": 0, "number": 18, "camera_x": 12, "camera_y": 8},
        "player": {"name": "PERE"},
        "party": [
            {
                "species": "Squirtle",
                "species_id": 7,
                "nickname": "SQUIRTLE",
                "level": 5,
                "current_hp": 4,
                "status": 0,
                "experience": 135,
                "moves": [33, 39, 44, 0],
                "pp": [25, 25, 20, 0],
            }
        ],
        "battle": {"active": False},
        "dialog": {"text": "Estàs segur que vols marxar?"},
        "signals": {"fading": False, "frame": 12345},
    }
    questions = build_questions()
    started = time.time()
    response = _ask(backend_kind, client, args.provider, args.model, state, questions)
    elapsed_ms = round((time.time() - started) * 1000)
    dec = extract_decisions(response)
    usage = getattr(response, "usage", None)
    print(f"backend={backend_kind} model={args.model if backend_kind != 'jev' else 'jev-latest'} latency={elapsed_ms}ms")
    print(
        f"screen_mode={dec.screen_mode} (conf {dec.screen_confidence:.2f}) | "
        f"overworld={dec.overworld} | dialog={dec.dialog} | battle={dec.battle} | objective={dec.objective}"
    )
    print(f"party_critical={dec.hp_critical:.3f} enemy_threat={dec.enemy_threat:.2f}")
    print(f"probabilitats screen_mode: {dec.raw['probabilities'].get('screen_mode')}")
    if usage is not None:
        print(f"usage: input={getattr(usage, 'input_tokens', None) or getattr(usage, 'input_tokens_total', '?')} "
              f"output={getattr(usage, 'output_tokens', None) or getattr(usage, 'output_tokens_total', '?')}")


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="flamaroja", description="Jev System One harness per a Pokémon Flama Roja")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="bucle principal estat -> preguntes -> accions")
    p_run.add_argument("--rom", help="ROM .gba (o FLAMAROJA_ROM)")
    p_run.add_argument("--sav", help="battery save .sav del costat de la ROM")
    p_run.add_argument("--save", help="save state inicial")
    p_run.add_argument("--backend", choices=["auto", "jev", "adapter"], default="auto")
    p_run.add_argument("--provider", choices=["openai", "anthropic"], default="openai")
    p_run.add_argument("--model", default="gpt-4o-mini")
    p_run.add_argument("--ticks", type=int, default=100_000)
    p_run.add_argument("--trace", default="trace.jsonl")
    p_run.add_argument("--window", action="store_true", help="mostra una finestra amb el joc en directe")
    p_run.add_argument("--record", metavar="FITXER.mp4", help="grava el gameplay en mp4 (cal ffmpeg)")
    p_run.add_argument("--dashboard", action="store_true", help="dashboard web amb decisions de Jev en directe")
    p_run.add_argument("--port", type=int, default=8000)
    p_run.add_argument("--memory", default="world.json", help="on es bolca la memoria del harness (mapes visitats i notes)")
    p_run.set_defaults(func=cmd_run)

    p_boot = sub.add_parser("boot", help="salta el titol (CONTINUAR) i desa un save state a l'overworld")
    p_boot.add_argument("--rom")
    p_boot.add_argument("--sav", help="battery save .sav del costat de la ROM")
    p_boot.add_argument("--out", default="boot.ss")
    p_boot.add_argument("--window", action="store_true", help="mostra una finestra amb el joc en directe")
    p_boot.set_defaults(func=cmd_boot)

    p_probe = sub.add_parser("probe", help="arrenca la ROM i bolca l'estat per verificar offsets")
    p_probe.add_argument("--rom")
    p_probe.add_argument("--sav")
    p_probe.add_argument("--save")
    p_probe.add_argument("--warmup", type=int, default=600)
    p_probe.add_argument("--screenshot", help="desa un PNG de la pantalla")
    p_probe.set_defaults(func=cmd_probe)

    p_shot = sub.add_parser("screenshot", help="arrenca i desa un PNG")
    p_shot.add_argument("--rom")
    p_shot.add_argument("--save")
    p_shot.add_argument("--warmup", type=int, default=600)
    p_shot.add_argument("--out", default="shot.png")
    p_shot.set_defaults(func=cmd_screenshot)

    p_play = sub.add_parser("play", help="juga tu amb teclat (per fer la intro) i desa save state en sortir")
    p_play.add_argument("--rom")
    p_play.add_argument("--sav")
    p_play.add_argument("--out", default="play.ss")
    p_play.set_defaults(func=cmd_play)

    p_smoke = sub.add_parser("smoke", help="1 crida real al backend per validar clau i workflow")
    p_smoke.add_argument("--backend", choices=["auto", "jev", "adapter"], default="auto")
    p_smoke.add_argument("--provider", choices=["openai", "anthropic"], default="openai")
    p_smoke.add_argument("--model", default="gpt-4o-mini")
    p_smoke.set_defaults(func=cmd_smoke)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
