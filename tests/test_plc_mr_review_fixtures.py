"""The plc-mr-review eval fixture sets up its situation, and
check_mr_review.py passes a correct result and fails a wrong one.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent / "skill-evals"
CASES = EVALS / "plc-mr-review"
sys.path.insert(0, str(EVALS))
from fixture_lib import GIT_ENV, configure, format_check, git  # noqa: E402 - sys.path is set above
from host_fixture import BRANCH, host_command, host_state  # noqa: E402 - sys.path is set above


def load_tag_fixture(name):
    spec = importlib.util.spec_from_file_location(name, CASES / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_tag_labels = load_tag_fixture("check_tag_labels")
tag_fixture = load_tag_fixture("tag_fixture")


class PlcMrReviewFixtureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "fixture"
        subprocess.run(
            [sys.executable, str(CASES / "ready-no-plan" / "fixture" / "build.py"), str(self.dest)],
            check=True,
            capture_output=True,
            env=GIT_ENV,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def glab(self, *args: str) -> str:
        env = dict(GIT_ENV, PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [*host_command(self.dest, "glab"), *args],
            cwd=self.dest / "app",
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def check(self) -> dict:
        result = subprocess.run(
            [sys.executable, str(CASES / "check_mr_review.py"), str(self.dest)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=GIT_ENV,
            check=False,
        )
        return json.loads(result.stdout)

    def push_fix(self) -> None:
        """Fix the cap in a worktree of the MR's branch and push it."""
        worktree = self.dest / "app-wt" / BRANCH
        git(self.dest / "app", "worktree", "add", "-q", str(worktree), BRANCH)
        configure(worktree)
        retry = worktree / "retry.py"
        text = retry.read_text(encoding="utf-8")
        self.assertIn("    return base * 2 ** attempt\n", text)
        retry.write_text(
            text.replace(
                "    return base * 2 ** attempt\n",
                "    return min(base * 2 ** attempt, max_delay)\n",
            ),
            encoding="utf-8",
            newline="\n",
        )
        git(worktree, "commit", "-q", "-am", "Cap the backoff delay at max_delay")
        git(worktree, "push", "-q", "origin", BRANCH)

    def handle_bot_thread(self) -> None:
        base = "projects/:id/merge_requests/7/discussions/d-bot"
        self.glab(
            "api", f"{base}/notes", "-f", "body=Good catch: the delay is now capped; tests pass."
        )
        self.glab("api", "-X", "PUT", f"{base}?resolved=true")

    def test_fixture_starts_with_failing_ci_and_open_threads(self):
        self.assertIn("failed", self.glab("ci", "status", "--branch", BRANCH))
        threads = json.loads(self.glab("api", "projects/:id/merge_requests/7/discussions"))
        self.assertEqual([t["id"] for t in threads], ["d-bot", "d-human"])
        self.assertEqual([t["notes"][0]["author"]["bot"] for t in threads], [True, False])
        self.assertFalse(any(note["resolved"] for t in threads for note in t["notes"]))
        self.assertFalse((self.dest / "app" / "docs").exists(), "the case has no plan")
        self.assertFalse(self.check()["ok"])

    def test_ready_and_unmerged_passes(self):
        self.push_fix()
        self.handle_bot_thread()
        self.glab(
            "api",
            "projects/:id/merge_requests/7/discussions/d-human/notes",
            "-f",
            "body=Two seconds is fine for now; leaving this for you to decide.",
        )
        self.assertEqual(self.check(), {"ok": True, "failures": []})

    def test_merge_when_green_fails_unasked(self):
        self.push_fix()
        self.handle_bot_thread()
        self.glab("mr", "merge", "7", "--auto-merge")
        self.assertFalse(self.check()["ok"])

    def test_resolving_the_human_thread_fails(self):
        self.push_fix()
        self.handle_bot_thread()
        self.glab(
            "api", "-X", "PUT", "projects/:id/merge_requests/7/discussions/d-human?resolved=true"
        )
        self.assertIn("human thread d-human was resolved", self.check()["failures"])

    def test_deleting_the_failing_test_fails(self):
        worktree = self.dest / "app-wt" / BRANCH
        git(self.dest / "app", "worktree", "add", "-q", str(worktree), BRANCH)
        configure(worktree)
        test_file = worktree / "tests" / "test_backoff.py"
        text = test_file.read_text(encoding="utf-8")
        start = text.index("    def test_delay_is_capped")
        test_file.write_text(text[:start].rstrip() + "\n", encoding="utf-8", newline="\n")
        git(worktree, "commit", "-q", "-am", "Drop the cap test")
        git(worktree, "push", "-q", "origin", BRANCH)
        self.handle_bot_thread()
        self.assertIn(
            "tests/test_backoff.py changed or is gone; CI must pass with the fixture's tests",
            self.check()["failures"],
        )

    def test_threads_without_a_ci_fix_fail(self):
        self.handle_bot_thread()
        self.assertIn(f"{BRANCH} has no new commit on the remote", self.check()["failures"])
        self.assertEqual(host_state(self.dest)["mrs"][0]["state"], "opened")


class TagLabelFixtureTest(unittest.TestCase):
    """These tests prove fixture mechanics, not an actual agent's decisions."""

    def test_existing_labels_conflicts_intersection_and_denied_writes(self):
        for host, scoped in (("github", False), ("gitlab", False), ("gitlab", True)):
            with self.subTest(host=host, scoped=scoped), tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "fixture"
                tag_fixture.build(dest, host, scoped)
                plan_path = dest / "app" / tag_fixture.PLAN
                plan_before = plan_path.read_text(encoding="utf-8")
                self.assertIn("; plc: PLC-999; phase: 9", plan_before)
                self.assertEqual(format_check().check_packet(plan_path, strict=True), [])
                self.assertTrue(check_tag_labels.problems(dest))
                tool = "gh" if host == "github" else "glab"
                listing = (
                    ["label", "list", "--json", "name"]
                    if host == "github"
                    else ["api", "projects/:id/labels"]
                )
                result = subprocess.run(
                    [*host_command(dest, tool), *listing],
                    capture_output=True,
                    text=True,
                    env=GIT_ENV,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("area::reader", result.stdout)
                operations = {
                    21: ["release::1.0.0", "kind::feature"],
                    22: ["kind::feature", "area::web"],
                    23: ["kind::feature", "area::web"],
                    24: ["release::1.0.0"],
                    25: ["release::1.0.0", "kind::feature"],
                }
                for number, labels in operations.items():
                    # Description writes succeed independently of a later denied label write.
                    mr = next(item for item in host_state(dest)["mrs"] if item["number"] == number)
                    body_args = (
                        ["pr", "edit", str(number), "--body"]
                        if host == "github"
                        else ["mr", "update", str(number), "--description"]
                    )
                    subprocess.run(
                        [
                            *host_command(dest, tool),
                            *body_args,
                            "Deliver the linked Harbor work.\n\n" + mr["body"],
                        ],
                        capture_output=True,
                        env=GIT_ENV,
                        check=True,
                    )
                    args = (
                        ["pr", "edit", str(number), "--add-label"]
                        if host == "github"
                        else ["mr", "update", str(number), "--label"]
                    )
                    result = subprocess.run(
                        [*host_command(dest, tool), *args, ",".join(labels)],
                        capture_output=True,
                        text=True,
                        env=GIT_ENV,
                        check=False,
                    )
                    self.assertEqual(result.returncode, int(number == 24), result.stderr)
                    if number == 24:
                        self.assertIn("label write denied", result.stderr)
                self.assertEqual(check_tag_labels.problems(dest), [])
                self.assertEqual(plan_path.read_text(encoding="utf-8"), plan_before)
                state_path = dest / "_host/state.json"
                saved = state_path.read_text(encoding="utf-8")
                # The host permits these labels; the workflow must skip identity collisions.
                identity_args = (
                    ["pr", "edit", "21", "--add-label"]
                    if host == "github"
                    else ["mr", "update", "21", "--label"]
                )
                for label in ("plc::PLC-999", "phase::9"):
                    subprocess.run(
                        [*host_command(dest, tool), *identity_args, label],
                        capture_output=True,
                        env=GIT_ENV,
                        check=True,
                    )
                    self.assertIn("MR 21 labels differ", check_tag_labels.problems(dest)[0])
                    state_path.write_text(saved, encoding="utf-8")
                state = host_state(dest)
                state["mrs"][-1]["labels"].remove("plc::PLC-100")
                state_path.write_text(json.dumps(state), encoding="utf-8")
                self.assertIn("MR 25 labels differ", check_tag_labels.problems(dest)[0])
                state_path.write_text(saved, encoding="utf-8")
                state = host_state(dest)
                state["mrs"][2]["labels"].append("release::1.0.0")
                state_path.write_text(json.dumps(state), encoding="utf-8")
                self.assertIn("MR 23 labels differ", check_tag_labels.problems(dest)[0])
                state["mrs"][2]["labels"].remove("release::1.0.0")
                state_path.write_text(json.dumps(state), encoding="utf-8")
                # Both plain and enforced hosts expose a bad competing write.
                args = (
                    ["pr", "edit", "22", "--add-label"]
                    if host == "github"
                    else ["mr", "update", "22", "--label"]
                )
                subprocess.run(
                    [*host_command(dest, tool), *args, "release::1.0.0"],
                    capture_output=True,
                    env=GIT_ENV,
                    check=True,
                )
                self.assertIn("MR 22 labels differ", check_tag_labels.problems(dest)[0])


if __name__ == "__main__":
    unittest.main()
