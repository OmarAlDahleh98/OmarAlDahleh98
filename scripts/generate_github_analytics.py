import json
import math
import os
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "OmarAlDahleh98")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT_DIR = "profile"

BG = "#0D1117"
TEXT = "#E6EDF3"
MUTED = "#8B949E"
GRID = "#30363D"
PURPLE = "#A855F7"
PURPLE_SOFT = "#24153A"
MINT = "#6FFFE9"


def api_get(path):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "github-profile-analytics",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def weekly_labels(since, count=52):
    start = since - timedelta(days=since.weekday())
    return [start + timedelta(days=7 * i) for i in range(count)]


def commit_activity(repos, since):
    counts = Counter()
    for repo in repos:
        for page in range(1, 11):
            params = urllib.parse.urlencode({"since": since.isoformat().replace("+00:00", "Z"), "per_page": 100, "page": page})
            commits = api_get(f"/repos/{OWNER}/{repo['name']}/commits?{params}")
            if not commits:
                break
            stop = False
            for item in commits:
                stamp = item.get("commit", {}).get("author", {}).get("date")
                if not stamp:
                    continue
                dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                if dt < since:
                    stop = True
                    break
                bucket = dt - timedelta(days=dt.weekday())
                counts[bucket.date()] += 1
            if stop or len(commits) < 100:
                break
    return counts


def language_bytes(repos):
    totals = Counter()
    for repo in repos:
        try:
            totals.update(api_get(f"/repos/{OWNER}/{repo['name']}/languages"))
        except Exception:
            pass
    return totals


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def activity_svg(counts, labels):
    width, height = 1100, 330
    left, right, top, bottom = 70, 30, 70, 55
    pw, ph = width - left - right, height - top - bottom
    values = [counts.get(d.date(), 0) for d in labels]
    max_v = max(values or [1])
    points = []
    for i, value in enumerate(values):
        x = left + pw * i / max(1, len(values) - 1)
        y = top + ph - (value / max_v) * ph
        points.append((x, y))
    path = " ".join(("M" if i == 0 else "L") + f" {x:.1f} {y:.1f}" for i, (x, y) in enumerate(points))
    area = path + f" L {left + pw} {top + ph} L {left} {top + ph} Z"
    grid = []
    for tick in range(5):
        y = top + ph - ph * tick / 4
        value = round(max_v * tick / 4)
        grid.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+pw}" y2="{y:.1f}" stroke="{GRID}"/>')
        grid.append(f'<text x="{left-12}" y="{y+4:.1f}" text-anchor="end" font-size="12" fill="{MUTED}">{value}</text>')
    labels_svg = []
    for i in [0, 12, 24, 36, 48, 51]:
        if i < len(labels):
            x = left + pw * i / max(1, len(labels)-1)
            labels_svg.append(f'<text x="{x:.1f}" y="{height-18}" text-anchor="middle" font-size="12" fill="{MUTED}">{esc(labels[i].strftime("%b %Y"))}</text>')
    dots = ''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{MINT}"/>' for x, y in points if y < top + ph)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" rx="18" fill="{BG}"/>
<text x="35" y="35" font-family="Arial,sans-serif" font-size="18" font-weight="700" fill="{TEXT}">GitHub Activity</text>
<text x="35" y="53" font-family="Arial,sans-serif" font-size="11" fill="{MUTED}">Public commit activity · Last 12 months</text>
{''.join(grid)}
<path d="{area}" fill="{PURPLE_SOFT}"/>
<path d="{path}" fill="none" stroke="{PURPLE}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
{dots}
{''.join(labels_svg)}
<text x="35" y="312" font-family="Arial,sans-serif" font-size="11" fill="{MUTED}">Local SVG asset · refreshed by GitHub Actions</text>
</svg>'''


def polar(cx, cy, r, angle):
    a = math.radians(angle - 90)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def donut_svg(langs):
    width, height = 700, 360
    cx, cy, r = 170, 180, 105
    palette = [PURPLE, MINT, "#7C83FD", "#2EA44F", "#F2C811", "#FF4ECD"]
    items = langs.most_common(6) or [("Portfolio", 1)]
    total = sum(v for _, v in items) or 1
    parts = []
    angle = 0
    for i, (name, value) in enumerate(items):
        sweep = value / total * 360
        end = angle + sweep
        x1, y1 = polar(cx, cy, r, angle)
        x2, y2 = polar(cx, cy, r, end)
        large = 1 if sweep > 180 else 0
        d = f"M {x1:.2f} {y1:.2f} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f}"
        parts.append(f'<path d="{d}" fill="none" stroke="{palette[i % len(palette)]}" stroke-width="34"/>')
        angle = end
    rows = []
    y = 92
    for i, (name, value) in enumerate(items):
        pct = value / total * 100
        rows.append(f'<circle cx="390" cy="{y-4}" r="6" fill="{palette[i % len(palette)]}"/><text x="408" y="{y}" font-family="Arial,sans-serif" font-size="14" font-weight="600" fill="{TEXT}">{esc(name)}</text><text x="650" y="{y}" text-anchor="end" font-family="Arial,sans-serif" font-size="13" fill="{MUTED}">{pct:.1f}%</text>')
        y += 42
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" rx="18" fill="{BG}"/>
<text x="35" y="38" font-family="Arial,sans-serif" font-size="18" font-weight="700" fill="{TEXT}">Analytics Stack</text>
<text x="35" y="57" font-family="Arial,sans-serif" font-size="11" fill="{MUTED}">Core technologies used across the portfolio</text>
{''.join(parts)}
<circle cx="170" cy="180" r="71" fill="{BG}"/>
<text x="170" y="176" text-anchor="middle" font-family="Arial,sans-serif" font-size="24" font-weight="800" fill="{PURPLE}">BI</text>
<text x="170" y="197" text-anchor="middle" font-family="Arial,sans-serif" font-size="11" fill="{MUTED}">portfolio</text>
<g>{''.join(rows)}</g>
<text x="35" y="330" font-family="Arial,sans-serif" font-size="11" fill="{MUTED}">Static repository asset · no external image service required</text>
</svg>'''


def main():
    since = datetime.now(timezone.utc) - timedelta(days=365)
    repos = api_get(f"/users/{OWNER}/repos?per_page=100&type=owner&sort=updated")
    repos = [r for r in repos if not r.get("fork") and not r.get("archived")]
    counts = commit_activity(repos, since)
    labels = weekly_labels(since)
    langs = language_bytes(repos)
    write(f"{OUT_DIR}/github-activity.svg", activity_svg(counts, labels))
    write(f"{OUT_DIR}/github-languages.svg", donut_svg(langs))


if __name__ == "__main__":
    main()
