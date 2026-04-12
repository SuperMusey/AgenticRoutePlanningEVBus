"""
Test harness for NewsParsingAgent.
Run with: python test_news_parser.py
Requires GENAI_API_KEY environment variable to be set.
"""

import json
from news_parser_agent import NewsParsingAgent

# ── TEST ARTICLES ──────────────────────────────────────────────────────────────

DISRUPTION_ARTICLE = """
Pittsburgh city officials announced Tuesday that Forbes Avenue will be closed 
between Murray Avenue and Shady Avenue in Squirrel Hill starting Wednesday morning 
due to an emergency water main break. The closure is expected to last approximately 
48 hours while crews work to repair the damaged pipe. Drivers are advised to use 
Fifth Avenue or Beeler Street as alternate routes. Port Authority bus routes 61C 
and 61D will be affected, with buses unable to serve stops along the closed section.
Emergency vehicles will maintain access throughout the repair period.
"""

NON_DISRUPTION_ARTICLE = """
The Pittsburgh Steelers announced Tuesday that they have signed three new players 
ahead of the upcoming NFL draft. The team's general manager expressed confidence 
in the new additions, saying the signings reflect the organization's commitment 
to building a competitive roster for the coming season. Fans can expect to see 
the new players at training camp later this summer at the UPMC Rooney Sports Complex.
"""

VAGUE_ARTICLE = """
There are reports of some traffic issues in the East End of Pittsburgh this morning. 
Commuters may want to consider alternate routes. Officials have not yet provided 
details on the cause or expected duration of the delays.
"""

MULTI_ROAD_ARTICLE = """
A serious accident involving two tractor-trailers has shut down Interstate 376 
westbound near the Squirrel Hill Tunnel, with delays backing up past the Edgewood 
exit. The tunnel itself remains open but traffic is being merged into a single lane 
approaching the incident. Pennsylvania State Police say the road may not fully reopen 
until late afternoon. The Boulevard of the Allies is seeing heavy spillover traffic 
as a result. Expect significant delays throughout the East End and into Downtown Pittsburgh.
"""

# ── TEST RUNNER ────────────────────────────────────────────────────────────────

def print_result(label: str, result: dict) -> None:
    print(f"\n{'─' * 60}")
    print(f"TEST: {label}")
    print(f"{'─' * 60}")
    if result is None:
        print("RESULT: None (article filtered out)")
    else:
        print("RESULT: Disruption detected")
        print(json.dumps(result, indent=2))

def run_tests():
    print("Initializing NewsParsingAgent...")
    agent = NewsParsingAgent()

    tests = [
        ("Clear disruption — Forbes Ave water main", DISRUPTION_ARTICLE),
        ("Non-disruption — Steelers news",           NON_DISRUPTION_ARTICLE),
        ("Vague disruption — East End traffic",      VAGUE_ARTICLE),
        ("Multi-road disruption — I-376 accident",  MULTI_ROAD_ARTICLE),
    ]

    results = {}
    for label, article in tests:
        print(f"\nRunning: {label}...")
        result = agent.parse_article(article)
        print_result(label, result)
        results[label] = result

    # ── ASSERTIONS ─────────────────────────────────────────────────────────────
    print(f"\n{'═' * 60}")
    print("ASSERTIONS")
    print(f"{'═' * 60}")

    checks = [
        (
            "Forbes Ave article returns a result",
            results["Clear disruption — Forbes Ave water main"] is not None
        ),
        (
            "Steelers article returns None",
            results["Non-disruption — Steelers news"] is None
        ),
        (
            "Forbes Ave result contains roads_affected",
            results["Clear disruption — Forbes Ave water main"] is not None
            and len(results["Clear disruption — Forbes Ave water main"].get("roads_affected", [])) > 0
        ),
        (
            "Forbes Ave result mentions Forbes",
            results["Clear disruption — Forbes Ave water main"] is not None
            and any("forbes" in r.lower()
                    for r in results["Clear disruption — Forbes Ave water main"].get("roads_affected", []))
        ),
        (
            "I-376 result contains multiple roads",
            results["Multi-road disruption — I-376 accident"] is not None
            and len(results["Multi-road disruption — I-376 accident"].get("roads_affected", [])) > 1
        ),
    ]

    passed = 0
    for description, condition in checks:
        status = "PASS" if condition else "FAIL"
        if condition:
            passed += 1
        print(f"  [{status}] {description}")

    print(f"\n{passed}/{len(checks)} assertions passed")

if __name__ == "__main__":
    run_tests()