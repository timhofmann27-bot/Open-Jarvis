"""Clap-based wake listener (double-clap detection).

Usage:
    from actions.wake_word import start_clap_listener
    start_clap_listener(callback=on_wake)

Provides a simple energy-based double-clap detector using `sounddevice`.
The listener runs until the program exits. Callback is called on detection.
"""
from __future__ import annotations

import time
import threading
from typing import Callable

import numpy as np
import sounddevice as sd


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
        # indata shape: (frames, channels)
        if indata.size == 0:
            return
        # Normalize int16 -> float32 in [-1,1]
        data = indata.astype('float32')
        if data.dtype == np.int16 or data.dtype == np.int32:
            maxv = np.iinfo(indata.dtype).max
            data = data / float(maxv)

        # Use mono energy
        if data.ndim > 1:
            data = data.mean(axis=1)

        rms = float(np.sqrt(np.mean(data * data)))
        now = time.time()

        if rms >= self.clap_threshold:
            # tiny refractory to avoid same-clap multiple frames
            if not self._peaks or (now - self._peaks[-1]) > 0.04:
                self._peaks.append(now)
                # keep only last 4
                if len(self._peaks) > 4:
                    self._peaks = self._peaks[-4:]

        # check for double clap: last two peaks within interval
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
                    # clear peaks to avoid retrigger
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
            print(f"[WAKE] Clap listener error: {e}")

    def stop(self):
        self._running = False


def start_clap_listener(callback: Callable[[], None], **kwargs) -> ClapListener:
    """Start a blocking clap listener in the current thread.

    Typical usage is to launch this in a background thread:
        threading.Thread(target=start_clap_listener, args=(cb,), daemon=True).start()
    """
    listener = ClapListener(callback=callback, **kwargs)
    listener.run()
    return listener


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Test double-clap wake listener')
    parser.add_argument('--threshold', type=float, default=0.20, help='RMS threshold for clap (0-1)')
    parser.add_argument('--sr', type=int, default=16000, help='Sample rate')
    args = parser.parse_args()

    def _on_wake():
        print('[WAKE] Doppelklatschen erkannt!')

    print('[WAKE] Starte Clap Listener (Ctrl+C zum Beenden)')
    try:
        start_clap_listener(callback=_on_wake, samplerate=args.sr, clap_threshold=args.threshold)
    except KeyboardInterrupt:
        print('\n[WAKE] Beendet')
