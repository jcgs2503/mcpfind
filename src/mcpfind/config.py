"""Configuration loading from TOML files."""

import os
import re
from pathlib import Path

import tomli

from mcpfind.models import ProxyConfig, ServerConfig

GLOBAL_CONFIG_PATH = Path.home() / ".config" / "mcpfind" / "mcpfind.toml"
LOCAL_CONFIG_NAME = "mcpfind.toml"


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
    """Load and validate a MCPFind configuration file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "rb") as f:
        data = tomli.load(f)

    proxy_data = data.get("proxy", {})
    config = ProxyConfig(
        embedding_provider=proxy_data.get("embedding_provider", "local"),
        embedding_model=proxy_data.get("embedding_model", "all-MiniLM-L6-v2"),
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


def _merge_configs(global_cfg: ProxyConfig, local_cfg: ProxyConfig) -> ProxyConfig:
    """Merge global and local configs. Local overrides global for same-name servers."""
    merged = ProxyConfig(
        embedding_provider=(
            local_cfg.embedding_provider
            if local_cfg.embedding_provider != "local"
            else global_cfg.embedding_provider
        ),
        embedding_model=(
            local_cfg.embedding_model
            if local_cfg.embedding_model != "all-MiniLM-L6-v2"
            else global_cfg.embedding_model
        ),
        mfu_boost_weight=(
            local_cfg.mfu_boost_weight
            if local_cfg.mfu_boost_weight != 0.15
            else global_cfg.mfu_boost_weight
        ),
        mfu_persist=(
            local_cfg.mfu_persist
            if not local_cfg.mfu_persist
            else global_cfg.mfu_persist
        ),
        default_max_results=(
            local_cfg.default_max_results
            if local_cfg.default_max_results != 5
            else global_cfg.default_max_results
        ),
    )

    # Servers: global as base, local same-name overrides, local unique gets added
    servers_by_name = {s.name: s for s in global_cfg.servers}
    for s in local_cfg.servers:
        servers_by_name[s.name] = s  # override or add
    merged.servers = list(servers_by_name.values())

    return merged


def _load_config_or_none(path: Path) -> ProxyConfig | None:
    """Load config from path, returning None if file doesn't exist."""
    if not path.exists():
        return None
    return load_config(path)


def load_merged_config() -> ProxyConfig:
    """Load global and local configs, merging them together.

    Global config: ~/.config/mcpfind/mcpfind.toml
    Local config: ./mcpfind.toml

    If both exist, local overrides global for same-name servers and
    non-default proxy settings. If only one exists, that config is used.
    """
    global_cfg = _load_config_or_none(GLOBAL_CONFIG_PATH)
    local_cfg = _load_config_or_none(Path(LOCAL_CONFIG_NAME))

    if global_cfg is None and local_cfg is None:
        raise FileNotFoundError(
            "No configuration found.\n"
            f"  Global: {GLOBAL_CONFIG_PATH} (not found)\n"
            f"  Local:  ./{LOCAL_CONFIG_NAME} (not found)\n\n"
            "Run 'mcpfind setup' to create a global config, or\n"
            "'mcpfind init' to create a project-local config."
        )

    if global_cfg is None:
        return local_cfg
    if local_cfg is None:
        return global_cfg

    return _merge_configs(global_cfg, local_cfg)
