import copy
import importlib.util
import json
from pathlib import Path
import unittest

root = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('publish_mac', root / 'publish_mac.py')
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)
plan = json.loads((root / 'publication-plan.json').read_text())


class PublicationGuards(unittest.TestCase):
    def baseline(self):
        return {'id': plan['releaseId'], 'tag_name': plan['tag'], 'draft': False, 'prerelease': False, 'name': plan['expectedWindows']['name'], 'body': plan['expectedWindows']['body'], 'assets': copy.deepcopy(plan['expectedWindows']['assets'])}

    def test_existing_windows_release_and_verified_partial_resume_are_allowed(self):
        release = self.baseline()
        publish.check_release(release, plan)
        asset = plan['macAssets'][0]
        release['assets'].append({'id': 1, 'name': asset['name'], 'size': asset['bytes'], 'digest': 'sha256:' + asset['sha256'], 'updated_at': 'synthetic'})
        publish.check_release(release, plan)

    def test_wrong_target_windows_change_unknown_assets_and_changed_body_fail(self):
        for change in ('id', 'tag', 'draft', 'title', 'windows', 'unknown', 'body', 'mac-digest'):
            with self.subTest(change=change):
                release = self.baseline()
                if change == 'id': release['id'] = 1
                elif change == 'tag': release['tag_name'] = 'v1.1.9'
                elif change == 'draft': release['draft'] = True
                elif change == 'title': release['name'] = 'Unrelated concurrent release edit'
                elif change == 'windows': release['assets'][0]['digest'] = 'sha256:' + '0' * 64
                elif change == 'unknown': release['assets'].append({'name': 'unexpected.exe'})
                elif change == 'body': release['body'] = 'unrelated concurrent edit'
                else:
                    asset = plan['macAssets'][0]
                    release['assets'].append({'name': asset['name'], 'size': asset['bytes'], 'digest': 'sha256:' + '0' * 64})
                with self.assertRaises(AssertionError): publish.check_release(release, plan)


if __name__ == '__main__':
    unittest.main()
