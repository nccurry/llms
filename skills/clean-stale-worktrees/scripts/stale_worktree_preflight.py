#!/usr/bin/env python3
"""Preview delivery evidence and removal readiness; never delete user work."""
import argparse
import json
import os
import subprocess
import sys

from delivery_checks import DeliveryChecks, git
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


def choose_refs(root, requested, remote):
    refs = set(git(root, 'for-each-ref', '--format=%(refname)').decode().splitlines())
    if requested:
        main = requested
    else:
        # Prefer main/master over a possibly stale cached remote HEAD.
        main = next((name for name in ('main', 'master')
                     if f'refs/heads/{name}' in refs or f'refs/remotes/{remote}/{name}' in refs), None)
        if not main and remote:
            result = subprocess.run(['git', '-C', root, 'symbolic-ref', '--quiet',
                                     f'refs/remotes/{remote}/HEAD'], capture_output=True, text=True)
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


def build_report(path, requested_main=None, requested_remote=None, keep=(), fetch=False):
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
    main_branch, base_ref = choose_refs(root, requested_main, remote)
    main_hash = git(root, 'rev-parse', '--verify', base_ref + '^{commit}').decode().strip()
    worktrees = parse_worktrees(git(root, 'worktree', 'list', '--porcelain', '-z'))
    if not worktrees:
        raise RuntimeError('no worktrees found')
    primary = worktrees[0]['path']
    reviews = discover_reviews(root, remote, main_branch)
    protected = set(filter(None, [main_branch, 'main', 'master', current_branch, *keep]))
    open_branches = {review['branch'] for review in reviews['open']}
    checks = DeliveryChecks(root, main_hash, reviews)
    branches = []
    for branch in git(root, 'for-each-ref', '--format=%(refname:short)', 'refs/heads').decode().splitlines():
        delivery = checks.check(branch)
        protections = []
        if branch in protected:
            protections.append('protected or current branch')
        if branch in open_branches:
            protections.append('open MR/PR')
        if not reviews['complete']:
            protections.append('open MR/PR status could not be verified')
        if not delivery['confirmed']:
            protections.append(delivery['reason'])
        branches.append({'name': branch, 'mergeCheck': delivery, 'mergedIntoBase': delivery['confirmed'],
                         'head': delivery['branchHash'], 'blockedReasons': protections,
                         'deleteCommand': ('git branch -d' if delivery['method'] == 'commitHistory' else 'git branch -D')
                         if delivery['confirmed'] and not protections else None})
    by_branch = {branch['name']: branch for branch in branches}
    classified = []
    checked_out = set()
    for worktree in worktrees:
        branch = worktree['branch']
        if branch:
            checked_out.add(branch)
        status, status_error = worktree_status(worktree['path']) if not worktree['bare'] else (None, 'bare worktree')
        reasons = []
        for condition, reason in ((same_path(worktree['path'], primary), 'primary worktree'),
                                  (same_path(worktree['path'], root), 'current worktree'),
                                  (worktree['bare'], 'bare worktree'),
                                  (worktree['detached'] or not branch, 'detached or branchless worktree'),
                                  (worktree['locked'], 'locked worktree'),
                                  (worktree['prunable'], 'missing or prunable worktree'),
                                  (status_error is not None, 'worktree status unreadable'),
                                  (bool(status), 'dirty worktree')):
            if condition:
                reasons.append(reason)
        info = by_branch.get(branch)
        if info:
            reasons.extend(info['blockedReasons'])
            if info['head'] != worktree['head']:
                reasons.append('branch and worktree heads differ')
        elif branch:
            reasons.append('branch is not local')
        readiness = removal_preflight(worktree['path']) if not reasons else None
        if readiness and not readiness['ready']:
            reasons.append('removal preflight found blocking paths')
        classified.append(dict(worktree, statusLines=status, statusError=status_error,
                               isDirty=bool(status) if status is not None else None,
                               removalReadiness=readiness, blockedReasons=reasons,
                               removeCandidate=bool(info and not reasons)))
    delete_now = [b['name'] for b in branches if not b['blockedReasons'] and b['name'] not in checked_out]
    remove = [w for w in classified if w['removeCandidate']]
    delete_after = [w['branch'] for w in remove]
    for branch in branches:
        branch['deleteNowCandidate'] = branch['name'] in delete_now
        branch['deleteAfterWorktreeRemovalCandidate'] = branch['name'] in delete_after
    return {'repoRoot': root, 'currentBranch': current_branch, 'currentWorktreePath': root,
            'primaryWorktreePath': primary, 'mainBranch': main_branch, 'baseRef': base_ref,
            'mainHash': main_hash, 'remote': remote, 'fetchRan': bool(fetch and remote),
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
    parser.add_argument('--main', help='intended main branch')
    parser.add_argument('--remote', help='remote holding the intended main branch')
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
            report = build_report(args.path, args.main, args.remote, args.keep, args.fetch)
            code = 0
    except (RuntimeError, OSError) as exc:
        report, code = {'canProceed': False, 'problems': [str(exc)]}, 1
    print(json.dumps(report, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
