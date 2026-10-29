from __future__ import annotations

from pathlib import Path

BUTTONS = ("a", "b", "start", "select", "up", "down", "left", "right", "l", "r")


class GbaEmulator:
    def __init__(self, rom_path: str | Path, sav_path: str | Path | None = None, window: bool = False) -> None:
        import mgba.image
        import mgba.log
        from mgba._pylib import ffi, lib
        from pygba import PyGBA

        rom = Path(rom_path).expanduser().resolve()
        if not rom.is_file():
            raise FileNotFoundError(f"ROM no trobada: {rom}")
        sav = Path(sav_path).expanduser().resolve() if sav_path else None
        if sav is not None and not sav.is_file():
            raise FileNotFoundError(f"Save no trobat: {sav}")
        self._log_filter = ffi.new("struct mLogFilter*")
        lib.mLogFilterInit(self._log_filter)
        self._log_filter.defaultLevels = 0
        self._logger = mgba.log.NullLogger()
        ffi.cast("void **", self._logger._native)[1] = self._log_filter
        lib.mLogSetDefaultLogger(self._logger._native)
        self._gba = PyGBA.load(str(rom), save_file=str(sav) if sav else None)
        self._screen_img = mgba.image.Image(240, 160)
        self._gba.core.set_video_buffer(self._screen_img)
        self._gba.core.reset()
        self._pygame = None
        self._window = None
        self._audio_channel = None
        self._audio_buffer = None
        self._audio_cbuf = None
        self._audio_fifo = bytearray()
        if window:
            import pygame

            core = self._gba.core._core
            try:
                freq = core.audioSampleRate(core)
            except Exception:
                freq = 32768
            self._pygame = pygame
            self._pygame.mixer.pre_init(frequency=freq, size=-16, channels=2, buffer=512)
            self._pygame.init()
            self._window = self._pygame.display.set_mode((720, 480))
            self._pygame.display.set_caption("flama-roja-jev")
            core.setAudioBufferSize(core, 4096)
            self._audio_buffer = core.getAudioBuffer(core)
            self._audio_cbuf = ffi.new("int16_t[4096]")
            self._audio_channel = self._pygame.mixer.Channel(0)
        self.frame = 0
        self.frame_hook = None
        self._scripted = False  # press() en curs: el teclat de la finestra no ha de trencar el boto mantingut

    def _drain_audio(self) -> None:
        if self._audio_channel is None:
            return
        from mgba._pylib import ffi, lib

        avail = lib.mAudioBufferAvailable(self._audio_buffer)
        if avail > 0:
            n = min(avail, 4096)
            n = lib.mAudioBufferRead(self._audio_buffer, self._audio_cbuf, n)
            if n > 0:
                self._audio_fifo += bytes(ffi.buffer(self._audio_cbuf, n * 4))

        chunk_bytes = 1024 * 4
        while len(self._audio_fifo) >= chunk_bytes:
            if self._audio_channel.get_queue() is not None:
                break
            sound = self._pygame.mixer.Sound(buffer=bytes(self._audio_fifo[:chunk_bytes]))
            del self._audio_fifo[:chunk_bytes]
            if not self._audio_channel.get_busy():
                self._audio_channel.play(sound)
            else:
                self._audio_channel.queue(sound)

        if len(self._audio_fifo) > 1 << 16:
            del self._audio_fifo[: len(self._audio_fifo) - 16384]

    @property
    def title(self) -> str:
        return self.read_range(0x080000A0, 12).decode("ascii", "ignore").strip("\x00 ")

    @property
    def game_code(self) -> str:
        return self.read_range(0x080000AC, 4).decode("ascii", "ignore")

    def _handle_keys(self) -> None:
        if self._window is None or self._scripted:
            return
        pressed = self._pygame.key.get_pressed()
        mapping = {
            self._pygame.K_UP: "up",
            self._pygame.K_DOWN: "down",
            self._pygame.K_LEFT: "left",
            self._pygame.K_RIGHT: "right",
            self._pygame.K_x: "a",
            self._pygame.K_z: "b",
            self._pygame.K_a: "l",
            self._pygame.K_s: "r",
            self._pygame.K_RETURN: "start",
            self._pygame.K_BACKSPACE: "select",
        }
        mask = 0
        for pygame_key, button in mapping.items():
            if pressed[pygame_key]:
                mask |= self._key_mask(button)
        core = self._gba.core._core
        core.setKeys(core, mask)

    def _blit(self) -> None:
        if self._window is None:
            return
        frame = self._pygame.image.frombuffer(
            self._screen_img.to_pil().tobytes(), (240, 160), "RGBX"
        )
        self._window.blit(
            self._pygame.transform.scale(frame, self._window.get_size()), (0, 0)
        )
        self._pygame.display.flip()
        self._drain_audio()
        self._handle_keys()
        for event in self._pygame.event.get():
            if event.type in (self._pygame.QUIT,):
                raise KeyboardInterrupt
            if event.type == self._pygame.KEYDOWN and event.key == self._pygame.K_ESCAPE:
                raise KeyboardInterrupt

    def tick(self, frames: int = 1) -> None:
        for _ in range(max(0, frames)):
            self._gba.core.run_frame()
            self.frame += 1
            if self.frame_hook is not None:
                self.frame_hook()
            if self._window is not None:
                self._drain_audio()
                if self.frame % 4 == 0:
                    self._blit()

    def _key_mask(self, button: str) -> int:
        import mgba.gba

        return 1 << getattr(mgba.gba.GBA, f"KEY_{button.upper()}")

    def press(self, button: str, hold: int = 2, settle: int = 20) -> None:
        if button not in BUTTONS:
            raise ValueError(f"Botó desconegut: {button}")
        core = self._gba.core._core
        core.setKeys(core, self._key_mask(button))
        self._scripted = True
        try:
            self.tick(hold)
        finally:
            self._scripted = False
        core.setKeys(core, 0)
        self.tick(settle)

    def read_u8(self, addr: int) -> int:
        return self._gba.core._core.busRead8(self._gba.core._core, addr)

    def read_u16(self, addr: int) -> int:
        return self._gba.core._core.busRead16(self._gba.core._core, addr)

    def read_u32(self, addr: int) -> int:
        return self._gba.core._core.busRead32(self._gba.core._core, addr)

    def read_range(self, addr: int, size: int) -> bytes:
        return bytes(self._gba.read_memory(addr, size))

    def screen(self):
        return self._screen_img.to_pil().convert("RGB")

    def save_state(self, path: str | Path) -> None:
        state = self._gba.core.save_raw_state()
        if not state:
            raise RuntimeError("save_state ha fallat")
        Path(path).write_bytes(bytes(state))

    def load_state(self, path: str | Path) -> None:
        self._gba.core.load_raw_state(Path(path).read_bytes())

    def close(self) -> None:
        self._gba = None
