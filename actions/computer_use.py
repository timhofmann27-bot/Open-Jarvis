"""
Computer Use Agent: see screen → analyze → click/type/scroll → repeat.
Uses Gemini Vision + pyautogui for autonomous computer control.
"""

import io
import time

import pyautogui
pyautogui.FAILSAFE = False
from PIL import Image, ImageDraw
from google import genai
from google.genai import types


GRID_COLS = 40
GRID_ROWS = 22


def _get_api_key():
    import json
    from pathlib import Path
    cfg = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
    return json.loads(cfg.read_text(encoding="utf-8"))["gemini_api_key"]


def _capture_with_grid():
    """Capture screen and overlay coordinate grid. Returns (PIL Image, screen_w, screen_h)."""
    img = pyautogui.screenshot()
    w, h = img.size
    draw = ImageDraw.Draw(img)

    cell_w = w // GRID_COLS
    cell_h = h // GRID_ROWS

    # Vertical lines + labels
    for i in range(GRID_COLS + 1):
        x = i * cell_w
        draw.line([(x, 0), (x, h)], fill=(255, 80, 80, 120), width=1)
        if i % 5 == 0:
            draw.text((x + 2, 4), str(i), fill=(255, 255, 255))

    # Horizontal lines + labels
    for i in range(GRID_ROWS + 1):
        y = i * cell_h
        draw.line([(0, y), (w, y)], fill=(255, 80, 80, 120), width=1)
        if i % 5 == 0:
            draw.text((4, y + 2), str(i), fill=(255, 255, 255))

    return img, w, h


def _grid_to_pixel(gx: int, gy: int, screen_w: int, screen_h: int):
    """Convert grid coordinates to pixel coordinates."""
    return (gx * screen_w // GRID_COLS, gy * screen_h // GRID_ROWS)


def _ask_gemini(image_bytes: bytes, prompt: str) -> str:
    """Send image + prompt to Gemini Vision, get text response."""
    client = genai.Client(api_key=_get_api_key())
    resp = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=[
            prompt,
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        ],
    )
    return resp.text.strip()


def _parse_action(response: str):
    """Parse Gemini response into (action, x, y, text, amount)."""
    action = "done"
    x = y = -1
    text = ""
    amount = 0

    for line in response.split("\n"):
        line = line.strip()
        if line.upper().startswith("ACTION:"):
            action = line.split(":", 1)[1].strip().lower()
        elif line.upper().startswith("X:"):
            try:
                x = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.upper().startswith("Y:"):
            try:
                y = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.upper().startswith("TEXT:"):
            text = line.split(":", 1)[1].strip()
        elif line.upper().startswith("AMOUNT:"):
            try:
                amount = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass

    return action, x, y, text, amount


def computer_use_action(parameters: dict, player=None, speak=None) -> str:
    task = (parameters or {}).get("task", "").strip()
    max_steps = int((parameters or {}).get("max_steps", 8))
    if not task:
        return "Keine Aufgabe angegeben."

    if player:
        player.write_log(f"[ComputerUse] Aufgabe: {task}")

    screen_w = pyautogui.size().width
    screen_h = pyautogui.size().height

    for step in range(max_steps):
        if player:
            player.write_log(f"[ComputerUse] Schritt {step + 1}/{max_steps}")

        # 1. Capture with grid
        img, img_w, img_h = _capture_with_grid()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        # 2. Send to Gemini
        prompt = (
            f"AUFGABE: {task}\n"
            f"SCHRITT {step + 1}/{max_steps}\n\n"
            f"Der Bildschirm hat ein Gitter mit {GRID_COLS}x{GRID_ROWS} Zellen. "
            f"X-Achse: 0-{GRID_COLS-1}, Y-Achse: 0-{GRID_ROWS-1}.\n\n"
            f"Was ist der nächste Schritt? Antworte EXAKT in diesem Format:\n"
            f"ACTION: click | type | scroll | wait | done\n"
            f"X: <Grid-X>\nY: <Grid-Y>\n"
            f"TEXT: <Text zum Tippen>\n"
            f"AMOUNT: <Pixel für Scroll>\n"
            f"REASON: <Warum dieser Schritt?>\n\n"
            f"Beispiele:\n"
            f"ACTION: click\nX: 5\nY: 10\nREASON: 'Conflicts' Layer anklicken\n\n"
            f"ACTION: type\nTEXT: Ukraine\nREASON: In die Suchleiste tippen\n\n"
            f"ACTION: scroll\nAMOUNT: -300\nREASON: Nach unten scrollen\n\n"
            f"ACTION: wait\nREASON: Kurz warten bis Seite lädt\n\n"
            f"ACTION: done\nREASON: Aufgabe erledigt"
        )

        try:
            response = _ask_gemini(img_bytes, prompt)
        except Exception as e:
            return f"Gemini-Fehler: {e}"

        if player:
            player.write_log(f"[ComputerUse] Gemini: {response[:200]}")

        # 3. Parse and execute
        action, gx, gy, text, amount = _parse_action(response)

        if action == "done":
            return "Aufgabe erledigt."

        elif action == "wait":
            time.sleep(2)
            continue

        elif action == "click":
            if gx < 0 or gy < 0:
                if player:
                    player.write_log(f"[ComputerUse] Ungültige Koordinaten: gx={gx} gy={gy}")
                continue
            px, py = _grid_to_pixel(gx, gy, screen_w, screen_h)
            pyautogui.moveTo(px, py, duration=0.3)
            time.sleep(0.2)
            pyautogui.click()
            if player:
                player.write_log(f"[ComputerUse] Click ({gx},{gy}) -> ({px},{py})")
            time.sleep(1.5)

        elif action == "type":
            if text:
                pyautogui.typewrite(text, interval=0.05)
                pyautogui.press("enter")
                if player:
                    player.write_log(f"[ComputerUse] Type: {text}")
            time.sleep(1.5)

        elif action == "scroll":
            pyautogui.scroll(amount)
            if player:
                player.write_log(f"[ComputerUse] Scroll: {amount}")
            time.sleep(1)

        else:
            if player:
                player.write_log(f"[ComputerUse] Unbekannte Aktion: {action}")
            time.sleep(1)

    return f"Computer Use beendet nach {max_steps} Schritten."
