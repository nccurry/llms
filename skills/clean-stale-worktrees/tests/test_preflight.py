import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
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
        os.chmod(Path(self.root) / 'file', 0o755)
        mode = self.commit('executable mode')
        self.g('checkout', 'main')
        self.g('cherry-pick', source, mode)
        self.write('binary', b'\x00later\x00')
        os.chmod(Path(self.root) / 'file', 0o644)
        self.commit('later binary and mode')
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
        return path

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
        self.assertIn('cache/', entry['removalReadiness']['ignoredDirectories'])
        self.assertEqual(entry['removalReadiness']['blockers'][0]['path'], str(cache))
        self.assertTrue(cache.exists())
        self.assertTrue(self.g('show-ref', '--verify', 'refs/heads/feature'))

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

    def test_dirty_locked_and_open_review_protected(self):
        worktree = self.worktree()
        self.write('unused', 'current work')
        Path(worktree, 'untracked').write_text('keep')
        self.g('worktree', 'lock', '--reason', 'keep', worktree)
        reviews = {'complete': True, 'open': [{'branch': 'feature'}], 'merged': [], 'errors': []}
        with patch('stale_worktree_preflight.discover_reviews', return_value=reviews):
            report = build_report(self.root)
        entry = next(w for w in report['worktrees'] if w['path'] == worktree)
        self.assertFalse(entry['removeCandidate'])
        for reason in ('dirty worktree', 'locked worktree', 'open MR/PR'):
            self.assertIn(reason, entry['blockedReasons'])

    def test_unreadable_status_preserved(self):
        worktree = self.worktree()
        with patch('stale_worktree_preflight.worktree_status', return_value=(None, 'cannot read')):
            report = build_report(self.root)
        entry = next(w for w in report['worktrees'] if w['path'] == worktree)
        self.assertFalse(entry['removeCandidate'])
        self.assertIsNone(entry['isDirty'])

    def test_unknown_open_review_status_blocks_proven_delivery(self):
        worktree = self.worktree()
        reviews = {'complete': False, 'open': [], 'merged': [], 'errors': ['unavailable']}
        with patch('stale_worktree_preflight.discover_reviews', return_value=reviews):
            report = build_report(self.root)
        self.assertFalse(report['cleanupCandidates']['removeWorktrees'])
        branch = next(b for b in report['branches'] if b['name'] == 'feature')
        self.assertTrue(branch['mergeCheck']['confirmed'])
        self.assertIsNone(branch['deleteCommand'])

    def test_detached_and_keep_list_protected(self):
        worktree = self.worktree()
        report = build_report(self.root, keep=['feature'])
        self.assertFalse(report['cleanupCandidates']['removeWorktrees'])
        self.g('worktree', 'remove', worktree)
        self.g('worktree', 'add', '--detach', worktree, 'main')
        report = build_report(self.root)
        entry = next(w for w in report['worktrees'] if w['path'] == worktree)
        self.assertFalse(entry['removeCandidate'])
        self.assertIn('detached or branchless worktree', entry['blockedReasons'])

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
        result = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        report = json.loads(result.stdout)
        self.assertEqual(report['cleanupCandidates']['deleteBranchesAfterWorktreeRemoval'], ['feature'])
        check = subprocess.run(command + ['--verify-removed', worktree], text=True, capture_output=True)
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
