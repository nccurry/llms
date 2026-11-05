"""A small stand-in for `glab`, `gh` and a `jira` CLI, for eval cases that
need a code host or tracker without network access or a login.

A fixture copies this file into `<dest>/_host/` and writes `<dest>/bin/glab`,
`<dest>/bin/gh` and `<dest>/bin/jira` wrappers that run it; the agent's
session puts `<dest>/bin` first on PATH. State lives in
`<dest>/_host/state.json`, and every call, with its arguments, is appended to
`<dest>/_host/calls.jsonl`, so checkers can see what the agent read and wrote.

It knows one project. Its merge requests (GitLab) or pull requests (GitHub)
come from branches of the fixture's bare remote. CI status for a commit is
computed by running the fixture's `run_tests.py` on that commit, so pushing a
fix turns CI green. It supports the commands agents commonly use, including
`glab api` for merge request discussions; anything else exits 1 with a
message, and the call is still logged.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

HOST_DIR = Path(__file__).resolve().parent
STATE = HOST_DIR / "state.json"
CALLS = HOST_DIR / "calls.jsonl"
# The account the agent works as. Notes it posts are by this user, not a bot.
USER = "dev"


def load() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8"))


def save(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def log(argv: list[str]) -> None:
    with CALLS.open("a", encoding="utf-8") as file:
        file.write(json.dumps({"argv": argv}) + "\n")


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def git(*args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    result = subprocess.run(
        ["git", "--git-dir", load()["remote"], *args],
        capture_output=True, text=True, encoding="utf-8", env=env,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def head_of(branch: str) -> str:
    return git("rev-parse", f"refs/heads/{branch}")


def ci_for(sha: str) -> dict:
    """Run run_tests.py on `sha` once and cache the result in the state."""
    state = load()
    cache = state.setdefault("ci", {})
    if sha not in cache:
        with tempfile.TemporaryDirectory() as tmp:
            archive = subprocess.run(
                ["git", "--git-dir", state["remote"], "archive", sha],
                capture_output=True,
            )
            subprocess.run(["tar", "-x", "-C", tmp], input=archive.stdout, check=True)
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            run = subprocess.run(
                [sys.executable, "run_tests.py"], cwd=tmp, capture_output=True,
                text=True, encoding="utf-8", env=env,
            )
        cache[sha] = {
            "id": 1000 + len(cache),
            "status": "success" if run.returncode == 0 else "failed",
            "log": run.stdout + run.stderr,
        }
        save(state)
    return cache[sha]


def option(args: list[str], *names: str) -> str | None:
    """The value of the first of `names` in args, as `--x v` or `--x=v`."""
    for index, arg in enumerate(args):
        for name in names:
            if arg == name and index + 1 < len(args):
                return args[index + 1]
            if arg.startswith(name + "="):
                return arg[len(name) + 1:]
    return None


def text_option(args: list[str], names: tuple[str, ...], file_names: tuple[str, ...]) -> str | None:
    value = option(args, *names)
    if value is None and (path := option(args, *file_names)) is not None:
        value = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return value


def positional(args: list[str]) -> list[str]:
    """Arguments that are neither flags nor flag values (a rough guess)."""
    out, skip = [], False
    for arg in args:
        if skip:
            skip = False
            continue
        if arg.startswith("-"):
            skip = "=" not in arg and arg not in BOOLEAN_FLAGS
            continue
        out.append(arg)
    return out


BOOLEAN_FLAGS = {
    "--comments", "--yes", "-y", "--fill", "--draft", "--web", "--auto", "--squash",
    "--merge", "--rebase", "--auto-merge", "--when-pipeline-succeeds", "--remove-source-branch",
    "--delete-branch", "--all", "--paginate", "--include-head", "--no-input", "--plain",
    "--raw", "--json-output", "--live", "--wait", "-c",
}


def json_wanted(args: list[str]) -> bool:
    return option(args, "-F", "--output") == "json" or "--json" in " ".join(args)


def find_mr(state: dict, ref: str | None) -> dict:
    mrs = state["mrs"]
    if ref is None:
        current = subprocess.run(
            ["git", "branch", "--show-current"], capture_output=True, text=True
        ).stdout.strip()
        match = [mr for mr in mrs if mr["source"] == current]
    else:
        ref = ref.lstrip("!#")
        match = [mr for mr in mrs if str(mr["number"]) == ref or mr["source"] == ref]
    if not match:
        fail(f"no merge request found for {ref or 'the current branch'}")
    return match[0]


def mr_json(mr: dict, gitlab: bool) -> dict:
    sha = head_of(mr["source"])
    ci = ci_for(sha) if sha else {"id": None, "status": "none"}
    if gitlab:
        return {
            "iid": mr["number"], "title": mr["title"], "description": mr["body"],
            "state": mr["state"], "source_branch": mr["source"], "target_branch": mr["target"],
            "sha": sha, "merge_when_pipeline_succeeds": mr["auto_merge"],
            "web_url": f"https://gitlab.example.com/example/app/-/merge_requests/{mr['number']}",
            "head_pipeline": {"id": ci["id"], "status": ci["status"], "sha": sha},
        }
    checks = "SUCCESS" if ci["status"] == "success" else "FAILURE"
    return {
        "number": mr["number"], "title": mr["title"], "body": mr["body"],
        "state": {"opened": "OPEN"}.get(mr["state"], mr["state"].upper()),
        "headRefName": mr["source"], "baseRefName": mr["target"], "headRefOid": sha,
        "autoMergeRequest": {"enabledBy": {"login": USER}} if mr["auto_merge"] else None,
        "url": f"https://github.example.com/example/app/pull/{mr['number']}",
        "statusCheckRollup": [{"name": "test", "conclusion": checks}],
        "comments": [
            {"author": {"login": note["author"]}, "body": note["body"]}
            for thread in mr["discussions"] for note in thread["notes"]
        ],
    }


def print_mr(mr: dict, gitlab: bool, args: list[str]) -> None:
    data = mr_json(mr, gitlab)
    if json_wanted(args):
        print(json.dumps(data, indent=2))
        return
    sign = "!" if gitlab else "#"
    print(f"{sign}{mr['number']} {mr['title']} ({mr['source']} -> {mr['target']}) {mr['state']}")
    print(f"pipeline: {ci_for(head_of(mr['source']))['status']}")
    print(f"auto-merge: {mr['auto_merge']}\n\n{mr['body']}")
    if "--comments" in args or "-c" in args:
        for thread in mr["discussions"]:
            for note in thread["notes"]:
                print(f"\n--- {note['author']} (thread {thread['id']}, resolved: {thread['resolved']})")
                print(note["body"])


def body_option(args: list[str], gitlab: bool) -> str | None:
    """The MR or PR text: glab's --description, or gh's --body or --body-file."""
    if gitlab:
        return text_option(args, ("--description", "-d"), ("--description-file",))
    return text_option(args, ("--body", "-b"), ("--body-file", "-F"))


def create_mr(state: dict, args: list[str], gitlab: bool) -> None:
    title = option(args, "--title", "-t")
    source = option(args, "--source-branch", "-s", "--head", "-H") or subprocess.run(
        ["git", "branch", "--show-current"], capture_output=True, text=True
    ).stdout.strip()
    names = ("--target-branch", "-b") if gitlab else ("--base", "-B")
    target = option(args, *names) or state["default_branch"]
    if not title:
        fail("a title is required (--title)")
    if not head_of(source):
        fail(f"branch {source} is not on the remote; push it first")
    number = state["next_mr"]
    state["next_mr"] += 1
    mr = {"number": number, "title": title, "body": body_option(args, gitlab) or "",
          "source": source, "target": target, "state": "opened", "auto_merge": False,
          "discussions": []}
    state["mrs"].append(mr)
    save(state)
    print(mr_json(mr, gitlab)["web_url" if gitlab else "url"])


def update_mr(state: dict, mr: dict, args: list[str], gitlab: bool) -> None:
    title = option(args, "--title", "-t")
    body = body_option(args, gitlab)
    if title is not None:
        mr["title"] = title
    if body is not None:
        mr["body"] = body
    save(state)
    print(f"updated {mr['number']}")


def merge_mr(state: dict, mr: dict, auto: bool) -> None:
    if auto:
        mr["auto_merge"] = True
    else:
        mr["state"] = "merged"
    save(state)
    print("set to merge when the pipeline succeeds" if auto else f"merged {mr['number']}")


def add_note(state: dict, mr: dict, body: str, thread_id: str | None = None) -> dict:
    note = {"id": state.setdefault("next_note", 500), "author": USER, "bot": False, "body": body}
    state["next_note"] += 1
    if thread_id is None:
        mr["discussions"].append(
            {"id": f"general-{note['id']}", "resolvable": False, "resolved": False, "notes": [note]}
        )
    else:
        thread = next((t for t in mr["discussions"] if t["id"] == thread_id), None)
        if thread is None:
            fail(f"no discussion {thread_id}")
        thread["notes"].append(note)
    save(state)
    return note


def discussion_json(thread: dict) -> dict:
    return {
        "id": thread["id"], "individual_note": not thread["resolvable"],
        "notes": [
            {
                "id": note["id"], "body": note["body"], "resolvable": thread["resolvable"],
                "resolved": thread["resolved"], "position": note.get("position"),
                "author": {"username": note["author"], "bot": note.get("bot", False)},
            }
            for note in thread["notes"]
        ],
    }


def api_fields(args: list[str]) -> dict[str, str]:
    fields = {}
    for index, arg in enumerate(args):
        if arg in ("-f", "-F", "--field", "--raw-field") and index + 1 < len(args):
            key, _, value = args[index + 1].partition("=")
            fields[key] = value
    if (path := option(args, "--input")) is not None:
        text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
        fields.update(json.loads(text))
    return fields


def glab_api(state: dict, args: list[str]) -> None:
    path = positional(args)[0] if positional(args) else fail("glab api needs a path")
    method = (option(args, "-X", "--method") or "GET").upper()
    parsed = urllib.parse.urlparse(path)
    query = dict(urllib.parse.parse_qsl(parsed.query))
    fields = {**query, **api_fields(args)}
    if method == "GET" and fields and not query and option(args, "-X", "--method") is None:
        method = "POST"
    route = re.sub(r"^/?(api/v4/)?projects/[^/]+/", "", parsed.path)
    mr_match = re.match(r"merge_requests/(\d+)(/.*)?$", route)
    if mr_match:
        mr = find_mr(state, mr_match[1])
        rest = mr_match[2] or ""
        if rest == "" and method == "GET":
            return print(json.dumps(mr_json(mr, True)))
        if rest == "" and method == "PUT":
            if "title" in fields:
                mr["title"] = fields["title"]
            if "description" in fields:
                mr["body"] = fields["description"]
            save(state)
            return print(json.dumps(mr_json(mr, True)))
        if rest == "/merge":
            return merge_mr(state, mr, fields.get("merge_when_pipeline_succeeds") in ("true", True)
                            or fields.get("auto_merge") in ("true", True))
        if rest == "/discussions" and method == "GET":
            return print(json.dumps([discussion_json(t) for t in mr["discussions"]]))
        if rest == "/notes" and method == "GET":
            return print(json.dumps([n for t in mr["discussions"] for n in discussion_json(t)["notes"]]))
        if rest in ("/notes", "/discussions") and method == "POST":
            return print(json.dumps(add_note(state, mr, fields.get("body", ""))))
        thread = re.match(r"/discussions/([^/]+)(/notes)?(/\d+)?$", rest)
        if thread:
            if thread[2] and method == "POST":
                return print(json.dumps(add_note(state, mr, fields.get("body", ""), thread[1])))
            found = next((t for t in mr["discussions"] if t["id"] == thread[1]), None)
            if found is None:
                fail(f"no discussion {thread[1]}")
            if method == "PUT" and "resolved" in fields:
                found["resolved"] = str(fields["resolved"]).lower() == "true"
                save(state)
            return print(json.dumps(discussion_json(found)))
        if rest == "/pipelines":
            ci = ci_for(head_of(mr["source"]))
            return print(json.dumps([{"id": ci["id"], "status": ci["status"], "sha": head_of(mr["source"])}]))
    if route.startswith("pipelines") or route.startswith("jobs"):
        return glab_ci(state, ["view"] if "trace" not in route else ["trace"], json_out=True)
    if route.startswith("issues"):
        return print(json.dumps(state["issues"]))
    fail(f"fake glab api does not know {method} {path}")


def glab_ci(state: dict, args: list[str], json_out: bool = False) -> None:
    branch = option(args, "--branch", "-b") or subprocess.run(
        ["git", "branch", "--show-current"], capture_output=True, text=True
    ).stdout.strip()
    if not head_of(branch):
        branch = state["mrs"][0]["source"] if state["mrs"] else state["default_branch"]
    sha = head_of(branch)
    ci = ci_for(sha)
    if args and args[0] in ("trace", "get") or "trace" in args:
        print(ci["log"])
        return
    data = {"id": ci["id"], "status": ci["status"], "ref": branch, "sha": sha,
            "jobs": [{"name": "test", "status": ci["status"]}]}
    print(json.dumps(data) if json_out or json_wanted(args) else
          f"pipeline {ci['id']} on {branch} @ {sha[:8]}: {ci['status']}\n  test: {ci['status']}")


def issues(state: dict, args: list[str], gitlab: bool) -> None:
    sub, rest = args[0], args[1:]
    if sub == "list":
        found = state["issues"]
        if (search := option(rest, "--search", "-S")) is not None:
            words = search.lower().replace("in:title", "").split()
            found = [i for i in found if all(w in (i["title"] + i["body"]).lower() for w in words)]
        if json_wanted(rest):
            return print(json.dumps(found))
        for issue in found:
            print(f"#{issue['number']}\t{issue['state']}\t{issue['title']}")
        return
    if sub == "create":
        title = option(rest, "--title", "-t")
        number = state["next_issue"]
        state["next_issue"] += 1
        state["issues"].append({"number": number, "title": title or "", "state": "open",
                                "body": text_option(rest, ("--body", "-b", "--description", "-d"), ("--body-file", "-F")) or "",
                                "comments": []})
        save(state)
        return print(f"https://host.example.com/example/app/issues/{number}")
    numbers = positional(rest)
    issue = next((i for i in state["issues"] if numbers and str(i["number"]) == numbers[0].lstrip("#")), None)
    if issue is None:
        fail("issue not found")
    if sub == "view":
        return print(json.dumps(issue) if json_wanted(rest) else
                     f"#{issue['number']} {issue['title']} [{issue['state']}]\n\n{issue['body']}")
    if sub in ("comment", "note"):
        issue["comments"].append(text_option(rest, ("--body", "-b", "--message", "-m"), ("--body-file", "-F")) or "")
    elif sub == "close":
        issue["state"] = "closed"
    else:
        fail(f"fake issue command does not know {sub}")
    save(state)
    print("ok")


def glab(args: list[str]) -> None:
    state = load()
    if args[:2] == ["auth", "status"]:
        return print(f"Logged in to gitlab.example.com as {USER}")
    group, sub, rest = args[0], (args[1] if len(args) > 1 else ""), args[2:]
    if group == "api":
        return glab_api(state, args[1:])
    if group == "ci":
        return glab_ci(state, args[1:])
    if group == "issue":
        return issues(state, args[1:], True)
    if group == "mr":
        if sub == "list":
            open_mrs = [m for m in state["mrs"] if m["state"] == "opened"]
            if json_wanted(rest):
                return print(json.dumps([mr_json(m, True) for m in open_mrs]))
            for mr in open_mrs:
                print(f"!{mr['number']}\t{mr['title']}\t({mr['source']} -> {mr['target']})")
            return
        if sub == "create":
            return create_mr(state, rest, True)
        mr = find_mr(state, positional(rest)[0] if positional(rest) else None)
        if sub == "view":
            return print_mr(mr, True, rest)
        if sub == "update":
            return update_mr(state, mr, rest, True)
        if sub in ("note", "comment"):
            add_note(state, mr, option(rest, "--message", "-m") or "")
            return print("note added")
        if sub == "merge":
            return merge_mr(state, mr, "--auto-merge" in rest or "--when-pipeline-succeeds" in rest)
        if sub == "diff":
            return print(git("diff", f"refs/heads/{mr['target']}...refs/heads/{mr['source']}"))
    fail(f"fake glab does not know: {' '.join(args)}")


def gh(args: list[str]) -> None:
    state = load()
    if args[:2] == ["auth", "status"]:
        return print(f"Logged in to github.example.com account {USER}")
    group, sub, rest = args[0], (args[1] if len(args) > 1 else ""), args[2:]
    if group == "repo" and sub == "view":
        data = {"nameWithOwner": "example/app", "defaultBranchRef": {"name": state["default_branch"]}}
        return print(json.dumps(data) if json_wanted(rest) else "example/app")
    if group == "issue":
        return issues(state, args[1:], False)
    if group == "pr":
        if sub == "list":
            open_mrs = [m for m in state["mrs"] if m["state"] == "opened"]
            if json_wanted(rest):
                return print(json.dumps([mr_json(m, False) for m in open_mrs]))
            for mr in open_mrs:
                print(f"#{mr['number']}\t{mr['title']}\t{mr['source']}")
            return
        if sub == "create":
            return create_mr(state, rest, False)
        mr = find_mr(state, positional(rest)[0] if positional(rest) else None)
        if sub == "view":
            return print_mr(mr, False, rest)
        if sub == "edit":
            return update_mr(state, mr, rest, False)
        if sub == "comment":
            add_note(state, mr, text_option(rest, ("--body", "-b"), ("--body-file", "-F")) or "")
            return print("comment added")
        if sub == "checks":
            ci = ci_for(head_of(mr["source"]))
            return print(f"test\t{'pass' if ci['status'] == 'success' else 'fail'}")
        if sub == "merge":
            return merge_mr(state, mr, "--auto" in rest)
        if sub == "diff":
            return print(git("diff", f"refs/heads/{mr['target']}...refs/heads/{mr['source']}"))
    fail(f"fake gh does not know: {' '.join(args)}")


def jira(args: list[str]) -> None:
    state = load()
    tickets = state.get("jira", [])
    if args[:2] == ["issue", "view"] and len(args) > 2:
        ticket = next((t for t in tickets if t["key"] == args[2]), None)
        if ticket is None:
            fail(f"{args[2]} not found")
        return print(f"{ticket['key']} [{ticket['status']}] {ticket['summary']}\n\n{ticket['description']}")
    if args[:2] == ["issue", "list"]:
        for ticket in tickets:
            print(f"{ticket['key']}\t{ticket['status']}\t{ticket['summary']}")
        return
    if args[:1] == ["me"]:
        return print(f"{USER}@example.com")
    # Every other command is a write; record it for the checker and accept it.
    state.setdefault("jira_writes", []).append(args)
    save(state)
    print("ok")


def main() -> None:
    tool, args = sys.argv[1], sys.argv[2:]
    log([tool, *args])
    if not args or args[0] in ("--help", "-h", "help", "--version", "version"):
        return print(f"fake {tool} for eval fixtures")
    {"glab": glab, "gh": gh, "jira": jira}[tool](args)


if __name__ == "__main__":
    main()
