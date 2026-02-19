# MP3 Converter

A web application that converts YouTube and SoundCloud links to downloadable MP3 files.

## Features
- Convert YouTube videos to MP3
- Convert SoundCloud tracks to MP3
- Clean, modern web interface
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

Then open http://localhost:5000 in your browser.

## Usage
1. Choose YouTube or SoundCloud
2. Paste the link to the video or track
3. Click Convert and wait
4. Download your MP3 file
