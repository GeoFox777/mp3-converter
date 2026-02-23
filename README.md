# MP3 Converter

A web application that converts YouTube and SoundCloud links to MP3 files.

## Features
- Convert YouTube videos to MP3
- Convert SoundCloud tracks to MP3
- Bulk conversion — paste multiple links at once (up to 20)
- Browser cookie support for age-restricted YouTube videos
- Clean, modern web interface with progress tracking
- Auto-cleanup of downloaded files after 10 minutes

## Requirements
- Python 3.11+
- ffmpeg
- yt-dlp

## Setup
```bash
pip install flask yt-dlp
python mp3_converter/app.py
```

Then open http://localhost:5001 in your browser.

## Usage
1. Choose YouTube or SoundCloud
2. Paste one or more links (one per line)
3. If needed, select your browser for cookie authentication (for age-restricted videos)
4. Click Convert and wait
5. Download your MP3 files
