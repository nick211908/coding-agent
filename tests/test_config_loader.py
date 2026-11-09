from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.loader import get_system_config_path, load_config, save_system_config


class ConfigLoaderTests(unittest.TestCase):
    def test_save_system_config_persists_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            with patch("config.loader.user_config_dir", return_value=str(root / "cfg")):
                save_system_config(
                    {
                        "api_key": "test-key",
                        "base_url": "https://example.test/v1",
                        "model": {"name": "demo-model"},
                    }
                )

                config_path = get_system_config_path()
                self.assertTrue(config_path.is_file())
                config_text = config_path.read_text(encoding="utf-8")
                self.assertIn('api_key = "test-key"', config_text)
                self.assertIn('base_url = "https://example.test/v1"', config_text)
                self.assertIn("[model]", config_text)

    def test_load_config_reads_saved_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_root = root / "cfg"
            config_root.mkdir(parents=True)
            (config_root / "config.toml").write_text(
                'api_key = "saved-key"\n'
                'base_url = "https://saved.example/v1"\n',
                encoding="utf-8",
            )

            with patch("config.loader.user_config_dir", return_value=str(config_root)):
                config = load_config(cwd=root)

            self.assertEqual(config.api_key, "saved-key")
            self.assertEqual(config.base_url, "https://saved.example/v1")

    def test_parse_toml_with_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_root = root / "cfg"
            config_root.mkdir(parents=True)
            # Write with UTF-8 BOM
            (config_root / "config.toml").write_bytes(
                b'\xef\xbb\xbfapi_key = "bom-key"\nbase_url = "https://bom.example/v1"\n'
            )

            with patch("config.loader.user_config_dir", return_value=str(config_root)):
                config = load_config(cwd=root)

            self.assertEqual(config.api_key, "bom-key")

    def test_save_system_config_overwrites_corrupted_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_root = root / "cfg"
            config_root.mkdir(parents=True)
            # Corrupted file with illegal control char \x17
            (config_root / "config.toml").write_bytes(
                b'api_key = "bad\x17key"\n'
            )

            with patch("config.loader.user_config_dir", return_value=str(config_root)):
                save_system_config({"api_key": "fixed-key\x17", "base_url": "https://fixed.example/v1"})

                config = load_config(cwd=root)

            self.assertEqual(config.api_key, "fixed-key")
            self.assertEqual(config.base_url, "https://fixed.example/v1")
