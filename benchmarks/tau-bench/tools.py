"""Tool corpus generator for tau-bench.

Generates realistic MCP tool definitions: a fixed set of target tools
(correct answers for tasks) plus configurable distractor tools.
"""

from __future__ import annotations

import hashlib
import random

# ---------------------------------------------------------------------------
# Target tools — these are the correct answers for benchmark tasks
# ---------------------------------------------------------------------------

TARGET_TOOLS: list[dict] = [
    # Gmail
    {
        "server": "gmail",
        "name": "send_email",
        "description": "Compose and send an email to one or more recipients",
        "schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body content"},
                "cc": {"type": "string", "description": "CC recipients (optional)"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "server": "gmail",
        "name": "search_emails",
        "description": "Search inbox for emails matching a query string",
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results"},
            },
            "required": ["query"],
        },
    },
    {
        "server": "gmail",
        "name": "read_email",
        "description": "Read the full content of an email by its ID",
        "schema": {
            "type": "object",
            "properties": {
                "email_id": {"type": "string", "description": "Email ID"},
            },
            "required": ["email_id"],
        },
    },
    {
        "server": "gmail",
        "name": "draft_email",
        "description": "Create a draft email without sending it",
        "schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    # GitHub
    {
        "server": "github",
        "name": "create_issue",
        "description": "Create a new issue in a GitHub repository",
        "schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository (owner/name)"},
                "title": {"type": "string", "description": "Issue title"},
                "body": {"type": "string", "description": "Issue description"},
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels to apply",
                },
            },
            "required": ["repo", "title"],
        },
    },
    {
        "server": "github",
        "name": "create_pull_request",
        "description": "Open a pull request from one branch to another",
        "schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "title": {"type": "string"},
                "head": {"type": "string", "description": "Source branch"},
                "base": {"type": "string", "description": "Target branch"},
                "body": {"type": "string"},
            },
            "required": ["repo", "title", "head", "base"],
        },
    },
    {
        "server": "github",
        "name": "list_pull_requests",
        "description": "List open pull requests in a repository",
        "schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "state": {"type": "string", "enum": ["open", "closed", "all"]},
            },
            "required": ["repo"],
        },
    },
    {
        "server": "github",
        "name": "search_code",
        "description": "Search for code across GitHub repositories",
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "repo": {"type": "string", "description": "Limit to repo (optional)"},
            },
            "required": ["query"],
        },
    },
    # Slack
    {
        "server": "slack",
        "name": "post_message",
        "description": "Send a message to a Slack channel",
        "schema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel name or ID"},
                "text": {"type": "string", "description": "Message text"},
            },
            "required": ["channel", "text"],
        },
    },
    {
        "server": "slack",
        "name": "search_messages",
        "description": "Search Slack message history across channels",
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "channel": {"type": "string", "description": "Limit to channel"},
            },
            "required": ["query"],
        },
    },
    {
        "server": "slack",
        "name": "list_channels",
        "description": "List all accessible Slack channels",
        "schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "server": "slack",
        "name": "send_direct_message",
        "description": "Send a direct message to a Slack user",
        "schema": {
            "type": "object",
            "properties": {
                "user": {"type": "string", "description": "User ID or name"},
                "text": {"type": "string"},
            },
            "required": ["user", "text"],
        },
    },
    # Filesystem
    {
        "server": "filesystem",
        "name": "read_file",
        "description": "Read the contents of a file at a given path",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"},
            },
            "required": ["path"],
        },
    },
    {
        "server": "filesystem",
        "name": "write_file",
        "description": "Write content to a file, creating it if it doesn't exist",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "server": "filesystem",
        "name": "list_directory",
        "description": "List files and subdirectories in a directory",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    },
    {
        "server": "filesystem",
        "name": "search_files",
        "description": "Search for files matching a name pattern recursively",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Root directory"},
                "pattern": {"type": "string", "description": "Glob pattern"},
            },
            "required": ["path", "pattern"],
        },
    },
    # Calendar
    {
        "server": "calendar",
        "name": "create_event",
        "description": "Create a new calendar event with a title, time, and attendees",
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "description": "ISO 8601 datetime"},
                "end": {"type": "string", "description": "ISO 8601 datetime"},
                "attendees": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "start", "end"],
        },
    },
    {
        "server": "calendar",
        "name": "list_events",
        "description": "List upcoming calendar events within a date range",
        "schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
            },
            "required": ["start_date"],
        },
    },
    {
        "server": "calendar",
        "name": "delete_event",
        "description": "Delete a calendar event by its ID",
        "schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
            },
            "required": ["event_id"],
        },
    },
    {
        "server": "calendar",
        "name": "update_event",
        "description": "Update an existing calendar event's details",
        "schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "title": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
            },
            "required": ["event_id"],
        },
    },
]

# ---------------------------------------------------------------------------
# Distractor tool templates — plausible but irrelevant tools
# ---------------------------------------------------------------------------

_DISTRACTOR_SERVERS = [
    "jira",
    "confluence",
    "notion",
    "linear",
    "asana",
    "trello",
    "airtable",
    "hubspot",
    "salesforce",
    "zendesk",
    "intercom",
    "datadog",
    "pagerduty",
    "sentry",
    "grafana",
    "aws-s3",
    "aws-lambda",
    "gcp-bigquery",
    "azure-devops",
    "stripe",
    "twilio",
    "sendgrid",
    "mongodb",
    "redis",
    "elasticsearch",
    "snowflake",
    "dbt",
    "airflow",
    "kubernetes",
    "docker",
    "terraform",
    "vault",
    "cloudflare",
    "vercel",
    "netlify",
    "figma",
    "miro",
    "dropbox",
    "box",
    "onedrive",
]

_DISTRACTOR_ACTIONS = [
    ("create_{entity}", "Create a new {entity} in {server}"),
    ("update_{entity}", "Update an existing {entity} in {server}"),
    ("delete_{entity}", "Delete a {entity} from {server}"),
    ("list_{entity}s", "List all {entity}s in {server}"),
    ("get_{entity}", "Get details of a specific {entity} from {server}"),
    ("search_{entity}s", "Search for {entity}s in {server} matching a query"),
    ("archive_{entity}", "Archive a {entity} in {server}"),
    ("export_{entity}s", "Export {entity}s from {server} as CSV or JSON"),
    ("import_{entity}s", "Import {entity}s into {server} from a file"),
    ("assign_{entity}", "Assign a {entity} to a user in {server}"),
    ("comment_on_{entity}", "Add a comment to a {entity} in {server}"),
    ("share_{entity}", "Share a {entity} with other users in {server}"),
    ("duplicate_{entity}", "Duplicate an existing {entity} in {server}"),
    ("move_{entity}", "Move a {entity} to a different location in {server}"),
    ("tag_{entity}", "Add tags or labels to a {entity} in {server}"),
]

_DISTRACTOR_ENTITIES = [
    "ticket",
    "task",
    "project",
    "document",
    "page",
    "board",
    "record",
    "contact",
    "deal",
    "pipeline",
    "alert",
    "incident",
    "dashboard",
    "report",
    "workspace",
    "bucket",
    "function",
    "query",
    "dataset",
    "deployment",
    "payment",
    "message",
    "collection",
    "index",
    "schema",
    "workflow",
    "container",
    "resource",
    "component",
    "asset",
]

_DISTRACTOR_PARAMS = [
    {"name": {"type": "string", "description": "Name or title"}},
    {"description": {"type": "string", "description": "Description text"}},
    {"id": {"type": "string", "description": "Unique identifier"}},
    {"query": {"type": "string", "description": "Search query"}},
    {"limit": {"type": "integer", "description": "Maximum number of results"}},
    {"status": {"type": "string", "description": "Filter by status"}},
    {"owner": {"type": "string", "description": "Owner or assignee"}},
    {"tags": {"type": "array", "items": {"type": "string"}}},
    {"path": {"type": "string", "description": "Path or location"}},
    {"data": {"type": "object", "description": "Payload data"}},
]


def _make_distractor(server: str, action_tpl: str, desc_tpl: str, entity: str) -> dict:
    """Generate a single distractor tool."""
    name = action_tpl.format(entity=entity)
    description = desc_tpl.format(entity=entity, server=server)

    # Deterministic but varied schema based on tool identity
    seed = hashlib.md5(f"{server}:{name}".encode()).hexdigest()
    rng = random.Random(seed)

    num_params = rng.randint(1, 4)
    param_pool = list(_DISTRACTOR_PARAMS)
    rng.shuffle(param_pool)
    properties = {}
    for p in param_pool[:num_params]:
        properties.update(p)

    required = [list(p.keys())[0] for p in param_pool[: max(1, num_params // 2)]]

    return {
        "server": server,
        "name": name,
        "description": description,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def generate_corpus(total_tools: int, seed: int = 42) -> list[dict]:
    """Generate a tool corpus with target tools + distractors.

    Args:
        total_tools: Total number of tools in the corpus.
            Must be >= len(TARGET_TOOLS) (20).
        seed: Random seed for reproducibility.

    Returns:
        List of tool dicts, shuffled. Each has keys:
        server, name, description, schema.
    """
    if total_tools < len(TARGET_TOOLS):
        raise ValueError(
            f"total_tools ({total_tools}) must be >= {len(TARGET_TOOLS)} (target count)"
        )

    rng = random.Random(seed)
    num_distractors = total_tools - len(TARGET_TOOLS)

    # Generate distractor pool (much larger than we need)
    pool: list[dict] = []
    for server in _DISTRACTOR_SERVERS:
        for action_tpl, desc_tpl in _DISTRACTOR_ACTIONS:
            for entity in _DISTRACTOR_ENTITIES:
                pool.append(_make_distractor(server, action_tpl, desc_tpl, entity))

    # Deduplicate by server:name
    seen = set()
    unique_pool = []
    for tool in pool:
        key = f"{tool['server']}:{tool['name']}"
        if key not in seen:
            seen.add(key)
            unique_pool.append(tool)

    # Also exclude any that collide with target tool names
    target_keys = {f"{t['server']}:{t['name']}" for t in TARGET_TOOLS}
    unique_pool = [
        t for t in unique_pool if f"{t['server']}:{t['name']}" not in target_keys
    ]

    rng.shuffle(unique_pool)
    distractors = unique_pool[:num_distractors]

    corpus = list(TARGET_TOOLS) + distractors
    rng.shuffle(corpus)
    return corpus


def format_tool_schema_for_prompt(tool: dict) -> str:
    """Format a single tool as a JSON-like schema string for LLM context."""
    import json

    return json.dumps(
        {
            "server": tool["server"],
            "name": tool["name"],
            "description": tool["description"],
            "inputSchema": tool["schema"],
        },
        indent=2,
    )
