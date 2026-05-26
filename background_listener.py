"""Background listener: Wake Word (Hey Jarvis) + Clap, startet mit Windows.

- Ein gemeinsamer Audio-Stream für beide Erkennungen
- "Hey Jarvis" per openWakeWord (lokal, kein API-Key)
- Doppelklatschen per RMS-Detektor
- Startet main.py oder holt Fenster in Vordergrund
"""

import ctypes
import logging
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

_PYW = sys.executable.replace("python.exe", "pythonw.exe")
if not _PYW.endswith("pythonw.exe"):
    _PYW = sys.executable

_JARVIS_TITLE = "J.A.R.V.I.S \u2014 Open-Jarvis"

logging.basicConfig(
    filename=str(BASE_DIR / "listener.log"),
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)


def _find_window(title: str) -> int:
    return ctypes.windll.user32.FindWindowW(None, title)


def _bring_to_front(hwnd: int) -> None:
    u = ctypes.windll.user32
    u.ShowWindow(hwnd, 9)
    u.SetForegroundWindow(hwnd)


def _is_window(hwnd: int) -> bool:
    return ctypes.windll.user32.IsWindow(hwnd) != 0


class BackgroundListener:
    def __init__(self):
        self._running = False
        self._stream: sd.InputStream | None = None
        self._oww = None
        self._clap_peaks: list[float] = []
        self._clap_cooldown = 0.0
        self._busy = False
        self._ignore_until = 0.0
        self._last_callback = 0.0
        self._remote_proc = None
        self._last_working_device = None
        self._stream_started_at = 0.0

    def _init_voice(self) -> bool:
        if self._oww is not None:
            return True
        try:
            from openwakeword import Model
            self._oww = Model(wakeword_models=["hey_jarvis"],
                              inference_framework="onnx")
            return True
        except Exception as e:
            logging.warning(f"openWakeWord Init fehlgeschlagen: {e}")
            return False

    def _audio_callback(self, indata, frames, time_info, status):
        self._last_callback = time.time()
        if status:
            logging.warning(f"Audio Status: {status}")
        if self._busy:
            return
        now = time.time()
        if now < self._ignore_until:
            return

        # Clap
        data = indata.astype("float32")
        if indata.dtype in (np.int16, np.int32):
            data = data / float(np.iinfo(indata.dtype).max)
        if data.ndim > 1:
            data = data.mean(axis=1)
        rms = float(np.sqrt(np.mean(data * data)))
        if rms >= 0.25:
            if not self._clap_peaks or (now - self._clap_peaks[-1]) > 0.04:
                self._clap_peaks.append(now)
                if len(self._clap_peaks) > 4:
                    self._clap_peaks = self._clap_peaks[-4:]
        if len(self._clap_peaks) >= 2:
            dt = self._clap_peaks[-1] - self._clap_peaks[-2]
            if 0.12 <= dt <= 0.6 and now - self._clap_cooldown > 1.0:
                self._clap_cooldown = now
                self._clap_peaks.clear()
                logging.info("Klatschen erkannt")
                self._launch()

        # Voice
        if self._oww is not None:
            try:
                pcm = indata.copy()
                if pcm.dtype != np.int16:
                    pcm = (pcm * 32767).astype(np.int16)
                score = self._oww.predict(pcm.flatten()).get("hey_jarvis", 0.0)
                if score > 0.65:
                    logging.info(f"Hey Jarvis erkannt ({score:.2f})")
                    self._launch()
            except Exception as e:
                logging.warning(f"openWakeWord predict Fehler: {e}")

    _DEVICE_CANDIDATES = [
        {"device": None, "hostapi": None},       # default (MME)
        {"device": 9, "hostapi": None},           # WASAPI Microphone Array
        {"device": 1, "hostapi": None},           # MME Microphone Array
        {"device": 15, "hostapi": None},          # WDM-KS Mikrofonarray
        {"device": 12, "hostapi": None},          # WDM-KS Mikrofon
        {"device": None, "hostapi": None, "blocksize": 1024},
    ]

    def _device_key(self, cfg: dict) -> str:
        return f"dev={cfg.get('device')}|bs={cfg.get('blocksize',1280)}"

    def _start_stream(self) -> bool:
        if self._stream is not None:
            return True
        candidates = list(self._DEVICE_CANDIDATES)
        if self._last_working_device:
            key = self._device_key(self._last_working_device)
            candidates = [c for c in candidates if self._device_key(c) != key]
            candidates.insert(0, self._last_working_device)
        for cfg in candidates:
            for attempt in range(2):
                try:
                    dev = cfg.get("device")
                    bs = cfg.get("blocksize", 1280)
                    self._last_callback = 0.0
                    self._stream = sd.InputStream(
                        samplerate=16000, channels=1, dtype="int16",
                        blocksize=bs, callback=self._audio_callback,
                        device=dev,
                    )
                    self._stream.start()
                    self._ignore_until = time.time() + 15.0
                    self._stream_started_at = time.time()
                    # kurz warten ob Callback wirklich kommt
                    for _ in range(10):
                        time.sleep(0.2)
                        if self._last_callback > 0:
                            self._last_working_device = cfg
                            logging.info(f"Mikrofon aktiv (device={dev}, blocksize={bs})")
                            return True
                    # kein Callback gekommen – Device taugt nicht
                    logging.warning(f"Device {dev} liefert keine Audio-Daten")
                    self._stop_stream()
                except Exception as e:
                    logging.warning(f"Device cfg={cfg} failed: {e}")
                    self._stop_stream()
                    time.sleep(1.0)
        logging.error("Stream Start endgültig fehlgeschlagen")
        return False

    def _stop_stream(self):
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass
        self._stream = None
        self._last_callback = 0.0
        logging.info("Mikrofon freigegeben")

    def _launch(self):
        if self._busy:
            return
        self._busy = True
        self._stop_stream()
        time.sleep(0.2)
        started_main = False
        try:
            if _is_window(_find_window(_JARVIS_TITLE)):
                _bring_to_front(_find_window(_JARVIS_TITLE))
                logging.info("Fenster in Vordergrund")
            else:
                started_main = True
                logging.info(f"Starte: {_PYW} main.py")
                start = time.time()
                proc = subprocess.Popen(
                    [_PYW, "main.py"], cwd=str(BASE_DIR),
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                logging.info("main.py gestartet")
                proc.wait()
                elapsed = time.time() - start
                logging.info(f"Jarvis beendet (exit={proc.returncode}, lief={elapsed:.0f}s).")
                # kurz gelaufen + exit 0 = Fenster wurde geschlossen → Pause
                if elapsed < 60 and proc.returncode == 0:
                    logging.info("Kurzlauf erkannt. Warte 30s...")
                    time.sleep(30)
                else:
                    time.sleep(1.0)
        finally:
            self._busy = False
            if started_main:
                # Stream sofort neustarten (main.py ist beendet, Mikro sollte frei sein)
                time.sleep(1.0)
                self._start_stream()
                # Ignorier-Puffer verlängern: mindestens 8s ab jetzt
                self._ignore_until = max(self._ignore_until, time.time() + 8.0)

    def run(self):
        if not self._init_voice():
            logging.error("Voice Init fehlgeschlagen – beende")
            return
        self._running = True
        self._start_stream()

        self._remote_proc = subprocess.Popen(
            [_PYW, "remote_server.py"], cwd=str(BASE_DIR),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        logging.info("Remote-Server gestartet")

        logging.info("Listener gestartet (Hey Jarvis + Klatschen)")
        try:
            while self._running:
                time.sleep(1.0)
                if self._busy:
                    continue

                jarvis_running = _is_window(_find_window(_JARVIS_TITLE))

                if jarvis_running:
                    if self._stream is not None:
                        logging.info("Jarvis aktiv – Mikro pausiert")
                        self._stop_stream()
                    continue

                # Jarvis läuft nicht – Mikro bereit halten
                if self._stream is None:
                    # Sicherstellen, dass Stream nicht kurz nach neustart
                    # direkt wieder abgewürgt wird (Fenster-Schließ- Rennen)
                    if time.time() - self._stream_started_at < 3.0:
                        continue
                    logging.info("Stream unterbrochen – Neustart...")
                    self._start_stream()
                elif self._last_callback > 0 and time.time() - self._last_callback > 15.0:
                    logging.warning("Kein Callback seit 15s – naechstes Device probieren")
                    self._last_working_device = None
                    self._stop_stream()
                    self._start_stream()
        except KeyboardInterrupt:
            pass
        finally:
            self._stop_stream()
            if self._remote_proc:
                try:
                    self._remote_proc.kill()
                except Exception:
                    pass

    def stop(self):
        self._running = False
        if self._remote_proc:
            try:
                self._remote_proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    bl = BackgroundListener()
    bl.run()
