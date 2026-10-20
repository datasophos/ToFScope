import unittest
from fastapi.testclient import TestClient
from service_fixture import setup_case
from tofscope.api.app import create_app


class CollectionTests(unittest.TestCase):
    def test_owner_file_collection_without_public_workspaces(self):
        setup_case(self, mode='proxy', trusted_proxies=('testclient',), public_origin='http://testserver')
        with TestClient(create_app(self.settings)) as c:
            h = {'x-tofscope-user': 'a', 'Origin': 'http://testserver'}
            self.assertEqual(c.get('/api/v1/analyses', headers=h).status_code, 200)
            first = c.post('/api/v1/analyses', headers=h, json={'relative_path': 'a.h5'}).json()
            second = c.post('/api/v1/analyses', headers=h, json={'relative_path': 'a.h5'}).json()
            self.assertNotEqual(first['id'], second['id'])
            self.assertNotIn('workspace_id', first)
            self.assertEqual(len(c.get('/api/v1/analyses', headers=h).json()), 2)
            self.assertEqual(c.get('/api/v1/analyses', headers=h | {'x-tofscope-user': 'b'}).json(), [])
            self.assertEqual(c.get('/api/v1/workspaces', headers=h).status_code, 404)
            c.delete('/api/v1/analyses/' + first['id'], headers=h, params={'expected_revision': first['revision']})
            self.assertEqual([a['id'] for a in c.get('/api/v1/analyses', headers=h).json()], [second['id']])

    def test_stale_close_cannot_discard_a_newer_revision(self):
        setup_case(self, mode='proxy', trusted_proxies=('testclient',), public_origin='http://testserver')
        with TestClient(create_app(self.settings)) as c:
            h = {'x-tofscope-user': 'a', 'Origin': 'http://testserver'}
            a = c.post('/api/v1/analyses', headers=h, json={'relative_path': 'a.h5'}).json()
            updated = c.post('/api/v1/analyses/' + a['id'] + '/commands', headers=h, json={
                'request_id': 'other-tab', 'expected_revision': a['revision'],
                'dataset_generation': a['dataset']['generation'],
                'command': {'type': 'set_display', 'log': False, 'relative': True, 'image': 'sims'},
            })
            self.assertEqual(updated.status_code, 200, updated.text)
            closed = c.delete('/api/v1/analyses/' + a['id'], headers=h, params={'expected_revision': a['revision']})
            self.assertEqual(closed.status_code, 409, closed.text)
            self.assertEqual(c.get('/api/v1/analyses/' + a['id'], headers=h).json()['revision'], updated.json()['revision'])
            self.assertEqual(c.delete('/api/v1/analyses/' + a['id'], headers=h).status_code, 422)
            self.assertEqual(c.delete('/api/v1/analyses/' + a['id'], headers=h,
                params={'expected_revision': updated.json()['revision']}).status_code, 204)
