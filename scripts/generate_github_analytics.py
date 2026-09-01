import json
import math
import os
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "OmarAlDahleh98")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT_DIR = "profile"


def api_get(path):
    url = "https://api.github.com" + path
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "github-profile-analytics",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def weeks_since(since, count=52):
    start = since - timedelta(days=since.weekday())
    return [start + timedelta(days=7 * i) for i in range(count)]


def commit_activity(repos, since):
    counts = Counter()
    for repo in repos:
        page = 1
        while page <= 10:
            params = urllib.parse.urlencode(
                {"since": since.isoformat().replace("+00:00", "Z"), "per_page": 100, "page": page}
            )
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
                bucket = bucket.replace(hour=0, minute=0, second=0, microsecond=0)
                counts[bucket.date()] += 1
            if stop or len(commits) < 100:
                break
            page += 1
    return counts


def language_bytes(repos):
    totals = Counter()
    for repo in repos:
        try:
            data = api_get(f"/repos/{OWNER}/{repo['name']}/languages")
            totals.update(data)
        except Exception:
            continue
    return totals


def esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def activity_svg(counts, labels):
    width, height = 1100, 330
    left, right, top, bottom = 70, 30, 50, 55
    plot_w, plot_h = width - left - right, height - top - bottom
    values = [counts.get(d.date(), 0) for d in labels]
    max_v = max(values) if values else 1
    points = []
    for i, value in enumerate(values):
        x = left + (plot_w * i / max(1, len(values) - 1))
        y = top + plot_h - (value / max_v) * plot_h
        points.append((x, y))
    path = " ".join(("M" if i == 0 else "L") + f" {x:.1f} {y:.1f}" for i, (x, y) in enumerate(points))
    area = path + f" L {left + plot_w:.1f} {top + plot_h:.1f} L {left:.1f} {top + plot_h:.1f} Z"

    grid = []
    for tick in range(0, 5):
        y = top + plot_h - (plot_h * tick / 4)
        val = round(max_v * tick / 4)
        grid.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#E5E7EB"/>')
        grid.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#6B7280">{val}</text>')

    label_idx = [0, 12, 24, 36, 48, 51]
    xlabels = []
    for i in label_idx:
        if i < len(labels):
            x = left + (plot_w * i / max(1, len(labels) - 1))
            text = labels[i].strftime("%b %Y")
            xlabels.append(f'<text x="{x:.1f}" y="{height - 18}" text-anchor="middle" font-size="12" fill="#6B7280">{esc(text)}</text>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" rx="18" fill="#FFFFFF"/>
<text x="35" y="34" font-family="Inter,Arial,sans-serif" font-size="18" font-weight="700" fill="#1F2937">GitHub Activity</text>
<text x="35" y="52" font-family="Inter,Arial,sans-serif" font-size="11" fill="#6B7280">Public commit activity · Last 12 months</text>
<path d="{area}" fill="#EAF7F0"/>
{''.join(grid)}
<path d="{path}" fill="none" stroke="#2EA44F" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
{''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.8" fill="#2EA44F"/>' for x, y in points)}
{''.join(xlabels)}
</svg>'''


def polar(cx, cy, r, angle):
    a = math.radians(angle - 90)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def donut_svg(langs):
    width, height = 700, 360
    cx, cy, r = 170, 180, 105
    palette = ["#2EA44F", "#6C63FF", "#F2C811", "#0A66C2", "#9CA3AF", "#111827"]
    items = langs.most_common(6)
    total = sum(v for _, v in items) or 1
    if not items:
        items = [("No language data", 1)]
        total = 1
    paths = []
    angle = 0
    for idx, (name, value) in enumerate(items):
        sweep = value / total * 360
        end = angle + sweep
        x1, y1 = polar(cx, cy, r, angle)
        x2, y2 = polar(cx, cy, r, end)
        large = 1 if sweep > 180 else 0
        path = f"M {x1:.2f} {y1:.2f} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f}"
        paths.append(f'<path d="{path}" fill="none" stroke="{palette[idx % len(palette)]}" stroke-width="34" stroke-linecap="butt"/>')
        angle = end

    rows = []
    y = 92
    for idx, (name, value) in enumerate(items):
        pct = value / total * 100
        rows.append(
            f'<circle cx="390" cy="{y - 4}" r="6" fill="{palette[idx % len(palette)]}"/>'
            f'<text x="408" y="{y}" font-family="Inter,Arial,sans-serif" font-size="14" font-weight="600" fill="#1F2937">{esc(name)}</text>'
            f'<text x="650" y="{y}" text-anchor="end" font-family="Inter,Arial,sans-serif" font-size="13" fill="#6B7280">{pct:.1f}%</text>'
        )
        y += 42

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" rx="18" fill="#FFFFFF"/>
<text x="35" y="38" font-family="Inter,Arial,sans-serif" font-size="18" font-weight="700" fill="#1F2937">Top Languages</text>
<text x="35" y="57" font-family="Inter,Arial,sans-serif" font-size="11" fill="#6B7280">Across public repositories</text>
<g transform="rotate(0 170 180)">{''.join(paths)}</g>
<circle cx="170" cy="180" r="76" fill="#FFFFFF"/>
<text x="170" y="176" text-anchor="middle" font-family="Inter,Arial,sans-serif" font-size="26" font-weight="800" fill="#1F2937">{len(langs)}</text>
<text x="170" y="197" text-anchor="middle" font-family="Inter,Arial,sans-serif" font-size="11" fill="#6B7280">languages</text>
{''.join(rows)}
</svg>'''


def main():
    since = datetime.now(timezone.utc) - timedelta(days=365)
    repos = api_get(f"/users/{OWNER}/repos?per_page=100&type=owner&sort=updated")
    repos = [r for r in repos if not r.get("fork") and not r.get("archived")]
    counts = commit_activity(repos, since)
    labels = weeks_since(since, 52)
    langs = language_bytes(repos)
    write_file(os.path.join(OUT_DIR, "github-activity.svg"), activity_svg(counts, labels))
    write_file(os.path.join(OUT_DIR, "github-languages.svg"), donut_svg(langs))


if __name__ == "__main__":
    main()
