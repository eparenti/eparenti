#!/usr/bin/env python3
"""Update the profile with contribution counts from both account owners."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ACCOUNTS = {"eparenti": "EPARENTI_CONTRIBUTIONS_TOKEN", "tempo-64": "TEMPO_CONTRIBUTIONS_TOKEN"}
START = "<!-- contributions:start -->"
END = "<!-- contributions:end -->"
FIELDS = (
    "totalCommitContributions",
    "totalPullRequestContributions",
    "totalPullRequestReviewContributions",
    "totalIssueContributions",
)
QUERY = """
query {
  viewer {
    login
    contributionsCollection {
      startedAt
      endedAt
      contributionCalendar { totalContributions }
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
    }
  }
}
"""


def fetch_counts(account, token):
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "eparenti-profile-contributions",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            scopes = response.headers.get("X-OAuth-Scopes")
            if scopes is not None and not {"read:user", "user"}.intersection(
                scope.strip() for scope in scopes.split(",")
            ):
                raise ValueError(f"{account}: token needs read:user permission")
            payload = json.load(response)
    except HTTPError as error:
        raise ValueError(f"{account}: GitHub returned HTTP {error.code}") from None
    except (URLError, TimeoutError):
        raise ValueError(f"{account}: could not reach GitHub") from None

    if payload.get("errors"):
        raise ValueError(f"{account}: GitHub returned query errors; keeping the previous count")
    try:
        viewer = payload["data"]["viewer"]
        if viewer["login"] != account:
            raise ValueError(f"{account}: token must belong to this account")
        collection = viewer["contributionsCollection"]
        counts = {field: collection[field] for field in FIELDS}
        counts["total"] = collection["contributionCalendar"]["totalContributions"]
        period = (collection["startedAt"], collection["endedAt"])
        for timestamp in period:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (KeyError, TypeError):
        raise ValueError(f"{account}: GitHub returned incomplete contribution data") from None
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError(f"{account}: GitHub returned invalid contribution counts")
    if counts["total"] < sum(counts[field] for field in FIELDS):
        raise ValueError(f"{account}: contribution counts exceed the calendar total")
    return counts, period


def update(readme, today, *, check=False):
    original = readme.read_text()
    if original.count(START) != 1 or original.count(END) != 1:
        raise ValueError("README must contain exactly one pair of contribution markers")
    before, rest = original.split(START)
    previous, after = rest.split(END) if END in rest else (None, None)
    if previous is None:
        raise ValueError("README contribution markers are in the wrong order")

    missing = [name for name in ACCOUNTS.values() if not os.environ.get(name, "").strip()]
    if missing:
        raise ValueError("Missing repository secrets: " + ", ".join(missing))

    results = [fetch_counts(account, os.environ[name].strip()) for account, name in ACCOUNTS.items()]
    if results[0][1] != results[1][1]:
        raise ValueError("The account calendars cover different periods; keeping the previous count")
    counts = [result[0] for result in results]
    totals = {field: sum(account[field] for account in counts) for field in (*FIELDS, "total")}
    paragraph = (
        f"{totals['total']:,} GitHub contributions in the last year across my two accounts "
        f"(including {totals['totalCommitContributions']:,} commits, "
        f"{totals['totalPullRequestContributions']:,} pull requests, "
        f"{totals['totalPullRequestReviewContributions']:,} reviews, "
        f"{totals['totalIssueContributions']:,} issues), most of them in private repositories. "
        f"Counted {today.isoformat()}."
    )
    updated = before + START + "\n" + paragraph + "\n" + END + after
    if not check and updated != original:
        readme.write_text(updated)
    print(paragraph)
    return updated != original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Show the new paragraph without writing it")
    args = parser.parse_args()
    readme = Path(__file__).resolve().parents[1] / "README.md"
    try:
        update(readme, datetime.now(timezone.utc).date(), check=args.check)
    except (ValueError, OSError) as error:
        print(f"Contribution update failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
