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

# Edit these to change the "About me" card (keep each value under ~45 characters)
ABOUT = [
    ("working_on", "whatever's in my pinned repos"),
    ("learning", "something new every week"),
    ("fun_fact", "this profile updates itself"),
]

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

def graphql(token, variables, query=QUERY):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
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

    history = fetch_history(token)

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
        "weeks": [[(d["date"], d["contributionCount"]) for d in w["contributionDays"]]
                  for w in cc["contributionCalendar"]["weeks"]],
        # recent days from the main calendar win, so the streak card always matches it
        "history": sorted({**dict(history),
                           **{d["date"]: d["contributionCount"] for d in days}}.items()),
    }


def fetch_history(token):
    """Every day since the first contribution year (for all-time streaks and totals)."""
    years = graphql(token, {}, "query { viewer { contributionsCollection { contributionYears } } }")
    years = sorted(years["contributionsCollection"]["contributionYears"])
    fields = "\n".join(
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") '
        f'{{ contributionCalendar {{ weeks {{ contributionDays {{ date contributionCount }} }} }} }}'
        for y in years)
    data = graphql(token, {}, f"query {{ viewer {{ {fields} }} }}")
    today = date.today().isoformat()
    days = {}
    for y in years:
        for w in data[f"y{y}"]["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                if d["date"] <= today:
                    days[d["date"]] = d["contributionCount"]
    return sorted(days.items())


def sample():
    import random
    random.seed(4)
    names = [("HTML", "#e34c26", 350000, 9), ("JavaScript", "#f1e05a", 5400, 7), ("CSS", "#663399", 4100, 8),
             ("Python", "#3572A5", 3900, 4), ("TypeScript", "#3178c6", 2200, 2), ("C#", "#178600", 1800, 2),
             ("Java", "#b07219", 1300, 1), ("C++", "#f34b7d", 900, 1), ("Shell", "#89e051", 400, 3),
             ("PHP", "#4F5D95", 300, 1), ("Lua", "#000080", 150, 1), ("Batchfile", "#C1F12E", 90, 1),
             ("PowerShell", "#012456", 60, 1), ("Dockerfile", "#384d54", 20, 1)]
    today = date.today().toordinal()
    start = today - 364 - (date.fromordinal(today - 364).isoweekday() % 7)  # back to Sunday
    days_all = [(date.fromordinal(o).isoformat(), max(0, int(random.gauss(1, 4))))
                for o in range(start, today + 1)]
    weeks = [days_all[i:i + 7] for i in range(0, len(days_all), 7)]
    return {
        "history": days_all,
        "weeks": weeks,
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


def card(height, body, title, subtitle="", width=W):
    sub = (f'<text x="{width - 25}" y="38" text-anchor="end" class="muted">{escape(subtitle)}</text>'
           if subtitle else "")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" role="img">
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
<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
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


def heatmap_card(weeks):
    """Full-year contribution calendar: every day readable, with month labels,
    a legend, hover tooltips and a few summary numbers."""
    levels = ["#24253a", "#4a1d5c", "#7b2d8e", "#c2357a", "#ff4f8b"]
    days = [d for w in weeks for d in w]
    nonzero = sorted(c for _, c in days if c > 0)

    def q(p):
        return nonzero[min(len(nonzero) - 1, int(p * len(nonzero)))] if nonzero else 1

    cuts = [q(0.25), q(0.5), q(0.75)]

    def level(c):
        if c == 0:
            return 0
        return 1 + sum(c > cut for cut in cuts)

    cell, gap = 11, 3
    pitch = cell + gap
    grid_w = len(weeks) * pitch - gap
    left = (W - grid_w) / 2 + 14
    top = 92
    parts = []

    # summary numbers
    total = sum(c for _, c in days)
    active = sum(1 for _, c in days if c > 0)
    best_d, best_c = max(days, key=lambda d: d[1]) if days else ("", 0)
    best_label = datetime.fromisoformat(best_d).strftime("%b %d") if best_d else "-"
    summary = [(short(total), "contributions"), (str(active), "active days"),
               (f"{best_c}", f"best day · {best_label}")]
    sx = (W - 50) / len(summary)
    colors = [TITLE, LILAC, RED]
    for i, (val, label) in enumerate(summary):
        x = 25 + sx * i + sx / 2
        parts.append(f'<text x="{x:.0f}" y="62" text-anchor="middle" style="font-size:16px;font-weight:800;fill:{colors[i]}">{escape(val)}'
                     f'<tspan style="font-size:11px;font-weight:400;fill:{MUTED}"> {escape(label)}</tspan></text>')

    # month labels
    last_month = None
    for wi, week in enumerate(weeks):
        m = datetime.fromisoformat(week[0][0]).strftime("%b")
        if m != last_month:
            if wi < len(weeks) - 2:
                parts.append(f'<text x="{left + wi * pitch:.1f}" y="{top - 8}" class="muted">{m}</text>')
            last_month = m
    # weekday labels
    for r, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        parts.append(f'<text x="{left - 8:.1f}" y="{top + r * pitch + 9}" text-anchor="end" class="muted" style="font-size:10px">{name}</text>')

    # cells, revealed week by week
    for wi, week in enumerate(weeks):
        cells = []
        for d, c in week:
            r = (datetime.fromisoformat(d).isoweekday() % 7)
            nice = datetime.fromisoformat(d).strftime("%a %b %d, %Y")
            cells.append(f'<rect x="{left + wi * pitch:.1f}" y="{top + r * pitch}" width="{cell}" height="{cell}" rx="2.5" '
                         f'fill="{levels[level(c)]}"><title>{c} contribution{"s" if c != 1 else ""} on {nice}</title></rect>')
        parts.append(f'<g class="fade" style="animation-delay:{wi * 0.018:.3f}s">{"".join(cells)}</g>')

    # legend
    ly = top + 7 * pitch + 18
    lx = left + grid_w - 5 * pitch - 40
    parts.append(f'<text x="{lx - 8:.1f}" y="{ly + 9}" text-anchor="end" class="muted">Less</text>')
    for i, colr in enumerate(levels):
        parts.append(f'<rect x="{lx + i * pitch:.1f}" y="{ly}" width="{cell}" height="{cell}" rx="2.5" fill="{colr}"/>')
    parts.append(f'<text x="{lx + 5 * pitch + 6:.1f}" y="{ly + 9}" class="muted">More</text>')

    return card(int(ly + 32), "\n".join(parts), "Contributions · past year", "")


def streaks(days):
    """-> (current, cur_start, cur_end, longest, long_start, long_end).
    Today with 0 contributions doesn't break the current streak yet."""
    longest = run = 0
    long_s = long_e = run_s = None
    for d, c in days:
        if c > 0:
            if run == 0:
                run_s = d
            run += 1
            if run > longest:
                longest, long_s, long_e = run, run_s, d
        else:
            run = 0
    cur, cur_s, cur_e = 0, None, None
    for i, (d, c) in enumerate(reversed(days)):
        if c > 0:
            cur += 1
            cur_s = d
            cur_e = cur_e or d
        elif i > 0:
            break
    return cur, cur_s, cur_e, longest, long_s, long_e


def span(a, b):
    if not a:
        return "-"
    fa, fb = datetime.fromisoformat(a), datetime.fromisoformat(b)
    if a == b:
        return fa.strftime("%b %d")
    if fa.year != fb.year:
        return f"{fa.strftime('%b %d, %Y')} – {fb.strftime('%b %d, %Y')}"
    return f"{fa.strftime('%b %d')} – {fb.strftime('%b %d')}"


SIDE_W, SIDE_H = 410, 200


def streak_card(history):
    cur, cs, ce, longest, ls, le = streaks(history)
    total = sum(c for _, c in history)
    first = next((d for d, c in history if c > 0), None)
    since = f"since {datetime.fromisoformat(first).strftime('%b %Y')}" if first else ""
    cx = SIDE_W / 2
    cy = 104
    r = 36
    circ = 2 * 3.14159 * r
    parts = [
        f'<defs><linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{RED}"/><stop offset=".5" stop-color="{TITLE}"/>'
        f'<stop offset="1" stop-color="{PURPLE}"/></linearGradient></defs>',
        f'<style>.ring {{ stroke-dasharray: {circ:.1f}; stroke-dashoffset: {circ:.1f}; '
        f'animation: draw 1.2s ease-out .2s forwards; }} @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}</style>',
        f'<circle cx="{cx}" cy="{cy}" r="{r}" stroke="{BORDER}" stroke-width="6" fill="none"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{r}" stroke="url(#ring)" stroke-width="6" fill="none" '
        f'stroke-linecap="round" class="ring" transform="rotate(-90 {cx} {cy})"/>',
        f'<rect x="{cx - 11}" y="{cy - r - 13}" width="22" height="24" fill="{BG}"/>',
        f'<path transform="translate({cx - 9} {cy - r - 13}) scale(.75)" fill="{RED}" '
        f'd="M12 0c1 5 9 9 9 17a9 9 0 0 1-18 0c0-4 2-7 4-9 0 4 2 6 4 7 0-6-3-10 1-15z"/>',
        f'<text x="{cx}" y="{cy + 10}" text-anchor="middle" class="fade" '
        f'style="font-size:30px;font-weight:800;fill:{TITLE};animation-delay:.4s">{cur}</text>',
        f'<text x="{cx}" y="{cy + 64}" text-anchor="middle" style="font-size:13px;font-weight:700;fill:{TITLE}">Current streak</text>',
        f'<text x="{cx}" y="{cy + 81}" text-anchor="middle" class="muted" style="font-size:11px">{escape(span(cs, ce))}</text>',
    ]
    for x, val, label, sub, color in ((68, short(total), "Total contributions", since, LILAC),
                                      (SIDE_W - 68, str(longest), "Longest streak", span(ls, le), PURPLE)):
        parts.append(
            f'<g class="fade" style="animation-delay:.3s">'
            f'<text x="{x}" y="{cy + 10}" text-anchor="middle" style="font-size:28px;font-weight:800;fill:{color}">{val}</text>'
            f'<text x="{x}" y="{cy + 64}" text-anchor="middle" class="label">{escape(label)}</text>'
            f'<text x="{x}" y="{cy + 81}" text-anchor="middle" class="muted" style="font-size:11px">{escape(sub)}</text></g>')
    for x in (SIDE_W / 2 - 72, SIDE_W / 2 + 72):
        parts.append(f'<line x1="{x}" y1="66" x2="{x}" y2="180" stroke="{BORDER}"/>')
    return card(SIDE_H, "\n".join(parts), "Streaks", "", width=SIDE_W)


def about_card():
    mono = "font-family:'Fira Code', Consolas, 'Courier New', monospace"
    parts = ["<style>.blink { animation: blink 1s steps(1) infinite; } "
             "@keyframes blink { 50% { opacity: 0; } }</style>"]
    for i, (key, value) in enumerate(ABOUT):
        y = 70 + i * 40
        parts.append(
            f'<g class="fade" style="animation-delay:{0.2 + i * 0.25:.2f}s">'
            f'<text x="25" y="{y}" style="{mono};font-size:12px;fill:{MUTED}">'
            f'<tspan fill="{TITLE}">&gt;</tspan> {escape(key)}</text>'
            f'<text x="39" y="{y + 19}" style="{mono};font-size:13.5px;fill:{TEXT}">{escape(value)}</text></g>')
    y = 70 + len(ABOUT) * 40 + 2
    parts.append(f'<text x="25" y="{y}" style="{mono};font-size:13px;fill:{TITLE}">&gt; '
                 f'<tspan class="blink">_</tspan></text>')
    return card(SIDE_H, "\n".join(parts), "About me", "~/eienmode", width=SIDE_W)


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
        "contributions.svg": heatmap_card(data["weeks"]),
        "streak.svg": streak_card(data["history"]),
        "about.svg": about_card(),
    }
    for name, svg in outputs.items():
        if svg:
            with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
                f.write(svg)
            print("wrote", name)


if __name__ == "__main__":
    main()
