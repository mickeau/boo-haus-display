#!/usr/bin/env python3
"""
Boo Haus Display — Web Dashboard
Control panel for the e-ink display.

Run: python3 web_dashboard.py
Access: http://127.0.0.1:5000
Set BOO_HAUS_DASHBOARD_HOST=0.0.0.0 to expose it on the local network.
"""

import json
import os
import signal
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
SCREEN_NAMES = ['weather', 'week', 'nfl', 'calendar', 'news', 'birthday', 'status']


def resolve_path(path):
    path = Path(path)
    return path if path.is_absolute() else BASE_DIR / path


CONFIG_FILE = resolve_path(os.environ.get('BOO_HAUS_CONFIG_FILE', 'boo_haus_config.json'))


def get_nested(data, key, default=None):
    value = data
    for part in key.split('.'):
        if not isinstance(value, dict):
            return default
        value = value.get(part)
        if value is None:
            return default
    return value


def state_file(config_data):
    return resolve_path(get_nested(config_data, 'state_file', 'display_state.json'))


def log_file(config_data):
    return resolve_path(get_nested(config_data, 'logging.display_log_file', 'logs/display.log'))


def image_dir(config_data):
    return resolve_path(get_nested(config_data, 'display.image_directory', 'display_images'))


def enabled_screen_names(config_data):
    screens_config = config_data.get('screens', {})
    return [
        name for name in SCREEN_NAMES
        if screens_config.get(name, {}).get('enabled', True)
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def get_display_pid():
    """Find the PID of the running boo_haus_main.py process."""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'boo_haus_main.py.*--cycle'],
            capture_output=True, text=True, timeout=5
        )
        pids = result.stdout.strip().split()
        return int(pids[0]) if pids else None
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return None


def wake_display():
    """Send SIGALRM to the display process to wake it from signal.pause()."""
    pid = get_display_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGALRM)
            return True
        except OSError:
            pass
    return False


def parse_line_count(value, default=80, minimum=1, maximum=500):
    """Parse and clamp a dashboard log line count."""
    try:
        line_count = int(value)
    except (TypeError, ValueError):
        return default

    return max(minimum, min(maximum, line_count))


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return DASHBOARD_HTML


# --- Screen previews ---

@app.route('/api/screens')
def api_screens():
    """List all screens with their enabled status and latest preview image."""
    config = read_json(CONFIG_FILE)
    state = read_json(state_file(config))
    screens_config = config.get('screens', {})

    active_screen_names = enabled_screen_names(config)
    current_index = state.get('current_screen', 0)
    requested_screen = state.get('requested_screen')

    screens = []
    for name in SCREEN_NAMES:
        sc = screens_config.get(name, {})
        latest_img = f"{name}_latest.png"
        image_path = image_dir(config) / latest_img
        has_image = image_path.exists()
        is_current = (
            requested_screen == name or
            (name in active_screen_names and active_screen_names.index(name) == current_index)
        )

        screens.append({
            'name': name,
            'enabled': sc.get('enabled', True),
            'has_image': has_image,
            'image_url': f'/images/{latest_img}' if has_image else None,
            'is_current': is_current
        })

    return jsonify({
        'screens': screens,
        'cycle_count': state.get('cycle_count', 0),
        'last_update': state.get('last_update'),
    })


@app.route('/images/<filename>')
def serve_image(filename):
    config = read_json(CONFIG_FILE)
    return send_from_directory(str(image_dir(config)), filename)


# --- Screen controls ---

@app.route('/api/screen/<name>/toggle', methods=['POST'])
def toggle_screen(name):
    if name not in SCREEN_NAMES:
        return jsonify({'error': f'Unknown screen: {name}'}), 404

    config = read_json(CONFIG_FILE)
    screens = config.setdefault('screens', {})
    sc = screens.setdefault(name, {})
    sc['enabled'] = not sc.get('enabled', True)
    write_json(CONFIG_FILE, config)
    return jsonify({'name': name, 'enabled': sc['enabled']})


@app.route('/api/screen/<name>/show', methods=['POST'])
def show_screen(name):
    """Skip to a specific screen immediately."""
    if name not in SCREEN_NAMES:
        return jsonify({'error': f'Unknown screen: {name}'}), 404

    config = read_json(CONFIG_FILE)
    if name not in enabled_screen_names(config):
        return jsonify({'error': f'Screen is disabled: {name}'}), 400

    state = read_json(state_file(config))
    state['requested_screen'] = name
    write_json(state_file(config), state)
    wake_display()
    return jsonify({'requested': name})


@app.route('/api/refresh', methods=['POST'])
def force_refresh():
    wake_display()
    return jsonify({'status': 'ok', 'message': 'Display woken'})


@app.route('/api/restart', methods=['POST'])
def restart_service():
    failures = []
    for command in (
        ['systemctl', 'restart', 'boo-haus-display'],
        ['sudo', '-n', 'systemctl', 'restart', 'boo-haus-display'],
    ):
        try:
            subprocess.run(
                command,
                capture_output=True, text=True, check=True, timeout=10
            )
            return jsonify({'status': 'ok', 'message': 'Service restarting'})
        except FileNotFoundError as e:
            failures.append(str(e))
        except subprocess.TimeoutExpired as e:
            failures.append(f"Timed out running {' '.join(e.cmd)}")
        except subprocess.CalledProcessError as e:
            failures.append(e.stderr.strip() or e.stdout.strip() or str(e))
        except OSError as e:
            failures.append(str(e))

    return jsonify({'status': 'error', 'message': failures[-1] if failures else 'Restart failed'}), 500


# --- Log viewer ---

@app.route('/api/logs')
def api_logs():
    lines = parse_line_count(request.args.get('lines', 80))
    config = read_json(CONFIG_FILE)
    try:
        result = subprocess.run(
            ['tail', f'-{lines}', str(log_file(config))],
            capture_output=True, text=True, timeout=5
        )
        return jsonify({'lines': result.stdout.strip().split('\n')})
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as e:
        return jsonify({'lines': [f'Error reading logs: {e}']})


# --- Config editor ---

@app.route('/api/config', methods=['GET'])
def get_config():
    config = read_json(CONFIG_FILE)
    return jsonify(config)


@app.route('/api/config', methods=['POST'])
def save_config():
    try:
        new_config = request.get_json(silent=True)
        if not isinstance(new_config, dict):
            return jsonify({'error': 'Invalid config'}), 400

        # Back up current config
        backup = CONFIG_FILE.with_name(CONFIG_FILE.name + '.bak')
        config = read_json(CONFIG_FILE)
        write_json(backup, config)

        write_json(CONFIG_FILE, new_config)
        return jsonify({'status': 'ok', 'message': 'Config saved (backup at .bak)'})
    except (OSError, TypeError, ValueError) as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Dashboard HTML (single-page app)
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Boo Haus Dashboard</title>
<style>
  :root { --bg: #1a1a2e; --card: #16213e; --accent: #5668e6; --text: #e0e0e0;
          --green: #4caf50; --red: #ef5350; --orange: #ff9800; --border: #2a2a4a; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: var(--bg); color: var(--text); padding: 16px; }
  h1 { color: var(--accent); margin-bottom: 16px; font-size: 1.5em; }
  h2 { color: var(--accent); margin: 20px 0 10px; font-size: 1.1em; }

  .tabs { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
  .tab { padding: 8px 16px; border: 1px solid var(--border); border-radius: 6px;
         background: var(--card); color: var(--text); cursor: pointer; font-size: 0.9em; }
  .tab.active { background: var(--accent); color: #fff; border-color: var(--accent); }

  .panel { display: none; }
  .panel.active { display: block; }

  /* Screens panel */
  .screen-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
                 gap: 12px; }
  .screen-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px;
                 padding: 12px; text-align: center; }
  .screen-card.current { border-color: var(--accent); box-shadow: 0 0 8px rgba(86,104,230,0.3); }
  .screen-card img { width: 100%; border-radius: 4px; margin: 8px 0;
                     image-rendering: auto; }
  .screen-card .name { font-weight: 600; text-transform: capitalize; }
  .screen-card .badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
                        font-size: 0.75em; margin-top: 4px; }
  .badge.on { background: var(--green); color: #fff; }
  .badge.off { background: var(--red); color: #fff; }

  .btn { padding: 6px 14px; border: none; border-radius: 5px; cursor: pointer;
         font-size: 0.85em; margin: 3px; color: #fff; }
  .btn-toggle { background: var(--orange); }
  .btn-show { background: var(--accent); }
  .btn-action { background: var(--green); }
  .btn-danger { background: var(--red); }

  .controls { margin: 12px 0; display: flex; gap: 8px; flex-wrap: wrap; }
  .stats { color: #888; font-size: 0.85em; margin-top: 8px; }

  /* Logs panel */
  .log-box { background: #0d1117; color: #c9d1d9; font-family: 'Courier New', monospace;
             font-size: 0.8em; padding: 12px; border-radius: 8px; max-height: 70vh;
             overflow-y: auto; white-space: pre-wrap; word-break: break-all;
             line-height: 1.5; }
  .log-line.error { color: var(--red); }
  .log-line.warning { color: var(--orange); }
  .log-line.info { color: var(--green); }

  /* Config panel */
  .config-editor { width: 100%; min-height: 50vh; background: #0d1117; color: #c9d1d9;
                   font-family: 'Courier New', monospace; font-size: 0.85em;
                   padding: 12px; border-radius: 8px; border: 1px solid var(--border);
                   resize: vertical; }
  .config-msg { margin-top: 8px; font-size: 0.85em; }
  .config-msg.ok { color: var(--green); }
  .config-msg.err { color: var(--red); }
</style>
</head>
<body>

<h1>Boo Haus Dashboard</h1>

<div class="tabs">
  <div class="tab active" onclick="showTab('screens')">Screens</div>
  <div class="tab" onclick="showTab('logs')">Logs</div>
  <div class="tab" onclick="showTab('config')">Config</div>
</div>

<div id="screens" class="panel active">
  <div class="controls">
    <button class="btn btn-action" onclick="refresh()">Wake Display</button>
    <button class="btn btn-danger" onclick="restartService()">Restart Service</button>
  </div>
  <div class="stats" id="stats"></div>
  <div class="screen-grid" id="screen-grid"></div>
</div>

<div id="logs" class="panel">
  <div class="controls">
    <button class="btn btn-action" onclick="loadLogs()">Refresh Logs</button>
    <select id="log-lines" onchange="loadLogs()" style="padding:6px;border-radius:5px;">
      <option value="50">50 lines</option>
      <option value="100" selected>100 lines</option>
      <option value="200">200 lines</option>
      <option value="500">500 lines</option>
    </select>
  </div>
  <div class="log-box" id="log-box">Loading...</div>
</div>

<div id="config" class="panel">
  <p style="margin-bottom:8px;font-size:0.85em;color:#888;">
    Edit config below. A backup is saved automatically before each save.
  </p>
  <textarea class="config-editor" id="config-editor"></textarea>
  <div class="controls">
    <button class="btn btn-action" onclick="saveConfig()">Save Config</button>
    <button class="btn btn-danger" onclick="restartService()">Save &amp; Restart</button>
  </div>
  <div class="config-msg" id="config-msg"></div>
</div>

<script>
const API = '';

function showTab(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(name).classList.add('active');
  event.target.classList.add('active');
  if (name === 'logs') loadLogs();
  if (name === 'config') loadConfig();
  if (name === 'screens') loadScreens();
}

// --- Screens ---
async function loadScreens() {
  const res = await fetch(API + '/api/screens');
  const data = await res.json();
  const grid = document.getElementById('screen-grid');
  const stats = document.getElementById('stats');

  stats.textContent = `Cycles: ${data.cycle_count || 0} | Last update: ${data.last_update ? new Date(data.last_update).toLocaleTimeString() : 'N/A'}`;

  grid.innerHTML = data.screens.map(s => `
    <div class="screen-card ${s.is_current ? 'current' : ''}">
      <div class="name">${s.name}</div>
      <span class="badge ${s.enabled ? 'on' : 'off'}">${s.enabled ? 'ON' : 'OFF'}</span>
      ${s.has_image ? `<img src="${s.image_url}?t=${Date.now()}" alt="${s.name}">` : '<p style="color:#666;margin:12px 0;">No preview</p>'}
      <div>
        <button class="btn btn-toggle" onclick="toggleScreen('${s.name}')">Toggle</button>
        <button class="btn btn-show" onclick="showScreen('${s.name}')">Show Now</button>
      </div>
    </div>
  `).join('');
}

async function toggleScreen(name) {
  await fetch(API + `/api/screen/${name}/toggle`, {method:'POST'});
  loadScreens();
}

async function showScreen(name) {
  await fetch(API + `/api/screen/${name}/show`, {method:'POST'});
  setTimeout(loadScreens, 2000);
}

async function refresh() {
  await fetch(API + '/api/refresh', {method:'POST'});
}

async function restartService() {
  if (!confirm('Restart the display service?')) return;
  const res = await fetch(API + '/api/restart', {method:'POST'});
  const data = await res.json();
  alert(data.message);
  setTimeout(loadScreens, 5000);
}

// --- Logs ---
async function loadLogs() {
  const lines = document.getElementById('log-lines').value;
  const res = await fetch(API + `/api/logs?lines=${lines}`);
  const data = await res.json();
  const box = document.getElementById('log-box');
  box.innerHTML = data.lines.map(l => {
    let cls = '';
    if (l.includes('ERROR')) cls = 'error';
    else if (l.includes('WARNING')) cls = 'warning';
    else if (l.includes('INFO')) cls = 'info';
    return `<div class="log-line ${cls}">${escHtml(l)}</div>`;
  }).join('');
  box.scrollTop = box.scrollHeight;
}

// --- Config ---
async function loadConfig() {
  const res = await fetch(API + '/api/config');
  const data = await res.json();
  document.getElementById('config-editor').value = JSON.stringify(data, null, 2);
  document.getElementById('config-msg').textContent = '';
}

async function saveConfig() {
  const msg = document.getElementById('config-msg');
  const text = document.getElementById('config-editor').value;
  let parsed;
  try { parsed = JSON.parse(text); } catch(e) {
    msg.className = 'config-msg err';
    msg.textContent = 'Invalid JSON: ' + e.message;
    return;
  }
  const res = await fetch(API + '/api/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(parsed)
  });
  const data = await res.json();
  if (res.ok) {
    msg.className = 'config-msg ok';
    msg.textContent = data.message;
  } else {
    msg.className = 'config-msg err';
    msg.textContent = data.error || 'Save failed';
  }
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// Auto-refresh screens every 30s
loadScreens();
setInterval(loadScreens, 30000);
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    host = os.environ.get('BOO_HAUS_DASHBOARD_HOST', '127.0.0.1')
    port = int(os.environ.get('BOO_HAUS_DASHBOARD_PORT', '5000'))
    app.run(host=host, port=port, debug=False)
