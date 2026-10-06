#!/usr/bin/env python3
"""Generate a recruiter-friendly GitHub engineering telemetry SVG."""

from __future__ import annotations

import html
import json
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


GRAPHQL_URL = "https://api.github.com/graphql"
OUTPUT = Path("assets/engineering-metrics.svg")

QUERY = r"""
query EngineeringMetrics($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    repositories(
      first: 100
      ownerAffiliations: [OWNER]
      isFork: false
      privacy: PUBLIC
      orderBy: {field: PUSHED_AT, direction: DESC}
    ) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
              color
            }
          }
        }
      }
    }
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
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
      contributionCalendar {
        weeks {
          contributionDays {
            contributionCount
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
            "User-Agent": "engineering-metrics-svg",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)

    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], indent=2))
    return result["data"]["user"]


def compact(number: int) -> str:
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}m".rstrip("0").rstrip(".")
    if number >= 1_000:
        return f"{number / 1_000:.1f}k".rstrip("0").rstrip(".")
    return str(number)


def safe(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_svg(login: str, user: dict, generated_at: datetime) -> str:
    contributions = user["contributionsCollection"]
    repos = user["repositories"]

    commits = contributions["totalCommitContributions"]
    issues = contributions["totalIssueContributions"]
    prs = contributions["totalPullRequestContributions"]
    reviews = contributions["totalPullRequestReviewContributions"]

    external_prs = 0
    external_repos = 0
    for item in contributions["pullRequestContributionsByRepository"]:
        if item["repository"]["owner"]["login"].lower() != login.lower():
            count = item["contributions"]["totalCount"]
            external_prs += count
            if count:
                external_repos += 1

    stars = sum(repo["stargazerCount"] for repo in repos["nodes"])

    language_bytes: dict[str, int] = defaultdict(int)
    language_colors: dict[str, str] = {}
    for repo in repos["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            language_bytes[name] += edge["size"]
            language_colors[name] = edge["node"].get("color") or "#58a6ff"

    top_languages = sorted(
        language_bytes.items(), key=lambda item: item[1], reverse=True
    )[:4]
    language_total = sum(language_bytes.values()) or 1

    weeks = [
        sum(day["contributionCount"] for day in week["contributionDays"])
        for week in contributions["contributionCalendar"]["weeks"]
    ][-52:]
    if len(weeks) < 52:
        weeks = [0] * (52 - len(weeks)) + weeks
    max_week = max(weeks) or 1

    width, height = 900, 470
    metric_x = [32, 242, 452, 662]
    metrics = [
        ("COMMITS", commits),
        ("PULL REQUESTS", prs),
        ("REVIEWS", reviews),
        ("EXTERNAL PRS", external_prs),
    ]

    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Engineering telemetry</title>',
        f'<desc id="desc">GitHub engineering activity for {safe(login)} over the last twelve months.</desc>',
        "<style>",
        "text{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,'Liberation Mono',monospace}",
        ".muted{fill:#7d8590}.label{fill:#8b949e;font-size:11px;font-weight:600;letter-spacing:1.3px}",
        ".value{fill:#f0f6fc;font-size:28px;font-weight:700}.small{fill:#c9d1d9;font-size:12px}",
        "</style>",
        '<rect x="1" y="1" width="898" height="468" rx="18" fill="#0d1117" stroke="#30363d"/>',
        '<circle cx="34" cy="33" r="5" fill="#3fb950"/>',
        '<text x="50" y="38" class="label">ENGINEERING TELEMETRY / LAST 12 MONTHS</text>',
        f'<text x="32" y="78" fill="#f0f6fc" font-size="21" font-weight="700">{safe(login)}@github:~$ <tspan fill="#58a6ff">inspect --activity</tspan></text>',
        '<line x1="32" y1="98" x2="868" y2="98" stroke="#21262d"/>',
    ]

    for x, (label, value) in zip(metric_x, metrics):
        out.extend(
            [
                f'<rect x="{x}" y="120" width="188" height="82" rx="12" fill="#161b22" stroke="#30363d"/>',
                f'<text x="{x + 16}" y="147" class="label">{safe(label)}</text>',
                f'<text x="{x + 16}" y="181" class="value">{safe(compact(value))}</text>',
            ]
        )

    out.append('<text x="32" y="238" class="label">LANGUAGE FOOTPRINT / OWNED PUBLIC REPOS</text>')
    bar_x, bar_width = 158, 282
    for index in range(4):
        y = 267 + index * 31
        if index < len(top_languages):
            name, size = top_languages[index]
            pct = size / language_total
            color = language_colors[name]
            fill_width = max(3, round(bar_width * pct))
            out.extend(
                [
                    f'<text x="32" y="{y + 4}" class="small">{safe(name[:15])}</text>',
                    f'<rect x="{bar_x}" y="{y - 7}" width="{bar_width}" height="10" rx="5" fill="#21262d"/>',
                    f'<rect x="{bar_x}" y="{y - 7}" width="{fill_width}" height="10" rx="5" fill="{safe(color)}"/>',
                    f'<text x="452" y="{y + 4}" class="small">{pct * 100:4.1f}%</text>',
                ]
            )
        else:
            out.extend(
                [
                    f'<text x="32" y="{y + 4}" class="small muted">—</text>',
                    f'<rect x="{bar_x}" y="{y - 7}" width="{bar_width}" height="10" rx="5" fill="#21262d"/>',
                ]
            )

    out.extend(
        [
            '<text x="540" y="238" class="label">OPEN-SOURCE SIGNAL</text>',
            '<rect x="540" y="253" width="328" height="125" rx="12" fill="#161b22" stroke="#30363d"/>',
            '<text x="558" y="281" class="small muted">external repositories</text>',
            f'<text x="842" y="281" class="small" text-anchor="end">{external_repos}</text>',
            '<text x="558" y="310" class="small muted">owned public repositories</text>',
            f'<text x="842" y="310" class="small" text-anchor="end">{repos["totalCount"]}</text>',
            '<text x="558" y="339" class="small muted">stars on owned repositories</text>',
            f'<text x="842" y="339" class="small" text-anchor="end">{stars}</text>',
            '<text x="558" y="368" class="small muted">issues opened / 12m</text>',
            f'<text x="842" y="368" class="small" text-anchor="end">{issues}</text>',
            '<text x="32" y="405" class="label">ACTIVITY SIGNAL / 52 WEEKS</text>',
        ]
    )

    graph_x, graph_y = 32, 445
    graph_width, max_height = 836, 26
    gap = 3
    bar_w = (graph_width - gap * 51) / 52
    for i, value in enumerate(weeks):
        height_px = 3 if value == 0 else max(4, (value / max_week) * max_height)
        x = graph_x + i * (bar_w + gap)
        y = graph_y - height_px
        opacity = 0.35 + 0.65 * (value / max_week)
        out.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{height_px:.2f}" rx="1.5" fill="#2f81f7" opacity="{opacity:.2f}"/>'
        )

    timestamp = generated_at.strftime("%Y-%m-%d UTC")
    out.extend(
        [
            f'<text x="868" y="459" class="muted" font-size="9" text-anchor="end">GraphQL → SVG · refreshed {safe(timestamp)}</text>',
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
