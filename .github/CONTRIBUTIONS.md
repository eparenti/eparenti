# Contribution updates

The workflow updates the marked paragraph in `README.md` each day at 05:23 UTC.
GitHub can delay scheduled runs. You can also run **Update contribution counts**
from the Actions tab.

## Account access

Add these repository secrets in Settings, Secrets and variables, Actions:

| Secret | Account that owns the token |
| --- | --- |
| `EPARENTI_CONTRIBUTIONS_TOKEN` | `eparenti` |
| `TEMPO_CONTRIBUTIONS_TOKEN` | `tempo-64` |

Use a separate classic personal access token for each account with the `read:user`
scope. GitHub documents this scope for private and internal contribution counts.
The script checks the account identity and queries only aggregate counts. It does
not request repository names or contents. Renew the tokens before they expire.

The workflow uses its built-in `GITHUB_TOKEN` to commit the updated README. The
account tokens are used only for the count queries. Pull requests run the tests
without access to either account token.

## Counting rules

Both accounts use GitHub's default yearly contribution calendar. The script checks
that both calendars cover the same period before adding their counts.
The total comes from each account's contribution calendar. The four named counts
are a subset of that total, so the sentence uses "including". Counts can fall as
older activity leaves the period. The updater commits as `github-actions[bot]`.

If either query fails, returns incomplete data, or uses the wrong account, the
workflow fails and leaves the previous paragraph and count date in place. Read the
failed run in Actions to check for expired tokens or API errors. GitHub can disable
scheduled workflows after 60 days without repository activity.

Run tests with `python3 -m unittest discover -s tests -v`. With both token environment
variables set, preview the paragraph with
`python3 scripts/update_contributions.py --check`. Omit `--check` to update the local README.

Sources: [GitHub contribution API](https://docs.github.com/en/graphql/reference/users#contributionscollection)
and [scheduled workflow rules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
