let currentSource = 'youtube';
let polling = null;

const placeholders = {
    youtube: 'Paste your YouTube link here...',
    soundcloud: 'Paste your SoundCloud link here...'
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

document.getElementById('url-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') startConvert();
});

function resetUI() {
    document.getElementById('status-area').classList.add('hidden');
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('error-section').classList.add('hidden');
    document.getElementById('download-section').classList.add('hidden');
    if (polling) {
        clearInterval(polling);
        polling = null;
    }
}

function showProgress(msg) {
    document.getElementById('status-area').classList.remove('hidden');
    document.getElementById('progress-section').classList.remove('hidden');
    document.getElementById('error-section').classList.add('hidden');
    document.getElementById('download-section').classList.add('hidden');
    document.getElementById('status-text').textContent = msg;
}

function showError(msg) {
    document.getElementById('status-area').classList.remove('hidden');
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('error-section').classList.remove('hidden');
    document.getElementById('download-section').classList.add('hidden');
    document.getElementById('error-text').textContent = msg;
}

function showDownloads(jobId, files) {
    document.getElementById('status-area').classList.remove('hidden');
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('error-section').classList.add('hidden');
    document.getElementById('download-section').classList.remove('hidden');

    const container = document.getElementById('download-links');
    container.innerHTML = '';

    files.forEach(file => {
        const displayName = file.replace(/^[a-f0-9]{8}_/, '').replace(/\.mp3$/, '');
        const link = document.createElement('a');
        link.href = '/api/download/' + jobId + '/' + encodeURIComponent(file);
        link.className = 'download-link';
        link.textContent = displayName + '.mp3';
        link.download = '';
        container.appendChild(link);
    });
}

async function startConvert() {
    const url = document.getElementById('url-input').value.trim();
    if (!url) {
        showError('Please paste a link first.');
        return;
    }

    resetUI();
    showProgress('Starting conversion...');

    const btn = document.getElementById('convert-btn');
    btn.disabled = true;

    try {
        const resp = await fetch('/api/convert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, source: currentSource })
        });

        const data = await resp.json();

        if (!resp.ok) {
            showError(data.error || 'Something went wrong.');
            btn.disabled = false;
            return;
        }

        showProgress('Downloading and converting to MP3...');
        pollStatus(data.job_id);

    } catch (err) {
        showError('Could not connect to the server.');
        btn.disabled = false;
    }
}

function pollStatus(jobId) {
    polling = setInterval(async () => {
        try {
            const resp = await fetch('/api/status/' + jobId);
            const data = await resp.json();

            if (data.status === 'complete') {
                clearInterval(polling);
                polling = null;
                showDownloads(jobId, data.files);
                document.getElementById('convert-btn').disabled = false;
            } else if (data.status === 'error') {
                clearInterval(polling);
                polling = null;
                showError(data.error || 'An error occurred during conversion.');
                document.getElementById('convert-btn').disabled = false;
            } else {
                showProgress('Downloading and converting to MP3...');
            }
        } catch (err) {
            clearInterval(polling);
            polling = null;
            showError('Lost connection to the server.');
            document.getElementById('convert-btn').disabled = false;
        }
    }, 2000);
}
