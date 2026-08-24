from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent.persistence import PersistenceManager, SessionSnapshot
from client.response import TokenUsage


class PersistenceTests(unittest.TestCase):
    def test_failed_atomic_save_keeps_existing_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("agent.persistence.get_data_dir", return_value=Path(directory)):
                manager = PersistenceManager()
                snapshot = SessionSnapshot(
                    session_id="session-1",
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    turn_count=1,
                    messages=[{"role": "user", "content": "original"}],
                    total_usage=TokenUsage(),
                )
                manager.save_session(snapshot)

                replacement = SessionSnapshot(
                    session_id=snapshot.session_id,
                    created_at=snapshot.created_at,
                    updated_at=datetime.now(),
                    turn_count=2,
                    messages=[{"role": "user", "content": "replacement"}],
                    total_usage=TokenUsage(),
                )
                with patch("agent.persistence.os.replace", side_effect=OSError("boom")):
                    with self.assertRaises(OSError):
                        manager.save_session(replacement)

                loaded = manager.load_session(snapshot.session_id)
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded.messages, snapshot.messages)


if __name__ == "__main__":
    unittest.main()