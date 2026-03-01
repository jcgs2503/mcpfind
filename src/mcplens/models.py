"""Data models for MCPLens."""

from dataclasses import dataclass, field


@dataclass
class ToolEntry:
    """A tool discovered from a backend MCP server."""

    server: str
    name: str
    description: str
    full_schema: dict
    embedding: list[float] = field(default_factory=list)


@dataclass
class SearchResult:
    """A tool returned from a search query."""

    server: str
    name: str
    description: str
    score: float


@dataclass
class ServerConfig:
    """Configuration for a single backend MCP server."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class ProxyConfig:
    """Top-level proxy configuration."""

    embedding_model: str = "text-embedding-3-small"
    mfu_boost_weight: float = 0.15
    mfu_persist: bool = True
    default_max_results: int = 5
    servers: list[ServerConfig] = field(default_factory=list)
