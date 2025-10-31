"""Command-line tool to turn a text file into a natural-sounding audiobook using Microsoft Edge neural voices."""
from __future__ import annotations

import argparse
import asyncio
import pathlib
import re
from typing import Iterable, Iterator

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=pathlib.Path, help="Path to the source text file")
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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


if __name__ == "__main__":
    main()
