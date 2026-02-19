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


def run_download(job_id, url, source_type):
    jobs[job_id]['status'] = 'downloading'

    command = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--no-playlist" if source_type == "soundcloud" else "",
        "-o", os.path.join(DOWNLOAD_DIR, f"{job_id}_%(title)s.%(ext)s"),
        url
    ]
    command = [c for c in command if c]

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


@app.route('/api/convert', methods=['POST'])
def convert():
    data = request.get_json()
    url = data.get('url', '').strip()
    source_type = data.get('source', 'youtube')

    if not url:
        return jsonify({'error': 'Please provide a URL'}), 400

    if source_type not in ('youtube', 'soundcloud'):
        return jsonify({'error': 'Invalid source type'}), 400

    if not validate_url(url, source_type):
        if source_type == 'youtube':
            return jsonify({'error': 'Please provide a valid YouTube URL'}), 400
        else:
            return jsonify({'error': 'Please provide a valid SoundCloud URL'}), 400

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {'status': 'queued', 'files': [], 'error': None, 'created': time.time()}

    thread = threading.Thread(target=run_download, args=(job_id, url, source_type), daemon=True)
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
        'error': job['error']
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
