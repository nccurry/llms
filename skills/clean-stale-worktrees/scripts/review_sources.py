"""Read review metadata through existing GitHub/GitLab CLI authentication."""
import json
import re
import subprocess
from urllib.parse import quote, urlparse


def json_pages(output):
    decoder = json.JSONDecoder()
    rows = []
    remainder = output.strip()
    if not remainder:
        raise ValueError('review lookup returned no JSON response')
    while remainder:
        page, end = decoder.raw_decode(remainder)
        if not isinstance(page, list):
            raise ValueError('expected a page of reviews')
        rows.extend(page)
        remainder = remainder[end:].lstrip()
    return rows


def discover_reviews(root, remote, main_branch):
    report = {'complete': False, 'remote': remote, 'open': [], 'merged': [], 'errors': []}
    if remote is None:
        return dict(report, complete=True, reason='repository has no remote')
    try:
        url_result = subprocess.run(['git', '-C', root, 'remote', 'get-url', remote],
                                    text=True, capture_output=True, check=True)
        url = url_result.stdout.strip()
        if '://' in url:
            parsed = urlparse(url)
            host, project = parsed.hostname, parsed.path.lstrip('/')
        else:
            match = re.fullmatch(r'(?:[^@]+@)?([^:]+):(.+)', url)
            if not match:
                raise ValueError('remote is not a supported hosted repository URL')
            host, project = match.groups()
        project = project.removesuffix('.git').rstrip('/')
        if not host or not project:
            raise ValueError('could not identify remote repository')
        if host == 'github.com':
            command = ['gh', 'api', '--hostname', host, '--paginate',
                       f'repos/{project}/pulls?state=all&per_page=100']
            provider = 'github'
        elif 'gitlab' in host.lower():
            command = ['glab', 'api', '--hostname', host, '--paginate',
                       f'projects/{quote(project, safe="")}/merge_requests?state=all&scope=all&per_page=100']
            provider = 'gitlab'
        else:
            raise ValueError('host needs a verified review lookup through its connector; automatic lookup supports github.com and GitLab-named hosts')
        result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=120)
        if result.returncode:
            raise RuntimeError(f'{command[0]} review lookup failed; check authentication and access')
        for row in json_pages(result.stdout):
            if provider == 'github':
                source = row['head']['sha']
                branch = row['head']['ref']
                state = 'merged' if row.get('merged_at') else row['state']
                target = row['base']['ref']
                squash = row.get('merge_commit_sha')
                source_project = (row['head'].get('repo') or {}).get('full_name')
                same_project = source_project == project
                review_url = row['html_url']
            else:
                source = row.get('sha') or (row.get('diff_refs') or {}).get('head_sha')
                branch, state, target = row['source_branch'], row['state'], row['target_branch']
                squash = row.get('squash_commit_sha')
                same_project = row.get('source_project_id') == row.get('target_project_id')
                review_url = row['web_url']
            if state in ('open', 'opened', 'locked') and same_project:
                # Open work remains protected even when its MR targets another branch.
                report['open'].append({'branch': branch, 'sourceHash': source, 'url': review_url})
            if state == 'merged' and target == main_branch:
                report['merged'].append({'sourceHash': source, 'squashHash': squash,
                                         'branch': branch, 'url': review_url})
        report['complete'] = True
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        report['errors'].append(str(exc))
    return report
