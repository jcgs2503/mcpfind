"""Configuration loading from TOML files."""

import os
import re
from pathlib import Path

import tomli

from mcplens.models import ProxyConfig, ServerConfig


def _expand_env_vars(value: str) -> str:
    """Expand ${VAR} patterns with environment variable values."""
    return re.sub(
        r"\$\{(\w+)\}",
        lambda m: os.environ.get(m.group(1), m.group(0)),
        value,
    )


def _expand_env_in_dict(d: dict) -> dict:
    """Recursively expand environment variables in a dict's string values."""
    result = {}
    for k, v in d.items():
        if isinstance(v, str):
            result[k] = _expand_env_vars(v)
        elif isinstance(v, dict):
            result[k] = _expand_env_in_dict(v)
        else:
            result[k] = v
    return result


def load_config(path: str | Path) -> ProxyConfig:
    """Load and validate a MCPLens configuration file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "rb") as f:
        data = tomli.load(f)

    proxy_data = data.get("proxy", {})
    config = ProxyConfig(
        embedding_model=proxy_data.get("embedding_model", "text-embedding-3-small"),
        mfu_boost_weight=proxy_data.get("mfu_boost_weight", 0.15),
        mfu_persist=proxy_data.get("mfu_persist", True),
        default_max_results=proxy_data.get("default_max_results", 5),
    )

    for server_data in data.get("servers", []):
        if "name" not in server_data:
            raise ValueError("Each server must have a 'name' field")
        if "command" not in server_data:
            raise ValueError(
                f"Server '{server_data['name']}' must have a 'command' field"
            )

        env = _expand_env_in_dict(server_data.get("env", {}))

        config.servers.append(
            ServerConfig(
                name=server_data["name"],
                command=server_data["command"],
                args=server_data.get("args", []),
                env=env,
            )
        )

    return config
