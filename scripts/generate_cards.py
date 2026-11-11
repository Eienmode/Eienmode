"""Generate the profile's live stat cards as SVG files.

Runs inside GitHub Actions (see .github/workflows/cards.yml) with a personal
access token in the GH_TOKEN env var, so it can see private repos too.
Only totals are drawn - private repo names are never written to the cards.

Local preview without a token:  python scripts/generate_cards.py --sample
"""

import json
import os
import sys
import urllib.request
from datetime import date, datetime, timezone
from html import escape

OUT_DIR = os.environ.get("CARDS_OUT", "cards")

# Theme: Tokyo Night base with red / pink / purple accents
BG = "#1a1b27"
BORDER = "#2a2b3d"
TITLE = "#ff4f8b"
TEXT = "#c0caf5"
MUTED = "#565f89"
PURPLE = "#9d4edd"
LILAC = "#bb9af7"
RED = "#e0245e"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"
W = 840

QUERY = """
query($cursor: String) {
  viewer {
    login
    name
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY]) { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 50, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


# ---------------------------------------------------------------- data

def graphql(token, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise SystemExit(f"GitHub API error: {payload['errors']}")
    return payload["data"]["viewer"]


def fetch(token):
    cursor, first, repos = None, None, []
    while True:
        viewer = graphql(token, {"cursor": cursor})
        first = first or viewer
        repos += viewer["repositories"]["nodes"]
        page = viewer["repositories"]["pageInfo"]
        if not page["hasNextPage"]:
            break
        cursor = page["endCursor"]

    langs = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            entry = langs.setdefault(name, {"bytes": 0, "repos": 0, "color": edge["node"]["color"] or LILAC})
            entry["bytes"] += edge["size"]
            entry["repos"] += 1

    cc = first["contributionsCollection"]
    days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    return {
        "login": first["login"],
        "languages": langs,
        "stats": {
            "Total stars": sum(r["stargazerCount"] for r in repos),
            "Commits (past year)": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
            "Contributions (past year)": cc["contributionCalendar"]["totalContributions"],
            "Pull requests": first["pullRequests"]["totalCount"],
            "Issues": first["issues"]["totalCount"],
            "Repositories": first["repositories"]["totalCount"],
            "Contributed to": first["repositoriesContributedTo"]["totalCount"],
            "Followers": first["followers"]["totalCount"],
        },
        "days": [(d["date"], d["contributionCount"]) for d in days],
    }


def sample():
    import random
    random.seed(4)
    names = [("HTML", "#e34c26", 350000, 9), ("JavaScript", "#f1e05a", 5400, 7), ("CSS", "#663399", 4100, 8),
             ("Python", "#3572A5", 3900, 4), ("TypeScript", "#3178c6", 2200, 2), ("C#", "#178600", 1800, 2),
             ("Java", "#b07219", 1300, 1), ("C++", "#f34b7d", 900, 1), ("Shell", "#89e051", 400, 3),
             ("PHP", "#4F5D95", 300, 1), ("Lua", "#000080", 150, 1), ("Batchfile", "#C1F12E", 90, 1),
             ("PowerShell", "#012456", 60, 1), ("Dockerfile", "#384d54", 20, 1)]
    today = date.today().toordinal()
    return {
        "login": "Eienmode",
        "languages": {n: {"bytes": b, "repos": r, "color": c} for n, c, b, r in names},
        "stats": {"Total stars": 12, "Commits (past year)": 188, "Contributions (past year)": 203,
                  "Pull requests": 5, "Issues": 3, "Repositories": 21, "Contributed to": 4, "Followers": 9},
        "days": [(date.fromordinal(today - i).isoformat(), max(0, int(random.gauss(2, 3))))
                 for i in range(364, -1, -1)],
    }


# ---------------------------------------------------------------- svg helpers

def short(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(n)


def size(b):
    for unit in ("B", "kB", "MB", "GB"):
        if b < 1000 or unit == "GB":
            return f"{b:.0f} {unit}" if unit == "B" else f"{b:.1f} {unit}"
        b /= 1000


def card(height, body, title, subtitle=""):
    sub = (f'<text x="{W - 25}" y="38" text-anchor="end" class="muted">{escape(subtitle)}</text>'
           if subtitle else "")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" fill="none" role="img">
<title>{escape(title)}</title>
<style>
  text {{ font-family: {FONT}; }}
  .title {{ font-size: 19px; font-weight: 700; fill: {TITLE}; }}
  .muted {{ font-size: 12px; fill: {MUTED}; }}
  .label {{ font-size: 13px; fill: {TEXT}; }}
  .fade {{ opacity: 0; animation: fade .5s ease-out forwards; }}
  @keyframes fade {{ to {{ opacity: 1; }} }}
  @keyframes grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{height - 1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
<text x="25" y="38" class="title">{escape(title)}</text>
{sub}
{body}
</svg>
"""


# ---------------------------------------------------------------- cards

def languages_card(langs):
    items = sorted(langs.items(), key=lambda kv: kv[1]["bytes"], reverse=True)
    total = sum(v["bytes"] for _, v in items) or 1
    top_name, top = items[0]
    by_repos_name, by_repos = max(items, key=lambda kv: (kv[1]["repos"], kv[1]["bytes"]))
    parts = []

    # Highlight: most used language
    parts.append(f'<text x="25" y="70" class="muted">MOST USED</text>')
    parts.append(f'<circle cx="34" cy="96" r="8" fill="{top["color"]}"/>')
    parts.append(f'<text x="50" y="105" style="font-size:28px;font-weight:800;fill:{TEXT}">{escape(top_name)}</text>')
    parts.append(f'<text x="50" y="125" class="muted">{top["bytes"] / total * 100:.2f}% of all my code · {size(top["bytes"])}</text>')
    parts.append(f'<text x="{W - 25}" y="70" text-anchor="end" class="muted">IN THE MOST REPOS</text>')
    parts.append(f'<text x="{W - 25}" y="105" text-anchor="end" style="font-size:22px;font-weight:700;fill:{LILAC}">{escape(by_repos_name)}</text>')
    parts.append(f'<text x="{W - 25}" y="125" text-anchor="end" class="muted">used in {by_repos["repos"]} repos</text>')

    # Stacked bar (every language gets at least a sliver so it is visible)
    bar_y, bar_w = 145, W - 50
    min_w = 3
    widths = [max(min_w, v["bytes"] / total * bar_w) for _, v in items]
    scale = bar_w / sum(widths)
    x = 25.0
    segs = []
    for (name, v), w in zip(items, widths):
        w *= scale
        segs.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{w + 0.5:.2f}" height="12" fill="{v["color"]}"><title>{escape(name)}</title></rect>')
        x += w
    parts.append(f'<clipPath id="bar"><rect x="25" y="{bar_y}" width="{bar_w}" height="12" rx="6"/></clipPath>')
    parts.append(f'<g clip-path="url(#bar)" style="transform-origin:25px 0;animation:grow .9s ease-out">{"".join(segs)}</g>')

    # Full list, 3 columns
    cols, row_h, list_y = 3, 30, bar_y + 45
    col_w = (W - 50) / cols
    rows = (len(items) + cols - 1) // cols
    for i, (name, v) in enumerate(items):
        col, row = i // rows, i % rows
        cx = 25 + col * col_w
        cy = list_y + row * row_h
        pct = v["bytes"] / total * 100
        pct_s = f"{pct:.2f}%" if pct >= 0.01 else "<0.01%"
        repos = f'{v["repos"]} repo' + ("s" if v["repos"] != 1 else "")
        parts.append(
            f'<g class="fade" style="animation-delay:{0.15 + i * 0.05:.2f}s">'
            f'<circle cx="{cx + 6}" cy="{cy - 4}" r="5" fill="{v["color"]}"/>'
            f'<text x="{cx + 18}" y="{cy}" class="label">{escape(name)}</text>'
            f'<text x="{cx + col_w - 20}" y="{cy}" text-anchor="end" class="label" style="fill:{LILAC}">{escape(pct_s)}</text>'
            f'<text x="{cx + 18}" y="{cy + 13}" class="muted" style="font-size:10px">{repos} · {size(v["bytes"])}</text>'
            f'</g>'
        )

    height = int(list_y + rows * row_h + 10)
    return card(height, "\n".join(parts), "Languages I use",
                f"{len(items)} languages across all my repos (incl. private)")


def stats_card(stats):
    items = list(stats.items())
    cols = 4
    tile_w = (W - 50) / cols
    parts = []
    palette = [TITLE, LILAC, RED, PURPLE]
    for i, (label, value) in enumerate(items):
        col, row = i % cols, i // cols
        cx = 25 + col * tile_w + tile_w / 2
        cy = 95 + row * 80
        parts.append(
            f'<g class="fade" style="animation-delay:{0.1 + i * 0.07:.2f}s">'
            f'<text x="{cx}" y="{cy}" text-anchor="middle" style="font-size:30px;font-weight:800;fill:{palette[i % 4]}">{short(value)}</text>'
            f'<text x="{cx}" y="{cy + 22}" text-anchor="middle" class="label">{escape(label)}</text>'
            f'</g>'
        )
    rows = (len(items) + cols - 1) // cols
    height = 95 + (rows - 1) * 80 + 45
    updated = datetime.now(timezone.utc).strftime("updated %b %d, %Y %H:%M UTC")
    return card(height, "\n".join(parts), "GitHub stats", updated)


def activity_card(days, n=31):
    days = days[-n:]
    counts = [c for _, c in days]
    peak = max(max(counts), 1)
    top = max(4, peak + (-peak % 4))  # round axis up to a multiple of 4
    left, right, y0, y1 = 60, W - 25, 70, 240
    step = (right - left) / (len(days) - 1)
    pts = [(left + i * step, y1 - c / top * (y1 - y0)) for i, c in enumerate(counts)]
    parts = []
    for k in range(5):  # grid + y labels
        val = top * k / 4
        y = y1 - k / 4 * (y1 - y0)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="{BORDER}" stroke-dasharray="3 4"/>')
        parts.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" class="muted">{val:g}</text>')
    for i, (d, _) in enumerate(days):  # x labels every 5 days
        if i % 5 == 0 or i == len(days) - 1:
            label = datetime.fromisoformat(d).strftime("%b %d")
            anchor = "end" if i == len(days) - 1 else "start" if i == 0 else "middle"
            parts.append(f'<text x="{pts[i][0]:.1f}" y="{y1 + 22}" text-anchor="{anchor}" class="muted">{label}</text>')
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{left},{y1} {line} {right},{y1}"
    parts.append(f'<defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0" stop-color="{PURPLE}" stop-opacity=".55"/>'
                 f'<stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></linearGradient>'
                 f'<linearGradient id="stroke" x1="0" y1="0" x2="1" y2="0">'
                 f'<stop offset="0" stop-color="{RED}"/><stop offset=".5" stop-color="{TITLE}"/>'
                 f'<stop offset="1" stop-color="{PURPLE}"/></linearGradient></defs>')
    parts.append(f'<polygon points="{area}" fill="url(#fill)" class="fade"/>')
    parts.append(f'<polyline points="{line}" stroke="url(#stroke)" stroke-width="2.5" stroke-linejoin="round" fill="none" class="fade"/>')
    for (x, y), (d, c) in zip(pts, days):
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{BG}" stroke="{TITLE}" stroke-width="2" class="fade">'
                     f'<title>{d}: {c} contributions</title></circle>')
    total = sum(counts)
    return card(285, "\n".join(parts), f"Contributions · last {n} days", f"{total} contributions")


# ---------------------------------------------------------------- main

def main():
    if "--sample" in sys.argv:
        data = sample()
    else:
        token = os.environ.get("GH_TOKEN")
        if not token:
            raise SystemExit("GH_TOKEN is not set")
        data = fetch(token)
    os.makedirs(OUT_DIR, exist_ok=True)
    outputs = {
        "languages.svg": languages_card(data["languages"]) if data["languages"] else None,
        "stats.svg": stats_card(data["stats"]),
        "activity.svg": activity_card(data["days"]),
    }
    for name, svg in outputs.items():
        if svg:
            with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
                f.write(svg)
            print("wrote", name)


if __name__ == "__main__":
    main()
