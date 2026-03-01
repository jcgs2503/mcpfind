"""MCPFind CLI entry point."""

import asyncio
import logging

import click

from mcpfind.config import load_config


@click.group()
def main():
    """MCPFind: Context-efficient MCP tool proxy."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


@main.command()
@click.option(
    "--config",
    "config_path",
    default="mcpfind.toml",
    help="Path to configuration file.",
)
def serve(config_path: str):
    """Start the MCPFind proxy server (stdio MCP transport)."""
    from mcpfind.proxy.server import run_proxy

    asyncio.run(run_proxy(config_path))


@main.command("list-tools")
@click.option(
    "--config",
    "config_path",
    default="mcpfind.toml",
    help="Path to configuration file.",
)
def list_tools(config_path: str):
    """List all tools discovered from backend servers."""

    async def _list():
        from mcpfind.backend.discovery import discover_all_tools
        from mcpfind.backend.manager import BackendManager

        config = load_config(config_path)
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
@click.argument("query")
@click.option(
    "--config",
    "config_path",
    default="mcpfind.toml",
    help="Path to configuration file.",
)
@click.option("--max-results", "-k", default=5, help="Number of results to return.")
def search(query: str, config_path: str, max_results: int):
    """Test semantic search against discovered tools."""

    async def _search():
        from mcpfind.backend.discovery import discover_all_tools
        from mcpfind.backend.manager import BackendManager
        from mcpfind.index.embeddings import create_embedding_client
        from mcpfind.index.vector import VectorIndex

        config = load_config(config_path)
        manager = BackendManager(config.servers)
        await manager.start_all()
        try:
            entries = await discover_all_tools(manager)

            embedding_client = create_embedding_client(
                provider=config.embedding_provider, model=config.embedding_model
            )
            texts = [f"{e.name}: {e.description}" for e in entries]
            if texts:
                embeddings = embedding_client.embed_batch(texts)
                for entry, emb in zip(entries, embeddings):
                    entry.embedding = emb

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
