import os
import subprocess
import uuid
import threading
import time
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ripped_tunes')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

jobs = {}

CLEANUP_DELAY = 600

ALLOWED_YOUTUBE_HOSTS = {'www.youtube.com', 'youtube.com', 'm.youtube.com', 'youtu.be', 'music.youtube.com'}
ALLOWED_SOUNDCLOUD_HOSTS = {'soundcloud.com', 'www.soundcloud.com', 'm.soundcloud.com'}


def cleanup_job(job_id, files):
    time.sleep(CLEANUP_DELAY)
    for f in files:
        try:
            filepath = os.path.join(DOWNLOAD_DIR, f)
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass
    jobs.pop(job_id, None)


def cleanup_failed_jobs():
    while True:
        time.sleep(300)
        now = time.time()
        to_remove = []
        for jid, job in list(jobs.items()):
            if job.get('status') in ('error',) and now - job.get('created', now) > 300:
                to_remove.append(jid)
        for jid in to_remove:
            jobs.pop(jid, None)


cleanup_thread = threading.Thread(target=cleanup_failed_jobs, daemon=True)
cleanup_thread.start()


def validate_url(url, source_type):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        host = parsed.hostname
        if not host:
            return False
        if source_type == 'youtube':
            return host in ALLOWED_YOUTUBE_HOSTS
        elif source_type == 'soundcloud':
            return host in ALLOWED_SOUNDCLOUD_HOSTS
        return False
    except Exception:
        return False


SUPPORTED_BROWSERS = {'chrome', 'firefox', 'edge', 'safari', 'opera', 'brave', 'chromium', 'vivaldi'}


def build_command(output_prefix, url, source_type, browser=None):
    command = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
    ]
    if source_type == "soundcloud":
        command.append("--no-playlist")
    if browser and browser in SUPPORTED_BROWSERS:
        command.extend(["--cookies-from-browser", browser])
    command.extend(["-o", os.path.join(DOWNLOAD_DIR, f"{output_prefix}_%(title)s.%(ext)s")])
    command.append(url)
    return command


def run_download(job_id, url, source_type, browser=None):
    jobs[job_id]['status'] = 'downloading'

    command = build_command(job_id, url, source_type, browser)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            downloaded_files = []
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(job_id) and f.endswith('.mp3'):
                    downloaded_files.append(f)

            if downloaded_files:
                jobs[job_id]['status'] = 'complete'
                jobs[job_id]['files'] = downloaded_files
                t = threading.Thread(target=cleanup_job, args=(job_id, downloaded_files), daemon=True)
                t.start()
            else:
                jobs[job_id]['status'] = 'error'
                jobs[job_id]['error'] = 'Download finished but no MP3 file was found. The source may not be supported.'
        else:
            error_msg = result.stderr or result.stdout or 'Unknown error occurred'
            jobs[job_id]['status'] = 'error'
            jobs[job_id]['error'] = error_msg[:500]

    except subprocess.TimeoutExpired:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['error'] = 'Download timed out after 5 minutes.'
    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['error'] = str(e)[:500]


@app.route('/')
def index():
    return render_template('index.html')


def run_batch_download(batch_id, urls, source_type, browser=None):
    batch = jobs[batch_id]
    batch['status'] = 'downloading'
    batch['total'] = len(urls)
    batch['completed_count'] = 0
    batch['errors'] = []

    for i, url in enumerate(urls):
        sub_id = f"{batch_id}_{i}"
        command = build_command(sub_id, url, source_type, browser)

        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                for f in os.listdir(DOWNLOAD_DIR):
                    if f.startswith(sub_id) and f.endswith('.mp3') and f not in batch['files']:
                        batch['files'].append(f)
            else:
                error_msg = result.stderr or result.stdout or 'Unknown error'
                batch['errors'].append(f"Link {i+1}: {error_msg[:200]}")
        except subprocess.TimeoutExpired:
            batch['errors'].append(f"Link {i+1}: Timed out after 5 minutes")
        except Exception as e:
            batch['errors'].append(f"Link {i+1}: {str(e)[:200]}")

        batch['completed_count'] = i + 1
        batch['status_detail'] = f"Processing {i+1} of {len(urls)}..."

    if batch['files']:
        batch['status'] = 'complete'
        t = threading.Thread(target=cleanup_job, args=(batch_id, batch['files']), daemon=True)
        t.start()
    elif batch['errors']:
        batch['status'] = 'error'
        batch['error'] = '\n'.join(batch['errors'])
    else:
        batch['status'] = 'error'
        batch['error'] = 'No MP3 files were created. The sources may not be supported.'


@app.route('/api/convert', methods=['POST'])
def convert():
    data = request.get_json()
    raw_urls = data.get('urls', [])
    single_url = data.get('url', '').strip()
    source_type = data.get('source', 'youtube')

    if single_url and not raw_urls:
        raw_urls = [single_url]

    urls = [u.strip() for u in raw_urls if u.strip()]

    if not urls:
        return jsonify({'error': 'Please provide at least one URL'}), 400

    if len(urls) > 20:
        return jsonify({'error': 'Maximum 20 links at a time'}), 400

    if source_type not in ('youtube', 'soundcloud'):
        return jsonify({'error': 'Invalid source type'}), 400

    invalid = []
    for i, url in enumerate(urls):
        if not validate_url(url, source_type):
            invalid.append(i + 1)

    if invalid:
        label = 'YouTube' if source_type == 'youtube' else 'SoundCloud'
        if len(invalid) == len(urls):
            return jsonify({'error': f'Please provide valid {label} URLs'}), 400
        return jsonify({'error': f'Invalid {label} URL(s) at line(s): {", ".join(str(n) for n in invalid)}'}), 400

    browser = data.get('browser', '').strip().lower()
    if browser and browser not in SUPPORTED_BROWSERS:
        browser = ''

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        'status': 'queued', 'files': [], 'error': None, 'errors': [],
        'created': time.time(), 'total': len(urls), 'completed_count': 0,
        'status_detail': f'Queued {len(urls)} link(s)...'
    }

    if len(urls) == 1:
        thread = threading.Thread(target=run_download, args=(job_id, urls[0], source_type, browser or None), daemon=True)
    else:
        thread = threading.Thread(target=run_batch_download, args=(job_id, urls, source_type, browser or None), daemon=True)
    thread.start()

    return jsonify({'job_id': job_id})


@app.route('/api/status/<job_id>')
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify({
        'status': job['status'],
        'files': job['files'],
        'error': job['error'],
        'total': job.get('total', 1),
        'completed_count': job.get('completed_count', 0),
        'status_detail': job.get('status_detail', ''),
        'errors': job.get('errors', [])
    })


@app.route('/api/download/<job_id>/<filename>')
def download_file(job_id, filename):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    if filename not in job.get('files', []):
        return jsonify({'error': 'File not found for this job'}), 404
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
