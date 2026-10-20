import io
import time
import unittest
from fastapi.testclient import TestClient
from service_fixture import setup_case
from tofscope.api.app import create_app


class SaveApiTests(unittest.TestCase):
    def test_saved_files_are_private_streamed_and_reopenable(self):
        setup_case(self, mode='proxy', trusted_proxies=('testclient',), public_origin='http://testserver')
        with TestClient(create_app(self.settings)) as client:
            headers = {'x-tofscope-user': 'a', 'Origin': 'http://testserver'}
            a = client.post("/api/v1/analyses", headers=headers, json={'relative_path': 'a.h5'}).json()
            envelope = dict(request_id='save', expected_revision=a['revision'], dataset_generation=a['dataset']['generation'], filename='my copy.h5')
            response = client.post(f"/api/v1/analyses/{a['id']}/saves", headers=headers, json=envelope)
            self.assertEqual(response.status_code, 202, response.text)
            job_id = response.json()['id']
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                job = client.get(f'/api/v1/jobs/{job_id}', headers=headers).json()
                if job['status'] in ('succeeded', 'failed', 'cancelled', 'obsolete'): break
                time.sleep(.01)
            self.assertEqual(job['status'], 'succeeded', job)
            files = client.get('/api/v1/saved-files', headers=headers).json()
            self.assertEqual(len(files), 1)
            file_id = files[0]['id']
            downloaded = client.get(f'/api/v1/saved-files/{file_id}/download', headers=headers)
            self.assertEqual(downloaded.status_code, 200)
            self.assertTrue(downloaded.content.startswith(b'\x89HDF'))
            self.assertIn('attachment', downloaded.headers['content-disposition'])
            self.assertEqual(client.get(f'/api/v1/saved-files/{file_id}/download', headers=headers | {'x-tofscope-user': 'b'}).status_code, 404)
            self.assertEqual(client.get('/api/v1/saved-files', headers=headers | {'x-tofscope-user': 'b'}).json(), [])
            opened = client.post("/api/v1/analyses", headers=headers, json={'relative_path': file_id, 'location': 'saved'})
            self.assertEqual(opened.status_code, 200, opened.text)
            self.assertEqual(opened.json()['dataset']['name'], 'my copy.h5')
            self.assertEqual(client.get('/api/v1/files?location=saved', headers=headers).json()['entries'][0]['name'], 'my copy.h5')
            root_entries = client.get('/api/v1/files', headers=headers).json()['entries']
            self.assertNotIn('outputs', [x['name'] for x in root_entries])
            self.assertEqual(client.get('/api/v1/files?directory=outputs', headers=headers).status_code, 422)

    def test_folder_locations_and_shared_root_preserve_owner_isolation(self):
        from pathlib import Path
        setup_case(self, output_root=None, mode='proxy', trusted_proxies=('testclient',), public_origin='http://testserver')
        with TestClient(create_app(self.settings)) as client:
            h = {'x-tofscope-user': 'a', 'Origin': 'http://testserver'}
            response = client.get('/api/v1/locations', headers=h)
            self.assertEqual(response.status_code, 200, response.text)
            locations = response.json()
            self.assertEqual(locations['acquisitions'], str(self.settings.data_root))
            self.assertEqual(locations['saved_copies'], str(self.settings.data_root))
            a = client.post('/api/v1/analyses', headers=h, json={'relative_path': 'a.h5'})
            self.assertEqual(a.status_code, 200, a.text)
            a = a.json()
            job = client.post(f"/api/v1/analyses/{a['id']}/saves", headers=h, json=dict(request_id='save', expected_revision=a['revision'], dataset_generation=a['dataset']['generation'], filename='copy.h5')).json()
            done = client.app.state.services.jobs.wait('a', job['id'], 5)
            self.assertEqual(done.status, 'succeeded', done.safe_error)
            saved = Path(locations['save_destination']) / 'copy.h5'
            self.assertTrue(saved.is_file())
            entries = client.get('/api/v1/files', headers=h).json()['entries']
            self.assertIn('a.h5', [e['name'] for e in entries])
            self.assertNotIn(saved.parent.name, [e['name'] for e in entries])
            bypass = client.post('/api/v1/analyses', headers=h | {'x-tofscope-user':'b'}, json={'relative_path': str(saved.relative_to(self.settings.data_root))})
            self.assertEqual(bypass.status_code, 404, bypass.text)
            self.assertEqual(client.get('/api/v1/saved-files', headers=h | {'x-tofscope-user':'b'}).json(), [])
            self.assertNotEqual(client.get('/api/v1/locations', headers=h | {'x-tofscope-user':'b'}).json()['save_destination'], locations['save_destination'])
