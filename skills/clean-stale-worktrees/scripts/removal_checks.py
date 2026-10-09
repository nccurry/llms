"""Read-only removal readiness and post-removal checks."""
import os
import stat
import subprocess


def removal_preflight(path):
    blockers = []
    ignored = []
    if os.path.islink(path) or not os.path.isdir(path):
        return {'ready': False, 'blockers': [{'path': path, 'reason': 'worktree path is missing or a symlink'}], 'ignoredDirectories': []}
    result = subprocess.run(['git', '-C', path, 'ls-files', '--others', '--ignored',
                             '--exclude-standard', '--directory', '-z'], capture_output=True)
    if result.returncode:
        return {'ready': False, 'blockers': [{'path': path, 'reason': 'could not inspect ignored files'}], 'ignoredDirectories': []}
    ignored = [os.fsdecode(item) for item in result.stdout.split(b'\0') if item.endswith(b'/')]

    def inspect(directory):
        try:
            info = os.stat(directory, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                return
            # Check mode bits too: a privileged process should still report read-only caches.
            writable = bool(info.st_mode & 0o222) and os.access(directory, os.W_OK | os.X_OK)
            searchable = bool(info.st_mode & 0o111)
            if not writable or not searchable:
                blockers.append({'path': directory, 'reason': 'directory lacks write/search access',
                                 'mode': oct(stat.S_IMODE(info.st_mode)), 'owner': info.st_uid})
            if info.st_mode & stat.S_ISVTX:
                blockers.append({'path': directory, 'reason': 'sticky directory requires a separate ownership check'})
        except OSError as exc:
            blockers.append({'path': directory, 'reason': str(exc)})

    def walk_error(exc):
        blockers.append({'path': exc.filename, 'reason': str(exc)})

    inspect(os.path.dirname(os.path.abspath(path)))
    for directory, children, files in os.walk(path, followlinks=False, onerror=walk_error):
        inspect(directory)
        # Linked caches are entries to unlink; their targets must never be traversed.
        children[:] = [name for name in children if not os.path.islink(os.path.join(directory, name))]
        if '.git' in children:
            blockers.append({'path': os.path.join(directory, '.git'), 'reason': 'embedded repository needs separate review'})
        for name in files:
            entry = os.path.join(directory, name)
            if name == '.git' and directory != path:
                blockers.append({'path': entry, 'reason': 'nested repository or submodule needs separate review'})
    return {'ready': not blockers, 'blockers': blockers, 'ignoredDirectories': ignored,
            'note': 'Read-only files alone do not block unlinking. ACLs, immutable flags, mounts, and concurrent changes can still make removal fail.'}


def verify_removed(root, path):
    result = subprocess.run(['git', '-C', root, 'worktree', 'list', '--porcelain', '-z'], capture_output=True)
    if result.returncode:
        return {'removed': False, 'directoryAbsent': not os.path.lexists(path),
                'registrationAbsent': None, 'reason': 'could not read worktree registrations'}
    target = os.path.normcase(os.path.abspath(path))
    registrations = [os.path.normcase(os.path.abspath(os.fsdecode(field[9:])))
                     for field in result.stdout.split(b'\0') if field.startswith(b'worktree ')]
    directory_absent = not os.path.lexists(path)
    registration_absent = target not in registrations
    return {'removed': directory_absent and registration_absent,
            'directoryAbsent': directory_absent, 'registrationAbsent': registration_absent}
