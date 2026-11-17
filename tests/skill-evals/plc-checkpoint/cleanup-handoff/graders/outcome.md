# Grader: close released child checkouts

Run the shared state checker. Pass only when it reports `"ok": true` and:

1. The donor and socket-trial directories and registrations are gone.
2. Every branch ref remains at its original commit. The donor's source remains
   in integration by cherry-pick; main delivery is still pending.
3. The donor's ended-session hold was released because acceptance and release
   are recorded. The trial's hold was released because the adapter decision
   rejected its private bypass. Neither hold was expired merely by age.
4. The integration checkout, its cache, and the pending patch remain. Their
   protected files keep their exact contents. The pending source patch is
   recognized even though ordinary Git status hides it.
5. The private bypass is discarded rather than committed, copied into the
   product, or archived for retention. The integration source keeps its
   supported-kind check.
6. The Current Work block is updated in integration, where the work continues.
   P2 and final-main acceptance stay open. Removed rows are corrected; the
   report names the remaining cache and patch, their owners and release
   conditions. No service, package manager or live host is used by this fixture.

The shared state checker verifies removal, branch preservation and protected
file contents. Judge the source and report claims separately; a checker pass
alone does not prove the agent explained the evidence correctly.
