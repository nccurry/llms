import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from delivery_checks import DeliveryChecks, exact_changes, git
from removal_checks import removal_preflight, verify_removed
from review_sources import discover_reviews, json_pages
from stale_worktree_preflight import build_report, parse_worktrees


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = str(Path(self.directory.name) / 'repo')
        os.mkdir(self.root)
        self.g('init', '-b', 'main')
        self.g('config', 'user.email', 'test@example.invalid')
        self.g('config', 'user.name', 'Test')
        self.write('file', 'old\n' + ''.join(f'line {i}\n' for i in range(12)))
        self.write('.gitignore', 'cache/\n')
        self.commit('initial')
        self.fork = self.head()

    def g(self, *args):
        return git(self.root, *args).decode().strip()

    def head(self):
        return self.g('rev-parse', 'HEAD')

    def write(self, name, content):
        path = Path(self.root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())

    def commit(self, message):
        self.g('add', '-A')
        self.g('commit', '-m', message)
        return self.head()

    def branch(self):
        self.g('checkout', '-b', 'feature')

    def check(self, reviews=None):
        return DeliveryChecks(self.root, self.g('rev-parse', 'main'),
                              reviews or {'complete': True, 'merged': [], 'remote': None}).check('feature')

    def squash(self):
        self.g('checkout', 'main')
        self.g('merge', '--squash', 'feature')
        return self.commit('squashed')

    def test_ancestry(self):
        self.branch()
        self.write('extra', 'delivered\n')
        self.commit('change')
        self.g('checkout', 'main')
        self.g('merge', '--ff-only', 'feature')
        self.assertEqual(self.check()['method'], 'commitHistory')

    def test_current_squash(self):
        self.branch()
        self.write('extra', 'delivered\n')
        self.commit('change')
        self.squash()
        self.assertEqual(self.check()['method'], 'contentMatch')

    def test_historical_squash_after_later_edit(self):
        self.branch()
        self.write('file', 'delivered\n')
        self.commit('change')
        squash = self.squash()
        self.write('file', 'later\n')
        self.commit('later edit')
        result = self.check()
        self.assertEqual(result['method'], 'historicalMain')
        self.assertEqual(result['attempts'][-1]['snapshot'], squash)

    def test_never_delivered_deletion_is_preserved(self):
        self.branch()
        self.write('file', ''.join(f'line {i}\n' for i in range(12)))
        self.commit('delete first line')
        self.g('checkout', 'main')
        result = self.check()
        self.assertFalse(result['confirmed'])
        self.assertEqual(result['method'], 'deliveryNotProven')
        self.assertTrue(result['unmatchedChanges'])
        self.assertEqual([a['check'] for a in result['attempts']],
                         ['currentMain', 'historicalMain', 'mergedSources', 'cherryPicks'])

    def test_no_net_changes(self):
        self.branch()
        self.write('extra', 'temporary\n')
        change = self.commit('change')
        self.g('revert', '--no-edit', change)
        self.g('checkout', 'main')
        result = self.check()
        self.assertEqual(result['method'], 'noFileChanges')
        self.assertNotIn('empty', result['reason'])

    def test_verified_source_integration_and_later_edits(self):
        original = (Path(self.root) / 'file').read_text()
        self.branch()
        self.write('file', original.replace('old\n', 'delivered\n'))
        source = self.commit('source')
        self.g('checkout', 'main')
        self.write('file', original.replace('line 11\n', 'main-only change\n'))
        self.commit('target changes in same file')
        squash = self.squash()
        self.write('file', 'later\n')
        self.commit('later changes')
        reviews = {'complete': True, 'remote': None, 'merged': [
            {'sourceHash': source, 'squashHash': squash, 'url': 'https://example.invalid/mr/1'}]}
        result = self.check(reviews)
        self.assertEqual(result['method'], 'mergedSource', result)
        self.assertEqual(result['source']['integrationTree'], self.g('rev-parse', squash + '^{tree}'))
        self.assertFalse(result['attempts'][1]['matched'])

    def test_mismatched_source_tree_rejected(self):
        self.branch()
        self.write('extra', 'source\n')
        source = self.commit('source')
        squash = self.squash()
        self.write('extra', 'wrong squash content\n')
        self.g('add', '-A')
        self.g('commit', '--amend', '-m', 'different integration')
        squash = self.head()
        checks = DeliveryChecks(self.root, squash, {'complete': True, 'remote': None, 'merged': [
            {'sourceHash': source, 'squashHash': squash, 'url': 'review'}]})
        self.assertEqual(checks.merged_sources(), [])
        self.assertIn('differs', checks.source_errors[0]['reason'])

    def test_missing_review_object_preserved(self):
        checks = DeliveryChecks(self.root, self.head(), {'complete': True, 'remote': None, 'merged': [
            {'sourceHash': 'a' * 40, 'squashHash': self.head(), 'url': 'review'}]})
        self.assertEqual(checks.merged_sources(), [])
        self.assertIn('missing', checks.source_errors[0]['reason'])

    def test_source_squash_outside_main_rejected(self):
        self.branch()
        self.write('extra', 'source\n')
        source = self.commit('source')
        squash = self.squash()
        self.g('reset', '--hard', self.fork)
        checks = DeliveryChecks(self.root, self.head(), {'complete': True, 'remote': None, 'merged': [
            {'sourceHash': source, 'squashHash': squash, 'url': 'review'}]})
        self.assertEqual(checks.merged_sources(), [])

    def test_split_cherry_picks_exact_hunks(self):
        original = (Path(self.root) / 'file').read_text()
        self.branch()
        self.write('file', original.replace('old\n', 'first\n').replace('line 11\n', 'second\n'))
        self.commit('two separate hunks')
        self.g('checkout', 'main')
        self.write('file', original.replace('old\n', 'first\n') + 'main-only tail\n')
        self.commit('first hunk plus unrelated edit')
        self.write('file', (Path(self.root) / 'file').read_text().replace('line 11\n', 'second\n'))
        self.commit('second hunk')
        self.write('file', 'changed again\n')
        self.commit('later edits')
        result = self.check()
        self.assertEqual(result['method'], 'exactChanges', result)
        self.assertEqual(len(result['attempts'][-1]['accountedChanges']), 2)

    def test_patch_id_does_not_hide_whitespace(self):
        self.branch()
        self.write('file', 'value = 1\n')
        source = self.commit('source')
        branch_changes = exact_changes(self.root, self.fork, source)
        self.g('checkout', 'main')
        self.write('file', 'value=1\n')
        candidate = self.commit('whitespace differs')
        target_changes = exact_changes(self.root, self.fork, candidate)
        self.assertEqual(branch_changes[0][0], target_changes[0][0])
        self.assertNotEqual(branch_changes[0][1], target_changes[0][1])
        self.assertFalse(self.check()['confirmed'])

    def test_post_merge_work_remains(self):
        self.branch()
        self.write('file', 'delivered\n')
        source = self.commit('source')
        squash = self.squash()
        self.write('file', 'later\n')
        self.commit('target later edit')
        self.g('checkout', 'feature')
        self.write('new', 'undelivered\n')
        post = self.commit('post-merge change')
        self.g('checkout', 'main')
        result = self.check({'complete': True, 'remote': None, 'merged': [
            {'sourceHash': source, 'squashHash': squash, 'url': 'review'}]})
        self.assertFalse(result['confirmed'])
        self.assertIn(post, [c['commit'] for c in result['unmatchedChanges']])

    def test_merge_resolution_remains(self):
        self.branch()
        self.write('file', 'feature\n')
        feature = self.commit('feature')
        self.g('checkout', '-b', 'side', self.fork)
        self.write('other', 'side\n')
        side = self.commit('side')
        self.g('checkout', 'feature')
        self.g('merge', '--no-commit', '--no-ff', 'side')
        self.write('resolution', 'merge-only work\n')
        merge = self.commit('merge with extra change')
        self.g('checkout', 'main')
        self.g('cherry-pick', feature, side)
        self.write('file', 'target later\n')
        self.commit('later')
        result = self.check()
        self.assertFalse(result['confirmed'])
        self.assertIn(merge, [c['commit'] for c in result['unmatchedChanges']])

    def test_repeated_change_requires_multiple_deliveries(self):
        original = (Path(self.root) / 'file').read_text()
        self.branch()
        self.write('file', 'new\n')
        first = self.commit('first occurrence')
        self.write('file', original)
        back = self.commit('reverse local change')
        self.write('file', 'new\n')
        repeated = self.commit('repeat identical change')
        self.write('extra', 'also delivered\n')
        extra = self.commit('separate change')
        self.g('checkout', 'main')
        self.g('cherry-pick', first, back, extra)
        # Main received one forward and one reverse occurrence, plus extra.
        # No full snapshot contains the final branch files together.
        result = self.check()
        self.assertFalse(result['confirmed'], result)
        self.assertEqual(result['unmatchedChanges'][0]['commit'], repeated)
        self.assertEqual(len(result['unmatchedChanges']), 1)

    def test_old_prefork_change_is_not_a_new_delivery(self):
        original = (Path(self.root) / 'file').read_text()
        self.write('file', 'seen long ago\n')
        self.commit('old change')
        self.write('file', original)
        self.commit('old change reversed')
        self.fork = self.head()
        self.branch()
        self.write('file', 'seen long ago\n')
        self.commit('new local occurrence')
        self.write('extra', 'delivered extra\n')
        extra = self.commit('extra')
        self.g('checkout', 'main')
        self.g('cherry-pick', extra)
        result = self.check()
        self.assertFalse(result['confirmed'], result)
        self.assertTrue(result['unmatchedChanges'])

    def test_gitlink_change_cannot_be_hidden_by_diff_configuration(self):
        self.branch()
        self.g('config', 'diff.ignoreSubmodules', 'all')
        self.g('update-index', '--add', '--cacheinfo', '160000,' + self.fork + ',dependency')
        self.g('commit', '-m', 'undelivered gitlink')
        result = self.check()
        self.assertFalse(result['confirmed'], result)
        self.assertNotEqual(result['method'], 'noFileChanges')
        self.assertIn('Subproject commit', result['unmatchedChanges'][0]['exactChange'])

    @unittest.skipIf(os.name == 'nt', 'Windows does not permit colon filenames')
    def test_literal_pathspec_names_do_not_hide_unmatched_files(self):
        self.branch()
        self.write(':!file', 'must be checked\n')
        self.commit('literal pathspec-like file')
        self.g('checkout', 'main')
        self.assertFalse(self.check()['confirmed'])

    def test_binary_and_mode_changes_need_exact_delivery(self):
        self.branch()
        self.write('binary', b'\x00one\x00')
        source = self.commit('binary content')
        self.g('update-index', '--chmod=+x', 'file')
        self.g('commit', '-m', 'executable mode')
        mode = self.head()
        self.g('checkout', 'main')
        self.g('cherry-pick', source, mode)
        self.write('binary', b'\x00later\x00')
        self.g('add', '-A')
        self.g('update-index', '--chmod=-x', 'file')
        self.g('commit', '-m', 'later binary and mode')
        result = self.check()
        # Earlier exact snapshot proves both bytes and mode.
        self.assertTrue(result['confirmed'], result)
        self.g('reset', '--hard', self.fork)
        self.write('binary', b'\x00wrong\x00')
        self.commit('wrong binary')
        self.assertFalse(self.check()['confirmed'])

    def test_missing_registered_directory_is_not_removed(self):
        worktree = self.worktree()
        moved = worktree + '-moved'
        os.rename(worktree, moved)
        result = verify_removed(self.root, worktree)
        self.assertFalse(result['removed'])
        self.assertTrue(result['directoryAbsent'])
        self.assertFalse(result['registrationAbsent'])
        report = build_report(self.root)
        entry = next(w for w in report['worktrees'] if w['path'] == worktree)
        self.assertFalse(entry['removeCandidate'])

    def worktree(self, name='linked'):
        self.branch()
        self.write('extra', 'delivered\n')
        self.commit('source')
        self.squash()
        path = str(Path(self.directory.name) / name)
        self.g('worktree', 'add', path, 'feature')
        # Git reports forward-slash paths on Windows as well as POSIX.
        return Path(path).as_posix()

    @unittest.skipIf(os.name == 'nt', 'POSIX directory mode restrictions are not Windows ACLs')
    def test_readonly_ignored_directory_blocks_before_removal(self):
        worktree = self.worktree()
        cache = Path(worktree) / 'cache'
        cache.mkdir()
        (cache / 'object').write_text('build artifact')
        cache.chmod(0o555)
        self.addCleanup(cache.chmod, 0o755)
        report = build_report(self.root)
        entry = next(w for w in report['worktrees'] if w['path'] == worktree)
        self.assertFalse(entry['removeCandidate'])
        readiness = removal_preflight(worktree)
        self.assertIn('cache/', readiness['ignoredDirectories'])
        self.assertEqual(readiness['blockers'][0]['path'], str(cache))
        self.assertTrue(cache.exists())
        self.assertTrue(self.g('show-ref', '--verify', 'refs/heads/feature'))

    @unittest.skipIf(os.name == 'nt', 'Requires POSIX directory modes and unprivileged symlinks')
    def test_readonly_file_and_external_symlink_are_safe_to_inspect(self):
        worktree = self.worktree()
        cache = Path(worktree) / 'cache'
        cache.mkdir()
        object_path = cache / 'object'
        object_path.write_text('artifact')
        object_path.chmod(0o444)
        outside = Path(self.directory.name) / 'external'
        outside.mkdir()
        outside.chmod(0o555)
        self.addCleanup(outside.chmod, 0o755)
        (cache / 'external').symlink_to(outside, target_is_directory=True)
        self.assertTrue(removal_preflight(worktree)['ready'])

    def test_locked_worktree_stays_protected(self):
        worktree = self.worktree()
        self.write('unused', 'current work')
        Path(worktree, 'untracked').write_text('keep')
        self.g('worktree', 'lock', '--reason', 'keep', worktree)
        reviews = {'complete': True, 'open': [{'branch': 'feature'}], 'merged': [], 'errors': []}
        with patch('stale_worktree_preflight.discover_reviews', return_value=reviews):
            report = build_report(self.root)
        entry = next(w for w in report['worktrees'] if w['path'] == worktree)
        self.assertFalse(entry['removeCandidate'])
        self.assertIn('locked worktree', entry['blockedReasons'])
        self.assertTrue(next(b for b in report['branches'] if b['name'] == 'feature')['hasOpenReview'])

    def test_unreadable_status_preserved(self):
        worktree = self.worktree()
        with patch('stale_worktree_preflight.worktree_status', return_value=(None, 'cannot read')):
            report = build_report(self.root)
        entry = next(w for w in report['worktrees'] if w['path'] == worktree)
        self.assertFalse(entry['removeCandidate'])
        self.assertIsNone(entry['isDirty'])

    def test_unknown_open_review_status_does_not_veto_complete_git_proof(self):
        self.worktree()
        reviews = {'complete': False, 'open': [], 'merged': [], 'errors': ['unavailable']}
        with patch('stale_worktree_preflight.discover_reviews', return_value=reviews):
            report = build_report(self.root)
        self.assertTrue(report['cleanupCandidates']['removeWorktrees'])
        branch = next(b for b in report['branches'] if b['name'] == 'feature')
        self.assertTrue(branch['mergeCheck']['confirmed'])
        self.assertIsNotNone(branch['deleteCommand'])

    def test_detached_main_is_eligible_and_keep_list_is_protected(self):
        worktree = self.worktree()
        report = build_report(self.root, keep=['feature'])
        self.assertFalse(report['cleanupCandidates']['removeWorktrees'])
        self.g('worktree', 'remove', worktree)
        self.g('worktree', 'add', '--detach', worktree, 'main')
        report = build_report(self.root)
        entry = next(w for w in report['worktrees'] if w['path'] == worktree)
        self.assertTrue(entry['removeCandidate'], entry)
        self.assertEqual(entry['mergeCheck']['method'], 'commitHistory')
        self.assertNotIn(None, report['cleanupCandidates']['deleteBranchesAfterWorktreeRemoval'])

    def test_detached_squash_is_eligible_but_unique_commit_is_preserved(self):
        worktree = self.worktree()
        self.g('worktree', 'remove', worktree)
        self.g('worktree', 'add', '--detach', worktree, 'feature')
        report = build_report(self.root, selected_worktrees=[worktree])
        self.assertTrue(report['worktrees'][0]['removeCandidate'], report)
        Path(worktree, 'unique').write_bytes(b'not in main\n')
        git(worktree, 'add', 'unique')
        git(worktree, 'commit', '-m', 'unique detached work')
        report = build_report(self.root, selected_worktrees=[worktree])
        self.assertFalse(report['worktrees'][0]['removeCandidate'])
        self.assertFalse(report['worktrees'][0]['mergeCheck']['confirmed'])

    def test_dirty_tracked_content_in_main_can_be_removed(self):
        worktree = self.worktree()
        self.write('extra', 'new main content\n')
        self.commit('main update')
        Path(worktree, 'extra').write_bytes(b'new main content\n')
        report = build_report(self.root, selected_worktrees=[worktree])
        entry = report['worktrees'][0]
        self.assertTrue(entry['removeCandidate'], entry)
        self.assertTrue(entry['requiresForce'])
        self.assertTrue(entry['localContentCheck']['confirmed'])
        git(self.root, 'worktree', 'remove', '--force', worktree)
        self.assertTrue(verify_removed(self.root, worktree)['removed'])

    def test_dirty_unique_content_is_preserved(self):
        worktree = self.worktree()
        Path(worktree, 'extra').write_bytes(b'not in main\n')
        report = build_report(self.root, selected_worktrees=[worktree])
        entry = report['worktrees'][0]
        self.assertFalse(entry['removeCandidate'])
        self.assertEqual(entry['localContentCheck']['unmatched'][0]['path'], 'extra')
        self.assertEqual(Path(worktree, 'extra').read_bytes(), b'not in main\n')

    def test_unique_staged_version_is_not_hidden_by_delivered_working_file(self):
        worktree = self.worktree()
        Path(worktree, 'extra').write_bytes(b'unique staged work\n')
        git(worktree, 'add', 'extra')
        Path(worktree, 'extra').write_bytes(b'delivered\n')
        before = git(worktree, 'show', ':extra')
        report = build_report(self.root, selected_worktrees=[worktree])
        entry = report['worktrees'][0]
        self.assertFalse(entry['removeCandidate'])
        self.assertEqual(entry['localContentCheck']['unmatched'][0]['layer'], 'index')
        self.assertEqual(git(worktree, 'show', ':extra'), before)

    def test_staged_and_unstaged_versions_already_in_main_are_eligible(self):
        worktree = self.worktree()
        self.write('extra', 'stage version\n')
        self.commit('stage version delivered')
        self.write('extra', 'disk version\n')
        self.commit('disk version delivered')
        Path(worktree, 'extra').write_bytes(b'stage version\n')
        git(worktree, 'add', 'extra')
        Path(worktree, 'extra').write_bytes(b'disk version\n')
        report = build_report(self.root, selected_worktrees=[worktree])
        self.assertTrue(report['worktrees'][0]['removeCandidate'], report)
        self.assertEqual({row['layer'] for row in report['worktrees'][0]['localContentCheck']['changes']},
                         {'index', 'worktree'})

    def test_local_deletion_requires_delivery_after_the_committed_source(self):
        worktree = self.worktree()
        Path(worktree, 'extra').unlink()
        report = build_report(self.root, selected_worktrees=[worktree])
        self.assertFalse(report['worktrees'][0]['removeCandidate'])
        self.g('rm', 'extra')
        self.commit('deletion delivered')
        report = build_report(self.root, selected_worktrees=[worktree])
        self.assertTrue(report['worktrees'][0]['removeCandidate'], report)

    def test_untracked_and_ignored_content_in_main_are_eligible(self):
        worktree = self.worktree()
        for name in ('untracked', 'cache/ignored'):
            self.write(name, 'already in main\n')
            self.g('add', '-f', name)
            self.g('commit', '-m', 'deliver ' + name)
            path = Path(worktree, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'already in main\n')
        report = build_report(self.root, selected_worktrees=[worktree])
        self.assertTrue(report['worktrees'][0]['removeCandidate'], report)

    def test_untracked_and_ignored_content_absent_from_main_are_preserved(self):
        worktree = self.worktree()
        Path(worktree, 'scratch.tmp').write_bytes(b'looks disposable but is not in main\n')
        Path(worktree, 'cache').mkdir()
        Path(worktree, 'cache', 'output').write_bytes(b'ignored and not in main\n')
        report = build_report(self.root, selected_worktrees=[worktree])
        entry = report['worktrees'][0]
        self.assertFalse(entry['removeCandidate'])
        self.assertEqual({row['path'] for row in entry['localContentCheck']['unmatched']},
                         {'scratch.tmp', 'cache/output'})

    def test_local_fingerprint_detects_file_and_index_changes(self):
        worktree = self.worktree()
        original = build_report(self.root, selected_worktrees=[worktree])['worktrees'][0]['localContentCheck']
        Path(worktree, 'extra').write_bytes(b'new unique work\n')
        changed = build_report(self.root, selected_worktrees=[worktree])['worktrees'][0]['localContentCheck']
        self.assertNotEqual(original['fingerprint'], changed['fingerprint'])
        self.assertFalse(changed['confirmed'])
        git(worktree, 'add', 'extra')
        staged = build_report(self.root, selected_worktrees=[worktree])['worktrees'][0]['localContentCheck']
        self.assertNotEqual(changed['fingerprint'], staged['fingerprint'])

    def test_assume_unchanged_does_not_hide_unique_disk_content(self):
        worktree = self.worktree()
        git(worktree, 'update-index', '--assume-unchanged', 'extra')
        Path(worktree, 'extra').write_bytes(b'hidden unique work\n')
        report = build_report(self.root, selected_worktrees=[worktree])
        self.assertFalse(report['worktrees'][0]['removeCandidate'])
        self.assertEqual(report['worktrees'][0]['localContentCheck']['unmatched'][0]['path'], 'extra')

    def test_recreated_change_before_fork_is_not_a_new_delivery(self):
        self.write('file', 'old occurrence\n')
        self.commit('earlier occurrence')
        self.write('file', 'new baseline\n')
        self.commit('earlier occurrence reverted')
        self.branch()
        self.write('file', 'old occurrence\n')
        self.commit('new undelivered occurrence')
        self.g('checkout', 'main')
        self.assertFalse(self.check()['confirmed'])

    def test_content_match_uses_earliest_delivery_for_local_history(self):
        worktree = self.worktree()
        self.write('file', 'historical local state\n')
        self.commit('local state delivered')
        self.write('file', 'main moved on\n')
        self.commit('later main state')
        Path(worktree, 'file').write_bytes(b'historical local state\n')
        report = build_report(self.root, selected_worktrees=[worktree])
        entry = report['worktrees'][0]
        self.assertEqual(entry['mergeCheck']['method'], 'contentMatch')
        self.assertTrue(entry['removeCandidate'], entry)
        repeat = build_report(self.root, selected_worktrees=[worktree])['worktrees'][0]
        self.assertEqual(entry['localContentCheck']['fingerprint'], repeat['localContentCheck']['fingerprint'])

    def test_local_history_accepts_independent_deliveries_on_merged_sides(self):
        worktree = self.worktree()
        self.g('checkout', '-b', 'side', self.fork)
        self.write('extra', 'delivered\n')
        self.write('file', 'side state already in main history\n')
        self.commit('independent side delivery')
        self.write('file', 'old\n' + ''.join(f'line {i}\n' for i in range(12)))
        self.commit('side state moved on')
        self.g('checkout', 'main')
        self.g('merge', '--no-ff', 'side', '-m', 'merge side')
        Path(worktree, 'file').write_bytes(b'side state already in main history\n')
        report = build_report(self.root, selected_worktrees=[worktree])
        self.assertTrue(report['worktrees'][0]['removeCandidate'], report)

    def test_filemode_false_does_not_hide_symlink_type_change(self):
        self.g('config', 'core.filemode', 'false')
        self.g('config', 'core.symlinks', 'false')
        self.write('link', 'target')
        oid = git(self.root, 'hash-object', '-w', '--stdin', data=b'target').decode().strip()
        self.g('update-index', '--add', '--cacheinfo', '120000', oid, 'link')
        self.g('commit', '-m', 'symlink delivered')
        worktree = self.worktree()
        self.g('config', 'core.symlinks', 'true')
        report = build_report(self.root, selected_worktrees=[worktree])
        entry = report['worktrees'][0]
        self.assertFalse(entry['removeCandidate'])
        self.assertEqual(entry['localContentCheck']['unmatched'][0]['entry'][0], '100644')

    def test_verify_both_directory_and_registration(self):
        worktree = self.worktree('linked with spaces')
        initial = verify_removed(self.root, worktree)
        self.assertFalse(initial['removed'])
        self.g('worktree', 'remove', worktree)
        self.assertTrue(verify_removed(self.root, worktree)['removed'])
        os.mkdir(worktree)
        orphan = verify_removed(self.root, worktree)
        self.assertFalse(orphan['removed'])
        self.assertTrue(orphan['registrationAbsent'])
        self.assertFalse(orphan['directoryAbsent'])

    def test_cli_reports_candidates_and_failed_removal_verification(self):
        worktree = self.worktree()
        command = [sys.executable, str(SCRIPTS / 'stale_worktree_preflight.py'), '--path', self.root]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        report = json.loads(result.stdout)
        self.assertEqual(report['cleanupCandidates']['deleteBranchesAfterWorktreeRemoval'], ['feature'])
        check = subprocess.run(command + ['--verify-removed', worktree], text=True, capture_output=True, check=False)
        self.assertEqual(check.returncode, 2)
        self.assertFalse(json.loads(check.stdout)['removed'])

    def test_remote_main_wins_over_stale_local_main_and_cached_head(self):
        self.branch()
        self.write('extra', 'delivered\n')
        self.commit('source')
        squash = self.squash()
        self.g('remote', 'add', 'origin', self.root)
        self.g('update-ref', 'refs/remotes/origin/main', squash)
        self.g('update-ref', 'refs/remotes/origin/old-default', self.fork)
        self.g('symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/old-default')
        self.g('reset', '--hard', self.fork)
        reviews = {'complete': True, 'open': [], 'merged': [], 'errors': []}
        with patch('stale_worktree_preflight.discover_reviews', return_value=reviews):
            report = build_report(self.root)
        self.assertEqual(report['baseRef'], 'refs/remotes/origin/main')
        self.assertEqual(report['mainHash'], squash)
        branch = next(b for b in report['branches'] if b['name'] == 'feature')
        self.assertTrue(branch['mergeCheck']['confirmed'])

    def test_selected_branch_limits_delivery_checks_and_worktrees(self):
        worktree = self.worktree()
        unrelated = str(Path(self.directory.name) / 'unrelated')
        self.g('worktree', 'add', '-b', 'unrelated', unrelated, 'main')
        checked = []
        original_check = DeliveryChecks.check

        def record_check(checks, branch):
            checked.append(branch)
            return original_check(checks, branch)

        with patch.object(DeliveryChecks, 'check', record_check):
            report = build_report(self.root, selected_branches=['feature'])
        self.assertEqual(checked, ['feature'])
        self.assertEqual([b['name'] for b in report['branches']], ['feature'])
        self.assertEqual([w['path'] for w in report['worktrees']], [worktree])
        self.assertEqual(report['cleanupCandidates']['deleteBranchesAfterWorktreeRemoval'], ['feature'])
        self.assertTrue(Path(unrelated).is_dir())

    def test_selected_worktree_does_not_offer_branch_checked_out_elsewhere(self):
        worktree = self.worktree('linked with spaces')
        other = str(Path(self.directory.name) / 'other')
        self.g('worktree', 'add', '--force', other, 'feature')
        report = build_report(self.root, selected_worktrees=[worktree])
        self.assertEqual([w['path'] for w in report['worktrees']], [worktree])
        self.assertEqual([b['name'] for b in report['branches']], ['feature'])
        self.assertEqual(len(report['cleanupCandidates']['removeWorktrees']), 1)
        self.assertFalse(report['cleanupCandidates']['deleteBranchesNow'])
        self.assertFalse(report['cleanupCandidates']['deleteBranchesAfterWorktreeRemoval'])
        self.assertTrue(Path(other).is_dir())

    def test_unknown_selection_stops_before_delivery_checks(self):
        self.worktree()
        with patch.object(DeliveryChecks, 'check') as check:
            with self.assertRaisesRegex(RuntimeError, 'selected branch does not exist'):
                build_report(self.root, selected_branches=['missing'])
            with self.assertRaisesRegex(RuntimeError, 'selected worktree is not registered'):
                build_report(self.root, selected_worktrees=[str(Path(self.directory.name) / 'missing')])
            check.assert_not_called()

    def test_local_target_ref_works_without_a_remote_counterpart(self):
        self.worktree()
        self.g('branch', 'integration', 'main')
        self.g('remote', 'add', 'origin', self.root)
        self.g('update-ref', 'refs/remotes/origin/main', self.fork)
        reviews = {'complete': True, 'open': [], 'merged': [], 'errors': []}
        with patch('stale_worktree_preflight.discover_reviews', return_value=reviews):
            default = build_report(self.root, selected_branches=['feature'])
            report = build_report(self.root, target_ref='refs/heads/integration',
                                  selected_branches=['feature'])
        self.assertFalse(default['branches'][0]['mergeCheck']['confirmed'])
        self.assertEqual(report['baseRef'], 'refs/heads/integration')
        self.assertEqual(report['mainHash'], self.g('rev-parse', 'integration'))
        self.assertTrue(report['branches'][0]['mergeCheck']['confirmed'])

    def test_temporary_integration_does_not_prove_delivery_to_main(self):
        self.branch()
        self.write('extra', 'delivered to integration only\n')
        self.commit('source')
        self.g('checkout', '-b', 'integration', 'main')
        self.g('merge', '--squash', 'feature')
        self.commit('integration squash')
        self.g('checkout', 'main')
        default = build_report(self.root, selected_branches=['feature'])
        self.assertFalse(default['branches'][0]['mergeCheck']['confirmed'])
        explicit = build_report(self.root, target_ref='refs/heads/integration',
                                selected_branches=['feature'])
        self.assertTrue(explicit['branches'][0]['mergeCheck']['confirmed'])

    def test_invalid_or_conflicting_target_ref_is_rejected(self):
        for target in ('main', 'HEAD', 'refs/tags/main', 'refs/heads/missing'):
            with self.subTest(target=target), self.assertRaises(RuntimeError):
                build_report(self.root, target_ref=target)
        with self.assertRaisesRegex(RuntimeError, 'choose either'):
            build_report(self.root, requested_main='main', target_ref='refs/heads/main')

    def test_cli_accepts_exact_selection_and_target_ref(self):
        worktree = self.worktree()
        command = [sys.executable, str(SCRIPTS / 'stale_worktree_preflight.py'),
                   '--path', self.root, '--target-ref', 'refs/heads/main',
                   '--branch', 'feature', '--worktree', worktree]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        report = json.loads(result.stdout)
        self.assertEqual([b['name'] for b in report['branches']], ['feature'])
        self.assertEqual([w['path'] for w in report['worktrees']], [worktree])
        self.assertTrue(report['branches'][0]['mergeCheck']['confirmed'])

    def test_preflight_does_not_touch_real_index_or_files(self):
        self.worktree()
        self.write('staged', 'keep staged\n')
        self.g('add', 'staged')
        before = self.g('status', '--porcelain')
        index_path = Path(self.root) / '.git' / 'index'
        index = index_path.read_bytes()
        build_report(self.root)
        self.assertEqual(self.g('status', '--porcelain'), before)
        self.assertEqual(index_path.read_bytes(), index)


class ParsingTests(unittest.TestCase):
    def test_nul_worktree_paths_and_lock(self):
        data = b'worktree /tmp/name\nwith spaces\0HEAD abc\0branch refs/heads/a\0locked keep\0\0'
        entry = parse_worktrees(data)[0]
        self.assertEqual(entry['path'], '/tmp/name\nwith spaces')
        self.assertTrue(entry['locked'])
        self.assertEqual(entry['lockedReason'], 'keep')

    def test_paginated_review_json(self):
        self.assertEqual(json_pages('[{"id":1}]\n[{"id":2}]'), [{'id': 1}, {'id': 2}])
        with self.assertRaises(ValueError):
            json_pages('{"error":"denied"}')
        with self.assertRaises(ValueError):
            json_pages('')

    def test_gitlab_open_review_to_other_target_still_protected(self):
        responses = [subprocess.CompletedProcess([], 0, 'git@gitlab.example:team/repo.git\n', ''),
                     subprocess.CompletedProcess([], 0,
                       '[{"sha":"abc","source_branch":"feature","state":"opened",'
                       '"target_branch":"release","source_project_id":1,"target_project_id":1,'
                       '"web_url":"review"}]', '')]
        with patch('review_sources.subprocess.run', side_effect=responses) as run:
            reviews = discover_reviews('/repo', 'origin', 'main')
        self.assertTrue(reviews['complete'])
        self.assertEqual(reviews['open'][0]['branch'], 'feature')
        self.assertIn('--paginate', run.call_args.args[0])
        self.assertIn('scope=all', run.call_args.args[0][-1])

    def test_lookup_failure_does_not_claim_closed(self):
        responses = [subprocess.CompletedProcess([], 0, 'git@github.com:team/repo.git\n', ''),
                     subprocess.CompletedProcess([], 1, '', 'auth failed')]
        with patch('review_sources.subprocess.run', side_effect=responses):
            reviews = discover_reviews('/repo', 'origin', 'main')
        self.assertFalse(reviews['complete'])
        self.assertTrue(reviews['errors'])


if __name__ == '__main__':
    unittest.main()
