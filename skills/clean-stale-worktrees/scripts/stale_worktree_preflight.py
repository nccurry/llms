#!/usr/bin/env python3
"""Preview delivery evidence and removal readiness; never delete user work."""
import argparse
import json
import os
import subprocess
import sys

from delivery_checks import DeliveryChecks, git
from local_changes import LocalChanges
from removal_checks import removal_preflight, verify_removed
from review_sources import discover_reviews


def same_path(left, right):
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def parse_worktrees(output):
    """Parse Git's NUL format so quoted, spaced, and newline paths stay intact."""
    worktrees, current = [], None
    for field in output.split(b'\0'):
        if field.startswith(b'worktree '):
            current = {'path': os.fsdecode(field[9:]), 'head': None, 'branch': None,
                       'detached': False, 'bare': False, 'locked': False, 'prunable': False}
            worktrees.append(current)
        elif current is not None:
            key, _, value = field.partition(b' ')
            if key == b'HEAD':
                current['head'] = value.decode()
            elif key == b'branch' and value.startswith(b'refs/heads/'):
                current['branch'] = os.fsdecode(value[11:])
            elif key in (b'detached', b'bare', b'locked', b'prunable'):
                current[key.decode()] = True
                if value:
                    current[key.decode() + 'Reason'] = os.fsdecode(value)
    return worktrees


def worktree_status(path):
    try:
        output = git(path, 'status', '--porcelain=v1', '-z', '--untracked-files=all',
                     '--ignore-submodules=none')
        return [os.fsdecode(field) for field in output.split(b'\0') if field], None
    except (RuntimeError, OSError) as exc:
        return None, str(exc)


def choose_refs(root, requested, remote, target_ref=None):
    refs = set(git(root, 'for-each-ref', '--format=%(refname)').decode().splitlines())
    if target_ref:
        if requested:
            raise RuntimeError('choose either --main or --target-ref')
        prefixes = ['refs/heads/'] + ([f'refs/remotes/{remote}/'] if remote else [])
        prefix = next((value for value in prefixes if target_ref.startswith(value)), None)
        if not prefix or target_ref not in refs:
            raise RuntimeError('target ref must be an existing full local branch ref or selected remote branch ref')
        symbolic = subprocess.run(['git', '-C', root, 'symbolic-ref', '--quiet', target_ref],
                                  capture_output=True, check=False)
        if symbolic.returncode != 1:
            raise RuntimeError('target ref must name a branch directly, not a symbolic ref')
        return target_ref[len(prefix):], target_ref
    if requested:
        main = requested
    else:
        # Prefer main/master over a possibly stale cached remote HEAD.
        main = next((name for name in ('main', 'master')
                     if f'refs/heads/{name}' in refs or f'refs/remotes/{remote}/{name}' in refs), None)
        if not main and remote:
            result = subprocess.run(['git', '-C', root, 'symbolic-ref', '--quiet',
                                     f'refs/remotes/{remote}/HEAD'], capture_output=True, text=True, check=False)
            prefix = f'refs/remotes/{remote}/'
            if result.returncode == 0 and result.stdout.strip().startswith(prefix):
                main = result.stdout.strip()[len(prefix):]
    if not main:
        raise RuntimeError('no main branch detected; select the intended branch with --main')
    remote_ref = f'refs/remotes/{remote}/{main}' if remote else None
    if remote_ref in refs:
        return main, remote_ref
    local = f'refs/heads/{main}'
    if local not in refs:
        raise RuntimeError('selected main branch does not exist')
    if remote:
        raise RuntimeError('remote exists but selected remote main is missing; fetch or select --remote/--main')
    return main, local


def build_report(path, requested_main=None, requested_remote=None, keep=(), fetch=False,
                 *, target_ref=None, selected_branches=(), selected_worktrees=()):
    root = os.fsdecode(git(path, 'rev-parse', '--show-toplevel').rstrip(b'\n'))
    current_branch = git(root, 'branch', '--show-current').decode().strip() or None
    remotes = git(root, 'remote').decode().splitlines()
    if requested_remote and requested_remote not in remotes:
        raise RuntimeError('selected remote does not exist')
    remote = requested_remote or ('origin' if 'origin' in remotes else remotes[0] if len(remotes) == 1 else None)
    if remotes and remote is None:
        raise RuntimeError('multiple remotes without origin; select --remote')
    if fetch and remote:
        git(root, 'fetch', '--prune', remote)
    main_branch, base_ref = choose_refs(root, requested_main, remote, target_ref)
    main_hash = git(root, 'rev-parse', '--verify', base_ref + '^{commit}').decode().strip()
    worktrees = parse_worktrees(git(root, 'worktree', 'list', '--porcelain', '-z'))
    if not worktrees:
        raise RuntimeError('no worktrees found')
    primary = worktrees[0]['path']
    local_branches = git(root, 'for-each-ref', '--format=%(refname:short)', 'refs/heads').decode().splitlines()
    explicit_branches = set(selected_branches)
    for branch in explicit_branches:
        if branch not in local_branches:
            raise RuntimeError('selected branch does not exist: ' + branch)
    selected_paths = set()
    branches_to_check = set(explicit_branches)
    for worktree_path in selected_worktrees:
        entry = next((w for w in worktrees if same_path(worktree_path, w['path'])), None)
        if entry is None:
            raise RuntimeError('selected worktree is not registered: ' + os.path.abspath(worktree_path))
        selected_paths.add(os.path.normcase(os.path.abspath(entry['path'])))
        if entry['branch']:
            branches_to_check.add(entry['branch'])
    scoped = bool(selected_branches or selected_worktrees)
    reviews = discover_reviews(root, remote, main_branch)
    protected = set(filter(None, [main_branch, 'main', 'master', current_branch, *keep]))
    open_branches = {review['branch'] for review in reviews['open']}
    checks = DeliveryChecks(root, main_hash, reviews)
    local_changes = LocalChanges(checks)
    branches = []
    for branch in local_branches:
        if scoped and branch not in branches_to_check:
            continue
        delivery = checks.check(branch)
        protections = []
        if branch in protected:
            protections.append('protected or current branch')
        if not delivery['confirmed']:
            protections.append(delivery['reason'])
        branches.append({'name': branch, 'mergeCheck': delivery, 'mergedIntoBase': delivery['confirmed'],
                         'head': delivery['branchHash'], 'blockedReasons': protections,
                         'hasOpenReview': branch in open_branches,
                         'deleteCommand': ('git branch -d' if delivery['method'] == 'commitHistory' else 'git branch -D')
                         if delivery['confirmed'] and not protections else None})
    by_branch = {branch['name']: branch for branch in branches}
    classified = []
    # Read all registrations even for a scoped report: an unselected checkout
    # still prevents deleting the branch that it uses.
    checked_out = {w['branch'] for w in worktrees if w['branch']}
    for worktree in worktrees:
        branch = worktree['branch']
        if (scoped and branch not in explicit_branches
                and os.path.normcase(os.path.abspath(worktree['path'])) not in selected_paths):
            continue
        status, status_error = worktree_status(worktree['path']) if not worktree['bare'] else (None, 'bare worktree')
        reasons = []
        for condition, reason in ((same_path(worktree['path'], primary), 'primary worktree'),
                                  (same_path(worktree['path'], root), 'current worktree'),
                                  (worktree['bare'], 'bare worktree'),
                                  (worktree['locked'], 'locked worktree'),
                                  (worktree['prunable'], 'missing or prunable worktree'),
                                  (status_error is not None, 'worktree status unreadable')):
            if condition:
                reasons.append(reason)
        info = by_branch.get(branch)
        delivery = info['mergeCheck'] if info else None
        if info:
            reasons.extend(info['blockedReasons'])
            if info['head'] != worktree['head']:
                reasons.append('branch and worktree heads differ')
        elif branch:
            reasons.append('branch is not local')
        elif not reasons:
            delivery = checks.check_commit(worktree['head'])
            if not delivery['confirmed']:
                reasons.append(delivery['reason'])
        content = local_changes.check(worktree['path'], delivery) if delivery and not reasons else None
        if content and not content['confirmed']:
            reasons.append(content['reason'])
        readiness = removal_preflight(worktree['path']) if not reasons else None
        if readiness and not readiness['ready']:
            reasons.append('removal preflight found blocking paths')
        classified.append(dict(worktree, statusLines=status, statusError=status_error,
                               isDirty=bool(status) if status is not None else None,
                               mergeCheck=delivery, localContentCheck=content,
                               requiresForce=bool(status),
                               removalReadiness=readiness, blockedReasons=reasons,
                               removeCandidate=bool(delivery and content and not reasons)))
    delete_now = [b['name'] for b in branches if not b['blockedReasons'] and b['name'] not in checked_out]
    remove = [w for w in classified if w['removeCandidate']]
    removed_paths = {os.path.normcase(os.path.abspath(w['path'])) for w in remove}
    delete_after = sorted({w['branch'] for w in remove if w['branch']
                           if all(os.path.normcase(os.path.abspath(other['path'])) in removed_paths
                                  for other in worktrees if other['branch'] == w['branch'])})
    for branch in branches:
        branch['deleteNowCandidate'] = branch['name'] in delete_now
        branch['deleteAfterWorktreeRemovalCandidate'] = branch['name'] in delete_after
    return {'repoRoot': root, 'currentBranch': current_branch, 'currentWorktreePath': root,
            'primaryWorktreePath': primary, 'mainBranch': main_branch, 'baseRef': base_ref,
            'mainHash': main_hash, 'remote': remote, 'fetchRan': bool(fetch and remote),
            'selection': {'scoped': scoped, 'branches': sorted(explicit_branches),
                          'worktrees': sorted(selected_paths)},
            'protectedBranches': sorted(protected), 'reviewLookup': reviews,
            'worktrees': classified, 'branches': branches,
            'cleanupCandidates': {'removeWorktrees': remove, 'deleteBranchesNow': delete_now,
                                  'deleteBranchesAfterWorktreeRemoval': delete_after},
            'blocked': {'worktrees': [w for w in classified if w['blockedReasons']],
                        'branches': [b for b in branches if b['blockedReasons']]},
            'canProceed': True, 'problems': [],
            'warnings': [] if fetch or not remote else ['refs were not fetched during this preflight; run with --fetch before cleanup']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', default='.')
    target = parser.add_mutually_exclusive_group()
    target.add_argument('--main', help='intended main branch')
    target.add_argument('--target-ref', help='exact full local or selected remote branch ref')
    parser.add_argument('--remote', help='remote holding the intended main branch')
    parser.add_argument('--branch', action='append', default=[], help='local branch to examine (repeatable)')
    parser.add_argument('--worktree', action='append', default=[], help='registered worktree to examine (repeatable)')
    parser.add_argument('--keep', action='append', default=[], help='local branch to preserve (repeatable)')
    parser.add_argument('--fetch', action='store_true', help='fetch selected remote before recording hashes')
    parser.add_argument('--verify-removed', metavar='PATH', help='check directory and registration after Git removal')
    args = parser.parse_args()
    try:
        if args.verify_removed:
            root = os.fsdecode(git(args.path, 'rev-parse', '--show-toplevel').rstrip(b'\n'))
            report = verify_removed(root, os.path.abspath(args.verify_removed))
            code = 0 if report['removed'] else 2
        else:
            report = build_report(args.path, args.main, args.remote, args.keep, args.fetch,
                                  target_ref=args.target_ref, selected_branches=args.branch,
                                  selected_worktrees=args.worktree)
            code = 0
    except (RuntimeError, OSError) as exc:
        report, code = {'canProceed': False, 'problems': [str(exc)]}, 1
    print(json.dumps(report, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
