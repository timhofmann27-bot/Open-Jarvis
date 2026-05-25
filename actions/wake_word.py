from __future__ import annotations

import json
import time
import threading
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


def _get_pv_key() -> str:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f).get("picovoice_api_key", "")
    except Exception:
        return ""


class ClapListener:
    def __init__(self,
                 callback: Callable[[], None],
                 samplerate: int = 16000,
                 blocksize: int = 1024,
                 clap_threshold: float = 0.20,
                 min_interval: float = 0.12,
                 max_interval: float = 0.6,
                 cooldown: float = 1.0):
        self.callback = callback
        self.sr = samplerate
        self.block = blocksize
        self.clap_threshold = clap_threshold
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.cooldown = cooldown
        self._peaks: list[float] = []
        self._last_trigger = 0.0
        self._running = False

    def _process_frame(self, indata: np.ndarray) -> None:
        if indata.size == 0:
            return
        data = indata.astype('float32')
        if indata.dtype == np.int16 or indata.dtype == np.int32:
            maxv = np.iinfo(indata.dtype).max
            data = data / float(maxv)
        if data.ndim > 1:
            data = data.mean(axis=1)
        rms = float(np.sqrt(np.mean(data * data)))
        now = time.time()
        if rms >= self.clap_threshold:
            if not self._peaks or (now - self._peaks[-1]) > 0.04:
                self._peaks.append(now)
                if len(self._peaks) > 4:
                    self._peaks = self._peaks[-4:]
        if len(self._peaks) >= 2:
            dt = self._peaks[-1] - self._peaks[-2]
            if self.min_interval <= dt <= self.max_interval:
                if now - self._last_trigger > self.cooldown:
                    self._last_trigger = now
                    try:
                        threading.Thread(target=self.callback, daemon=True).start()
                    except Exception:
                        try:
                            self.callback()
                        except Exception:
                            pass
                    self._peaks.clear()

    def _audio_callback(self, indata, frames, time_info, status):
        try:
            self._process_frame(indata.copy())
        except Exception:
            pass

    def run(self):
        self._running = True
        try:
            with sd.InputStream(samplerate=self.sr, channels=1, dtype='int16', blocksize=self.block, callback=self._audio_callback):
                while self._running:
                    time.sleep(0.1)
        except Exception as e:
            print(f"[WAKE] Clap error: {e}")

    def stop(self):
        self._running = False


class VoiceWakeListener:
    def __init__(self,
                 callback: Callable[[], None],
                 samplerate: int = 16000,
                 blocksize: int = 1024):
        self.callback = callback
        self.sr = samplerate
        self.block = blocksize
        self._running = False
        self._porcupine = None
        self._audio_stream = None

    def _init_porcupine(self) -> bool:
        if self._porcupine is not None:
            return True
        try:
            import pvporcupine
            api_key = _get_pv_key()
            if not api_key:
                print("[WAKE] Voice: kein Picovoice API-Key in config/api_keys.json")
                return False
            self._porcupine = pvporcupine.create(access_key=api_key, keywords=["jarvis"])
            return True
        except Exception as e:
            print(f"[WAKE] Voice Init fehlgeschlagen: {e}")
            return False

    def _audio_callback(self, indata, frames, time_info, status):
        try:
            if self._porcupine is None:
                return
            pcm = indata.copy()
            if pcm.dtype != np.int16:
                pcm = (pcm * 32767).astype(np.int16)
            flat = pcm.flatten()
            result = self._porcupine.process(flat.tolist())
            if result >= 0:
                print("[WAKE] Hey Jarvis erkannt!")
                try:
                    threading.Thread(target=self.callback, daemon=True).start()
                except Exception:
                    try:
                        self.callback()
                    except Exception:
                        pass
        except Exception:
            pass

    def run(self):
        if not self._init_porcupine():
            return
        self._running = True
        try:
            with sd.InputStream(samplerate=self.sr, channels=1, dtype='int16', blocksize=self.block, callback=self._audio_callback):
                while self._running:
                    time.sleep(0.1)
        except Exception as e:
            print(f"[WAKE] Voice error: {e}")

    def stop(self):
        self._running = False
        if self._porcupine:
            try:
                self._porcupine.delete()
            except Exception:
                pass
            self._porcupine = None


class OpenWakeWordListener:
    """Lokaler Wake-Word-Detektor mit openWakeWord (kein API-Key nötig)."""

    def __init__(self,
                 callback: Callable[[], None],
                 model_name: str = "hey_jarvis",
                 threshold: float = 0.5,
                 samplerate: int = 16000,
                 cooldown: float = 2.0):
        self.callback = callback
        self.model_name = model_name
        self.threshold = threshold
        self.sr = samplerate
        self.cooldown = cooldown
        self._running = False
        self._model = None
        self._last_trigger = 0.0

    def _init_model(self) -> bool:
        if self._model is not None:
            return True
        try:
            from openwakeword import Model
            self._model = Model(wakeword_models=[self.model_name],
                                inference_framework="onnx")
            return True
        except Exception as e:
            print(f"[WAKE] openWakeWord Init fehlgeschlagen: {e}")
            return False

    def _audio_callback(self, indata, frames, time_info, status):
        try:
            if self._model is None:
                return
            pcm = indata.copy()
            if pcm.dtype != np.int16:
                pcm = (pcm * 32767).astype(np.int16)
            flat = pcm.flatten()
            prediction = self._model.predict(flat)
            score = prediction.get(self.model_name, 0.0)
            now = time.time()
            if score > self.threshold and now - self._last_trigger > self.cooldown:
                self._last_trigger = now
                print(f"[WAKE] {self.model_name} erkannt! ({score:.2f})")
                try:
                    threading.Thread(target=self.callback, daemon=True).start()
                except Exception:
                    try:
                        self.callback()
                    except Exception:
                        pass
        except Exception:
            pass

    def run(self):
        if not self._init_model():
            return
        self._running = True
        try:
            with sd.InputStream(samplerate=self.sr, channels=1, dtype='int16',
                                blocksize=1280, callback=self._audio_callback):
                while self._running:
                    time.sleep(0.1)
        except Exception as e:
            print(f"[WAKE] openWakeWord error: {e}")

    def stop(self):
        self._running = False
        self._model = None
