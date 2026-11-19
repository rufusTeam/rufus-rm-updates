"""Restore the intended tag after GitHub assigned its draft placeholder.

No asset writes, release creation or stable publication. One guarded PATCH.
"""
import hashlib
import json
import os
from pathlib import Path
import urllib.request

HERE = Path(__file__).resolve().parent
EXPECTED = json.loads((HERE / 'inspected-state.json').read_text())
BASE = 'https://api.github.com/repos/rufusTeam/rufus-rm-updates'
RELEASE = '/releases/450687888'
PATCH = {'tag_name': 'v1.1.8', 'draft': True, 'prerelease': False, 'make_latest': 'false'}


def api(method, route, body=None):
    assert (method == 'GET' and route in [RELEASE, '/releases/latest']) or (method == 'PATCH' and route == RELEASE and body == PATCH)
    request = urllib.request.Request(BASE + route, method=method, data=None if body is None else json.dumps(body).encode(), headers={
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
        'Content-Type': 'application/json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Cache-Control': 'no-cache',
    })
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def assets(release):
    return sorted([{k: a.get(k) for k in ['id', 'name', 'size', 'digest', 'state']} for a in release['assets']], key=lambda a: a['id'])


def stable_snapshot(release):
    return {k: release.get(k) for k in ['id', 'tag_name', 'name', 'body', 'draft', 'prerelease', 'published_at']} | {'assets': sorted([{k: a.get(k) for k in ['id', 'name', 'size', 'digest', 'created_at', 'updated_at']} for a in release['assets']], key=lambda a: a['id'])}


def validate_before(release):
    assert release['id'] == 450687888 and release['draft'] is True and release['prerelease'] is False
    assert release['tag_name'] == 'untagged-747200a0c1c8cb9c72b4'
    assert assets(release) == sorted(EXPECTED['assets'], key=lambda a: a['id'])
    assert hashlib.sha256(release.get('body', '').encode()).hexdigest() == EXPECTED['body_sha256']


def main():
    assert os.environ.get('GITHUB_REPOSITORY') == 'rufusTeam/rufus-rm-updates'
    assert os.environ.get('GITHUB_REF') == 'refs/heads/codex/rrm118-mac-finalize-20261119'
    before, stable_before = api('GET', RELEASE), stable_snapshot(api('GET', '/releases/latest'))
    validate_before(before)
    assert stable_before['id'] == 448929324 and stable_before['tag_name'] == 'v1.1.7'
    result = api('PATCH', RELEASE, PATCH)
    assert result['id'] == 450687888 and result['draft'] is True
    final = api('GET', RELEASE)
    assert final['id'] == 450687888 and final['tag_name'] == 'v1.1.8' and final['draft'] is True and final['prerelease'] is False
    assert assets(final) == assets(before)
    assert final.get('body') == before.get('body')
    assert stable_snapshot(api('GET', '/releases/latest')) == stable_before
    receipt = {'release_id': 450687888, 'tag': final['tag_name'], 'draft': True, 'url': final['html_url'], 'status': 'MAC_WEB_CORE_ACCEPTED_DRAFT_PENDING_WINDOWS', 'mcp_excluded_by_owner': True, 'assets': assets(final), 'protected_mac_binary_assets_unchanged': True, 'stable_117_release_and_assets_preserved': True, 'document_update_verified_by_readback': True, 'draft_tag_restored_with_single_explicit_patch': True}
    (HERE / 'finalize-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
