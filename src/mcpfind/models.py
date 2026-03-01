"""Data models for MCPFind."""

from dataclasses import dataclass, field

DEFAULT_LOCAL_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


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

    embedding_provider: str = "local"
    embedding_model: str = DEFAULT_LOCAL_MODEL
    mfu_boost_weight: float = 0.15
    mfu_persist: bool = True
    default_max_results: int = 5
    servers: list[ServerConfig] = field(default_factory=list)
