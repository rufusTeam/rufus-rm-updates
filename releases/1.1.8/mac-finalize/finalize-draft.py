"""One-use document update. Never publishes, creates a release or alters binaries."""
import hashlib
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

REPOSITORY = 'rufusTeam/rufus-rm-updates'
RELEASE_ID = 450687888
BASE = 'https://api.github.com/repos/' + REPOSITORY
HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / 'manifest.json').read_text())
DOCUMENT_IDS = {765424762, 765424810, 765425553}
DOCUMENT_NAMES = {'RELEASE-NOTES-1.1.8-MAC-EN.md', 'RELEASE-SOURCES-1.1.8-MAC.json', 'SHA256SUMS-MAC.txt'}


def api(method, route, body=None):
    assert (method == 'GET' and route in ['/releases/latest', '/releases/' + str(RELEASE_ID)]) or (
        method == 'PATCH' and route == '/releases/' + str(RELEASE_ID)
        and body.get('draft') is True and body.get('prerelease') is False
        and body.get('make_latest') == 'false'
        and set(body) == {'body', 'draft', 'prerelease', 'make_latest'}
    ) or (method == 'DELETE' and route in {'/releases/assets/' + str(i) for i in DOCUMENT_IDS}), 'Request outside document-only scope'
    req = urllib.request.Request(BASE + route, method=method, headers={
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json',
    }, data=None if body is None else json.dumps(body).encode())
    with urllib.request.urlopen(req, timeout=90) as response:
        return None if response.status == 204 else json.load(response)


def asset_snapshot(row):
    return {k: row.get(k) for k in ['id', 'name', 'size', 'digest', 'state']}


def protected(release):
    return {k: release.get(k) for k in ['id', 'tag_name', 'name', 'body', 'draft', 'prerelease', 'published_at']} | {
        'assets': sorted([{k: a.get(k) for k in ['id', 'name', 'size', 'digest', 'created_at', 'updated_at']} for a in release.get('assets', [])], key=lambda a: a['id'])}


def validate_existing(release, expected):
    assert release['id'] == RELEASE_ID and release['tag_name'] == 'v1.1.8'
    assert release['draft'] is True and release['prerelease'] is False
    actual = {a['name']: asset_snapshot(a) for a in release['assets']}
    assert len(actual) == len(release['assets']) == len(expected) == 8
    assert actual == {a['name']: asset_snapshot(a) for a in expected}, 'Draft assets moved; inspect before retrying'
    assert {a['id'] for a in expected if a['name'] in DOCUMENT_NAMES} == DOCUMENT_IDS
    return actual


def main():
    assert os.environ.get('GITHUB_REPOSITORY') == REPOSITORY
    assert os.environ.get('GITHUB_REF') == 'refs/heads/' + PLAN['branch']
    assert PLAN['release_id'] == RELEASE_ID and PLAN['tag'] == 'v1.1.8'
    before_stable = protected(api('GET', '/releases/latest'))
    assert before_stable['tag_name'] == 'v1.1.7' and before_stable['draft'] is False
    before = api('GET', '/releases/' + str(RELEASE_ID))
    old = validate_existing(before, PLAN['expected_assets'])
    docs = PLAN['replace_documents']
    assert len(docs) == 3 and {a['name'] for a in docs} == DOCUMENT_NAMES
    bodies = {}
    for a in docs:
        parsed = urllib.parse.urlsplit(a['url'])
        assert parsed.scheme == 'https' and parsed.hostname == 'rufus-electron-app-downloads.s3.us-east-1.amazonaws.com'
        assert not parsed.query and not parsed.username and not parsed.password
        assert parsed.path == '/releases/1.1.8/mac-metadata-20261119-final/' + a['name']
        with urllib.request.urlopen(a['url'], timeout=90) as response:
            data = response.read()
        assert len(data) == a['bytes'] and hashlib.sha256(data).hexdigest() == a['sha256']
        bodies[a['name']] = data
    checksum_rows = dict(line.split('  ', 1)[::-1] for line in bodies['SHA256SUMS-MAC.txt'].decode().splitlines())
    expected_digests = {name: row['digest'].removeprefix('sha256:') for name, row in old.items() if name not in DOCUMENT_NAMES}
    expected_digests.update({a['name']: a['sha256'] for a in docs if a['name'] != 'SHA256SUMS-MAC.txt'})
    assert checksum_rows == expected_digests
    source = json.loads(bodies['RELEASE-SOURCES-1.1.8-MAC.json'])
    assert source['status'] == 'MAC_WEB_CORE_ACCEPTED_DRAFT_PENDING_WINDOWS'
    assert source['version'] == '1.1.8'

    # Every original asset and every replacement byte is verified before the
    # first mutation. There are no retries after an uncertain DELETE/upload.
    replacements = []
    for a in docs:
        api('DELETE', '/releases/assets/' + str(old[a['name']]['id']))
        url = 'https://uploads.github.com/repos/' + REPOSITORY + '/releases/' + str(RELEASE_ID) + '/assets?name=' + urllib.parse.quote(a['name'], safe='')
        req = urllib.request.Request(url, method='POST', data=bodies[a['name']], headers={
            'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': a['content_type'],
        })
        with urllib.request.urlopen(req, timeout=90) as response:
            new = json.load(response)
        assert new['name'] == a['name'] and new['size'] == a['bytes']
        assert new['digest'] == 'sha256:' + a['sha256'] and new['state'] == 'uploaded'
        replacements.append({'oldId': old[a['name']]['id'], **asset_snapshot(new)})
    api('PATCH', '/releases/' + str(RELEASE_ID), {'body': bodies['RELEASE-NOTES-1.1.8-MAC-EN.md'].decode(), 'draft': True, 'prerelease': False, 'make_latest': 'false'})
    final = api('GET', '/releases/' + str(RELEASE_ID))
    assert final['draft'] is True and final['prerelease'] is False and final['tag_name'] == 'v1.1.8'
    final_assets = {a['name']: asset_snapshot(a) for a in final['assets']}
    assert len(final['assets']) == 8 and set(final_assets) == set(old)
    for name in set(old) - DOCUMENT_NAMES:
        assert final_assets[name] == old[name], 'Protected binary/blockmap/latest-mac changed'
    for a in replacements:
        assert final_assets[a['name']] == {k: a[k] for k in ['id', 'name', 'size', 'digest', 'state']}
    assert protected(api('GET', '/releases/latest')) == before_stable
    receipt = {'release_id': RELEASE_ID, 'tag': 'v1.1.8', 'draft': True, 'url': final['html_url'], 'status': 'MAC_WEB_CORE_ACCEPTED_DRAFT_PENDING_WINDOWS', 'mcp_excluded_by_owner': True, 'protected_mac_binary_assets_unchanged': True, 'stable_117_release_and_assets_preserved': True, 'replaced_documents': replacements, 'assets': sorted(final_assets.values(), key=lambda a: a['id'])}
    (HERE / 'finalize-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
