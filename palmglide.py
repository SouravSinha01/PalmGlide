#!/usr/bin/env python3
import argparse
import ctypes
import math
import os
import platform
import signal
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "palmglide-matplotlib"))

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
FINGER_TIPS = (8, 12, 16, 20)
FINGER_PIPS = (6, 10, 14, 18)
PALM_POINTS = (0, 5, 9, 13, 17)


def resource_path(relative_path: str) -> Path:
    """Resolve assets both from source and from a PyInstaller bundle."""
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path / relative_path


DEFAULT_MODEL_PATH = resource_path("models/hand_landmarker.task")


@dataclass
class GestureState:
    active: bool = False
    open_frames: int = 0
    fist_frames: int = 0
    wheel_accumulator: float = 0.0


class ScrollOutput:
    def scroll(self, steps: int) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()


class LinuxScrollOutput(ScrollOutput):
    def __init__(self) -> None:
        from evdev import UInput, ecodes

        self._ecodes = ecodes
        capabilities = {ecodes.EV_REL: [ecodes.REL_WHEEL]}
        self._device = UInput(capabilities, name="palmglide-wheel")

    def scroll(self, steps: int) -> None:
        self._device.write(self._ecodes.EV_REL, self._ecodes.REL_WHEEL, steps)
        self._device.syn()

    def close(self) -> None:
        self._device.close()


class _WindowsMouseInput(ctypes.Structure):
    _fields_ = (
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    )


class _WindowsInputUnion(ctypes.Union):
    _fields_ = (("mi", _WindowsMouseInput),)


class _WindowsInput(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = (("type", ctypes.c_ulong), ("value", _WindowsInputUnion))


class WindowsScrollOutput(ScrollOutput):
    WHEEL_DELTA = 120
    INPUT_MOUSE = 0
    MOUSEEVENTF_WHEEL = 0x0800

    def __init__(self) -> None:
        self._send_input = ctypes.windll.user32.SendInput
        self._send_input.argtypes = (ctypes.c_uint, ctypes.POINTER(_WindowsInput), ctypes.c_int)
        self._send_input.restype = ctypes.c_uint

    def scroll(self, steps: int) -> None:
        wheel_data = ctypes.c_ulong(steps * self.WHEEL_DELTA).value
        event = _WindowsInput(
            type=self.INPUT_MOUSE,
            mi=_WindowsMouseInput(mouseData=wheel_data, dwFlags=self.MOUSEEVENTF_WHEEL),
        )
        if self._send_input(1, ctypes.byref(event), ctypes.sizeof(event)) != 1:
            raise ctypes.WinError()


def create_scroll_output() -> ScrollOutput:
    system = platform.system()
    if system == "Windows":
        return WindowsScrollOutput()
    if system == "Linux":
        return LinuxScrollOutput()
    raise RuntimeError(f"PalmGlide does not support {system} yet.")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def mean(values: Iterable[float]) -> float:
    values = tuple(values)
    return sum(values) / len(values)


def extended_fingers(hand_landmarks) -> int:
    return sum(
        1
        for tip, pip in zip(FINGER_TIPS, FINGER_PIPS)
        if hand_landmarks[tip].y < hand_landmarks[pip].y
    )


def palm_y(hand_landmarks) -> float:
    return mean(hand_landmarks[index].y for index in PALM_POINTS)


def scroll_velocity(y: float, neutral: float, deadzone: float, max_rate: float, invert: bool) -> float:
    offset = neutral - y
    if abs(offset) <= deadzone:
        return 0.0

    sign = 1 if offset > 0 else -1
    magnitude = (abs(offset) - deadzone) / max(0.001, (0.5 - deadzone))
    magnitude = clamp(magnitude, 0.0, 1.0)

    # High palm means "continue down the page" by default, which is a negative wheel event on Linux.
    direction = -sign
    if invert:
        direction *= -1
    return direction * (1.0 + magnitude * (max_rate - 1.0))


def emit_scroll(output: ScrollOutput, state: GestureState, velocity: float, dt: float) -> None:
    state.wheel_accumulator += velocity * dt
    steps = math.trunc(state.wheel_accumulator)
    if steps == 0:
        return

    state.wheel_accumulator -= steps
    output.scroll(steps)


def draw_overlay(frame, active: bool, gesture: str, y: float | None, args) -> None:
    height, width = frame.shape[:2]
    neutral_px = int(args.neutral * height)
    band = int(args.deadzone * height)
    color = (80, 220, 120) if active else (80, 160, 255)

    cv2.line(frame, (0, neutral_px - band), (width, neutral_px - band), (90, 90, 90), 1)
    cv2.line(frame, (0, neutral_px + band), (width, neutral_px + band), (90, 90, 90), 1)
    cv2.line(frame, (0, neutral_px), (width, neutral_px), (180, 180, 180), 1)
    if y is not None:
        cv2.circle(frame, (width // 2, int(y * height)), 10, color, -1)

    label = f"{'ACTIVE' if active else 'PAUSED'}  {gesture}"
    cv2.putText(frame, label, (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PalmGlide webcam gesture scrolling for Windows and Linux.")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH, help="Path to MediaPipe hand_landmarker.task.")
    parser.add_argument("--preview", dest="preview", action="store_true", help="Show camera preview (default).")
    parser.add_argument("--no-preview", dest="preview", action="store_false", help="Run without a preview window.")
    parser.add_argument("--neutral", type=float, default=0.50, help="Neutral palm Y position, normalized 0..1.")
    parser.add_argument("--deadzone", type=float, default=0.14, help="No-scroll band around neutral, normalized 0..1.")
    parser.add_argument("--max-rate", type=float, default=8.0, help="Maximum wheel detents per second.")
    parser.add_argument("--activation-frames", type=int, default=8, help="Frames of open palm required to activate.")
    parser.add_argument("--pause-frames", type=int, default=6, help="Frames of fist required to pause.")
    parser.add_argument("--invert", action="store_true", help="Invert scroll direction.")
    parser.set_defaults(preview=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    running = True

    def stop(_signum, _frame) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    if not args.model.exists():
        print(f"Missing model file: {args.model}", file=sys.stderr)
        print("Download it with: ./download_model.sh", file=sys.stderr)
        return 2

    try:
        output = create_scroll_output()
    except (OSError, RuntimeError) as error:
        print(f"Cannot initialize scrolling: {error}", file=sys.stderr)
        if platform.system() == "Linux":
            print("Run sudo ./setup_uinput.sh, then log out and back in.", file=sys.stderr)
        return 2

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Cannot open camera {args.camera}. Try --camera 1 or close other camera apps.", file=sys.stderr)
        output.close()
        return 2

    options = vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(args.model)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.65,
        min_hand_presence_confidence=0.65,
        min_tracking_confidence=0.65,
    )
    mp_hands = vision.HandLandmarksConnections
    mp_drawing = vision.drawing_utils
    mp_drawing_styles = vision.drawing_styles
    state = GestureState()
    last_time = time.monotonic()
    start_time = last_time

    with output, vision.HandLandmarker.create_from_options(options) as landmarker:
        while running:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.02)
                continue

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp_ms = int((time.monotonic() - start_time) * 1000)
            result = landmarker.detect_for_video(image, timestamp_ms)

            now = time.monotonic()
            dt = min(0.1, now - last_time)
            last_time = now

            gesture = "no hand"
            y = None
            velocity = 0.0

            if result.hand_landmarks:
                hand = result.hand_landmarks[0]
                fingers = extended_fingers(hand)
                y = palm_y(hand)

                if fingers >= 4:
                    state.open_frames += 1
                    state.fist_frames = 0
                    gesture = "open palm"
                    if state.open_frames >= args.activation_frames:
                        state.active = True
                elif fingers == 0:
                    state.fist_frames += 1
                    state.open_frames = 0
                    gesture = "fist"
                    if state.fist_frames >= args.pause_frames:
                        state.active = False
                        state.wheel_accumulator = 0.0
                else:
                    state.open_frames = 0
                    state.fist_frames = 0
                    gesture = "hold"

                if state.active and fingers >= 4:
                    velocity = scroll_velocity(y, args.neutral, args.deadzone, args.max_rate, args.invert)
                    emit_scroll(output, state, velocity, dt)

                if args.preview:
                    mp_drawing.draw_landmarks(
                        frame,
                        hand,
                        mp_hands.HAND_CONNECTIONS,
                        mp_drawing_styles.get_default_hand_landmarks_style(),
                        mp_drawing_styles.get_default_hand_connections_style(),
                    )
            else:
                state.open_frames = 0
                state.fist_frames = 0
                state.wheel_accumulator = 0.0

            if args.preview:
                draw_overlay(frame, state.active, gesture, y, args)
                cv2.imshow("PalmGlide", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    cap.release()
    if args.preview:
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
