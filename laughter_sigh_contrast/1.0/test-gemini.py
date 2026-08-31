import argparse
import asyncio
import os
import re
import subprocess
import tempfile
import wave
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from typing import Optional


MODEL = "gemini-3.1-flash-live-preview"

SYSTEM_PROMPT = """
Response like you are the friend.
""".strip()


def convert_to_pcm(input_path: str) -> bytes:
    """
    Convert MP3/WAV/etc. to:
        PCM signed 16-bit little endian
        mono
        16 kHz

    Returns raw PCM bytes.
    """
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-i", input_path,
        "-ac", "1",
        "-ar", "16000",
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "pipe:1",
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg was not found. On macOS install it with:\n"
            "    brew install ffmpeg"
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"ffmpeg conversion failed:\n{e.stderr.decode(errors='replace')}"
        )

    return result.stdout

def extract_sample_rate(
    mime_type: Optional[str],
    default: int = 24000,
) -> int:
    if not mime_type:
        return default

    match = re.search(r"rate=(\d+)", mime_type)
    if match:
        return int(match.group(1))

    return default


def save_pcm_as_wav(
    pcm_bytes: bytes,
    output_path: str,
    sample_rate: int = 24000,
):
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


async def run_gemini(
    input_path: str,
    transcript_output: str,
    audio_output: str,
):
    # Load .env
    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY was not found.\n\n"
            "Create a .env file containing:\n"
            "GEMINI_API_KEY=your_key_here"
        )

    print(f"Input: {input_path}")
    print("Converting audio to 16 kHz mono PCM...")

    input_pcm = convert_to_pcm(input_path)

    duration = len(input_pcm) / (16000 * 2)

    print(f"Audio duration: {duration:.2f} seconds")
    print(f"Model: {MODEL}")
    print("Thinking level: HIGH")
    print()

    client = genai.Client(api_key=api_key)

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],

        # Get transcript of Gemini's spoken response.
        output_audio_transcription={},

        # HIGH THINKING
        thinking_config=types.ThinkingConfig(
            thinking_level="high",
        ),

        system_instruction=types.Content(
            parts=[
                types.Part(text=SYSTEM_PROMPT)
            ]
        ),
    )

    response_text_parts = []
    response_audio = bytearray()

    output_sample_rate = 24000

    print("Connecting to Gemini Live API...")

    async with client.aio.live.connect(
        model=MODEL,
        config=config,
    ) as session:

        print("Sending audio...")

        await session.send_realtime_input(
            audio=types.Blob(
                data=input_pcm,
                mime_type="audio/pcm;rate=16000",
            )
        )

        # Tell Gemini there will be no more audio for this turn.
        await session.send_realtime_input(
            audio_stream_end=True
        )

        print("Waiting for response...\n")

        async for message in session.receive():

            server_content = message.server_content

            if server_content is None:
                continue

            # -----------------------------------------
            # Collect output transcription
            # -----------------------------------------

            if server_content.output_transcription:
                text = server_content.output_transcription.text

                if text:
                    print(text, end="", flush=True)
                    response_text_parts.append(text)

            # -----------------------------------------
            # Collect generated audio
            # -----------------------------------------

            if server_content.model_turn:

                for part in server_content.model_turn.parts or []:

                    inline_data = part.inline_data

                    if inline_data and inline_data.data:

                        mime = inline_data.mime_type or ""

                        if mime.startswith("audio/"):

                            response_audio.extend(inline_data.data)

                            output_sample_rate = extract_sample_rate(
                                mime,
                                default=output_sample_rate,
                            )

            # -----------------------------------------
            # End when Gemini finishes the turn
            # -----------------------------------------

            if server_content.turn_complete:
                break

    print("\n")

    # -----------------------------------------
    # Save transcript
    # -----------------------------------------

    response_text = "".join(response_text_parts).strip()

    Path(transcript_output).write_text(
        response_text,
        encoding="utf-8"
    )

    print(f"Transcript saved to: {transcript_output}")

    # -----------------------------------------
    # Save audio
    # -----------------------------------------

    if response_audio:

        save_pcm_as_wav(
            bytes(response_audio),
            audio_output,
            sample_rate=output_sample_rate,
        )

        print(
            f"Response audio saved to: {audio_output} "
            f"({output_sample_rate} Hz)"
        )

    else:
        print("No output audio was received.")

    print("\nModel response:")
    print("-" * 60)
    print(response_text)
    print("-" * 60)


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Test Gemini 3.1 Flash Live with HIGH thinking "
            "on a local audio file."
        )
    )

    parser.add_argument(
        "audio",
        help="Input MP3/WAV/audio file",
    )

    parser.add_argument(
        "--transcript",
        default="gemini_response.txt",
        help="Where to save Gemini's text response",
    )

    parser.add_argument(
        "--output-audio",
        default="gemini_response.wav",
        help="Where to save Gemini's spoken response",
    )

    args = parser.parse_args()

    if not Path(args.audio).exists():
        raise FileNotFoundError(
            f"Audio file not found: {args.audio}"
        )

    asyncio.run(
        run_gemini(
            input_path=args.audio,
            transcript_output=args.transcript,
            audio_output=args.output_audio,
        )
    )


if __name__ == "__main__":
    main()