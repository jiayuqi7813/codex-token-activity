#!/usr/bin/env python3
"""Generate a GitHub-profile-friendly Codex token activity SVG."""

from __future__ import annotations

import argparse
import getpass
import json
import math
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


API_URL = "https://chatgpt.com/backend-api/wham/profiles/me"


def request_profile(token: str) -> dict[str, Any]:
    token = token.removeprefix("Bearer ").strip()
    req = urllib.request.Request(
        API_URL,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "originator": "Codex Desktop",
            "User-Agent": "Codex Desktop profile-svg-export",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"Request failed: HTTP {exc.code}", file=sys.stderr)
        print(body[:500], file=sys.stderr)
        raise SystemExit(1) from exc


def demo_profile() -> dict[str, Any]:
    today = date.today()
    start = today - timedelta(days=364)
    buckets = []
    for i in range(365):
        day = start + timedelta(days=i)
        growth = max(0, i - 210) / 155
        wave = (math.sin(i / 9) + 1) / 2
        active = i > 250 and (i % 5 in (0, 1, 3) or wave > 0.72)
        tokens = 0 if not active else int((growth * 0.7 + wave * 0.3) * 820_000_000)
        if i > 330 and i % 3 != 2:
            tokens = max(tokens, int((0.45 + wave * 0.55) * 820_000_000))
        buckets.append({"start_date": day.isoformat(), "tokens": tokens})
    return {
        "profile": {
            "display_name": "xueshang xue",
            "username": "sn1war",
            "image_url": None,
        },
        "stats": {
            "lifetime_tokens": 9_400_000_000,
            "peak_daily_tokens": 820_000_000,
            "longest_running_turn_sec": 8 * 3600 + 51 * 60,
            "current_streak_days": 7,
            "longest_streak_days": 7,
            "daily_usage_buckets": buckets,
        },
    }


def human_tokens(value: int | float | None) -> str:
    if value is None:
        return "-"
    value = float(value)
    if value >= 1_000_000_000:
        shown = value / 1_000_000_000
        return f"{shown:.1f}B".replace(".0B", "B")
    if value >= 1_000_000:
        shown = value / 1_000_000
        return f"{shown:.1f}M".replace(".0M", "M")
    if value >= 1_000:
        shown = value / 1_000
        return f"{shown:.1f}K".replace(".0K", "K")
    return f"{int(value)}"


def human_duration(seconds: int | float | None) -> str:
    if seconds is None:
        return "-"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def color_for(tokens: int, peak: int) -> str:
    if tokens <= 0 or peak <= 0:
        return "#f1f3f5"
    ratio = tokens / peak
    if ratio < 0.18:
        return "#d7ebff"
    if ratio < 0.38:
        return "#add7ff"
    if ratio < 0.62:
        return "#79bbf7"
    if ratio < 0.82:
        return "#3f9df2"
    return "#147bd1"


def normalize_buckets(stats: dict[str, Any]) -> dict[str, int]:
    usage = stats.get("daily_usage_buckets") or []
    result: dict[str, int] = {}
    for bucket in usage:
        day = bucket.get("start_date")
        tokens = bucket.get("tokens")
        if isinstance(day, str) and isinstance(tokens, (int, float)):
            result[day[:10]] = int(tokens)
    return result


def build_svg(data: dict[str, Any]) -> str:
    stats = data.get("stats") or {}

    daily = normalize_buckets(stats)
    today = date.today()
    start = today - timedelta(days=364)
    start -= timedelta(days=start.weekday() + 1 if start.weekday() != 6 else 0)
    days = [start + timedelta(days=i) for i in range(371)]
    weeks = [days[i : i + 7] for i in range(0, len(days), 7)]
    peak = max([int(stats.get("peak_daily_tokens") or 0), *daily.values(), 1])

    width, height = 980, 380
    grid_x, grid_y = 112, 172
    cell, gap = 11, 4
    stat_x, stat_y = 102, 48

    stat_items = [
        (human_tokens(stats.get("lifetime_tokens")), "Total Tokens"),
        (human_tokens(stats.get("peak_daily_tokens")), "Peak Tokens"),
        (human_duration(stats.get("longest_running_turn_sec")), "Longest Task"),
        (f"{stats.get('current_streak_days') or '-'} days", "Current Streak"),
        (f"{stats.get('longest_streak_days') or '-'} days", "Longest Streak"),
    ]

    rects = []
    for week_idx, week in enumerate(weeks):
        for weekday_idx, day in enumerate(week):
            if day > today:
                continue
            tokens = daily.get(day.isoformat(), 0)
            rects.append(
                f'<rect x="{grid_x + week_idx * (cell + gap)}" '
                f'y="{grid_y + weekday_idx * (cell + gap)}" '
                f'width="{cell}" height="{cell}" rx="3" '
                f'fill="{color_for(tokens, peak)}"><title>{day.isoformat()}: {tokens:,} tokens</title></rect>'
            )

    month_labels = []
    last_month = None
    for week_idx, week in enumerate(weeks):
        month = week[-1].month
        if month != last_month and week_idx > 0:
            month_labels.append(
                f'<text x="{grid_x + week_idx * (cell + gap)}" y="{grid_y + 145}" '
                f'class="month">{month}月</text>'
            )
            last_month = month
        elif last_month is None:
            last_month = month

    stat_blocks = []
    for idx, (value, label) in enumerate(stat_items):
        x = stat_x + idx * 166
        stat_blocks.append(
            f'<g transform="translate({x} {stat_y})">'
            f'<text x="70" y="0" text-anchor="middle" class="stat-value">{escape(str(value))}</text>'
            f'<text x="70" y="34" text-anchor="middle" class="stat-label">{escape(label)}</text>'
            f'</g>'
        )
        if idx < len(stat_items) - 1:
            stat_blocks.append(
                f'<line x1="{x + 152}" y1="{stat_y - 20}" x2="{x + 152}" y2="{stat_y + 38}" class="divider"/>'
            )

    return f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .muted {{ font: 600 18px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #8c959f; }}
    .stat-value {{ font: 700 22px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #24292f; }}
    .stat-label {{ font: 600 17px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #6e7781; }}
    .section {{ font: 700 20px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #24292f; }}
    .month {{ font: 400 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #8c959f; }}
    .divider {{ stroke: #edf0f2; stroke-width: 1; }}
  </style>
  <rect x="32" y="12" width="916" height="96" rx="22" fill="#fff"/>
  {''.join(stat_blocks)}
  <text x="{grid_x}" y="{grid_y - 38}" class="section">Token Activity</text>
  <text x="{width - 250}" y="{grid_y - 38}" class="section">Daily</text>
  <text x="{width - 185}" y="{grid_y - 38}" class="muted">Weekly</text>
  <text x="{width - 112}" y="{grid_y - 38}" class="muted">Total</text>
  {''.join(rects)}
  {''.join(month_labels)}
</svg>
'''


def load_input(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Codex token activity SVG.")
    parser.add_argument("--input", type=Path, help="Read a saved /wham/profiles/me JSON response.")
    parser.add_argument("--output", type=Path, default=Path("reports/assets/codex-token-activity.svg"))
    parser.add_argument("--demo", action="store_true", help="Use screenshot-like demo values.")
    parser.add_argument("--save-json", type=Path, help="Also save the source JSON.")
    args = parser.parse_args()

    if args.demo:
        data = demo_profile()
    elif args.input:
        data = load_input(args.input)
    else:
        token = os.environ.get("CODEX_BEARER_TOKEN") or os.environ.get("CODEX_TOKEN")
        if not token:
            token = getpass.getpass("Bearer token: ")
        data = request_profile(token)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_svg(data), encoding="utf-8")
    if args.save_json:
        args.save_json.parent.mkdir(parents=True, exist_ok=True)
        args.save_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
