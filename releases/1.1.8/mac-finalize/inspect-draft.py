"""Read-only follow-up after finalization assertion; no release writes."""
import hashlib
import json
import os
from pathlib import Path
import urllib.request

HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / 'manifest.json').read_text())
BASE = 'https://api.github.com/repos/rufusTeam/rufus-rm-updates'


def read(route):
    assert route in ['/releases/latest', '/releases/450687888']
    request = urllib.request.Request(BASE + route, method='GET', headers={
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
        'X-GitHub-Api-Version': '2022-11-28',
        'Cache-Control': 'no-cache',
    })
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def main():
    assert os.environ.get('GITHUB_REPOSITORY') == 'rufusTeam/rufus-rm-updates'
    release, stable = read('/releases/450687888'), read('/releases/latest')
    fields = ['id', 'tag_name', 'draft', 'prerelease', 'published_at', 'name']
    asset_fields = ['id', 'name', 'size', 'digest', 'state']
    receipt = {'release': {k: release.get(k) for k in fields},
               'assets': [{k: a.get(k) for k in asset_fields} for a in release.get('assets', [])],
               'body_sha256': hashlib.sha256(release.get('body', '').encode()).hexdigest(),
               'stable': {k: stable.get(k) for k in fields},
               'readonly': True}
    print(json.dumps(receipt, indent=2))
    assert release['draft'] is True and release['id'] == 450687888
    assert stable['id'] == 448929324 and stable['tag_name'] == 'v1.1.7'
    previous = {a['name']: a for a in PLAN['expected_assets']}
    documents = {a['name']: a for a in PLAN['replace_documents']}
    assert len(release['assets']) == 8
    for a in release['assets']:
        if a['name'] in documents:
            d = documents[a['name']]
            assert a['size'] == d['bytes'] and a['digest'] == 'sha256:' + d['sha256']
        else:
            assert {k: a.get(k) for k in asset_fields} == {k: previous[a['name']].get(k) for k in asset_fields}
    (HERE / 'inspection-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
