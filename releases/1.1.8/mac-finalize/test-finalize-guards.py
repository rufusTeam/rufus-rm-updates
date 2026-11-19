import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('finalize', Path(__file__).with_name('finalize-draft.py'))


class FinalizeGuards(unittest.TestCase):
    def setUp(self):
        self.module = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(self.module)
        self.expected = copy.deepcopy(self.module.PLAN['expected_assets'])
        self.release = {'id': 450687888, 'tag_name': 'v1.1.8', 'draft': True, 'prerelease': False, 'assets': copy.deepcopy(self.expected)}

    def test_accepts_only_exact_existing_draft_and_asset_snapshot(self):
        self.assertEqual(len(self.module.validate_existing(self.release, self.expected)), 8)

    def test_published_release_or_wrong_id_is_rejected(self):
        for changed in [{'draft': False}, {'id': 448929324}, {'tag_name': 'v1.1.7'}]:
            with self.assertRaises(AssertionError):
                self.module.validate_existing(self.release | changed, self.expected)

    def test_changed_binary_or_missing_document_is_rejected(self):
        self.release['assets'][2]['digest'] = 'sha256:unexpected'
        with self.assertRaises(AssertionError):
            self.module.validate_existing(self.release, self.expected)
        self.release['assets'].pop()
        with self.assertRaises(AssertionError):
            self.module.validate_existing(self.release, self.expected)

    def test_no_create_publish_binary_delete_or_other_release_mutation(self):
        with patch.object(self.module.urllib.request, 'urlopen') as network:
            for method, route, body in [
                ('POST', '/releases', {'draft': True}),
                ('PATCH', '/releases/450687888', {'draft': False}),
                ('DELETE', '/releases/assets/765424863', None),
                ('PATCH', '/releases/448929324', {'draft': True}),
            ]:
                with self.assertRaises(AssertionError):
                    self.module.api(method, route, body)
            network.assert_not_called()

    def test_api_allows_only_document_delete_and_draft_preserving_patch(self):
        class Response(io.BytesIO):
            status = 200
        with patch.dict(self.module.os.environ, {'GITHUB_TOKEN': 'synthetic-test-only'}), patch.object(self.module.urllib.request, 'urlopen', return_value=Response(b'{}')) as network:
            self.module.api('PATCH', '/releases/450687888', {'body': 'reviewed notes', 'draft': True, 'prerelease': False, 'make_latest': 'false'})
            request = network.call_args.args[0]
            self.assertEqual(request.method, 'PATCH')
            self.assertTrue(json.loads(request.data)['draft'])


if __name__ == '__main__':
    unittest.main()
