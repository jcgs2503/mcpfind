"""MCPFind CLI entry point."""

import asyncio
import logging

import click

from mcpfind.config import load_config, load_merged_config


def _resolve_config(config_path: str | None):
    """Load config from explicit path or use merged global+local."""
    if config_path is not None:
        return load_config(config_path)
    return load_merged_config()


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Show detailed log output.")
@click.pass_context
def main(ctx, verbose):
    """MCPFind: Context-efficient MCP tool proxy."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


@main.command()
@click.option(
    "--config",
    "config_path",
    default=None,
    help="Path to configuration file. If omitted, loads global + local merged config.",
)
def serve(config_path: str | None):
    """Start the MCPFind proxy server (stdio MCP transport)."""
    from mcpfind.proxy.server import run_proxy

    logging.getLogger().setLevel(logging.INFO)
    config = _resolve_config(config_path)
    asyncio.run(run_proxy(config))


@main.command("list-tools")
@click.option(
    "--config",
    "config_path",
    default=None,
    help="Path to configuration file. If omitted, loads global + local merged config.",
)
def list_tools(config_path: str | None):
    """List all tools discovered from backend servers."""

    async def _list():
        from mcpfind.backend.discovery import discover_all_tools
        from mcpfind.backend.manager import BackendManager

        config = _resolve_config(config_path)
        manager = BackendManager(config.servers)
        await manager.start_all()
        try:
            entries = await discover_all_tools(manager)
            for entry in entries:
                click.echo(f"  {entry.server}:{entry.name} — {entry.description}")
            click.echo(f"\nTotal: {len(entries)} tools")
        finally:
            await manager.stop_all()

    asyncio.run(_list())


@main.command()
def setup():
    """Interactive setup wizard — configure global MCPFind config."""
    from mcpfind.setup import run_setup

    run_setup()


@main.command()
def init():
    """Create a project-local mcpfind.toml with project-specific servers."""
    from mcpfind.setup import run_init

    run_init()


@main.command()
@click.argument("query")
@click.option(
    "--config",
    "config_path",
    default=None,
    help="Path to configuration file. If omitted, loads global + local merged config.",
)
@click.option("--max-results", "-k", default=5, help="Number of results to return.")
def search(query: str, config_path: str | None, max_results: int):
    """Test semantic search against discovered tools."""

    async def _search():
        from mcpfind.backend.discovery import discover_all_tools
        from mcpfind.backend.manager import BackendManager
        from mcpfind.index.embeddings import create_embedding_client
        from mcpfind.index.vector import VectorIndex

        config = _resolve_config(config_path)
        manager = BackendManager(config.servers)
        await manager.start_all()
        try:
            entries = await discover_all_tools(manager)

            embedding_client = create_embedding_client(
                provider=config.embedding_provider, model=config.embedding_model
            )
            if entries:
                from mcpfind.index.cache import embed_with_cache

                embed_with_cache(entries, embedding_client)

            index = VectorIndex()
            index.build(entries)

            query_emb = embedding_client.embed_query(query)
            results = index.search(query_emb, k=max_results)

            click.echo(f"Search results for: '{query}'\n")
            for idx, score in results:
                entry = index.get_entry(idx)
                click.echo(
                    f"  {score:.4f}  {entry.server}:{entry.name} — {entry.description}"
                )
        finally:
            await manager.stop_all()

    asyncio.run(_search())


if __name__ == "__main__":
    main()
