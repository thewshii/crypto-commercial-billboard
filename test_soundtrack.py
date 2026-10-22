import os
import wave
import unittest
from sounds import (
    SOUNDS_DIR,
    SOUNDTRACK_TRACKS,
    BackgroundMusicPlayer,
    ensure_all_soundtracks
)


class TestSoundtrackSuite(unittest.TestCase):
    def setUp(self):
        ensure_all_soundtracks()

    def test_playlist_structure(self):
        self.assertGreaterEqual(len(SOUNDTRACK_TRACKS), 3)
        expected_ids = ["mothership", "nebula", "hyperdrive"]
        for i, tid in enumerate(expected_ids):
            self.assertEqual(SOUNDTRACK_TRACKS[i]["id"], tid)
            self.assertIn("filename", SOUNDTRACK_TRACKS[i])
            self.assertIn("title", SOUNDTRACK_TRACKS[i])
            self.assertIn("bpm", SOUNDTRACK_TRACKS[i])

    def test_track_files_exist_and_valid(self):
        for track in SOUNDTRACK_TRACKS:
            path = os.path.join(SOUNDS_DIR, track["filename"])
            self.assertTrue(os.path.exists(path), f"File {path} does not exist")
            with wave.open(path, "rb") as wf:
                self.assertEqual(wf.getnchannels(), 1)
                self.assertEqual(wf.getsampwidth(), 2)
                self.assertEqual(wf.getframerate(), 44100)
                # Ensure each file is at least 25 seconds long
                duration = wf.getnframes() / float(wf.getframerate())
                self.assertGreater(duration, 25.0)

    def test_music_player_navigation(self):
        player = BackgroundMusicPlayer(initial_track_idx=0)
        self.assertEqual(player.current_track_idx, 0)
        self.assertIn("Mothership", player.get_current_track_title())

        # Next track -> Track 2
        t2 = player.next_track()
        self.assertEqual(player.current_track_idx, 1)
        self.assertIn("Nebula", t2["title"])

        # Next track -> Track 3
        t3 = player.next_track()
        self.assertEqual(player.current_track_idx, 2)
        self.assertIn("Hyperdrive", t3["title"])

        # Prev track -> Track 2
        tp = player.prev_track()
        self.assertEqual(player.current_track_idx, 1)
        self.assertIn("Nebula", tp["title"])

        # Prev track -> Track 1
        tp0 = player.prev_track()
        self.assertEqual(player.current_track_idx, 0)
        self.assertIn("Mothership", tp0["title"])

        # Set track directly
        player.set_track(1)
        self.assertEqual(player.current_track_idx, 1)
        self.assertIn("Nebula", player.get_current_track_title())


if __name__ == "__main__":
    unittest.main()
