"""Synthetic extraction/guard tests; no library, service, or network access."""

import contextlib
import importlib.util
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/extract-embedded-subtitles.py"
SPEC = importlib.util.spec_from_file_location("extract_embedded", SCRIPT)
EXTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXTRACT)
SRT = "1\n00:00:01,250 --> 00:00:02,750\nSynthetic line one.\n\n2\n00:00:04,000 --> 00:00:05,500\nSynthetic line two.\n"


def stream(index=2, language="eng", codec="subrip", **flags):
    return {"index": index, "codec_name": codec, "tags": {"language": language},
            "disposition": flags}


class EmbeddedSubtitleTests(unittest.TestCase):
    def test_episode_markers_support_underscores_and_combined_episodes(self):
        for name in ("Series_S01E01_Pilot", "Series.S01E01E02.Combined", "Series - s1e2 - Title"):
            with self.subTest(name=name):
                match = EXTRACT.EPISODE.search(name)
                self.assertIsNotNone(match)
                self.assertEqual(int(match["season"]), 1)
        for name in ("SeriesS01E01", "Series.S01E1234"):
            with self.subTest(name=name):
                self.assertIsNone(EXTRACT.EPISODE.search(name))

    def test_selects_full_english_and_never_guesses_unknown_language(self):
        full = stream()
        self.assertEqual(EXTRACT.choose_stream([
            stream(3, "spa"), stream(4, forced=1), full,
        ]), full)
        for tracks in ([stream(language="und")], [stream(forced=1)], [],
                       [dict(stream(), tags={"language": "eng", "title": "Commentary"})]):
            with self.subTest(tracks=tracks), self.assertRaises(ValueError):
                EXTRACT.choose_stream(tracks)

    def test_refuses_bitmap_and_ambiguity_prefers_non_hearing_impaired(self):
        for tracks in ([stream(codec="hdmv_pgs_subtitle")], [stream(2), stream(3)]):
            with self.subTest(tracks=tracks), self.assertRaises(ValueError):
                EXTRACT.choose_stream(tracks)
        regular = stream(3)
        self.assertEqual(EXTRACT.choose_stream([stream(2, hearing_impaired=1), regular]), regular)
        self.assertEqual(EXTRACT.choose_stream([stream(2), stream(3, default=1)])["index"], 3)

    def test_season_filter_full_basename_and_name_collision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source"
            source.mkdir()
            for name in ("Series - S01E01 - Pilot.mkv", "Series - S02E01 - Return.mkv"):
                (source / name).write_bytes(b"fixture")
            (source / "Series - S01E01.es.srt").write_text(SRT)
            videos = EXTRACT.discover(source, {1})
            self.assertEqual(len(videos), 1)
            target = EXTRACT.targets(videos, root / "output")[0][1]
            self.assertEqual(target.relative_to(root / "output").as_posix(),
                             "Season 01/Series - S01E01 - Pilot.en.srt")
            with self.assertRaises(ValueError):
                EXTRACT.targets(videos + videos, root / "output")
            with self.assertRaises(ValueError):
                EXTRACT.discover(source, {3})

    def test_symlinks_are_refused_and_output_cannot_overlap_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            video = root / "Series - S01E01.mkv"
            video.write_bytes(b"fixture")
            source = root / "source"
            source.mkdir()
            (source / video.name).symlink_to(video)
            with self.assertRaises(ValueError):
                EXTRACT.discover(source, set())
            output = root / "output"
            output.mkdir()
            (output / "Season 01").symlink_to(source)
            with self.assertRaises(ValueError):
                EXTRACT.targets([(video, 1)], output)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                EXTRACT.main(["--source", str(source), "--output", str(source / "subtitles")])

    def test_validates_srt_and_rejects_empty_corrupt_or_negative_duration(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample.srt"
            path.write_text(SRT, encoding="utf-8")
            metadata = EXTRACT.inspect_srt(path)
            self.assertEqual(metadata["cues"], 2)
            self.assertEqual(metadata["first_start_ms"], 1250)
            self.assertEqual(metadata["last_end_ms"], 5500)
            for value in ("", "1\ninvalid\ntext", SRT.replace("00:00:02,750", "00:00:00,750")):
                path.write_text(value)
                with self.subTest(value=value), self.assertRaises(ValueError):
                    EXTRACT.inspect_srt(path)

    def test_preview_writes_nothing_and_apply_resumes_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source"
            source.mkdir()
            video = source / "Series - S01E01.mkv"
            video.write_bytes(b"media fixture")
            output = root / "output"
            args = ["--source", str(source), "--output", str(output)]
            with patch.object(EXTRACT.shutil, "which", side_effect=lambda name: name), \
                    patch.object(EXTRACT, "probe", return_value=[stream()]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(EXTRACT.main(args), 0)
            self.assertFalse(output.exists())
            target = output / "Season 01" / (video.stem + ".en.srt")
            target.parent.mkdir(parents=True)
            target.write_text(SRT)
            before = target.read_bytes()
            with patch.object(EXTRACT.shutil, "which", side_effect=lambda name: name), \
                    patch.object(EXTRACT, "probe", side_effect=AssertionError("Must skip existing")), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(EXTRACT.main(args + ["--apply"]), 0)
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(video.read_bytes(), b"media fixture")

    def test_extraction_failure_cleans_staging_and_keeps_existing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source, target = root / "source.mkv", root / "output.srt"
            source.write_bytes(b"fixture")
            with patch.object(EXTRACT, "run", side_effect=ValueError("mock failure")), \
                    self.assertRaises(ValueError):
                EXTRACT.extract(source, target, stream(), "ffmpeg")
            self.assertFalse(target.exists())
            self.assertFalse(list(root.glob(".extract-*")))
            target.write_text(SRT)
            with patch.object(EXTRACT, "run") as run, self.assertRaises(FileExistsError):
                EXTRACT.extract(source, target, stream(), "ffmpeg")
            run.assert_not_called()

    def test_interrupt_cleans_partial_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source, target = root / "source.mkv", root / "output.srt"
            source.write_bytes(b"fixture")
            with patch.object(EXTRACT, "run", side_effect=KeyboardInterrupt), \
                    self.assertRaises(KeyboardInterrupt):
                EXTRACT.extract(source, target, stream(), "ffmpeg")
            self.assertFalse(target.exists())
            self.assertFalse(list(root.glob(".extract-*")))

    def test_source_mutation_and_atomic_collision_do_not_publish_or_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source, target = root / "source.mkv", root / "output.srt"
            source.write_bytes(b"fixture")

            def mutate(command, **kwargs):
                Path(command[-1]).write_text(SRT)
                source.write_bytes(b"changed fixture")

            with patch.object(EXTRACT, "run", side_effect=mutate), self.assertRaises(ValueError):
                EXTRACT.extract(source, target, stream(), "ffmpeg")
            self.assertFalse(target.exists())

            def collide(command, **kwargs):
                Path(command[-1]).write_text(SRT)
                target.write_text("Existing content")

            with patch.object(EXTRACT, "run", side_effect=collide), self.assertRaises(FileExistsError):
                EXTRACT.extract(source, target, stream(), "ffmpeg")
            self.assertEqual(target.read_text(), "Existing content")
            self.assertFalse(list(root.glob(".extract-*")))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "Optional FFmpeg integration")
    def test_real_synthetic_mkv_preserves_cues_and_timestamps(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            subtitles, media, target = root / "input.srt", root / "synthetic.mkv", root / "output.srt"
            subtitles.write_text(SRT)
            subprocess.run([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=black:s=16x16:r=1:d=6", "-i", str(subtitles),
                "-map", "0:v:0", "-map", "1:s:0", "-c:v", "ffv1", "-c:s", "copy",
                "-metadata:s:s:0", "language=eng", str(media),
            ], check=True, capture_output=True)
            before = media.read_bytes()
            selected = EXTRACT.choose_stream(EXTRACT.probe(media, "ffprobe"))
            metadata = EXTRACT.extract(media, target, selected, "ffmpeg")
            self.assertEqual(metadata["cues"], 2)
            self.assertEqual(metadata["first_start_ms"], 1250)
            self.assertEqual(metadata["last_end_ms"], 5500)
            self.assertEqual(media.read_bytes(), before)
            self.assertEqual(target.read_text().strip(), SRT.strip())


if __name__ == "__main__":
    unittest.main()
