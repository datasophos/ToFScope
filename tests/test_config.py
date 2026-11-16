import unittest

from service_fixture import setup_case

from tofscope.config import Settings


class ConfigTests(unittest.TestCase):
    def test_signal_quotas(self):
        setup_case(self)
        self.assertEqual(
            (
                self.settings.signals_per_analysis,
                self.settings.signals_per_user,
                self.settings.signals_global,
            ),
            (129, 512, 2048),
        )
        for field in ("signals_per_analysis", "signals_per_user", "signals_global"):
            with self.assertRaises(ValueError):
                Settings(self.settings.data_root, **{field: 0})

    def test_folder_defaults_follow_working_directory_and_effective_data_root(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch

        from tofscope.config import load_settings

        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with patch("pathlib.Path.cwd", return_value=root):
                settings = load_settings(env={}, cli={"runtime_dir": root / "runtime"})
                self.assertEqual(settings.data_root, root)
                self.assertEqual(settings.output_root, root)
                self.assertEqual(Settings(runtime_dir=root / "runtime").data_root, root)
            source = root / "acquisitions"
            source.mkdir()
            settings = load_settings(
                env={"TOFSCOPE_DATA_ROOT": str(source)},
                cli={"runtime_dir": root / "runtime"},
            )
            self.assertEqual(settings.output_root, source)
            output = root / "copies"
            settings = load_settings(
                env={
                    "TOFSCOPE_DATA_ROOT": str(source),
                    "TOFSCOPE_OUTPUT_ROOT": str(output),
                },
                cli={"runtime_dir": root / "runtime"},
            )
            self.assertEqual(settings.output_root, output)


class ConfigDiscoveryTests(unittest.TestCase):
    def test_platform_locations(self):
        from pathlib import Path

        from tofscope.config import config_paths

        home = Path("/home/example")
        self.assertEqual(
            config_paths("linux", {"HOME": str(home), "XDG_CONFIG_HOME": "/custom"}),
            [Path("/etc/tofscope.toml"), Path("/custom/tofscope/config.toml")],
        )
        self.assertEqual(
            config_paths("darwin", {"HOME": str(home)}),
            [
                Path("/Library/Application Support/ToFScope/config.toml"),
                home / "Library/Application Support/ToFScope/config.toml",
            ],
        )
        self.assertEqual(
            config_paths(
                "win32",
                {
                    "PROGRAMDATA": "C:/ProgramData",
                    "LOCALAPPDATA": "C:/Users/example/AppData/Local",
                },
            ),
            [
                Path("C:/ProgramData/ToFScope/config.toml"),
                Path("C:/Users/example/AppData/Local/ToFScope/config.toml"),
            ],
        )

    def test_layers_and_loaded_files(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch

        from tofscope.config import load_settings_with_sources

        with TemporaryDirectory() as d:
            root = Path(d)
            system, user, explicit = (
                root / f"{name}.toml" for name in ("system", "user", "explicit")
            )
            system.write_text("[tofscope]\nport=8000\nworkers=3\n")
            user.write_text("[tofscope]\nport=8001\nworkers=4\n")
            explicit.write_text("[tofscope]\nport=8002\n")
            with patch("tofscope.config.config_paths", return_value=[system, user]):
                settings, sources = load_settings_with_sources(
                    explicit,
                    {"TOFSCOPE_PORT": "8003"},
                    {"port": 8004, "runtime_dir": root / "runtime"},
                )
            self.assertEqual((settings.port, settings.workers), (8004, 4))
            self.assertEqual(sources, [system, user, explicit])
            with patch("tofscope.config.config_paths", return_value=[system, user]):
                settings, _ = load_settings_with_sources(
                    explicit, {}, {"runtime_dir": root / "runtime"}
                )
                self.assertEqual(settings.port, 8002)
                settings, _ = load_settings_with_sources(
                    None, {"TOFSCOPE_PORT": "8003"}, {"runtime_dir": root / "runtime"}
                )
                self.assertEqual(settings.port, 8003)
                settings, _ = load_settings_with_sources(
                    None, {}, {"runtime_dir": root / "runtime"}
                )
                self.assertEqual(settings.port, 8001)
            with patch("tofscope.config.config_paths", return_value=[system]):
                settings, _ = load_settings_with_sources(
                    None, {}, {"runtime_dir": root / "runtime"}
                )
                self.assertEqual(settings.port, 8000)
            with patch("tofscope.config.config_paths", return_value=[explicit]):
                _, sources = load_settings_with_sources(
                    explicit, {}, {"runtime_dir": root / "runtime"}
                )
                self.assertEqual(sources, [explicit])

    def test_missing_defaults_and_invalid_files(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch

        from tofscope.config import load_settings_with_sources

        with TemporaryDirectory() as d:
            root = Path(d)
            missing = root / "missing.toml"
            with patch("tofscope.config.config_paths", return_value=[missing]):
                _, sources = load_settings_with_sources(
                    env={}, cli={"runtime_dir": root / "runtime"}
                )
                self.assertEqual(sources, [])
                with self.assertRaisesRegex(ValueError, "missing.toml"):
                    load_settings_with_sources(missing, env={})
            missing.write_text("[tofscope\n")
            with (
                patch("tofscope.config.config_paths", return_value=[missing]),
                self.assertRaisesRegex(ValueError, "missing.toml"),
            ):
                load_settings_with_sources(env={})

    def test_unreadable_config_names_path(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch

        from tofscope.config import load_settings_with_sources

        with TemporaryDirectory() as d:
            path = Path(d) / "unreadable.toml"
            with (
                patch("tofscope.config.config_paths", return_value=[path]),
                patch.object(
                    Path, "open", side_effect=PermissionError("permission denied")
                ),
                self.assertRaisesRegex(
                    ValueError, "unreadable.toml.*permission denied"
                ),
            ):
                load_settings_with_sources(env={})
