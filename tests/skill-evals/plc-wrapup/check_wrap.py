"""Check what a plc-wrapup run delivered and cleaned up, against _expect.json
and _snapshot.json.

Usage:
  python check_wrap.py <fixture-folder>

_expect.json may list:
  merged            commits that must be on the remote's main
  not_merged        commits that must not be on the remote's main
  removed_worktrees worktree paths (relative to the fixture) that must be gone:
                    unregistered, and their folders deleted
  kept_worktrees    worktree paths that must still be registered and present
  locked_worktrees  kept worktrees whose lock must still be in place
  deleted_branches  local branches that must be gone
  kept_branches     local branches that must remain
  deleted_remote_branches  branches that must be gone from the remote
  if_merged         [{commit, removed_worktrees, deleted_branches,
                    deleted_remote_branches}]: cleanup that is required only
                    when that commit reached the remote's main
  remote_files      paths that must exist on the remote's main
  absent_remote_files      paths that must not exist on the remote's main
  remote_text       {path: [text, ...]}: each text must appear in that file
                    on the remote's main
  absent_remote_text       {path: [text, ...]}: no text may appear in that
                    file on the remote's main
  plans             [{path, statuses, owner, historical, phases,
                    lists_no_removed_checkouts}]: a packet folder on the
                    remote's main. It must pass fixture_lib's
                    packet_shape_problems, including the Owner rule for
                    `owner`; its packet status must be one of `statuses`; and
                    its Current Work must open with the historical-record
                    line when `historical` is true, and not have it when false.
                    `phases` maps a phase ID to a fixture_lib phase_rule:
                    the phase's state word must be one of `states`; once
                    its note says `moved to P<n>` for a row that is new (not
                    the phase itself and not in `phases_at_start`), it must
                    be one of `after_move` instead. When `lists_no_removed_checkouts` is
                    true, "Where the work lives" must not name a worktree
                    from `removed_worktrees` that is no longer registered.

Every run is also compared with _snapshot.json. A worktree or local branch
the run added must be gone by the end, including the merge checkout the skill
makes. The primary checkout must stay on its branch, and its branch may only
gain commits that are on the remote's main (a fast-forward) or that touch only
docs/plans/; its uncommitted changes may only be under docs/plans/.

Prints a JSON report and exits 0 when every expectation holds, 1 otherwise.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fixture_lib import (  # noqa: E402
    GIT_ENV,
    is_ancestor,
    listed_checkouts,
    packet_shape_problems,
    packet_status,
    phase_rule_problem,
    run_git,
    section_lines,
    status_paths,
)

REPO = "notify"
PLANS_ROOT = "docs/plans/"
HISTORICAL = "Historical record as of"
CURRENT_TRUTH = "the code is the current truth"


def worktree_records(listing: str) -> dict[Path, list[str]]:
    """Map each worktree in `git worktree list --porcelain` output to its
    other attribute lines, such as `branch ...` or `locked ...`."""
    records = {}
    for block in listing.split("\n\n"):
        lines = block.strip().splitlines()
        if lines and lines[0].startswith("worktree "):
            records[Path(lines[0].removeprefix("worktree ")).resolve()] = lines[1:]
    return records


def relative(dest: Path, path: Path) -> str:
    try:
        return path.relative_to(dest).as_posix()
    except ValueError:
        return path.as_posix()


def opens_with_historical_record(readme: str) -> bool:
    """True when Current Work's first line is the historical-record line, as a
    plain line or a list item."""
    first = next((line for line in section_lines(readme, "Current Work") if line.strip()), "")
    first = first.strip().removeprefix("- ")
    return first.startswith(HISTORICAL) and CURRENT_TRUTH in first


class Checker:
    def __init__(self, dest: Path):
        self.dest = dest
        self.app = dest / REPO
        self.remote = dest / f"{REPO}.git"
        self.expect = json.loads((dest / "_expect.json").read_text(encoding="utf-8"))
        self.snapshot = json.loads((dest / "_snapshot.json").read_text(encoding="utf-8"))
        self.failures: list[str] = []
        self.missing: list[str] = []

    def remote_git(self, *args: str) -> subprocess.CompletedProcess:
        return run_git(self.dest, "--git-dir", str(self.remote), *args)

    def on_remote_main(self, commit: str) -> bool:
        return self.remote_git("merge-base", "--is-ancestor", commit, "main").returncode == 0

    def remote_file(self, path: str) -> str | None:
        shown = self.remote_git("show", f"main:{path}")
        return shown.stdout if shown.returncode == 0 else None

    def run(self) -> dict:
        self.check_remote_main()
        self.check_worktrees()
        self.check_branches()
        self.check_primary_checkout()
        self.check_files()
        for plan in self.expect.get("plans", []):
            self.check_plan(plan)
        # A missing file is reported once, however many expectations name it.
        self.failures += [
            f"{path} is missing on origin/main" for path in dict.fromkeys(self.missing)
        ]
        return {"ok": not self.failures, "failures": self.failures}

    def cleanup(self, key: str) -> list[str]:
        """An expectation list, plus what `if_merged` adds for merged commits."""
        items = list(self.expect.get(key, []))
        for rule in self.expect.get("if_merged", []):
            if self.on_remote_main(rule["commit"]):
                items += rule.get(key, [])
        return items

    def check_remote_main(self) -> None:
        before = dict(
            line.split(" ", 1)
            for line in self.snapshot["remotes"][f"{REPO}.git"].splitlines()
            if line
        )
        old_main = before.get("refs/heads/main")
        if old_main and not self.on_remote_main(old_main):
            self.failures.append(
                "origin/main was rewritten: its old tip is no longer in its history"
            )
        for commit in self.expect.get("merged", []):
            if not self.on_remote_main(commit):
                self.failures.append(f"{commit[:7]} is not on origin/main")
        for commit in self.expect.get("not_merged", []):
            if self.on_remote_main(commit):
                self.failures.append(f"{commit[:7]} reached origin/main but must not have")

    def check_worktrees(self) -> None:
        listing = run_git(self.app, "worktree", "list", "--porcelain").stdout
        records = worktree_records(listing)
        for rel in self.cleanup("removed_worktrees"):
            if (self.dest / rel).resolve() in records:
                self.failures.append(f"worktree {rel} is still registered")
            if (self.dest / rel).exists():
                self.failures.append(f"worktree {rel} folder still exists")
        for rel in self.expect.get("kept_worktrees", []):
            if (self.dest / rel).resolve() not in records:
                self.failures.append(f"worktree {rel} is no longer registered")
            if not (self.dest / rel).exists():
                self.failures.append(f"worktree {rel} folder is gone")
        for rel in self.expect.get("locked_worktrees", []):
            lines = records.get((self.dest / rel).resolve(), [])
            if not any(line == "locked" or line.startswith("locked ") for line in lines):
                self.failures.append(f"worktree {rel} lost its lock")
        before = set(self.snapshot["checkouts"][REPO]["worktrees"])
        for path in records:
            rel = relative(self.dest, path)
            if rel not in before:
                self.failures.append(f"worktree {rel} was added during the run and still exists")

    def check_branches(self) -> None:
        refs = run_git(self.app, "for-each-ref", "--format=%(refname:short)", "refs/heads")
        local = set(refs.stdout.split())
        for branch in self.cleanup("deleted_branches"):
            if branch in local:
                self.failures.append(f"local branch {branch} still exists")
        for branch in self.expect.get("kept_branches", []):
            if branch not in local:
                self.failures.append(f"local branch {branch} was deleted but must be kept")
        before = {
            line.split(" ", 1)[0].removeprefix("refs/heads/")
            for line in self.snapshot["checkouts"][REPO]["branches"].splitlines()
            if line
        }
        for branch in sorted(local - before):
            self.failures.append(
                f"local branch {branch} was added during the run and still exists"
            )
        heads = self.remote_git("for-each-ref", "--format=%(refname:short)", "refs/heads")
        remote_heads = set(heads.stdout.split())
        for branch in self.cleanup("deleted_remote_branches"):
            if branch in remote_heads:
                self.failures.append(f"remote branch {branch} still exists")

    def check_primary_checkout(self) -> None:
        before = self.snapshot["checkouts"][REPO]["worktrees"][REPO]
        branch = run_git(self.app, "branch", "--show-current").stdout.strip()
        if branch != before["branch"]:
            now = branch or "a detached HEAD"
            self.failures.append(f"primary checkout switched from {before['branch']} to {now}")
        head = run_git(self.app, "rev-parse", "HEAD").stdout.strip()
        if head != before["head"]:
            if not is_ancestor(self.app, before["head"], head):
                self.failures.append("primary checkout: history rewritten or reset")
            else:
                new = f"{before['head']}..{head}"
                commits = run_git(self.app, "rev-list", new).stdout.split()
                local_only = [commit for commit in commits if not self.on_remote_main(commit)]
                touched = sorted(
                    {
                        path
                        for commit in local_only
                        for path in self.files_changed_by(commit)
                        if not path.startswith(PLANS_ROOT)
                    }
                )
                if touched:
                    self.failures.append(
                        f"primary checkout: commits beyond a fast-forward touch {touched}"
                    )
        changed = status_paths(self.app) - set(before["status_paths"])
        outside = sorted(path for path in changed if not path.startswith(PLANS_ROOT))
        if outside:
            self.failures.append(f"primary checkout: uncommitted changes {outside}")

    def files_changed_by(self, commit: str) -> list[str]:
        """The paths a commit changes, against each parent of a merge."""
        changed = run_git(
            self.app, "diff-tree", "--no-commit-id", "--name-only", "-r", "-m", commit
        )
        return changed.stdout.split()

    def check_files(self) -> None:
        self.missing += [
            path for path in self.expect.get("remote_files", []) if self.remote_file(path) is None
        ]
        for path in self.expect.get("absent_remote_files", []):
            if self.remote_file(path) is not None:
                self.failures.append(f"{path} should not be on origin/main")
        for path, texts in self.expect.get("remote_text", {}).items():
            content = self.remote_file(path)
            if content is None:
                self.missing.append(path)
                continue
            for text in texts:
                if text not in content:
                    self.failures.append(f"{path} on origin/main lacks {text!r}")
        for path, texts in self.expect.get("absent_remote_text", {}).items():
            content = self.remote_file(path) or ""
            for text in texts:
                if text in content:
                    self.failures.append(f"{path} on origin/main must not contain {text!r}")

    def check_plan(self, plan: dict) -> None:
        """Extract the packet from the remote's main and judge it by the
        template's rules, its status word, its owner and its historical line."""
        path = plan["path"]
        label = f"plan {path} on origin/main"
        archive = subprocess.run(
            ["git", "--git-dir", str(self.remote), "archive", "--format=tar", "main", path],
            capture_output=True,
            env=GIT_ENV,
        )
        if archive.returncode:
            self.missing.append(f"{path}/README.md")
            return
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
                tar.extractall(root, filter="data")
            packet = root / path
            if not (packet / "README.md").is_file():
                self.missing.append(f"{path}/README.md")
                return
            prefix = f"{root.as_posix()}/"
            for problem in packet_shape_problems(packet, owner=plan.get("owner")):
                self.failures.append(f"{label}: {problem.replace(prefix, '')}")
            readme = (packet / "README.md").read_text(encoding="utf-8")
        status = packet_status(readme)
        if status not in plan.get("statuses", [status]):
            expected = " or ".join(plan["statuses"])
            self.failures.append(f"{label}: status is {status or 'missing'}, expected {expected}")
        historical = plan.get("historical")
        has_line = opens_with_historical_record(readme)
        if historical is True and not has_line:
            self.failures.append(
                f"{label}: Current Work does not open with the historical-record line"
            )
        if historical is False and HISTORICAL in "\n".join(section_lines(readme, "Current Work")):
            self.failures.append(f"{label}: Current Work has the historical-record line")
        for phase, rule in plan.get("phases", {}).items():
            problem = phase_rule_problem(readme, phase, rule)
            if problem:
                self.failures.append(f"{label}: {problem}")
        if plan.get("lists_no_removed_checkouts"):
            self.check_listed_checkouts(label, readme)

    def check_listed_checkouts(self, label: str, readme: str) -> None:
        """Where the work lives must not name a worktree the run removed."""
        listing = run_git(self.app, "worktree", "list", "--porcelain").stdout
        registered = worktree_records(listing)
        listed = listed_checkouts(readme)
        for rel in self.cleanup("removed_worktrees"):
            if (self.dest / rel).resolve() in registered:
                continue
            if any(Path(rel).name in cell for cell in listed):
                self.failures.append(f"{label}: Where the work lives still names removed {rel}")


def check(dest: Path) -> dict:
    return Checker(dest).run()


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit("usage: check_wrap.py <fixture-folder>")
    report = check(Path(sys.argv[1]).resolve())
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
