# Delivery proof details

The preflight makes no deletions. Its temporary indexes do not touch the real
index or worktree. Fetches may update remote-tracking refs or obtain missing
review objects; `merge-tree` may write Git objects. Review APIs use read-only GET
requests through existing CLI authentication. Never print credentials.

## Fix the comparison scope

Use the fetched, intended remote main branch and record its hash. Prefer a real
main/master ref over a cached remote HEAD, which can be stale. With multiple
remotes and no origin, select `--remote`. With a nonstandard default, inspect the
selected ref and supply `--main` if needed. Do not silently fall back to local
main when the selected remote main is missing.

For an execution workflow's explicitly chosen final destination, `--target-ref`
selects the exact full local or remote-tracking branch ref without remote-first
substitution. A remote ref must use the selected `--remote`. A local ref proves
local delivery only. The report retains the field names `baseRef` and `mainHash`
for compatibility; both identify this selected target. Do not switch from final
main to temporary integration merely because that branch contains the source.

Repeatable `--branch` and `--worktree` options narrow which branches receive
delivery checks and which worktrees may be candidates. Their selections form a
union. All registrations are still read so a branch used elsewhere cannot be
offered for deletion after removing only one selected checkout. Protections and
the complete proof sequence apply unchanged. A keep list is not a scan selector.

Each branch result records `branchHash`, `mainHash`, `forkPoint`, and `attempts`.
A changed branch or main hash invalidates that report for deletion. Missing or
shallow history may prevent proof; fetch the needed history within the authorized
repository scope, then rerun. Do not weaken the checks.

## Complete net content

Use a single established merge base and the entire binary-capable patch from
that base to the local tip. Disable external diff programs, text conversion,
rename heuristics, color, and whitespace normalization.

Load the target snapshot into a temporary index and reverse the whole patch.
Then require all touched files in the reconstructed index to equal their fork
point blobs and modes. A reverse-apply exit status alone is insufficient,
especially for deletion-only patches. This stronger check may reject content
that main has changed further; the next steps must then run automatically.

Historical search uses commits reachable from the recorded main hash at or after
the source fork, including merged side history, without an arbitrary date or commit limit. Record
the matching snapshot and independently check its ancestry in main. Later main
edits or reverts do not erase historical delivery. A canceled branch patch is
`noFileChanges`, not evidence that its individual commits were empty.

## Verified review sources

Read every page of available review metadata for the selected repository. Record
open reviews across targets so the parent can coordinate active users. An open
review is not evidence of unique local content and does not veto complete proof.
Only merged reviews targeting the selected main can provide source evidence.
Names and titles select candidates at most; they never prove delivery.

For each merged candidate:

1. Obtain the published source hash, squash hash, and review URL.
2. Obtain the exact commit objects, fetching only from the selected remote if
   necessary. Missing objects are an evidence gap, not a negative delivery finding.
3. Require the squash hash to be an ancestor of recorded main and to have one parent.
4. Run `git merge-tree --write-tree <squash-parent> <source-hash>`. Require a
   successful, conflict-free result and exact tree hash equality with the squash
   commit's tree. A conflict or mismatch preserves the candidate's unresolved work.
5. Prove the local tip is an ancestor of that source, or prove its complete net
   patch against that verified source with the same reconstructed-file check.
6. If the local branch extends beyond the verified source, account for covered
   commits by source ancestry, then check every remaining unique change.

The script supports github.com through `gh api` and GitLab-named hosts through
`glab api`, including paginated results. GitHub's published integration hash is
accepted only if its parent count and reproduced tree satisfy the squash proof;
a normal merge commit cannot be mistaken for a squash commit.

Unsupported hosts, unavailable CLI/authentication, incomplete metadata, or API
failures leave review-based proof unavailable. Continue independent history,
content, and exact-change checks; retain work if those cannot establish delivery.
Use an available host connector for authoritative review evidence when required,
then extend the provider in `review_sources.py` and rerun. Do not mark lookup
complete manually or use a saved review description as proof. A local repository
with no remote has no hosted review lookup to perform.

## Exact cherry-picked changes

The script indexes main's first-parent historical changes once per run. A merge's
first-parent diff covers imported changes and resolutions without also counting
the same side-branch delivery twice. Stable patch IDs
narrow the candidates, but they ignore whitespace and cannot authorize deletion.
The proof compares canonical patch bytes: paths, added and removed lines in
order, whitespace, newline markers, and applicable mode/binary metadata. Only
hunk positions and text blob index headers are excluded; binary blob identities
are retained. Renames are checked as deletion plus creation.

Match each hunk separately so split cherry-picks and commits containing extra
files can be accounted for. Keep creation, deletion, binary, and mode-change
patches whole. Count occurrences: one delivered change cannot cover multiple
repeated local changes. Only deliveries after the fork count. Commits after a
verified source require matching delivery after its squash commit. Empty commits
add no file-change obligation.

Enumerate unique commits after the fork, excluding commits reachable from main.
For a merge, require its complete first-parent diff as well as unique side commits.
This includes resolution edits. It deliberately may require extra evidence for
complex merges rather than dismissing them as empty or counting only ordinary
commits. Report those unmatched patches for further proof. The result records
source or main hashes for accounted changes and exact patches for unmatched ones.

## Detached commits and local content

`check_commit` applies the same committed-delivery proof to an immutable HEAD,
without inventing a branch for detached work. Exclude historical snapshots and
merged-source deliveries before the fork: a newly recreated change is not proven
delivered merely because main once contained and then reverted an earlier occurrence.

`local_changes.py` checks real index entries separately from disk files. It reads
tracked, untracked, and ignored paths, including tracked files marked assume-unchanged.
Changed states must exactly match the same path and mode in current main or in a
main snapshot at/after the proven committed delivery. A local deletion requires
absence after that boundary, not absence before the file was first delivered.
This preserves a unique staged version even if disk contents have been restored.

The inspector hashes local contents without writing objects. It allows Git's
built-in text conversion when no external clean filter is configured, retains
unproved filtered content, and reads symlink targets without following them.
Nested repositories, submodules, special files, unreadable data, and unresolved
index stages need separate proof and remain protected. Ignored files are checked
as content, not classified as disposable.

The report includes changed paths/layers, matching main snapshots, unmatched
states, index hash, and a raw-content fingerprint. Repeat preflight immediately
before removal and compare fingerprints as well as commit hashes. An index or
HEAD change during inspection invalidates that inspection. Missing review APIs
do not veto independently complete content/history proof; they still prevent any
proof that actually depends on unavailable review sources.

Exhausting a partial search, encountering an error, or finding similar lines is
not delivery proof. A concrete unmatched patch means it has no match in the
checked evidence; it does not establish that it never reached another source.

## Validation

Run the bundled behavior tests from any directory:

```sh
uv run --no-project --python ">=3.10" python -m unittest discover -s <skill-dir>/tests -v
```

Tests use disposable repositories and mocked review metadata/CLI responses.
They do not delete or change the user's repositories or contact hosted services.
Live provider authentication and host-specific API behavior still need verification
when the skill performs cleanup in that repository.
