"""
play_video.py — play an MP4 on the floor, with audio from the computer's
speakers.

The video is decoded frame by frame, heavily downscaled to the floor's pixel
resolution (whatever the active layout says — nothing here is hard-coded to
7x28), and pushed to the floor. Audio plays from the speakers, and the original
video is also shown in a small preview window for comparison.

Because the floor is only a few pixels across, the result is intentionally very
pixelated — think "colour impression of the video," not a watchable picture.

Requirements:
    pip install opencv-python numpy
    # audio uses ffplay (comes with ffmpeg). Install ffmpeg and make sure
    # `ffplay` is on your PATH. If it isn't, video still plays, just silent.

Usage:
    # Put a video path in VIDEO_PATH below, then:
    python run_sim.py examples/play_video.py
    python run.py     examples/play_video.py
"""

import shutil
import subprocess
import time

import numpy as np

from sdk import Game

# ---------------------------------------------------------------------------
# Point this at your video file.
VIDEO_PATH = "examples/sample.mp4"
# Show the original video in a preview window alongside the floor output.
SHOW_PREVIEW = True
# ---------------------------------------------------------------------------


class PlayVideo(Game):
    name = "Video Player"

    def setup(self, client):
        try:
            import cv2
        except ImportError as e:
            raise ImportError(
                "play_video needs opencv-python:  pip install opencv-python"
            ) from e
        self._cv2 = cv2

        self._cap = cv2.VideoCapture(VIDEO_PATH)
        if not self._cap.isOpened():
            raise FileNotFoundError(f"could not open video: {VIDEO_PATH}")

        # Source frame rate — we use it to pace playback so the video runs at
        # its natural speed regardless of the game loop's own FPS.
        self._src_fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._frame_period = 1.0 / self._src_fps
        self._next_frame_time = time.perf_counter()

        # Floor size comes from the layout via the client — not hard-coded.
        self._rows = client.rows
        self._cols = client.cols

        # Kick off audio from the speakers using ffplay (part of ffmpeg), fully
        # independent of the video decode. If ffplay isn't available we just
        # play silently.
        self._audio_proc = None
        if shutil.which("ffplay"):
            self._audio_proc = subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", VIDEO_PATH],
            )
        else:
            print("[play_video] ffplay not found on PATH — playing without audio")

        client.clear()

    def update(self, client, dt):
        cv2 = self._cv2
        now = time.perf_counter()

        # Pace decode to the video's own frame rate. If the game loop is faster
        # than the video, we simply hold the current floor image until it's time
        # for the next video frame. If it's slower, we skip ahead.
        if now < self._next_frame_time:
            return
        self._next_frame_time += self._frame_period

        ok, frame_bgr = self._cap.read()
        if not ok:
            # End of video — loop back to the start.
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return

        # Optional preview of the original (before downscaling).
        if SHOW_PREVIEW:
            cv2.imshow("video (original)", frame_bgr)
            cv2.waitKey(1)  # required for the preview window to refresh

        # Downscale straight to floor resolution. INTER_AREA averages source
        # pixels, which is what you want when shrinking this aggressively.
        small = cv2.resize(
            frame_bgr, (self._cols, self._rows), interpolation=cv2.INTER_AREA
        )
        # OpenCV is BGR; the floor wants RGB. Flip the last axis.
        small_rgb = small[:, :, ::-1]

        # Hand the whole floor to the client in one shot.
        client.set_frame(np.ascontiguousarray(small_rgb, dtype=np.uint8))

    def teardown(self, client):
        self._cap.release()
        if self._audio_proc is not None:
            self._audio_proc.terminate()
        if SHOW_PREVIEW:
            self._cv2.destroyAllWindows()
