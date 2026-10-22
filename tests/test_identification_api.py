import unittest
from fastapi.testclient import TestClient
from service_fixture import setup_case
from tofscope.api.app import create_app


class IdentificationAPITests(unittest.TestCase):
    def setUp(self):
        setup_case(self, mode='proxy', trusted_proxies=('testclient',), public_origin='http://testserver')
        self.client = TestClient(create_app(self.settings))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.headers = {'x-tofscope-user': 'a', 'Origin': 'http://testserver'}
        self.a = self.client.post('/api/v1/analyses', headers=self.headers, json={'relative_path': 'a.h5'}).json()
        self.url = f"/api/v1/analyses/{self.a['id']}"

    def test_matching_validation_and_cross_owner(self):
        body = dict(mz=26.981, tolerance=.01, unit='Th', charges=[1])
        result = self.client.post(self.url+'/candidates', headers=self.headers, json=body)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['candidates'][0]['isotope']['symbol'], 'Al')
        self.assertEqual(self.client.post(self.url+'/candidates', headers=self.headers | {'x-tofscope-user': 'b'}, json=body).status_code, 404)
        for patch in [dict(charges=[True]), dict(charges=[]), dict(mz=-1), dict(tolerance=-1), dict(unit='invalid')]:
            self.assertEqual(self.client.post(self.url+'/candidates', headers=self.headers, json=body | patch).status_code, 422)

    def test_measurement_and_csv_include_scope_and_provenance(self):
        body = dict(request_id='measure', expected_revision=0, dataset_generation=self.a['dataset']['generation'], signal_ids=[self.a['signals'][0]['id']])
        result = self.client.post(self.url+'/measurements', headers=self.headers, json=body)
        self.assertEqual(result.status_code, 202, result.text)
        job = result.json()['id']
        services = self.client.app.state.services
        self.assertEqual(services.jobs.wait('a', job).status, 'succeeded')
        value = self.client.get(self.url+'/measurements', headers=self.headers).json()
        self.assertEqual(value['rows'][0]['measurement']['summed_intensity'], 75)
        csv = self.client.get(self.url+'/isotopes.csv', headers=self.headers)
        self.assertEqual(csv.status_code, 200)
        self.assertIn('records_sha256', csv.text)
        self.assertIn('requested_first', csv.text)
        self.assertIn('75.0', csv.text)
        self.assertEqual(self.client.get(self.url+'/measurements', headers=self.headers | {'x-tofscope-user':'b'}).status_code, 404)

    def test_candidate_and_measurement_responses_obey_transport_admission(self):
        from dataclasses import replace
        services = self.client.app.state.services
        # Restrict the shared budget after opening a ready analysis.
        services.cache.budget.settings = replace(self.settings, global_bytes=1)
        body = dict(mz=27., tolerance=.1, unit='Th', charges=[1])
        self.assertEqual(self.client.post(self.url+'/candidates', headers=self.headers, json=body).status_code, 429)
        self.assertEqual(self.client.get(self.url+'/measurements', headers=self.headers).status_code, 429)

    def test_broad_candidate_query_is_bounded(self):
        body = dict(mz=100., tolerance=1e9, unit='Th', charges=[1,2,3,-1,-2,-3])
        result = self.client.post(self.url+'/candidates', headers=self.headers, json=body)
        self.assertEqual(result.status_code, 429)
        self.assertIn('narrow', result.json()['message'])
