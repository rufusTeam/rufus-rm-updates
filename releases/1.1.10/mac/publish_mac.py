import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = 'rufusTeam/rufus-rm-updates'
RELEASE_ID = 458713908
TAG = 'v1.1.10'
API = 'https://api.github.com/repos/' + REPOSITORY


def asset_snapshot(asset):
    return {key: asset[key] for key in ('id', 'name', 'size', 'digest', 'updated_at')}


def validate_plan(plan):
    assert plan['repository'] == REPOSITORY and plan['releaseId'] == RELEASE_ID and plan['tag'] == TAG
    expected = {
        'RUFUS-Race-Manager-1.1.10-arm64.dmg', 'RUFUS-Race-Manager-1.1.10-arm64.dmg.blockmap',
        'RUFUS-Race-Manager-1.1.10-x64.dmg', 'RUFUS-Race-Manager-1.1.10-x64.dmg.blockmap',
        'latest-mac.yml', 'RELEASE-NOTES-1.1.10-MAC-EN.md', 'RELEASE-SOURCES-1.1.10-MAC.json', 'SHA256SUMS-MAC.txt',
    }
    assert len(plan['macAssets']) == 8 and {a['name'] for a in plan['macAssets']} == expected
    assert len(plan['expectedWindows']['assets']) == 6
    assert not expected.intersection(a['name'] for a in plan['expectedWindows']['assets'])
    for asset in plan['macAssets']:
        assert asset['bytes'] > 0 and re.fullmatch('[a-f0-9]{64}', asset['sha256'])
    assert plan['s3Prefix'] == 'https://rufus-electron-app-downloads.s3.us-east-1.amazonaws.com/releases/1.1.10/mac-20261126-83944fc/'


def check_release(release, plan):
    validate_plan(plan)
    assert release['id'] == RELEASE_ID and release['tag_name'] == TAG
    assert not release['draft'] and not release['prerelease']
    assert release['name'] in (plan['expectedWindows']['name'], plan['publicationTitle'])
    expected = {a['name']: a for a in plan['expectedWindows']['assets']}
    mac = {a['name']: a for a in plan['macAssets']}
    actual = {a['name']: a for a in release['assets']}
    assert len(actual) == len(release['assets'])
    assert set(actual).issubset(set(expected) | set(mac))
    for name, original in expected.items():
        assert name in actual and asset_snapshot(actual[name]) == original
    for name in set(actual).intersection(mac):
        assert actual[name]['size'] == mac[name]['bytes']
        assert actual[name]['digest'] == 'sha256:' + mac[name]['sha256']
    final_body = plan['finalBody']
    assert release['body'] in (plan['expectedWindows']['body'], final_body)
    return actual


def request(url, method='GET', data=None, token=None, content_type=None):
    headers = {'User-Agent': 'RUFUS-1.1.10-Mac-publication', 'Cache-Control': 'no-cache'}
    if token:
        assert urllib.parse.urlparse(url).hostname in ('api.github.com', 'uploads.github.com')
        headers.update(Authorization='Bearer ' + token, Accept='application/vnd.github+json', **{'X-GitHub-Api-Version': '2022-11-28'})
    if content_type:
        headers['Content-Type'] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=180) as response:
        assert response.status in (200, 201)
        return response.read()


def api(path, token, method='GET', body=None):
    payload = None if body is None else json.dumps(body).encode()
    return json.loads(request(API + path, method, payload, token, 'application/json' if body is not None else None))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_previous(plan, token):
    expected = plan['previousRelease']
    previous = api('/releases/' + str(expected['id']), token)
    assert previous['tag_name'] == expected['tag'] and previous['body'] == expected['body']
    assert sorted((asset_snapshot(a) for a in previous['assets']), key=lambda a: a['id']) == sorted(expected['assets'], key=lambda a: a['id'])


def main():
    root = Path(__file__).resolve().parent
    plan = json.loads((root / 'publication-plan.json').read_text())
    validate_plan(plan)
    token = os.environ['GITHUB_TOKEN']
    output = root / 'verified-assets'
    output.mkdir(exist_ok=True)
    # No mutations until every public S3 body matches the locally accepted plan.
    for asset in plan['macAssets']:
        body = request(plan['s3Prefix'] + urllib.parse.quote(asset['name']))
        assert len(body) == asset['bytes'] and digest(body) == asset['sha256']
        (output / asset['name']).write_bytes(body)
    current = api('/releases/' + str(RELEASE_ID), token)
    existing = check_release(current, plan)
    assert api('/releases/latest', token)['id'] == RELEASE_ID
    verify_previous(plan, token)
    uploads = []
    # Keep latest-mac.yml last: the native updater sees metadata only after both installers exist.
    for asset in sorted(plan['macAssets'], key=lambda a: (a['name'] == 'latest-mac.yml', a['name'])):
        if asset['name'] in existing:
            uploads.append(asset_snapshot(existing[asset['name']]))
            continue
        url = 'https://uploads.github.com/repos/' + REPOSITORY + '/releases/' + str(RELEASE_ID) + '/assets?name=' + urllib.parse.quote(asset['name'])
        # A failed/uncertain POST is never automatically repeated.
        uploaded = json.loads(request(url, 'POST', (output / asset['name']).read_bytes(), token, 'application/octet-stream'))
        assert uploaded['size'] == asset['bytes'] and uploaded['digest'] == 'sha256:' + asset['sha256']
        uploads.append(asset_snapshot(uploaded))
        print(json.dumps({'uploaded': asset['name'], 'asset_id': uploaded['id'], 'sha256': asset['sha256']}), flush=True)
    current = api('/releases/' + str(RELEASE_ID), token)
    check_release(current, plan)
    assert len(current['assets']) == 14
    public_checks = []
    by_name = {a['name']: a for a in current['assets']}
    for expected in plan['macAssets']:
        # Anonymous GET retries are bounded; mutations are not retried.
        for attempt in range(3):
            try:
                body = request(by_name[expected['name']]['browser_download_url'])
                break
            except urllib.error.HTTPError as error:
                if error.code != 404 or attempt == 2:
                    raise
                time.sleep(2)
        assert len(body) == expected['bytes'] and digest(body) == expected['sha256']
        public_checks.append({'name': expected['name'], 'bytes': len(body), 'sha256': digest(body), 'anonymous': True})
    final_body = plan['finalBody']
    if current['body'] != final_body or current['name'] != plan['publicationTitle']:
        current = api('/releases/' + str(RELEASE_ID), token, 'PATCH', {'name': plan['publicationTitle'], 'body': final_body})
    check_release(current, plan)
    assert current['body'] == final_body and current['name'] == plan['publicationTitle']
    assert api('/releases/latest', token)['id'] == RELEASE_ID
    verify_previous(plan, token)
    receipt = {'status': 'PUBLISHED_VERIFIED', 'releaseId': RELEASE_ID, 'tag': TAG, 'assets': [asset_snapshot(a) for a in current['assets']], 'macAnonymousDownloads': public_checks, 'windowsUnchanged': True, 'previousReleaseUnchanged': True, 'stableLatest': True}
    (root / 'publication-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
