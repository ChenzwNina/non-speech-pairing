"""Forced alignment via WhisperX (wav2vec2 CTC), used for the timings the cut depends on.

Why this exists alongside whisper_backend.py: the two tools answer different questions.

    faster-whisper  "what did Dia actually say?"      -> validation, needs no reference
    WhisperX        "where exactly is each word?"     -> the cut, aligns a KNOWN transcript

faster-whisper derives word times by DTW over cross-attention, which is fine for subtitles and
too coarse for cutting audio. Measured against silence-gap ground truth on this dataset's 20
baselines, its turn-initial word onsets ran a median 235 ms early, with only 5% inside 50 ms.
WhisperX force-aligning the same known transcript came in at a median of -15 ms, 52% inside
50 ms. That difference is the whole reason a carried word could be cut out of a clip that was
supposed to contain it.

`whisperx.load_audio` shells out to ffmpeg, which this box does not have and does not need:
the pipeline's audio is already mono WAV, so it is read with soundfile and resampled to the
16 kHz wav2vec2 expects.
"""

from __future__ import annotations

from dataclasses import dataclass

from .align import AsrWord

ALIGN_SAMPLE_RATE = 16000


@dataclass(frozen=True)
class WhisperXConfig:
    language: str = "en"
    device: str = "cuda"
    model_name: str | None = None   # None -> torchaudio's default wav2vec2 for the language


class WhisperXAligner:
    """Force-aligns a known transcript to audio. Loaded and unloaded like the other backends,
    so it never shares the T4 with Dia."""

    def __init__(self, config: WhisperXConfig | None = None):
        self.config = config or WhisperXConfig()
        self._model = None
        self._meta = None

    def load(self) -> None:
        if self._model is not None:
            return
        from whisperx.alignment import load_align_model
        self._model, self._meta = load_align_model(
            language_code=self.config.language, device=self.config.device,
            model_name=self.config.model_name)

    @staticmethod
    def _load_16k(path: str):
        import numpy as np
        import soundfile as sf
        import torch
        import torchaudio
        samples, sample_rate = sf.read(path, dtype="float32")
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        if sample_rate != ALIGN_SAMPLE_RATE:
            samples = torchaudio.functional.resample(
                torch.from_numpy(samples), sample_rate, ALIGN_SAMPLE_RATE).numpy()
        return np.ascontiguousarray(samples)

    def align(self, path: str, text: str, duration: float) -> dict:
        """Word timings for `text` as spoken in `path`.

        Returns the same shape whisper_backend.transcribe does, so alignment code downstream
        does not care which backend produced it. Words the aligner could not place (it returns
        them without a start) are dropped rather than guessed at — an unplaced word must fail
        the boundary check, not silently get a made-up timestamp.
        """
        from whisperx.alignment import align as wx_align
        self.load()
        audio = self._load_16k(path)
        segments = [{"text": text.strip(), "start": 0.0, "end": duration}]
        result = wx_align(segments, self._model, self._meta, audio, self.config.device,
                          return_char_alignments=False)
        words: list[AsrWord] = []
        records = []
        for segment in result.get("segments", []):
            for word in segment.get("words", []):
                if word.get("start") is None or word.get("end") is None:
                    continue
                records.append({"word": word.get("word", ""), "start": word["start"],
                                 "end": word["end"], "probability": word.get("score")})
                words.append(AsrWord(text=word.get("word", ""), start=word["start"],
                                      end=word["end"]))
        return {
            "aligner": "whisperx",
            "language": self.config.language,
            "duration": duration,
            "segments": [{"start": 0.0, "end": duration, "text": text.strip(),
                           "words": records}],
            "words": words,
        }

    def unload(self) -> None:
        self._model = None
        self._meta = None
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except ImportError:
            pass
