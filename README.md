# Text-to-Audiobook Tool

This repository contains a small command-line utility that converts a text file into an audiobook with a neural, human-like voice.

The tool is designed to run on macOS (or any platform with Python 3.9+). It uses Microsoft's neural voices via the [`edge-tts`](https://github.com/rany2/edge-tts) library, which provides extremely natural-sounding narration.

## Prerequisites

1. Install Python 3.9 or later.
2. Install the required dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

   > Tip: `edge-tts` streams MP3 audio, so no additional audio tools are necessary.

## Usage

1. Save the text you want narrated to a UTF-8 encoded `.txt` file.
2. Run the CLI:

   ```bash
   python src/audiobook_tool.py path/to/book.txt -o book.mp3 \
       --voice en-US-JennyNeural --rate +5% --pitch +1Hz
   ```

   Key options:

   * `-o / --output`: Where to write the resulting audiobook (MP3 format by default).
   * `--voice`: Choose any Microsoft neural voice (run `edge-tts --list-voices` after installing the package to see options).
   * `--rate`: Fine-tune speaking speed. Use values like `+10%` or `-10%`.
   * `--pitch`: Adjust narration pitch, e.g., `+2Hz` or `-2Hz`.
   * `--max-chars`: Maximum characters sent to the speech service in a single request. Increase this if you see errors for very long sentences.

3. The script prints progress as it generates each chunk of narration and writes the MP3 file.

## Notes

* The utility automatically chunks long passages to stay within the Edge TTS limits while keeping sentences intact for natural pacing.
* If you need the audio in another format, convert the resulting `MP3` with `ffmpeg` (e.g., `ffmpeg -i book.mp3 book.m4a`).
* The tool requires internet access because the neural narration is streamed from Microsoft's Edge TTS service.
