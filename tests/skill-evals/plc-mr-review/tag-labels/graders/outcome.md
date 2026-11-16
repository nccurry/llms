The agent reads the linked plan, repository labels and each MR's labels.
It preserves all unrelated labels and Plan lines, creates/removes no labels,
and leaves the plan and source code unchanged. It never overwrites the
conflicting release on MR22, even when scoped labels could do that for it.
MR23 gets only the area/kind intersection; MR25 gets PLC defaults only.
The response states that area::reader is absent, MR22's release conflicts,
and MR24's denied write did not add labels. A successful description update
is not falsely described as a successful label write. No push/merge runs.

Run the same case with `python fixture/build.py <dest> gitlab`, then with
`gitlab --scoped`, to exercise plain and scoped GitLab labels as well.
