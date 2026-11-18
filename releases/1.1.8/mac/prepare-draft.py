"""One-use release preparation; never publishes or replaces an existing asset."""
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = 'rufusTeam/rufus-rm-updates'
TAG = 'v1.1.8'
BASE = 'https://api.github.com/repos/' + REPOSITORY
HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / 'manifest.json').read_text())


def api(method, route, body=None):
    assert (method == 'POST' and route == '/releases') or (method == 'GET' and (
        route.startswith('/releases') or route == '/commits/0b3c94363d44def9bca25af56a749e1a1ec568f4'
    )), 'Only release reads and the single draft create are permitted'
    request = urllib.request.Request(BASE + route, method=method, headers={
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json',
    }, data=None if body is None else json.dumps(body).encode())
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def protected(release):
    return {
        key: release.get(key) for key in
        ['id', 'tag_name', 'name', 'body', 'draft', 'prerelease', 'published_at']
    } | {'assets': sorted([
        {key: row.get(key) for key in ['id', 'name', 'size', 'digest', 'created_at', 'updated_at']}
        for row in release.get('assets', [])
    ], key=lambda row: row['id'])}


def main():
    assert os.environ.get('GITHUB_REPOSITORY') == REPOSITORY
    assert os.environ.get('GITHUB_REF') == 'refs/heads/codex/rrm118-mac-draft-20261119'
    assert PLAN['tag'] == TAG and PLAN['draft'] is True
    existing = []
    page = 1
    while True:
        rows = api('GET', '/releases?per_page=100&page=' + str(page))
        existing.extend(rows)
        if len(rows) < 100:
            break
        page += 1
    assert not any(row['tag_name'] == TAG for row in existing), 'Existing 1.1.8 found; inspect it, do not recreate or replace it'
    before = protected(api('GET', '/releases/latest'))
    assert before['tag_name'] == 'v1.1.7' and before['draft'] is False
    assert api('GET', '/commits/0b3c94363d44def9bca25af56a749e1a1ec568f4')['sha'] == PLAN['target_commitish']

    downloaded = []
    staging = HERE / 'verified-downloads'
    staging.mkdir()
    for asset in PLAN['assets']:
        parsed = urllib.parse.urlsplit(asset['url'])
        assert parsed.scheme == 'https'
        assert parsed.hostname == 'rufus-electron-app-downloads.s3.us-east-1.amazonaws.com'
        assert not parsed.query and not parsed.username and not parsed.password
        assert parsed.path == '/releases/1.1.8/mac-20261119-c1d61de/' + asset['name']
        assert Path(asset['name']).name == asset['name']
        path = staging / asset['name']
        digest = hashlib.sha256()
        total = 0
        with urllib.request.urlopen(asset['url'], timeout=180) as response, path.open('xb') as stream:
            assert response.status == 200 and response.url == asset['url']
            while block := response.read(1024 * 1024):
                stream.write(block)
                digest.update(block)
                total += len(block)
        assert total == asset['bytes'], asset['name']
        assert digest.hexdigest() == asset['sha256'], asset['name']
        downloaded.append((asset, path))

    # All eight downloads and the protected baseline are verified before the
    # only create request. A failed/uncertain create must be inspected, not retried.
    release = api('POST', '/releases', {
        'tag_name': TAG,
        'target_commitish': PLAN['target_commitish'],
        'name': 'RUFUS Race Manager 1.1.8 — Mac draft',
        'body': (staging / 'RELEASE-NOTES-1.1.8-MAC-EN.md').read_text(),
        'draft': True,
        'prerelease': False,
        'make_latest': 'false',
    })
    release_id = release['id']
    assert release['draft'] is True and release['tag_name'] == TAG
    receipt = {'release_id': release_id, 'draft': True, 'tag': TAG, 'url': release['html_url'], 'assets': []}
    (HERE / 'draft-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    for asset, path in downloaded:
        url = 'https://uploads.github.com/repos/' + REPOSITORY + '/releases/' + str(release_id) + '/assets?name=' + urllib.parse.quote(asset['name'], safe='')
        request = urllib.request.Request(url, method='POST', data=path.read_bytes(), headers={
            'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
            'Accept': 'application/vnd.github+json',
            'Content-Type': asset['content_type'],
            'X-GitHub-Api-Version': '2022-11-28',
        })
        with urllib.request.urlopen(request, timeout=180) as response:
            uploaded = json.load(response)
        assert uploaded['name'] == asset['name'] and uploaded['size'] == asset['bytes']
        assert uploaded['state'] == 'uploaded'
        assert uploaded['digest'] == 'sha256:' + asset['sha256']
        receipt['assets'].append({key: uploaded[key] for key in ['id', 'name', 'size', 'digest', 'state']})
        (HERE / 'draft-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')

    final = api('GET', '/releases/' + str(release_id))
    assert final['draft'] is True and final['prerelease'] is False
    assert len(final['assets']) == len(PLAN['assets']) == 8
    assert protected(api('GET', '/releases/latest')) == before, 'Prior stable release changed'
    receipt['stable_117_release_and_assets_preserved'] = True
    receipt['status'] = 'DRAFT_READY_HOLD_MCP_AND_WINDOWS'
    (HERE / 'draft-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as stream:
            stream.write('## RRM 1.1.8 Mac draft\n\n' + receipt['url'] + '\n\nEight verified assets. Still draft; 1.1.7 remains latest. MCP alignment and Windows remain pending.\n')


if __name__ == '__main__':
    main()
