"""Render the coverage summary posted as a pull request comment.

Reads an existing .coverage data file and writes markdown to stdout. Kept as a
script rather than inline workflow YAML so it can be run and checked locally:

    uv run python scripts/coverage_pr_comment.py --fail-under 55
"""

import argparse
import subprocess
import sys

MARKER = "<!-- coverage-summary -->"


def _coverage(*args: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "-m", "coverage", *args],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip()


def _changed_python_files(path: str | None) -> list[str]:
    if not path:
        return []
    with open(path) as f:
        names = [line.strip() for line in f if line.strip()]
    return [n for n in names if n.endswith(".py")]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--changed-files", help="file holding one changed path per line"
    )
    parser.add_argument("--fail-under", type=float, required=True)
    args = parser.parse_args()

    code, total = _coverage("report", "--format=total", "--precision=2")
    if code != 0:
        print(f"{MARKER}\n## Coverage\n\nNo coverage data was produced.")
        return 0

    total_pct = float(total)
    verdict = "✅" if total_pct >= args.fail_under else "❌"

    lines = [
        MARKER,
        "## Coverage",
        "",
        f"{verdict} **{total_pct:.2f}%** total — gate is {args.fail_under:g}%.",
    ]

    changed = _changed_python_files(args.changed_files)
    if changed:
        # --include is matched against the measured files, so paths the run does
        # not track (tests, transfers, deleted files) drop out on their own.
        code, table = _coverage(
            "report", "--format=markdown", "--include=" + ",".join(changed)
        )
        if code == 0 and table:
            lines += [
                "",
                "<details>",
                "<summary>Coverage for the Python files changed in this PR</summary>",
                "",
                table,
                "",
                "</details>",
            ]
        else:
            lines += ["", "_No measured coverage for the Python files changed here._"]

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
