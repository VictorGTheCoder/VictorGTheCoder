#!/usr/bin/env python3
"""Generate a representative engineering-profile SVG for the GitHub README."""

from __future__ import annotations

import html
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


GRAPHQL_URL = "https://api.github.com/graphql"
OUTPUT = Path("assets/engineering-metrics.svg")

QUERY = r"""
query EngineeringProfile($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    repositories(
      first: 100
      ownerAffiliations: [OWNER]
      isFork: false
      privacy: PUBLIC
      orderBy: {field: PUSHED_AT, direction: DESC}
    ) {
      totalCount
    }
    contributionsCollection(from: $from, to: $to) {
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      pullRequestContributionsByRepository(maxRepositories: 100) {
        contributions {
          totalCount
        }
        repository {
          owner {
            login
          }
        }
      }
    }
  }
}
"""


def graphql(token: str, variables: dict[str, str]) -> dict:
    payload = json.dumps({"query": QUERY, "variables": variables}).encode()
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "engineering-profile-svg",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)

    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], indent=2))
    return result["data"]["user"]


def safe(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_svg(login: str, user: dict, generated_at: datetime) -> str:
    contributions = user["contributionsCollection"]
    public_repos = user["repositories"]["totalCount"]
    prs = contributions["totalPullRequestContributions"]
    reviews = contributions["totalPullRequestReviewContributions"]
    issues = contributions["totalIssueContributions"]

    external_prs = 0
    external_repos = 0
    for item in contributions["pullRequestContributionsByRepository"]:
        if item["repository"]["owner"]["login"].lower() != login.lower():
            count = item["contributions"]["totalCount"]
            external_prs += count
            if count:
                external_repos += 1

    width, height = 900, 560
    metric_x = [32, 242, 452, 662]
    metrics = [
        ("PUBLIC REPOS", public_repos, "all-time, non-fork"),
        ("PULL REQUESTS", prs, "last 12 months"),
        ("CODE REVIEWS", reviews, "last 12 months"),
        ("EXTERNAL PRS", external_prs, f"{external_repos} external repos"),
    ]

    domains = [
        {
            "x": 32,
            "y": 240,
            "title": "SYSTEMS & LOW-LEVEL",
            "accent": "#f0883e",
            "stack": "C · C++ · graphics · concurrency · networking",
            "repos": "42_CPP · 42_miniRT · 42_Cube3D · philosophers",
        },
        {
            "x": 456,
            "y": 240,
            "title": "AI / ML / DATA",
            "accent": "#a371f7",
            "stack": "Python · ML · neural nets · algorithms",
            "repos": "IA-Journey · My-Own-AI · ChessIA-OpenGL · Project-Euler",
        },
        {
            "x": 32,
            "y": 356,
            "title": "BACKEND / WEB",
            "accent": "#58a6ff",
            "stack": "APIs · full-stack · automation · databases",
            "repos": "Tic-Tac-Toe-Website · API-Twitch · Puppeteer",
        },
        {
            "x": 456,
            "y": 356,
            "title": "INFRA / OPEN SOURCE",
            "accent": "#3fb950",
            "stack": "Linux · Docker · CI/CD · collaborative engineering",
            "repos": "inception · aegra · external PRs & reviews",
        },
    ]

    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Engineering profile</title>',
        f'<desc id="desc">Representative engineering profile for {safe(login)} combining public project history with recent GitHub collaboration signals.</desc>',
        "<style>",
        "text{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,'Liberation Mono',monospace}",
        ".muted{fill:#7d8590}.label{fill:#8b949e;font-size:11px;font-weight:600;letter-spacing:1.3px}",
        ".value{fill:#f0f6fc;font-size:28px;font-weight:700}.small{fill:#c9d1d9;font-size:12px}",
        ".tiny{fill:#7d8590;font-size:10px}.domain{fill:#f0f6fc;font-size:13px;font-weight:700;letter-spacing:.4px}",
        "</style>",
        '<rect x="1" y="1" width="898" height="558" rx="18" fill="#0d1117" stroke="#30363d"/>',
        '<circle cx="34" cy="33" r="5" fill="#3fb950"/>',
        '<text x="50" y="38" class="label">ENGINEERING PROFILE / BREADTH + RECENT SIGNAL</text>',
        f'<text x="32" y="78" fill="#f0f6fc" font-size="21" font-weight="700">{safe(login)}@github:~$ <tspan fill="#58a6ff">whoami --engineering</tspan></text>',
        '<text x="32" y="101" class="small muted">Systems foundations → software engineering → AI/data → open-source collaboration</text>',
        '<line x1="32" y1="118" x2="868" y2="118" stroke="#21262d"/>',
    ]

    for x, (label, value, note) in zip(metric_x, metrics):
        out.extend(
            [
                f'<rect x="{x}" y="138" width="188" height="80" rx="12" fill="#161b22" stroke="#30363d"/>',
                f'<text x="{x + 16}" y="163" class="label">{safe(label)}</text>',
                f'<text x="{x + 16}" y="194" class="value">{safe(value)}</text>',
                f'<text x="{x + 16}" y="209" class="tiny">{safe(note)}</text>',
            ]
        )

    for domain in domains:
        x = domain["x"]
        y = domain["y"]
        out.extend(
            [
                f'<rect x="{x}" y="{y}" width="412" height="98" rx="12" fill="#161b22" stroke="#30363d"/>',
                f'<rect x="{x}" y="{y}" width="5" height="98" rx="2.5" fill="{domain["accent"]}"/>',
                f'<text x="{x + 20}" y="{y + 27}" class="domain">{safe(domain["title"])}</text>',
                f'<text x="{x + 20}" y="{y + 52}" class="small">{safe(domain["stack"])}</text>',
                f'<text x="{x + 20}" y="{y + 76}" class="tiny">{safe(domain["repos"])}</text>',
            ]
        )

    out.extend(
        [
            '<line x1="32" y1="476" x2="868" y2="476" stroke="#21262d"/>',
            '<text x="32" y="503" class="label">REPRESENTATIVE STACK</text>',
            '<text x="32" y="528" class="small">C / C++ · Python · PHP · JavaScript / TypeScript · SQL · Docker · GitHub Actions</text>',
            f'<text x="868" y="503" class="tiny" text-anchor="end">recent GitHub signal: {issues} issues opened / 12m</text>',
            f'<text x="868" y="539" class="tiny" text-anchor="end">GraphQL + curated public project history · refreshed {safe(generated_at.strftime("%Y-%m-%d UTC"))}</text>',
            "</svg>",
        ]
    )

    return "\n".join(out) + "\n"


def main() -> None:
    token = os.environ.get("GH_TOKEN")
    login = os.environ.get("GH_LOGIN")
    if not token or not login:
        raise SystemExit("GH_TOKEN and GH_LOGIN are required")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365)
    variables = {
        "login": login,
        "from": start.isoformat().replace("+00:00", "Z"),
        "to": end.isoformat().replace("+00:00", "Z"),
    }
    user = graphql(token, variables)
    svg = render_svg(login, user, end)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
