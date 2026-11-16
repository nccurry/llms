# Choose how to merge and when to push

Follow the user's choice and enforced repository policy. Otherwise recommend
a method based on the change, dependent branches, and CI cost. Give the method
and a short reason in the existing report. Do not add an approval step for
routine permitted choices or expand permission to push or merge.

## Check what matters for this MR

Check allowed merge methods, squash settings, required checks, and the existing
queue/train. Reuse facts already verified in this session unless they changed.
A default squash checkbox does not mean squashing fits every MR.

Compare the actual target diff with the commit list. Prerequisites may have
landed, leaving a small change behind a long commit list. Identify dependent
MRs and whether the source branch will continue after merging.

Inspect CI configuration and recent runs when they affect the decision or push
timing. Check which jobs run for this MR, its merged result or queue/train,
and a push to the target. Include tag/release jobs only when relevant. Distinguish
time running jobs from time waiting for runners; a pipeline count alone does
not prove congestion.

## Choose a method

| Change | Recommendation when policy permits |
| --- | --- |
| Independent branch that ends at delivery | Squash temporary fixup commits. Keep useful commits that describe separate changes. |
| Stack prerequisite or continuing integration branch | Keep shared commits that dependent branches need; use a normal merge or an allowed fast-forward. |
| Stack whose delivery must squash or rebase | Record the old prerequisite tip. Move only each dependent MR's remaining changes onto the delivered target, bottom up. Refresh affected review and CI. |
| Release, backport, or upstream/mirror update | Follow existing history, sign-off, tagging, and cherry-pick conventions. |
| Plan or completion records | Include known facts with the work. Batch later results for one delivery/checkpoint. |

Squashing changes history, not the size of the final diff or the number of CI
triggers. Ship large PLCs as small, testable changes. Keep commit boundaries
that help identify or revert a bug. A clean one-commit MR needs no rewrite;
GitLab may still add a merge commit when squashing.

Do not rewrite published history just for tidiness. If a stack repair requires
rewriting an owned branch, coordinate with dependent work and protect the push
against concurrent updates. After squash merging, retire the source branch or
update it before reuse; do not replay changes already delivered.

## Push checked changes together

Group related code, tests, docs, repairs, and plan updates. Run local checks,
then push the batch when authorized. Recovery commits do not each need a push
or MR. Keep useful review increments; do not delay collaboration merely to
reduce run counts. Verify triggers: a push with several commits usually creates
one event, not a pipeline per ancestor commit.

Keep the branch stable during expensive checks. Update it for conflicts,
changed contracts, or host requirements, not just to look current. Use the
existing queue/train. Avoid bypassing it or repeatedly removing and re-adding
MRs, which can restart validation. Do not retarget an independent MR merely
to get lighter CI, or present light stack checks as final merge validation.

Record the pipeline ID, tested commit, source and target, pipeline type, and
required-job results. A merged-result or train commit can differ from the
source head. Use the pipeline's SHA, not a moving MR merge ref, to identify
earlier results. Reuse unaffected local evidence with a reason; do not carry
a required hosted pass to a new revision or mistake an external green status
for proof that required jobs ran. Run checks on the combined result as required.

Batch post-merge records; do not create another commit just to verify the
preceding record. Check whether a docs-only merge launches full target CI.
Keep required target/release runs and checks intact. Treat changes to CI rules,
capacity, or project settings as separate work.
