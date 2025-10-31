"""Command-line and GUI tool to turn a text file into a natural-sounding audiobook."""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import re
import threading
from typing import Iterable, Iterator, Sequence

import edge_tts


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, *, max_chars: int = 3000) -> list[str]:
    """Split ``text`` into manageable chunks without cutting sentences in half."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")

    stripped = text.strip()
    if not stripped:
        return []

    paragraphs = [p.strip() for p in stripped.splitlines() if p.strip()]

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        sentences = (
            [paragraph]
            if len(paragraph) <= max_chars
            else list(_split_sentences(paragraph, max_chars=max_chars))
        )

        new_paragraph = True
        for sentence in sentences:
            if len(sentence) > max_chars:
                raise ValueError(
                    "Encountered a sentence longer than max_chars. Increase the limit or shorten the source text."
                )

            prefix = ""
            if current:
                prefix = "\n\n" if new_paragraph else " "

            addition = f"{prefix}{sentence}" if prefix else sentence

            if len(current) + len(addition) <= max_chars:
                current += addition
            else:
                if current:
                    chunks.append(current)
                current = sentence

            new_paragraph = False

    if current:
        chunks.append(current)

    return chunks


def _split_sentences(paragraph: str, *, max_chars: int) -> Iterator[str]:
    start = 0
    for match in _SENTENCE_END.finditer(paragraph):
        sentence = paragraph[start : match.start()].strip()
        if sentence:
            if len(sentence) > max_chars:
                raise ValueError(
                    "Found a sentence longer than max_chars. Increase max_chars or edit the sentence."
                )
            yield sentence
        start = match.end()
    tail = paragraph[start:].strip()
    if tail:
        if len(tail) > max_chars:
            raise ValueError(
                "Found a sentence longer than max_chars. Increase max_chars or edit the sentence."
            )
        yield tail


async def synthesize_chunks(
    text_chunks: Iterable[str],
    *,
    voice: str,
    output_path: pathlib.Path,
    rate: str,
    pitch: str,
) -> None:
    """Generate speech for ``text_chunks`` and append the audio to ``output_path``."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    with output_path.open("ab") as output_file:
        for index, chunk in enumerate(text_chunks, start=1):
            communicate = edge_tts.Communicate(chunk, voice=voice, rate=rate, pitch=pitch)
            async for data in communicate.stream():
                if data["type"] == "audio":
                    output_file.write(data["data"])
            output_file.flush()
            print(f"Finished chunk {index}")


async def create_audiobook(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    *,
    voice: str,
    rate: str,
    pitch: str,
    max_chars: int,
) -> None:
    text = input_path.read_text(encoding="utf-8")
    chunks = chunk_text(text, max_chars=max_chars)
    if not chunks:
        raise SystemExit("Input file does not contain any readable text")
    print(f"Generating audiobook with {len(chunks)} chunk(s)...")
    await synthesize_chunks(
        chunks,
        voice=voice,
        output_path=output_path,
        rate=rate,
        pitch=pitch,
    )
    print(f"Saved audiobook to {output_path}")


async def _list_available_voices() -> list[str]:
    """Return the available neural voice short names, sorted alphabetically."""

    voices_manager = await edge_tts.VoicesManager.create()
    voices = {voice["ShortName"] for voice in voices_manager.voices}
    return sorted(voices)


def _default_voice(voices: Sequence[str]) -> str:
    for preferred in ("en-US-JennyNeural", "en-US-GuyNeural"):
        if preferred in voices:
            return preferred
    return voices[0] if voices else "en-US-JennyNeural"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        type=pathlib.Path,
        nargs="?",
        help="Path to the source text file. Leave empty or use --gui to launch the GUI.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("audiobook.mp3"),
        help="Where to save the generated audiobook (default: audiobook.mp3)",
    )
    parser.add_argument(
        "-v", "--voice", default="en-US-JennyNeural", help="Microsoft Edge TTS voice to use"
    )
    parser.add_argument(
        "--rate",
        default="+0%",
        help="Speech rate adjustment, e.g. +10% for faster, -10% for slower (default: +0%)",
    )
    parser.add_argument(
        "--pitch",
        default="+0Hz",
        help="Speech pitch adjustment, e.g. +2Hz or -2Hz (default: +0Hz)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=3000,
        help="Maximum characters per request to the speech service",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical interface for generating audiobooks.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.gui or args.input is None:
        launch_gui()
        return

    if not args.input.exists():
        raise SystemExit(f"Input file '{args.input}' does not exist")

    asyncio.run(
        create_audiobook(
            args.input,
            args.output,
            voice=args.voice,
            rate=args.rate,
            pitch=args.pitch,
            max_chars=args.max_chars,
        )
    )


def launch_gui() -> None:
    """Launch a Tkinter GUI for generating audiobooks."""

    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:  # pragma: no cover - tkinter may be missing in some envs
        raise SystemExit("Tkinter is required for the GUI but is not available on this system") from exc

    root = tk.Tk()
    root.title("Edge TTS Audiobook Generator")

    status_var = tk.StringVar(value="Select a text file to begin.")
    input_var = tk.StringVar()
    output_var = tk.StringVar()
    voice_var = tk.StringVar()
    rate_var = tk.StringVar(value="+0%")
    pitch_var = tk.StringVar(value="+0Hz")
    max_chars_var = tk.StringVar(value="3000")

    def load_voices() -> list[str]:
        try:
            return asyncio.run(_list_available_voices())
        except Exception as error:  # pragma: no cover - depends on remote service
            messagebox.showwarning(
                "Voice Download Failed",
                "Unable to download the list of voices. Using the default voice instead.\n"
                f"Details: {error}",
            )
            return ["en-US-JennyNeural"]

    voices = load_voices()
    if not voices:
        voices = ["en-US-JennyNeural"]
    voice_var.set(_default_voice(voices))

    rate_options = [
        "-25%",
        "-20%",
        "-15%",
        "-10%",
        "-5%",
        "+0%",
        "+5%",
        "+10%",
        "+15%",
        "+20%",
        "+25%",
    ]
    pitch_options = [
        "-6Hz",
        "-4Hz",
        "-2Hz",
        "+0Hz",
        "+2Hz",
        "+4Hz",
        "+6Hz",
    ]
    max_char_options = [1500, 2000, 2500, 3000, 3500]

    main_frame = ttk.Frame(root, padding=16)
    main_frame.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    def choose_file() -> None:
        path = filedialog.askopenfilename(
            title="Select text file", filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            input_var.set(path)
            if not output_var.get():
                output_var.set(f"{pathlib.Path(path).stem}.mp3")
            status_var.set("Ready to generate the audiobook.")

    def validate_inputs() -> tuple[pathlib.Path, pathlib.Path]:
        input_path = pathlib.Path(input_var.get())
        if not input_path.exists():
            raise ValueError("Please choose a valid input text file.")

        raw_output = output_var.get().strip() or f"{input_path.stem}.mp3"
        output_path = pathlib.Path.cwd() / raw_output

        if output_path.is_dir():
            raise ValueError("Output file name cannot be an existing directory.")

        return input_path, output_path

    def set_controls_state(state: str) -> None:
        for widget in (
            browse_button,
            generate_button,
            voice_combo,
            rate_combo,
            pitch_combo,
            max_char_combo,
            output_entry,
        ):
            widget.configure(state=state)

    def generate() -> None:
        try:
            input_path, output_path = validate_inputs()
        except ValueError as error:
            messagebox.showerror("Invalid Input", str(error))
            return

        status_var.set("Generating audiobook. This may take a few minutes...")
        set_controls_state("disabled")

        def worker() -> None:
            try:
                asyncio.run(
                    create_audiobook(
                        input_path,
                        output_path,
                        voice=voice_var.get(),
                        rate=rate_var.get(),
                        pitch=pitch_var.get(),
                        max_chars=int(max_chars_var.get()),
                    )
                )
            except Exception as error:  # pragma: no cover - GUI feedback
                root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Generation Failed",
                        "Unable to create the audiobook.\n"
                        f"Details: {error}",
                    ),
                )
                root.after(0, lambda: status_var.set("Generation failed. Please try again."))
            else:
                root.after(
                    0,
                    lambda: status_var.set(
                        f"Audiobook saved to {output_path.name} in {pathlib.Path.cwd()}"
                    ),
                )
                root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Audiobook Created",
                        f"Saved audiobook to {output_path}",
                    ),
                )
            finally:
                root.after(0, lambda: set_controls_state("normal"))

        threading.Thread(target=worker, daemon=True).start()

    ttk.Label(main_frame, text="Input text file:").grid(row=0, column=0, sticky="w")
    input_frame = ttk.Frame(main_frame)
    input_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    input_entry = ttk.Entry(input_frame, textvariable=input_var, width=50)
    input_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
    browse_button = ttk.Button(input_frame, text="Browse…", command=choose_file)
    browse_button.grid(row=0, column=1)
    input_frame.columnconfigure(0, weight=1)

    ttk.Label(main_frame, text="Voice:").grid(row=2, column=0, sticky="w")
    voice_combo = ttk.Combobox(main_frame, textvariable=voice_var, values=voices, state="readonly")
    voice_combo.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))

    ttk.Label(main_frame, text="Rate:").grid(row=4, column=0, sticky="w")
    rate_combo = ttk.Combobox(main_frame, textvariable=rate_var, values=rate_options, state="readonly")
    rate_combo.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 8))

    ttk.Label(main_frame, text="Pitch:").grid(row=6, column=0, sticky="w")
    pitch_combo = ttk.Combobox(main_frame, textvariable=pitch_var, values=pitch_options, state="readonly")
    pitch_combo.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 8))

    ttk.Label(main_frame, text="Max characters per chunk:").grid(row=8, column=0, sticky="w")
    max_char_combo = ttk.Combobox(
        main_frame,
        textvariable=max_chars_var,
        values=[str(option) for option in max_char_options],
        state="readonly",
    )
    max_char_combo.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(0, 8))

    ttk.Label(main_frame, text="Output filename (saved in current folder):").grid(
        row=10, column=0, sticky="w"
    )
    output_entry = ttk.Entry(main_frame, textvariable=output_var)
    output_entry.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(0, 8))

    generate_button = ttk.Button(main_frame, text="Generate Audiobook", command=generate)
    generate_button.grid(row=12, column=0, columnspan=2, pady=(4, 8))

    status_label = ttk.Label(main_frame, textvariable=status_var, wraplength=400)
    status_label.grid(row=13, column=0, columnspan=2, sticky="w")

    main_frame.columnconfigure(0, weight=1)
    main_frame.columnconfigure(1, weight=1)

    root.mainloop()


if __name__ == "__main__":
    main()
