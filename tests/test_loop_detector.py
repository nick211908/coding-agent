from __future__ import annotations

import unittest
from context.loop_detector import LoopDetector


class LoopDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = LoopDetector()

    def test_no_loop_on_different_actions(self) -> None:
        self.detector.record_action("tool_call", tool_name="read_file", args={"path": "a.txt"})
        self.detector.record_action("tool_call", tool_name="write_file", args={"path": "b.txt"})
        self.detector.record_action("response", text="I created the file")
        self.assertIsNone(self.detector.check_for_loop())

    def test_detects_exact_repeat_at_3(self) -> None:
        for _ in range(2):
            self.detector.record_action("tool_call", tool_name="read_file", args={"path": "a.txt"})
            self.assertIsNone(self.detector.check_for_loop())

        self.detector.record_action("tool_call", tool_name="read_file", args={"path": "a.txt"})
        loop_msg = self.detector.check_for_loop()
        self.assertIsNotNone(loop_msg)
        self.assertIn("Same action repeated 3 times", loop_msg)

    def test_detects_repeating_cycle(self) -> None:
        # A -> B -> A -> B
        self.detector.record_action("tool_call", tool_name="read_file", args={"path": "app.js"})
        self.detector.record_action("tool_call", tool_name="apply_patch", args={"file": "app.js"})
        self.detector.record_action("tool_call", tool_name="read_file", args={"path": "app.js"})
        self.detector.record_action("tool_call", tool_name="apply_patch", args={"file": "app.js"})

        loop_msg = self.detector.check_for_loop()
        self.assertIsNotNone(loop_msg)
        self.assertIn("Detected repeating cycle of length 2", loop_msg)

    def test_detects_tool_thrashing(self) -> None:
        # 5 consecutive shell calls with different args
        for i in range(5):
            self.detector.record_action("tool_call", tool_name="shell", args={"command": f"cmd_{i}"})

        loop_msg = self.detector.check_for_loop()
        self.assertIsNotNone(loop_msg)
        self.assertIn("Called 'shell' 5 times in a row without making progress", loop_msg)

