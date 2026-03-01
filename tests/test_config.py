"""Tests for configuration loading."""

import os
import tempfile
from pathlib import Path

import pytest

from mcpfind.config import load_config


def _write_toml(path: Path, content: str) -> None:
    path.write_text(content)


def test_load_basic_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test.toml"
        _write_toml(
            config_path,
            """
[proxy]
embedding_model = "text-embedding-3-small"
mfu_boost_weight = 0.2
mfu_persist = false
default_max_results = 10

[[servers]]
name = "test_server"
command = "echo"
args = ["hello"]
""",
        )

        config = load_config(config_path)
        assert config.embedding_model == "text-embedding-3-small"
        assert config.mfu_boost_weight == 0.2
        assert config.mfu_persist is False
        assert config.default_max_results == 10
        assert len(config.servers) == 1
        assert config.servers[0].name == "test_server"
        assert config.servers[0].command == "echo"
        assert config.servers[0].args == ["hello"]


def test_load_config_with_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test.toml"
        _write_toml(
            config_path,
            """
[[servers]]
name = "minimal"
command = "test"
""",
        )

        config = load_config(config_path)
        assert config.embedding_provider == "local"
        assert config.embedding_model == "all-MiniLM-L6-v2"
        assert config.mfu_boost_weight == 0.15
        assert config.mfu_persist is True
        assert config.default_max_results == 5


def test_env_var_expansion():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test.toml"
        _write_toml(
            config_path,
            """
[[servers]]
name = "test"
command = "test"
env = { API_KEY = "${TEST_MCPLENS_KEY}" }
""",
        )

        os.environ["TEST_MCPLENS_KEY"] = "secret123"
        try:
            config = load_config(config_path)
            assert config.servers[0].env["API_KEY"] == "secret123"
        finally:
            del os.environ["TEST_MCPLENS_KEY"]


def test_env_var_not_set_keeps_placeholder():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test.toml"
        _write_toml(
            config_path,
            """
[[servers]]
name = "test"
command = "test"
env = { TOKEN = "${NONEXISTENT_VAR_XYZ}" }
""",
        )

        config = load_config(config_path)
        assert config.servers[0].env["TOKEN"] == "${NONEXISTENT_VAR_XYZ}"


def test_missing_config_file():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/config.toml")


def test_missing_server_name():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test.toml"
        _write_toml(
            config_path,
            """
[[servers]]
command = "test"
""",
        )

        with pytest.raises(ValueError, match="name"):
            load_config(config_path)


def test_missing_server_command():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test.toml"
        _write_toml(
            config_path,
            """
[[servers]]
name = "test"
""",
        )

        with pytest.raises(ValueError, match="command"):
            load_config(config_path)


def test_multiple_servers():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test.toml"
        _write_toml(
            config_path,
            """
[[servers]]
name = "server1"
command = "cmd1"

[[servers]]
name = "server2"
command = "cmd2"
args = ["--flag"]
""",
        )

        config = load_config(config_path)
        assert len(config.servers) == 2
        assert config.servers[0].name == "server1"
        assert config.servers[1].name == "server2"
        assert config.servers[1].args == ["--flag"]
