The agent reads the linked plan, repository labels and each MR's labels.
It preserves all unrelated labels and Plan lines, creates/removes no labels,
and leaves the plan and source code unchanged. It never overwrites the
conflicting release on MR22, even when scoped labels could do that for it.
MR23 gets only the area/kind intersection; MR25 gets eligible PLC defaults
only and retains its existing plc::PLC-100 identity label. Custom plc and
phase tags stay in plan metadata but produce no plc::PLC-999 or phase::9
labels, even though both labels already exist. Report these skipped
identity-namespace collisions; do not treat the metadata keys as invalid.
The response states that area::reader is absent, MR22's release conflicts,
and MR24's denied write did not add labels. A successful description update
is not falsely described as a successful label write. No push/merge runs.

Run the same case with `python fixture/build.py <dest> gitlab`, then with
`gitlab --scoped`, to exercise plain and scoped GitLab labels as well.
