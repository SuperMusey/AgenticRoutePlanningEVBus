"""
PRT News Generator — MCP Client
---------------------------------
Connects to the prt-news-generator MCP server and produces rendered news
articles.

Produces a list of NewsArticle objects — each containing the rendered article text plus
lightweight metadata — and stops there. Feed the output directly into
your route-planner agent.

Typical integration
-------------------
    from client.news_generator import NewsGeneratorClient, NewsArticle

    async def your_pipeline():
        async with NewsGeneratorClient() as generator:
            articles: list[NewsArticle] = await generator.generate(count=10)

        for article in articles:
            # hand off to your existing route-analysis agent
            await your_route_planner.analyse(article.text, article.metadata)

CLI usage
---------
    python client/news_generator.py                        # 5 articles, stdout
    python client/news_generator.py --count 10 --seed 42
    python client/news_generator.py --output articles.json
    python client/news_generator.py --event-types fire weather --count 6

Requirements
------------
    pip install anthropic mcp
    export ANTHROPIC_API_KEY=sk-ant-...
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import sys
from pathlib import Path
from typing import Optional

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SERVER_SCRIPT = Path(__file__).parent.parent / "server" / "news_server.py"
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024


# ---------------------------------------------------------------------------
# Public data type
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class NewsArticle:
    """
    A single rendered news article plus the metadata your route-planner needs.

    Attributes
    ----------
    text:
        The full rendered article text (headline + body). This is what you
        pass to your route-analysis agent.
    event_type:
        Category of event (fire, traffic_accident, weather, etc.).
    severity:
        'minor', 'moderate', or 'severe'.
    affected_streets:
        The one or two street names the article is anchored to.
    affected_neighborhoods:
        The neighbourhood(s) mentioned in the article.
    timestamp:
        ISO-8601 generation timestamp (e.g. '2026-04-16T06:14:00').
    """
    text: str
    event_type: str
    severity: str
    affected_streets: list[str]
    affected_neighborhoods: list[str]
    timestamp: str

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class NewsGeneratorClient:
    """
    Async context-manager that owns the MCP server subprocess lifetime.

    Usage
    -----
        async with NewsGeneratorClient() as gen:
            articles = await gen.generate(count=5)

    You can also manage the session yourself if your framework already
    provides an MCP ClientSession:

        articles = await NewsGeneratorClient.generate_from_session(
            session, anthropic_client, count=5
        )
    """

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        server_script: Optional[Path] = None,
    ):
        self._api_key = anthropic_api_key or os.environ["ANTHROPIC_API_KEY"]
        self._server_script = server_script or SERVER_SCRIPT
        self._llm = anthropic.Anthropic(api_key=self._api_key)
        self._exit_stack = None
        self._session: Optional[ClientSession] = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "NewsGeneratorClient":
        server_params = StdioServerParameters(
            command="python",
            args=[str(self._server_script)],
            env=None,
        )
        self._read_write_ctx = stdio_client(server_params)
        read, write = await self._read_write_ctx.__aenter__()
        self._session_ctx = ClientSession(read, write)
        self._session = await self._session_ctx.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, *exc_info) -> None:
        if self._session_ctx:
            await self._session_ctx.__aexit__(*exc_info)
        if self._read_write_ctx:
            await self._read_write_ctx.__aexit__(*exc_info)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        count: int = 5,
        event_types: Optional[list[str]] = None,
        corridors: Optional[list[str]] = None,
        seed: Optional[int] = None,
    ) -> list[NewsArticle]:
        """
        Generate `count` news articles and return them as NewsArticle objects.

        Parameters
        ----------
        count:
            Number of articles to produce (1–20).
        event_types:
            Restrict to specific event types. Pass None for all types.
            Valid values: fire, traffic_accident, water_main_break,
            road_closure, medical_emergency, police_activity,
            special_event, weather, utility_work, bridge_inspection.
        corridors:
            Restrict to specific corridor names. Pass None for all corridors.
            Use list_corridors() to see valid values.
        seed:
            Integer random seed for reproducibility.

        Returns
        -------
        list[NewsArticle]
            Rendered articles ready to pass to your route-analysis agent.
        """
        if self._session is None:
            raise RuntimeError(
                "NewsGeneratorClient must be used as an async context manager. "
                "Use: async with NewsGeneratorClient() as gen: ..."
            )
        return await self.generate_from_session(
            self._session, self._llm,
            count=count, event_types=event_types,
            corridors=corridors, seed=seed,
        )

    async def list_corridors(self) -> dict:
        """Return the available corridor names and their geographic details."""
        if self._session is None:
            raise RuntimeError("Must be used inside async context manager.")
        result = await self._session.call_tool("list_available_corridors", arguments={})
        return json.loads(result.content[0].text)

    async def list_event_types(self) -> dict:
        """Return supported event types and severity levels."""
        if self._session is None:
            raise RuntimeError("Must be used inside async context manager.")
        result = await self._session.call_tool("get_event_types", arguments={})
        return json.loads(result.content[0].text)

    # ------------------------------------------------------------------
    # Static / class-level helper — use when you already have a session
    # ------------------------------------------------------------------

    @classmethod
    async def generate_from_session(
        cls,
        session: ClientSession,
        llm: anthropic.Anthropic,
        count: int = 5,
        event_types: Optional[list[str]] = None,
        corridors: Optional[list[str]] = None,
        seed: Optional[int] = None,
    ) -> list[NewsArticle]:
        """
        Generate articles using a pre-existing MCP ClientSession and
        Anthropic client. Useful when your framework manages the session.
        """
        # 1. Ask the MCP server for a batch of generation prompts
        args: dict = {"count": count}
        if seed is not None:
            args["seed"] = seed
        if event_types:
            args["event_types"] = event_types
        if corridors:
            args["corridors"] = corridors

        tool_result = await session.call_tool("generate_news_batch", arguments=args)
        batch = json.loads(tool_result.content[0].text)

        if "error" in batch:
            raise ValueError(f"MCP server error: {batch['error']}")

        # 2. Render each prompt into article text via Claude
        articles: list[NewsArticle] = []
        for meta in batch["articles"]:
            text = await cls._render(llm, meta["prompt"])
            articles.append(NewsArticle(
                text=text,
                event_type=meta["event_type"],
                severity=meta["severity"],
                affected_streets=meta["affected_streets"],
                affected_neighborhoods=meta["affected_neighborhoods"],
                timestamp=meta["timestamp"],
            ))

        return articles

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    async def _render(llm: anthropic.Anthropic, prompt: str) -> str:
        """Call Claude to turn a generation prompt into a news article."""
        response = llm.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=(
                "You are a local Pittsburgh news reporter. "
                "Write concise, factual articles in AP style. "
                "Never mention PRT route numbers."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# CLI  (for testing / ad-hoc generation outside your pipeline)
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate PRT transit disruption news articles."
    )
    p.add_argument("--count", type=int, default=5,
                   help="Number of articles to generate (default: 5, max: 20)")
    p.add_argument("--seed", type=int, default=None,
                   help="Random seed for reproducibility")
    p.add_argument("--event-types", nargs="+", default=None, metavar="EVENT",
                   help="Restrict to specific event types")
    p.add_argument("--corridors", nargs="+", default=None, metavar="CORRIDOR",
                   help="Restrict to specific corridor names")
    p.add_argument("--output", default=None,
                   help="Write articles to this JSON file instead of stdout")
    p.add_argument("--list-corridors", action="store_true",
                   help="Print available corridor names and exit")
    p.add_argument("--list-event-types", action="store_true",
                   help="Print available event types and exit")
    return p.parse_args()


async def _cli() -> None:
    args = _parse_args()

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    async with NewsGeneratorClient() as gen:

        if args.list_corridors:
            corridors = await gen.list_corridors()
            print(json.dumps(list(corridors.keys()), indent=2))
            return

        if args.list_event_types:
            types = await gen.list_event_types()
            print(json.dumps(types, indent=2))
            return

        print(f"Generating {args.count} article(s)...\n", file=sys.stderr)

        articles = await gen.generate(
            count=args.count,
            seed=args.seed,
            event_types=args.event_types,
            corridors=args.corridors,
        )

    if args.output:
        out = Path(args.output)
        with open(out, "w") as f:
            json.dump([a.to_dict() for a in articles], f, indent=2)
        print(f"Wrote {len(articles)} article(s) to {out}", file=sys.stderr)
    else:
        for i, article in enumerate(articles, 1):
            print(f"{'─'*60}")
            print(f"Article {i}  [{article.event_type} / {article.severity}]")
            print(f"Streets: {', '.join(article.affected_streets)}")
            print(f"{'─'*60}")
            print(article.text)
            print()


if __name__ == "__main__":
    asyncio.run(_cli())
