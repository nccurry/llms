"""Delivery evidence only. Never edits a worktree, branch, or the real index."""
import collections
import os
import re
import subprocess
import tempfile


def git(root, *args, data=None, env=None):
    result = subprocess.run(['git', '-C', root, '--literal-pathspecs', *args], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace').strip() or
                           f'git {args[0]} failed ({result.returncode})')
    return result.stdout


def ancestor(root, left, right):
    result = subprocess.run(['git', '-C', root, 'merge-base', '--is-ancestor', left, right],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.decode(errors='replace'))
    return result.returncode == 0


def patch(root, before, after):
    return git(root, 'diff', '--binary', '--full-index', '--no-ext-diff',
               '--no-textconv', '--no-renames', '--no-color', '--ignore-submodules=none',
               '--submodule=short', '--unified=0',
               before, after, '--')


def reverse_matches(root, change, snapshot, before, after):
    with tempfile.TemporaryDirectory(prefix='stale-worktree-index-') as directory:
        env = dict(os.environ, GIT_INDEX_FILE=os.path.join(directory, 'index'))
        git(root, 'read-tree', snapshot, env=env)
        result = subprocess.run(
            ['git', '-C', root, '-c', 'apply.ignoreWhitespace=no', 'apply', '--cached',
             '--reverse', '--check', '--unidiff-zero', '--whitespace=nowarn'],
            input=change, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        # Apply failure means no match; read-tree failures above are errors.
        if result.returncode != 0:
            return False
        git(root, '-c', 'apply.ignoreWhitespace=no', 'apply', '--cached', '--reverse',
            '--unidiff-zero', '--whitespace=nowarn', data=change, env=env)
        paths = [os.fsdecode(p) for p in git(root, 'diff', '--name-only', '-z',
                 '--no-renames', '--ignore-submodules=none', before, after, '--').split(b'\0') if p]
        # A reverse apply alone can accept a deletion that never happened.
        # Require the reconstructed touched files to equal their original blobs/modes.
        return not git(root, 'diff', '--cached', '--no-ext-diff', '--no-textconv',
                       '--no-renames', '--ignore-submodules=none', before, '--', *paths, env=env)


def exact_changes(root, before, after):
    """Return hunk-sized patches with positions removed, never whitespace removed.

    Metadata changes and binary patches stay whole. A patch ID indexes candidates;
    byte equality of the canonical patch is the actual evidence.
    """
    change = patch(root, before, after)
    output = []
    for section in re.split(br'(?m)(?=^diff --git )', change):
        if not section:
            continue
        lines = section.splitlines(keepends=True)
        binary = b'GIT binary patch\n' in lines
        headers, hunks, current = [], [], None
        for line in lines:
            if line.startswith(b'@@ '):
                current = [re.sub(br'^@@ -[0-9]+(,[0-9]+)? \+[0-9]+(,[0-9]+)? @@.*',
                                  lambda m: b'@@ -1' + (m[1] or b'') + b' +1' + (m[2] or b'') + b' @@',
                                  line)]
                hunks.append(current)
            elif current is not None:
                current.append(line)
            elif not line.startswith(b'index ') or binary:
                headers.append(line)
        # Mode, creation, deletion, and binary changes require the whole file patch.
        metadata = any(line.startswith((b'old mode ', b'new mode ', b'new file mode ',
                                       b'deleted file mode ')) for line in headers)
        if binary or metadata or not hunks:
            canonical = b''.join(headers) + b''.join(b''.join(h) for h in hunks)
            units = [canonical]
        else:
            units = [b''.join(headers + h) for h in hunks]
        for unit in units:
            value = git(root, 'patch-id', '--stable', data=unit).split()
            # Metadata-only patches may have no patch ID; exact bytes still govern.
            candidate_id = value[0].decode() if value else 'metadata'
            output.append((candidate_id, unit))
    return output


class DeliveryChecks:
    def __init__(self, root, main_hash, reviews):
        self.root = root
        self.main = main_hash
        self.reviews = reviews
        self.snapshots = git(root, 'rev-list', main_hash).decode().splitlines()
        self.verified_sources = None
        self.source_errors = []
        self.change_index = None

    def merged_sources(self):
        if self.verified_sources is not None:
            return self.verified_sources
        self.verified_sources = []
        for review in self.reviews.get('merged', []):
            source, squash = review.get('sourceHash'), review.get('squashHash')
            if not source or not squash:
                self.source_errors.append({'review': review.get('url'), 'reason': 'source or squash hash unavailable'})
                continue
            try:
                for commit in (source, squash):
                    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit):
                        raise RuntimeError('invalid source or squash hash')
                    try:
                        git(self.root, 'cat-file', '-e', commit + '^{commit}')
                    except RuntimeError:
                        # Fetch objects only; do not switch branches or update local refs.
                        remote = self.reviews.get('remote')
                        if not remote:
                            raise RuntimeError('review commit object missing and no source remote is available')
                        git(self.root, 'fetch', '--no-tags', '--no-write-fetch-head', remote, commit)
                if not ancestor(self.root, squash, self.main):
                    continue
                parents = git(self.root, 'rev-list', '--parents', '-n', '1', squash).decode().split()[1:]
                if len(parents) != 1:
                    raise RuntimeError('squash candidate must have exactly one parent')
                tree = git(self.root, 'merge-tree', '--write-tree', parents[0], source).decode().splitlines()[0]
                squash_tree = git(self.root, 'rev-parse', squash + '^{tree}').decode().strip()
                if tree != squash_tree:
                    raise RuntimeError('source integration tree differs from squash tree')
                self.verified_sources.append(dict(review, integrationTree=tree, squashParent=parents[0]))
            except RuntimeError as exc:
                self.source_errors.append({'review': review.get('url'), 'reason': str(exc)})
        return self.verified_sources

    def main_changes(self):
        if self.change_index is None:
            self.change_index = collections.defaultdict(list)
            for commit in git(self.root, 'rev-list', '--first-parent', self.main).decode().splitlines():
                parents = git(self.root, 'rev-list', '--parents', '-n', '1', commit).decode().split()[1:]
                # Include main merge resolutions through the complete first-parent diff.
                before = parents[0] if parents else git(self.root, 'hash-object', '-w', '-t', 'tree', '--stdin', data=b'').decode().strip()
                for identity in exact_changes(self.root, before, commit):
                    self.change_index[identity].append(commit)
        return self.change_index

    def check(self, branch):
        tip = git(self.root, 'rev-parse', '--verify', 'refs/heads/' + branch).decode().strip()
        attempts = []
        result = {'confirmed': False, 'method': 'deliveryNotProven', 'branchHash': tip,
                  'mainHash': self.main, 'attempts': attempts, 'forkPoint': None}
        try:
            if ancestor(self.root, tip, self.main):
                return dict(result, confirmed=True, method='commitHistory', reason='branch tip is in main history')
            forks = git(self.root, 'merge-base', '--all', tip, self.main).decode().splitlines()
            if len(forks) != 1:
                raise RuntimeError('a single common starting point could not be established')
            fork = forks[0]
            result['forkPoint'] = fork
            change = patch(self.root, fork, tip)
            if not change:
                return dict(result, confirmed=True, method='noFileChanges', reason='no net file changes since the fork point')
            matched = reverse_matches(self.root, change, self.main, fork, tip)
            attempts.append({'check': 'currentMain', 'matched': matched, 'snapshot': self.main})
            if matched:
                return dict(result, confirmed=True, method='contentMatch', reason='complete net patch matches current main')
            for snapshot in self.snapshots:
                if snapshot == self.main:
                    continue
                if reverse_matches(self.root, change, snapshot, fork, tip) and ancestor(self.root, snapshot, self.main):
                    attempts.append({'check': 'historicalMain', 'matched': True, 'snapshot': snapshot})
                    return dict(result, confirmed=True, method='historicalMain', reason='complete net patch matches an ancestor of current main')
            attempts.append({'check': 'historicalMain', 'matched': False, 'snapshotsChecked': len(self.snapshots) - 1})
            sources = self.merged_sources()
            attempts.append({'check': 'mergedSources', 'verified': sources, 'errors': self.source_errors,
                             'lookupComplete': self.reviews.get('complete', False)})
            for source in sources:
                if ancestor(self.root, tip, source['sourceHash']):
                    return dict(result, confirmed=True, method='mergedSource', reason='branch tip is in a verified merged source', source=source)
                if reverse_matches(self.root, change, source['sourceHash'], fork, tip):
                    return dict(result, confirmed=True, method='mergedSource', reason='complete net patch matches a verified merged source', source=source)
            # Require every unique commit, including full first-parent merge diffs.
            commits = git(self.root, 'rev-list', '--reverse', tip, '^' + fork, '^' + self.main).decode().splitlines()
            available = self.main_changes()
            consumed = collections.defaultdict(set)
            accounted, unmatched = [], []
            for commit in commits:
                source = next((s for s in sources if ancestor(self.root, commit, s['sourceHash'])), None)
                if source:
                    accounted.append({'commit': commit, 'source': source})
                    continue
                parents = git(self.root, 'rev-list', '--parents', '-n', '1', commit).decode().split()[1:]
                if not parents:
                    raise RuntimeError('unique commit has no parent')
                changes = exact_changes(self.root, parents[0], commit)
                for candidate_id, exact in changes:
                    identity = (candidate_id, exact)
                    matches = available.get(identity, [])
                    # Only deliveries after the fork count. Post-source commits
                    # need evidence after that source's squash, not its old delivery.
                    bounds = [s['squashHash'] for s in sources
                              if ancestor(self.root, s['sourceHash'], commit)]
                    match = next(((i, target) for i, target in enumerate(matches)
                                  if i not in consumed[identity] and target != fork
                                  and ancestor(self.root, fork, target)
                                  and all(target != bound and ancestor(self.root, bound, target)
                                          for bound in bounds)), None)
                    if match is not None:
                        offset, target = match
                        consumed[identity].add(offset)
                        accounted.append({'commit': commit, 'mainCommit': target, 'patchId': candidate_id,
                                          'exactChange': exact.decode(errors='backslashreplace')})
                    else:
                        unmatched.append({'commit': commit, 'patchId': candidate_id,
                                          'exactChange': exact.decode(errors='backslashreplace')})
            attempts.append({'check': 'cherryPicks', 'accountedChanges': accounted, 'unmatchedChanges': unmatched})
            if not unmatched:
                return dict(result, confirmed=True, method='exactChanges', reason='every unique commit change has exact delivery evidence')
            return dict(result, reason='delivery not yet proven: concrete changes have no exact match', unmatchedChanges=unmatched)
        except RuntimeError as exc:
            return dict(result, reason='delivery not yet proven: ' + str(exc))
