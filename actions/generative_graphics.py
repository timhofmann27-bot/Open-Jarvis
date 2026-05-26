"""
JARVIS Generative Graphics – erstellt Visualisierungen, Charts, 3D-Szenen und Diagramme on the fly.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional


TEMP_DIR = Path(tempfile.gettempdir()) / "jarvis_graphics"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def _open_in_browser(path: Path):
    subprocess.Popen(["cmd", "/c", "start", "", str(path)], shell=True)


def _html_page(title: str, body_js: str, body_html: str = "") -> str:
    """Generate a full HTML page with embedded JavaScript."""
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0a0a0a; color: #00d4ff; font-family: 'Segoe UI', Arial, sans-serif; }}
  #container {{ width: 100vw; height: 100vh; display: flex; align-items: center; justify-content: center; }}
  canvas {{ display: block; }}
  h1 {{ position: fixed; top: 20px; left: 50%; transform: translateX(-50%); color: #00d4ff;
        font-weight: 300; letter-spacing: 4px; text-transform: uppercase; font-size: 18px;
        text-shadow: 0 0 20px rgba(0,212,255,0.3); }}
  .label {{ color: #8899aa; font-size: 12px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div id="container">{body_html}</div>
<script>
{body_js}
</script>
</body>
</html>"""


# ── Chart Generation ─────────────────────────────────────────────────────────

def chart_chartjs(chart_type: str, data: dict, title: str = "Chart") -> Path:
    """Generate a Chart.js chart from data dict: {labels: [...], values: [...], colors: [...]}."""
    labels = json.dumps(data.get("labels", []))
    values = json.dumps(data.get("values", []))
    colors = json.dumps(data.get("colors", [
        "#00d4ff", "#ff6b6b", "#ffd93d", "#6bcb77", "#4d96ff",
        "#ff8a5c", "#a66cff", "#ff6b9d", "#00e5ff", "#76ff03"
    ]))

    js = f"""
const ctx = document.createElement('canvas');
document.getElementById('container').appendChild(ctx);
new Chart(ctx, {{
    type: '{chart_type}',
    data: {{
        labels: {labels},
        datasets: [{{
            label: '{title}',
            data: {values},
            backgroundColor: {colors},
            borderColor: '{'#00d4ff'}',
            borderWidth: 2,
            borderRadius: 4,
        }}]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
            legend: {{ labels: {{ color: '#00d4ff' }} }}
        }},
        scales: {{
            x: {{ ticks: {{ color: '#8899aa' }}, grid: {{ color: '#1a1a2e' }} }},
            y: {{ ticks: {{ color: '#8899aa' }}, grid: {{ color: '#1a1a2e' }} }}
        }}
    }}
}});
"""
    html = _html_page(title, js)
    path = TEMP_DIR / f"chart_{int(time.time())}.html"
    path.write_text(html, encoding="utf-8")
    return path


# ── 3D Scene Generation (Three.js) ──────────────────────────────────────────

def scene_3d(scene_type: str = "arc_reactor", params: dict = None) -> Path:
    """Generate a Three.js 3D scene. Types: arc_reactor, particle_field, wireframe_globe, data_tower."""
    p = params or {}

    scenes = {

        "arc_reactor": """
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, window.innerWidth/window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
document.getElementById('container').appendChild(renderer.domElement);

// Core glow
const coreGeo = new THREE.SphereGeometry(0.8, 32, 32);
const coreMat = new THREE.MeshBasicMaterial({ color: 0x00d4ff });
const core = new THREE.Mesh(coreGeo, coreMat);
scene.add(core);

// Rings
for (let i = 0; i < 3; i++) {
    const ringGeo = new THREE.TorusGeometry(1.5 + i * 0.5, 0.03, 16, 64);
    const ringMat = new THREE.MeshBasicMaterial({
        color: i === 0 ? 0x00d4ff : i === 1 ? 0x0088ff : 0x0044ff,
        transparent: true,
        opacity: 0.6 + i * 0.1,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = Math.PI / 2;
    ring.rotation.z = i * 0.5;
    scene.add(ring);
}

// Outer ring
const outerGeo = new THREE.TorusGeometry(3.0, 0.08, 16, 80);
const outerMat = new THREE.MeshBasicMaterial({ color: 0x00d4ff, transparent: true, opacity: 0.3 });
const outerRing = new THREE.Mesh(outerGeo, outerMat);
outerRing.rotation.x = Math.PI / 2;
scene.add(outerRing);

// Particles
const particleCount = 2000;
const particles = new THREE.BufferGeometry();
const pos = new Float32Array(particleCount * 3);
for (let i = 0; i < particleCount * 3; i++) {
    const r = 4 + Math.random() * 6;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    pos[i*3] = r * Math.sin(phi) * Math.cos(theta);
    pos[i*3+1] = r * Math.sin(phi) * Math.sin(theta);
    pos[i*3+2] = r * Math.cos(phi);
}
particles.setAttribute('position', new THREE.BufferAttribute(pos, 3));
const particleMat = new THREE.PointsMaterial({
    color: 0x00d4ff, size: 0.05, transparent: true, opacity: 0.6
});
const particleSystem = new THREE.Points(particles, particleMat);
scene.add(particleSystem);

camera.position.z = 10;

function animate() {
    requestAnimationFrame(animate);
    core.rotation.y += 0.01;
    outerRing.rotation.z += 0.005;
    particleSystem.rotation.y += 0.001;
    renderer.render(scene, camera);
}
animate();
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});
""",

        "particle_field": """
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, window.innerWidth/window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.getElementById('container').appendChild(renderer.domElement);

const count = 5000;
const geo = new THREE.BufferGeometry();
const pos = new Float32Array(count * 3);
const colors = new Float32Array(count * 3);
for (let i = 0; i < count; i++) {
    pos[i*3] = (Math.random() - 0.5) * 30;
    pos[i*3+1] = (Math.random() - 0.5) * 30;
    pos[i*3+2] = (Math.random() - 0.5) * 30;
    colors[i*3] = 0 + Math.random() * 0.5;
    colors[i*3+1] = 0.5 + Math.random() * 0.5;
    colors[i*3+2] = 0.8 + Math.random() * 0.2;
}
geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
const mat = new THREE.PointsMaterial({ size: 0.08, vertexColors: true, transparent: true, opacity: 0.8 });
const points = new THREE.Points(geo, mat);
scene.add(points);

camera.position.z = 18;
let time = 0;
function animate() {
    requestAnimationFrame(animate);
    time += 0.001;
    points.rotation.x = Math.sin(time * 0.1) * 0.1;
    points.rotation.y += 0.002;
    renderer.render(scene, camera);
}
animate();
""",

        "wireframe_globe": """
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, window.innerWidth/window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.getElementById('container').appendChild(renderer.domElement);

const geo = new THREE.SphereGeometry(3, 24, 18);
const mat = new THREE.MeshBasicMaterial({
    color: 0x00d4ff, wireframe: true, transparent: true, opacity: 0.4
});
const globe = new THREE.Mesh(geo, mat);
scene.add(globe);

// Inner glow
const innerGeo = new THREE.SphereGeometry(2.8, 32, 32);
const innerMat = new THREE.MeshBasicMaterial({
    color: 0x004488, transparent: true, opacity: 0.1
});
const inner = new THREE.Mesh(innerGeo, innerMat);
scene.add(inner);

// Lat/long lines
for (let i = 0; i < 12; i++) {
    const ringGeo = new THREE.TorusGeometry(3.05, 0.01, 8, 48);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0x0066aa, transparent: true, opacity: 0.2 });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = Math.PI / 2;
    ring.rotation.z = (i / 12) * Math.PI;
    scene.add(ring);
}

camera.position.z = 7;
function animate() {
    requestAnimationFrame(animate);
    globe.rotation.y += 0.005;
    inner.rotation.y += 0.003;
    renderer.render(scene, camera);
}
animate();
""",

        "data_tower": """
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, window.innerWidth/window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.getElementById('container').appendChild(renderer.domElement);

const bars = 24;
const spacing = 0.6;
const group = new THREE.Group();

for (let i = 0; i < bars; i++) {
    const h = 0.2 + Math.random() * 3;
    const geo = new THREE.BoxGeometry(0.3, h, 0.3);
    const hue = 0.5 + (i / bars) * 0.3;
    const color = new THREE.Color().setHSL(hue, 0.8, 0.5);
    const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.7 });
    const bar = new THREE.Mesh(geo, mat);
    const angle = (i / bars) * Math.PI * 2;
    const radius = 3;
    bar.position.x = Math.cos(angle) * radius;
    bar.position.z = Math.sin(angle) * radius;
    bar.position.y = h / 2;
    bar.lookAt(0, 0, 0);
    group.add(bar);
}

// Center glow
const glowGeo = new THREE.SphereGeometry(0.3, 16, 16);
const glowMat = new THREE.MeshBasicMaterial({ color: 0x00d4ff });
const glow = new THREE.Mesh(glowGeo, glowMat);
group.add(glow);

scene.add(group);
camera.position.set(8, 4, 8);
camera.lookAt(0, 0, 0);

function animate() {
    requestAnimationFrame(animate);
    group.rotation.y += 0.005;
    renderer.render(scene, camera);
}
animate();
""",
    }

    js = scenes.get(scene_type, scenes["arc_reactor"])
    html = _html_page(f"3D: {scene_type.replace('_', ' ').title()}", js)
    path = TEMP_DIR / f"3d_{scene_type}_{int(time.time())}.html"
    path.write_text(html, encoding="utf-8")
    return path


# ── Diagram Generation ───────────────────────────────────────────────────────

def network_diagram(nodes: list[dict], connections: list[tuple]) -> Path:
    """Generate a network topology diagram using Three.js."""
    nodes_json = json.dumps(nodes)
    conns_json = json.dumps(connections)

    js = f"""
const container = document.getElementById('container');
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, window.innerWidth/window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
container.appendChild(renderer.domElement);

const nodes = {nodes_json};
const connections = {conns_json};

const nodeGroup = new THREE.Group();
const nodeMap = {{}};

nodes.forEach((n, i) => {{
    const geo = new THREE.SphereGeometry(0.4, 16, 16);
    const color = n.color || '#00d4ff';
    const mat = new THREE.MeshBasicMaterial({{ color: parseInt(color.slice(1), 16) }});
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(n.x || 0, n.y || 0, n.z || 0);
    nodeGroup.add(mesh);
    nodeMap[n.id] = mesh;
}});

const lineMat = new THREE.LineBasicMaterial({{ color: 0x00d4ff, transparent: true, opacity: 0.2 }});
connections.forEach(conn => {{
    const a = nodeMap[conn[0]];
    const b = nodeMap[conn[1]];
    if (!a || !b) return;
    const points = [a.position.clone(), b.position.clone()];
    const geo = new THREE.BufferGeometry().setFromPoints(points);
    const line = new THREE.Line(geo, lineMat);
    nodeGroup.add(line);
}});

scene.add(nodeGroup);
camera.position.set(5, 3, 5);
camera.lookAt(0, 0, 0);

function animate() {{
    requestAnimationFrame(animate);
    nodeGroup.rotation.y += 0.003;
    renderer.render(scene, camera);
}}
animate();
"""
    html = _html_page("Netzwerk-Diagramm", js)
    path = TEMP_DIR / f"diagram_{int(time.time())}.html"
    path.write_text(html, encoding="utf-8")
    return path


# ── Procedural Image Generation ─────────────────────────────────────────────

def generate_image(style: str = "arc_reactor", params: dict = None) -> Path:
    """Generate a procedural image using Pillow. Returns path to PNG."""
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
    except ImportError:
        return _fallback_text("Pillow nicht installiert")

    p = params or {}
    w, h = 1920, 1080
    img = Image.new("RGB", (w, h), (10, 10, 30))
    draw = ImageDraw.Draw(img)

    if style == "arc_reactor":
        cx, cy = w // 2, h // 2
        max_r = min(w, h) // 3
        # Outer rings
        for r in range(max_r, 0, -max_r // 20):
            alpha = int(50 * (1 - r / max_r))
            color = (0, int(100 + 155 * (1 - r / max_r)), 255)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=2)
        # Center glow
        for r2 in range(max_r // 4, 0, -2):
            a = int(200 * (1 - r2 / (max_r // 4)))
            draw.ellipse([cx - r2, cy - r2, cx + r2, cy + r2],
                         fill=(0, int(100 + 155 * (1 - r2 / (max_r // 4))), 255, a))
        # Particles
        import random
        for _ in range(500):
            angle = random.random() * 360
            dist = random.random() * max_r * 1.5
            px = int(cx + dist * __import__('math').cos(__import__('math').radians(angle)))
            py = int(cy + dist * __import__('math').sin(__import__('math').radians(angle)))
            size = random.randint(1, 3)
            draw.ellipse([px, py, px + size, py + size], fill=(0, 212, 255, 100))

    elif style == "hologram":
        cx, cy = w // 2, h // 2
        draw.text((cx - 200, cy - 50), "HOLOGRAM", fill=(0, 212, 255, 200),
                  font=ImageFont.load_default())
        for i in range(0, w, 20):
            draw.line([(i, 0), (i + w // 2, h)], fill=(0, 212, 255, 30), width=1)
        for i in range(0, h, 20):
            draw.line([(0, i), (w, i)], fill=(0, 212, 255, 20), width=1)

    elif style == "data_dashboard":
        # Simulated dashboard blocks
        blocks = [(50, 50, 600, 300), (700, 50, 500, 300), (50, 400, 1150, 600)]
        for bx, by, bw, bh in blocks:
            draw.rectangle([bx, by, bx + bw, by + bh], outline=(0, 100, 200, 150), width=2)
            draw.text((bx + 20, by + 20), f"DATENBLOCK", fill=(0, 212, 255, 150))

    path = TEMP_DIR / f"img_{style}_{int(time.time())}.png"
    img.save(path)
    return path


def _fallback_text(text: str) -> Path:
    path = TEMP_DIR / f"fallback_{int(time.time())}.html"
    path.write_text(f"<html><body style='background:#0a0a0a;color:#00d4ff;font-size:24px'>{text}</body></html>",
                    encoding="utf-8")
    return path


# ── Main Entry Point ─────────────────────────────────────────────────────────

def generative_graphics_action(parameters: dict, player=None, speak=None) -> str:
    action = (parameters or {}).get("action", "chart").strip().lower()
    chart_type = (parameters or {}).get("chart_type", "bar")
    title = (parameters or {}).get("title", "JARVIS Visualization")
    scene_type = (parameters or {}).get("scene_type", "arc_reactor")
    style = (parameters or {}).get("style", "arc_reactor")

    if player:
        player.write_log(f"[GenerativeGraphics] action={action}")

    # Parse data from parameters
    data = {}
    labels_raw = (parameters or {}).get("labels", "")
    values_raw = (parameters or {}).get("values", "")
    if labels_raw:
        data["labels"] = [l.strip() for l in labels_raw.split(",")]
    if values_raw:
        data["values"] = [float(v.strip()) for v in values_raw.split(",")]

    try:
        if action == "chart":
            if not data.get("values"):
                return "Bitte 'values' angeben (komma-getrennte Zahlen)."
            path = chart_chartjs(chart_type, data, title)
            _open_in_browser(path)
            msg = f"{chart_type.title()}-Chart '{title}' geöffnet im Browser."
            if speak:
                speak(msg)
            return msg

        elif action == "scene_3d" or action == "3d":
            path = scene_3d(scene_type, parameters)
            _open_in_browser(path)
            msg = f"3D-Szene '{scene_type}' geöffnet im Browser."
            if speak:
                speak(msg)
            return msg

        elif action == "network_diagram" or action == "diagram":
            nodes_raw = (parameters or {}).get("nodes", "")
            conns_raw = (parameters or {}).get("connections", "")
            if not nodes_raw:
                return "Bitte 'nodes' im JSON-Format angeben."
            nodes = json.loads(nodes_raw) if isinstance(nodes_raw, str) else nodes_raw
            conns = json.loads(conns_raw) if isinstance(conns_raw, str) else (conns_raw or [])
            path = network_diagram(nodes, conns)
            _open_in_browser(path)
            return f"Netzwerk-Diagramm mit {len(nodes)} Knoten geöffnet."

        elif action == "image":
            path = generate_image(style, parameters)
            _open_in_browser(path)
            return f"Bild im {style}-Stil generiert."

        elif action == "preview_scenes":
            scenes = ["arc_reactor", "particle_field", "wireframe_globe", "data_tower"]
            paths = []
            for s in scenes:
                p = scene_3d(s)
                paths.append(p)
            for p in paths:
                _open_in_browser(p)
            return f"{len(scenes)} 3D-Szenen geöffnet: {', '.join(scenes)}"

        else:
            return (
                f"Unbekannte Aktion: {action}.\n\n"
                f"Verfügbar:\n"
                f"  chart         - Diagramm (chart_type: bar, line, pie, doughnut)\n"
                f"  scene_3d      - 3D-Szene (scene_type: arc_reactor, particle_field, wireframe_globe, data_tower)\n"
                f"  diagram       - Netzwerk-Diagramm\n"
                f"  image         - Prozedurales Bild (style: arc_reactor, hologram, data_dashboard)\n"
                f"  preview_scenes - Alle 3D-Szenen öffnen"
            )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Generative Graphics Fehler: {e}"
