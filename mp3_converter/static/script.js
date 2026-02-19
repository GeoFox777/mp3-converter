let currentSource = 'youtube';
let polling = null;

const placeholders = {
    youtube: 'Paste your YouTube link(s) here — one per line...',
    soundcloud: 'Paste your SoundCloud link(s) here — one per line...'
};

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        currentSource = tab.dataset.source;
        document.getElementById('url-input').placeholder = placeholders[currentSource];
        resetUI();
    });
});

function resetUI() {
    document.getElementById('status-area').classList.add('hidden');
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('error-section').classList.add('hidden');
    document.getElementById('download-section').classList.add('hidden');
    document.getElementById('progress-bar-container').classList.add('hidden');
    document.getElementById('progress-detail').textContent = '';
    document.getElementById('download-warnings').classList.add('hidden');
    if (polling) {
        clearInterval(polling);
        polling = null;
    }
}

function showProgress(msg, total, completed) {
    document.getElementById('status-area').classList.remove('hidden');
    document.getElementById('progress-section').classList.remove('hidden');
    document.getElementById('error-section').classList.add('hidden');
    document.getElementById('download-section').classList.add('hidden');
    document.getElementById('status-text').textContent = msg;

    if (total > 1) {
        const bar = document.getElementById('progress-bar-container');
        bar.classList.remove('hidden');
        const pct = Math.round((completed / total) * 100);
        document.getElementById('progress-bar').style.width = pct + '%';
        document.getElementById('progress-detail').textContent = completed + ' of ' + total + ' completed';
    }
}

function showError(msg) {
    document.getElementById('status-area').classList.remove('hidden');
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('error-section').classList.remove('hidden');
    document.getElementById('download-section').classList.add('hidden');
    document.getElementById('error-text').textContent = msg;
}

function showDownloads(jobId, files, errors) {
    document.getElementById('status-area').classList.remove('hidden');
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('error-section').classList.add('hidden');
    document.getElementById('download-section').classList.remove('hidden');

    const summary = document.getElementById('download-summary');
    if (files.length === 1) {
        summary.textContent = 'Your MP3 is ready!';
    } else {
        summary.textContent = files.length + ' MP3 files are ready!';
    }

    const warnings = document.getElementById('download-warnings');
    if (errors && errors.length > 0) {
        warnings.classList.remove('hidden');
        warnings.textContent = 'Some links had issues: ' + errors.join(' | ');
    } else {
        warnings.classList.add('hidden');
    }

    const container = document.getElementById('download-links');
    container.innerHTML = '';

    files.forEach(file => {
        const displayName = file.replace(/^[a-f0-9]{8}(_\d+)?_/, '').replace(/\.mp3$/, '');
        const link = document.createElement('a');
        link.href = '/api/download/' + jobId + '/' + encodeURIComponent(file);
        link.className = 'download-link';
        link.textContent = displayName + '.mp3';
        link.download = '';
        container.appendChild(link);
    });
}

async function startConvert() {
    const raw = document.getElementById('url-input').value.trim();
    if (!raw) {
        showError('Please paste at least one link.');
        return;
    }

    const urls = raw.split('\n').map(u => u.trim()).filter(u => u.length > 0);
    if (urls.length === 0) {
        showError('Please paste at least one link.');
        return;
    }

    if (urls.length > 20) {
        showError('Maximum 20 links at a time. You have ' + urls.length + '.');
        return;
    }

    resetUI();
    const label = urls.length === 1 ? 'Starting conversion...' : 'Starting conversion of ' + urls.length + ' links...';
    showProgress(label, urls.length, 0);

    const btn = document.getElementById('convert-btn');
    btn.disabled = true;

    try {
        const resp = await fetch('/api/convert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls, source: currentSource })
        });

        const data = await resp.json();

        if (!resp.ok) {
            showError(data.error || 'Something went wrong.');
            btn.disabled = false;
            return;
        }

        showProgress('Downloading and converting to MP3...', urls.length, 0);
        pollStatus(data.job_id, urls.length);

    } catch (err) {
        showError('Could not connect to the server.');
        btn.disabled = false;
    }
}

function pollStatus(jobId, total) {
    polling = setInterval(async () => {
        try {
            const resp = await fetch('/api/status/' + jobId);
            const data = await resp.json();

            if (data.status === 'complete') {
                clearInterval(polling);
                polling = null;
                showDownloads(jobId, data.files, data.errors);
                document.getElementById('convert-btn').disabled = false;
            } else if (data.status === 'error') {
                clearInterval(polling);
                polling = null;
                showError(data.error || 'An error occurred during conversion.');
                document.getElementById('convert-btn').disabled = false;
            } else {
                const msg = data.status_detail || 'Downloading and converting to MP3...';
                showProgress(msg, data.total || total, data.completed_count || 0);
            }
        } catch (err) {
            clearInterval(polling);
            polling = null;
            showError('Lost connection to the server.');
            document.getElementById('convert-btn').disabled = false;
        }
    }, 2000);
}
