"""Render a contributions card (total, current streak, longest streak) from the GitHub calendar.

The calendar includes private contribution counts, so the total matches the profile page.
"""

import json
import os
import sys
import urllib.request
from datetime import date, timedelta

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

THEMES = {
    "dark": {"bg": "#0D1117", "title": "#22D3EE", "accent": "#A78BFA", "text": "#C9D1D9", "muted": "#8B949E", "divider": "#30363D"},
    "light": {"bg": "#FFFFFF", "title": "#0969DA", "accent": "#8250DF", "text": "#24292F", "muted": "#57606A", "divider": "#D0D7DE"},
}


def fetch_calendar(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def streaks(days):
    counts = {date.fromisoformat(d["date"]): d["contributionCount"] for d in days}
    ordered = sorted(counts)

    longest = run = 0
    longest_range = (None, None)
    run_start = None
    for day in ordered:
        if counts[day] > 0:
            run_start = run_start or day
            run += 1
            if run > longest:
                longest, longest_range = run, (run_start, day)
        else:
            run, run_start = 0, None

    # Today not having a contribution yet should not break the current streak.
    cursor = ordered[-1]
    if counts[cursor] == 0:
        cursor -= timedelta(days=1)
    current, current_end = 0, cursor
    while counts.get(cursor, 0) > 0:
        current += 1
        cursor -= timedelta(days=1)
    current_range = (cursor + timedelta(days=1), current_end) if current else (None, None)

    return ordered[0], ordered[-1], current, current_range, longest, longest_range


def fmt_range(start, end):
    if not start:
        return "—"
    if start == end:
        return start.strftime("%b %d")
    return f"{start.strftime('%b %d')} – {end.strftime('%b %d')}"


def render(theme, total, first, last, current, current_range, longest, longest_range):
    t = THEMES[theme]
    font = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"
    columns = [
        (f"{total:,}", "Total Contributions", f"{first.strftime('%b %d, %Y')} – Present", t["text"]),
        (str(current), "Current Streak", fmt_range(*current_range), t["title"]),
        (str(longest), "Longest Streak", fmt_range(*longest_range), t["accent"]),
    ]
    parts = []
    for i, (value, label, sub, color) in enumerate(columns):
        x = 82 + i * 165
        parts.append(
            f'<text x="{x}" y="88" text-anchor="middle" fill="{color}" font-size="30" font-weight="700" font-family="{font}">{value}</text>'
            f'<text x="{x}" y="122" text-anchor="middle" fill="{t["text"]}" font-size="14" font-weight="600" font-family="{font}">{label}</text>'
            f'<text x="{x}" y="146" text-anchor="middle" fill="{t["muted"]}" font-size="12" font-family="{font}">{sub}</text>'
        )
    dividers = "".join(
        f'<line x1="{x}" y1="48" x2="{x}" y2="150" stroke="{t["divider"]}" stroke-width="1"/>' for x in (165, 330)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195" role="img" '
        f'aria-label="{total} contributions in the last year, current streak {current} days, longest streak {longest} days">'
        f'<rect width="495" height="195" rx="6" fill="{t["bg"]}"/>'
        f'<text x="25" y="32" fill="{t["title"]}" font-size="16" font-weight="600" font-family="{font}">Contributions in the last year</text>'
        f"{dividers}{''.join(parts)}"
        f'<text x="470" y="180" text-anchor="end" fill="{t["muted"]}" font-size="10" font-family="{font}">Updated {last.strftime("%b %d, %Y")}</text>'
        "</svg>"
    )


def main():
    login, out_dir = sys.argv[1], sys.argv[2]
    calendar = fetch_calendar(login, os.environ["GITHUB_TOKEN"])
    days = [d for week in calendar["weeks"] for d in week["contributionDays"]]
    first, last, current, current_range, longest, longest_range = streaks(days)

    os.makedirs(out_dir, exist_ok=True)
    for theme in THEMES:
        svg = render(theme, calendar["totalContributions"], first, last, current, current_range, longest, longest_range)
        with open(os.path.join(out_dir, f"contributions-{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(svg)
    print(f"total={calendar['totalContributions']} current={current} longest={longest}")


if __name__ == "__main__":
    main()
