import os
import re
import subprocess
import requests
from functools import wraps
from flask import Flask, render_template, jsonify, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-me-in-production')

DASHBOARD_PASSWORD = os.environ.get('DASHBOARD_PASSWORD', 'admin')
COMPOSE_DIR = os.environ.get('COMPOSE_DIR', '/home/ubuntu/pz-server')
CONTAINER_NAME = os.environ.get('CONTAINER_NAME', 'projectzomboid')
ENV_FILE = os.path.join(COMPOSE_DIR, '.env')


def read_env_file():
    """Read the .env file and return as dict."""
    env_vars = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


def write_env_file(env_vars):
    """Write dict back to .env file, preserving comments and order."""
    lines = []
    existing_keys = set()

    # Read existing file to preserve comments and order
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith('#') or not stripped:
                    lines.append(line.rstrip('\n'))
                elif '=' in stripped:
                    key = stripped.split('=', 1)[0].strip()
                    existing_keys.add(key)
                    if key in env_vars:
                        lines.append(f'{key}={env_vars[key]}')
                    else:
                        lines.append(line.rstrip('\n'))

    # Add new keys that weren't in the file
    for key, value in env_vars.items():
        if key not in existing_keys:
            lines.append(f'{key}={value}')

    with open(ENV_FILE, 'w') as f:
        f.write('\n'.join(lines) + '\n')


def get_mods():
    """Get current mod configuration."""
    env = read_env_file()
    workshop_items = env.get('WORKSHOP_ITEMS', '')
    mods = env.get('MODS', '')

    # Parse into lists (semicolon separated)
    workshop_list = [w.strip() for w in workshop_items.split(';') if w.strip()]
    mod_list = [m.strip() for m in mods.split(';') if m.strip()]

    return {
        'workshop_items': workshop_list,
        'mods': mod_list
    }


def save_mods(workshop_items, mods):
    """Save mod configuration."""
    env = read_env_file()
    env['WORKSHOP_ITEMS'] = ';'.join(workshop_items)
    env['MODS'] = ';'.join(mods)
    write_env_file(env)


def fetch_workshop_info(workshop_id):
    """Fetch mod info from Steam Workshop API."""
    try:
        url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
        data = {
            'itemcount': 1,
            'publishedfileids[0]': workshop_id
        }
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get('response', {}).get('publishedfiledetails'):
                details = result['response']['publishedfiledetails'][0]
                if details.get('result') == 1:
                    return {
                        'success': True,
                        'title': details.get('title', 'Unknown'),
                        'description': details.get('description', '')[:200],
                        'preview_url': details.get('preview_url', ''),
                        'workshop_id': workshop_id,
                        'is_collection': details.get('creator_appid') == 0  # Collections have creator_appid=0
                    }
        return {'success': False, 'error': 'Mod not found'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def fetch_collection_items(collection_id):
    """Fetch all items from a Steam Workshop collection."""
    try:
        url = "https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/"
        data = {
            'collectioncount': 1,
            'publishedfileids[0]': collection_id
        }
        response = requests.post(url, data=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get('response', {}).get('collectiondetails'):
                collection = result['response']['collectiondetails'][0]
                if collection.get('result') == 1:
                    children = collection.get('children', [])
                    item_ids = [str(child['publishedfileid']) for child in children]
                    return {
                        'success': True,
                        'items': item_ids,
                        'count': len(item_ids)
                    }
        return {'success': False, 'error': 'Collection not found or empty'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def run_docker_command(command):
    """Run a docker compose command and return output."""
    try:
        result = subprocess.run(
            command,
            cwd=COMPOSE_DIR,
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            'success': result.returncode == 0,
            'output': result.stdout or result.stderr
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'output': 'Command timed out'}
    except Exception as e:
        return {'success': False, 'output': str(e)}


def get_container_status():
    """Get the status of the PZ container."""
    result = subprocess.run(
        ['docker', 'ps', '-a', '--filter', f'name={CONTAINER_NAME}', '--format', '{{.Status}}'],
        capture_output=True,
        text=True
    )
    status = result.stdout.strip()
    if not status:
        return 'not found'
    if 'Up' in status:
        return 'running'
    return 'stopped'


def get_container_stats():
    """Get CPU/Memory usage of the container."""
    result = subprocess.run(
        ['docker', 'stats', CONTAINER_NAME, '--no-stream', '--format', '{{.CPUPerc}},{{.MemUsage}}'],
        capture_output=True,
        text=True
    )
    if result.returncode == 0 and result.stdout.strip():
        parts = result.stdout.strip().split(',')
        return {
            'cpu': parts[0] if len(parts) > 0 else 'N/A',
            'memory': parts[1] if len(parts) > 1 else 'N/A'
        }
    return {'cpu': 'N/A', 'memory': 'N/A'}


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == DASHBOARD_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid password')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    return render_template('index.html')


@app.route('/api/status')
@login_required
def api_status():
    status = get_container_status()
    stats = get_container_stats() if status == 'running' else {'cpu': 'N/A', 'memory': 'N/A'}
    return jsonify({
        'status': status,
        'cpu': stats['cpu'],
        'memory': stats['memory']
    })


@app.route('/api/logs')
@login_required
def api_logs():
    lines = request.args.get('lines', '100')
    result = subprocess.run(
        ['docker', 'logs', CONTAINER_NAME, '--tail', lines],
        capture_output=True,
        text=True
    )
    # Combine stdout and stderr (game logs go to stderr)
    output = result.stdout + result.stderr
    return jsonify({'logs': output})


@app.route('/api/start', methods=['POST'])
@login_required
def api_start():
    result = run_docker_command(['docker-compose', '-f', 'docker-compose.yml', 'up', '-d'])
    return jsonify(result)


@app.route('/api/stop', methods=['POST'])
@login_required
def api_stop():
    result = run_docker_command(['docker-compose', '-f', 'docker-compose.yml', 'down'])
    return jsonify(result)


@app.route('/api/restart', methods=['POST'])
@login_required
def api_restart():
    result = run_docker_command(['docker-compose', '-f', 'docker-compose.yml', 'restart'])
    return jsonify(result)


@app.route('/api/backup', methods=['POST'])
@login_required
def api_backup():
    """Create a backup of server-data."""
    import datetime
    timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_name = f'backup-{timestamp}.tar.gz'
    backup_path = os.path.join(COMPOSE_DIR, 'backups', backup_name)

    os.makedirs(os.path.join(COMPOSE_DIR, 'backups'), exist_ok=True)

    result = subprocess.run(
        ['tar', '-czf', backup_path, 'server-data'],
        cwd=COMPOSE_DIR,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        return jsonify({'success': True, 'output': f'Backup created: {backup_name}'})
    return jsonify({'success': False, 'output': result.stderr})


@app.route('/api/workshop/<workshop_id>')
@login_required
def api_workshop_lookup(workshop_id):
    """Lookup mod info from Steam Workshop."""
    return jsonify(fetch_workshop_info(workshop_id))


@app.route('/api/collection/<collection_id>')
@login_required
def api_collection_lookup(collection_id):
    """Lookup collection info and items from Steam Workshop."""
    # First get collection metadata
    info = fetch_workshop_info(collection_id)
    if not info.get('success'):
        return jsonify(info)

    # Then get collection items
    items = fetch_collection_items(collection_id)
    if items.get('success'):
        info['is_collection'] = True
        info['collection_items'] = items['items']
        info['collection_count'] = items['count']
    else:
        info['is_collection'] = False

    return jsonify(info)


@app.route('/api/mods/import-collection', methods=['POST'])
@login_required
def api_import_collection():
    """Import all mods from a Steam Workshop collection."""
    data = request.json
    collection_id = data.get('collection_id', '').strip()

    if not collection_id:
        return jsonify({'success': False, 'output': 'Collection ID is required'})

    # Fetch collection items
    result = fetch_collection_items(collection_id)
    if not result.get('success'):
        return jsonify({'success': False, 'output': result.get('error', 'Failed to fetch collection')})

    item_ids = result.get('items', [])
    if not item_ids:
        return jsonify({'success': False, 'output': 'Collection is empty'})

    current = get_mods()
    added_count = 0

    # Add each workshop item if not already present
    for workshop_id in item_ids:
        if workshop_id not in current['workshop_items']:
            current['workshop_items'].append(workshop_id)
            added_count += 1

    try:
        save_mods(current['workshop_items'], current['mods'])
        return jsonify({
            'success': True,
            'output': f'Added {added_count} mods from collection ({len(item_ids)} total, {len(item_ids) - added_count} already existed)',
            'added': added_count,
            'total': len(item_ids)
        })
    except Exception as e:
        return jsonify({'success': False, 'output': str(e)})


@app.route('/api/mods')
@login_required
def api_get_mods():
    """Get current mod list."""
    return jsonify(get_mods())


@app.route('/api/mods', methods=['POST'])
@login_required
def api_save_mods():
    """Save mod list (with order)."""
    data = request.json
    workshop_items = data.get('workshop_items', [])
    mods = data.get('mods', [])

    try:
        save_mods(workshop_items, mods)
        return jsonify({'success': True, 'output': 'Mods saved. Restart server to apply.'})
    except Exception as e:
        return jsonify({'success': False, 'output': str(e)})


@app.route('/api/mods/add', methods=['POST'])
@login_required
def api_add_mod():
    """Add a new mod by Workshop ID and Mod ID."""
    data = request.json
    workshop_id = data.get('workshop_id', '').strip()
    mod_id = data.get('mod_id', '').strip()

    if not workshop_id:
        return jsonify({'success': False, 'output': 'Workshop ID is required'})

    current = get_mods()

    # Add workshop ID if not already present
    if workshop_id not in current['workshop_items']:
        current['workshop_items'].append(workshop_id)

    # Add mod ID if provided and not already present
    if mod_id and mod_id not in current['mods']:
        current['mods'].append(mod_id)

    try:
        save_mods(current['workshop_items'], current['mods'])
        return jsonify({'success': True, 'output': f'Added mod {workshop_id}'})
    except Exception as e:
        return jsonify({'success': False, 'output': str(e)})


@app.route('/api/mods/remove', methods=['POST'])
@login_required
def api_remove_mod():
    """Remove a mod."""
    data = request.json
    workshop_id = data.get('workshop_id', '').strip()
    mod_id = data.get('mod_id', '').strip()

    current = get_mods()

    if workshop_id and workshop_id in current['workshop_items']:
        current['workshop_items'].remove(workshop_id)

    if mod_id and mod_id in current['mods']:
        current['mods'].remove(mod_id)

    try:
        save_mods(current['workshop_items'], current['mods'])
        return jsonify({'success': True, 'output': 'Mod removed'})
    except Exception as e:
        return jsonify({'success': False, 'output': str(e)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
