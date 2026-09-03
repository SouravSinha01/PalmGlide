import unittest

from palmglide import GestureState, ScrollOutput, clamp, emit_scroll, scroll_velocity


class RecordingOutput(ScrollOutput):
    def __init__(self):
        self.steps = []

    def scroll(self, steps: int) -> None:
        self.steps.append(steps)


class PalmGlideTests(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual(clamp(-2, 0, 1), 0)
        self.assertEqual(clamp(2, 0, 1), 1)
        self.assertEqual(clamp(0.4, 0, 1), 0.4)

    def test_deadzone_does_not_scroll(self):
        self.assertEqual(scroll_velocity(0.5, 0.5, 0.14, 8, False), 0)

    def test_scroll_direction_can_be_inverted(self):
        normal = scroll_velocity(0.1, 0.5, 0.14, 8, False)
        inverted = scroll_velocity(0.1, 0.5, 0.14, 8, True)
        self.assertLess(normal, 0)
        self.assertEqual(inverted, -normal)

    def test_fractional_scroll_is_accumulated(self):
        output = RecordingOutput()
        state = GestureState()
        emit_scroll(output, state, velocity=3, dt=0.2)
        self.assertEqual(output.steps, [])
        emit_scroll(output, state, velocity=3, dt=0.2)
        self.assertEqual(output.steps, [1])
        self.assertAlmostEqual(state.wheel_accumulator, 0.2)


if __name__ == "__main__":
    unittest.main()
