"""Prove local file states against main without staging or writing their contents."""
import hashlib
import json
import os
import stat

from delivery_checks import ancestor, git, patch, reverse_matches


def tree_entries(root, revision):
    entries = {}
    for record in git(root, 'ls-tree', '-r', '-z', revision).split(b'\0'):
        if record:
            metadata, path = record.split(b'\t', 1)
            mode, _, oid = metadata.decode().split()
            entries[os.fsdecode(path)] = (mode, oid)
    return entries


class LocalChanges:
    def __init__(self, checks):
        self.checks = checks
        self.main = tree_entries(checks.root, checks.main)
        self.delivery_boundaries = {}

    def boundaries(self, delivery):
        """Do not mistake a pre-delivery absence for delivery of a local deletion."""
        method = delivery['method']
        if method == 'commitHistory':
            return [delivery['branchHash']]
        if method in ('contentMatch', 'historicalMain'):
            tip, fork = delivery['branchHash'], delivery['forkPoint']
            if tip not in self.delivery_boundaries:
                change = patch(self.checks.root, fork, tip)
                found = []
                for snapshot in reversed(self.checks.snapshots):
                    if not ancestor(self.checks.root, fork, snapshot):
                        continue
                    if any(ancestor(self.checks.root, bound, snapshot) for bound in found):
                        continue
                    if reverse_matches(self.checks.root, change, snapshot, fork, tip):
                        found = [bound for bound in found
                                 if not ancestor(self.checks.root, snapshot, bound)]
                        found.append(snapshot)
                self.delivery_boundaries[tip] = found or [self.checks.main]
            return self.delivery_boundaries[tip]
        if method == 'mergedSource':
            return [delivery['source']['squashHash']]
        if method == 'noFileChanges':
            return [delivery['forkPoint']]
        if method == 'exactChanges':
            bounds = {item.get('mainCommit') or item['source']['squashHash']
                      for item in delivery['attempts'][-1]['accountedChanges']}
            for snapshot in reversed(self.checks.snapshots):
                if all(ancestor(self.checks.root, bound, snapshot) for bound in bounds):
                    return [snapshot]
        return [self.checks.main]

    def match(self, path, entry, delivery):
        if self.main.get(path) == entry:
            return self.checks.main
        boundaries = self.boundaries(delivery)
        for snapshot in self.checks.snapshots:
            if snapshot == self.checks.main or not any(
                    ancestor(self.checks.root, bound, snapshot) for bound in boundaries):
                continue
            output = git(self.checks.root, 'ls-tree', '-z', snapshot, '--', path)
            previous = None
            if output:
                metadata, returned_path = output.rstrip(b'\0').split(b'\t', 1)
                if os.fsdecode(returned_path) == path:
                    mode, _, oid = metadata.decode().split()
                    previous = (mode, oid)
            if previous == entry:
                return snapshot
        return None

    def check(self, root, delivery):
        result = {'confirmed': False, 'changes': [], 'unmatched': [], 'fingerprint': None}
        if not delivery['confirmed']:
            return dict(result, reason='committed source delivery is not proven')
        try:
            head = git(root, 'rev-parse', 'HEAD').decode().strip()
            if head != delivery['branchHash']:
                raise RuntimeError('worktree HEAD changed before local content inspection')
            index_path = os.fsdecode(git(root, 'rev-parse', '--path-format=absolute',
                                       '--git-path', 'index').rstrip(b'\n'))

            def index_hash():
                with open(index_path, 'rb') as stream:
                    return hashlib.sha256(stream.read()).hexdigest()

            original_index = index_hash()
            index = {}
            for record in git(root, 'ls-files', '--stage', '-z').split(b'\0'):
                if not record:
                    continue
                metadata, path = record.split(b'\t', 1)
                mode, oid, stage = metadata.decode().split()
                if stage != '0':
                    raise RuntimeError('unresolved index stages need separate delivery proof')
                index[os.fsdecode(path)] = (mode, oid)
            before = tree_entries(root, head)

            def account(path, entry, layer):
                snapshot = self.match(path, entry, delivery)
                row = {'path': path, 'layer': layer, 'entry': entry, 'mainSnapshot': snapshot}
                result['changes'].append(row)
                if snapshot is None:
                    result['unmatched'].append(row)

            for path in sorted(before.keys() | index.keys()):
                if before.get(path) != index.get(path):
                    account(path, index.get(path), 'index')

            paths = {os.fsdecode(path) for path in
                     git(root, 'ls-files', '--cached', '--others', '-z').split(b'\0') if path}
            skipped = {os.fsdecode(record[2:]) for record in
                       git(root, 'ls-files', '-v', '-z').split(b'\0')
                       if record[:1].upper() == b'S'}
            filemode = git(root, 'config', '--bool', '--default', 'true', 'core.filemode').strip() == b'true'
            symlinks = git(root, 'config', '--bool', '--default', 'true', 'core.symlinks').strip() == b'true'
            object_format = git(root, 'rev-parse', '--show-object-format').decode().strip()
            manifest = []
            for path in sorted(paths):
                absolute = os.path.join(root, path)
                expected = index.get(path)
                entry = None
                raw_hash = None
                kind = 'missing'
                if os.path.lexists(absolute):
                    info = os.lstat(absolute)
                    if stat.S_ISLNK(info.st_mode):
                        data = os.fsencode(os.readlink(absolute))
                        mode, kind = '120000', 'symlink'
                    elif stat.S_ISREG(info.st_mode):
                        with open(absolute, 'rb') as stream:
                            data = stream.read()
                        mode = '100755' if filemode and info.st_mode & 0o111 else '100644'
                        if expected and not filemode and expected[0] in ('100644', '100755'):
                            mode = expected[0]
                        if expected and expected[0] == '120000' and not symlinks:
                            mode = '120000'
                        kind = 'file'
                    else:
                        raise RuntimeError('nested repository, submodule, or special file: ' + path)
                    raw_hash = hashlib.sha256(data).hexdigest()
                    oid = hashlib.new(object_format, b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                    if mode != '120000' and (expected is None or oid != expected[1]):
                        # Built-in text conversion is useful on Windows. Never run
                        # an external clean filter on uncommitted or ignored files.
                        attributes = git(root, 'check-attr', '-z', 'filter', '--', path).split(b'\0')
                        if attributes[2] in (b'unspecified', b'unset'):
                            oid = git(root, 'hash-object', '--path=' + path, '--stdin', data=data).decode().strip()
                    entry = (mode, oid)
                elif expected and path in skipped:
                    entry = expected
                manifest.append((path, kind, raw_hash, entry))
                if entry != expected:
                    account(path, entry, 'worktree')
            if index_hash() != original_index or git(root, 'rev-parse', 'HEAD').decode().strip() != head:
                raise RuntimeError('HEAD or index changed during local content inspection')
            fingerprint = hashlib.sha256(json.dumps(
                [head, original_index, manifest], ensure_ascii=True).encode()).hexdigest()
            return dict(result, confirmed=not result['unmatched'], fingerprint=fingerprint,
                        headHash=head, indexHash=original_index,
                        reason='local content is in main' if not result['unmatched']
                        else 'local content has no exact match in main')
        except (RuntimeError, OSError, ValueError) as exc:
            return dict(result, reason='local content delivery is not proven: ' + str(exc))
