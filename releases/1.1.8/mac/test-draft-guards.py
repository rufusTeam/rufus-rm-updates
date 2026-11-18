import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('draft', Path(__file__).with_name('prepare-draft.py'))


class Response(io.BytesIO):
    status = 200

    def __init__(self, data, url):
        super().__init__(data)
        self.url = url


class DraftGuards(unittest.TestCase):
    def fixture(self, directory, existing=False, corrupt=False):
        module = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(module)
        module.HERE = Path(directory)
        names = ['RELEASE-NOTES-1.1.8-MAC-EN.md'] + [f'synthetic-{n}.bin' for n in range(7)]
        bodies = {name: ('synthetic ' + name).encode() for name in names}
        module.PLAN = {'tag': 'v1.1.8', 'draft': True, 'target_commitish': '0b3c94363d44def9bca25af56a749e1a1ec568f4',
                       'assets': [{'name': name, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                                   'content_type': 'application/octet-stream', 'url': 'https://rufus-electron-app-downloads.s3.us-east-1.amazonaws.com/releases/1.1.8/mac-20261119-c1d61de/' + name}
                                  for name, body in bodies.items()]}
        stable = {'id': 117, 'tag_name': 'v1.1.7', 'draft': False, 'body': 'protected',
                  'assets': [{'id': 1, 'name': 'protected.exe', 'size': 1, 'digest': 'sha256:protected'}]}
        created = {'id': 118, 'tag_name': 'v1.1.8', 'draft': True, 'prerelease': False,
                   'html_url': 'https://github.com/rufusTeam/rufus-rm-updates/releases/tag/untagged-synthetic', 'assets': []}
        calls, downloads = [], []

        def api(method, route, body=None):
            calls.append((method, route, body))
            if route.startswith('/releases?'):
                return [stable] + ([created] if existing else [])
            if route == '/releases/latest':
                return stable
            if route.startswith('/commits/'):
                return {'sha': module.PLAN['target_commitish']}
            if method == 'POST' and route == '/releases':
                assert body['draft'] is True and body['make_latest'] == 'false'
                return created
            if route == '/releases/118':
                return created
            raise AssertionError('Unexpected release request')

        def urlopen(request, timeout):
            if isinstance(request, str):
                name = request.rsplit('/', 1)[1]
                downloads.append(name)
                body = bodies[name] + (b'corrupt' if corrupt else b'')
                return Response(body, request)
            assert request.method == 'POST'
            assert request.full_url.startswith('https://uploads.github.com/repos/rufusTeam/rufus-rm-updates/releases/118/assets?name=')
            name = request.full_url.rsplit('=', 1)[1]
            row = {'id': 1000 + len(created['assets']), 'name': name, 'size': len(request.data),
                   'digest': 'sha256:' + hashlib.sha256(request.data).hexdigest(), 'state': 'uploaded'}
            created['assets'].append(row)
            return Response(json.dumps(row).encode(), request.full_url)

        module.api = api
        environment = {'GITHUB_REPOSITORY': module.REPOSITORY, 'GITHUB_REF': 'refs/heads/codex/rrm118-mac-draft-20261119', 'GITHUB_TOKEN': 'synthetic-test-only'}
        return module, calls, downloads, environment, urlopen

    def test_creates_only_a_new_draft_and_uploads_only_to_its_id(self):
        with tempfile.TemporaryDirectory() as directory:
            module, calls, downloads, environment, urlopen = self.fixture(directory)
            with patch.dict(module.os.environ, environment, clear=True), patch.object(module.urllib.request, 'urlopen', urlopen), patch('builtins.print'):
                module.main()
            self.assertEqual(len(downloads), 8)
            self.assertEqual([(method, route) for method, route, _ in calls if method != 'GET'], [('POST', '/releases')])
            receipt = json.loads((Path(directory) / 'draft-receipt.json').read_text())
            self.assertTrue(receipt['draft'])
            self.assertTrue(receipt['stable_117_release_and_assets_preserved'])
            self.assertEqual(len(receipt['assets']), 8)

    def test_existing_release_aborts_before_download_or_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            module, calls, downloads, environment, urlopen = self.fixture(directory, existing=True)
            with patch.dict(module.os.environ, environment, clear=True), patch.object(module.urllib.request, 'urlopen', urlopen):
                with self.assertRaises(AssertionError):
                    module.main()
            self.assertEqual(downloads, [])
            self.assertTrue(all(method == 'GET' for method, _, _ in calls))

    def test_corrupt_download_aborts_before_create(self):
        with tempfile.TemporaryDirectory() as directory:
            module, calls, downloads, environment, urlopen = self.fixture(directory, corrupt=True)
            with patch.dict(module.os.environ, environment, clear=True), patch.object(module.urllib.request, 'urlopen', urlopen):
                with self.assertRaises(AssertionError):
                    module.main()
            self.assertEqual(len(downloads), 1)
            self.assertTrue(all(method == 'GET' for method, _, _ in calls))


if __name__ == '__main__':
    unittest.main()
