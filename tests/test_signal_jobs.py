import unittest
import threading
from uuid import uuid4
from service_fixture import setup_case
from tofscope.api.app import build_services
from tofscope.application.jobs import IntegrationSpec
from tofscope.application.commands import CommandEnvelope


class SignalJobTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.s = build_services(self.settings)
        self.addCleanup(self.s.analyses.close_all)
        self.addCleanup(self.s.jobs.shutdown)
        self.a = self.s.analyses.create_analysis('a', self.s.repository.open('a', 'a.h5'))

    def state(self):
        return self.s.analyses.get('a', self.a.id)

    def env(self, request=None):
        a = self.state()
        return CommandEnvelope(request or str(uuid4()), a.revision, a.dataset.generation, {'type':'set_depth','depth':{'mode':'all'}})

    def submit(self, name='Ti', signal_id=None, version=None):
        return self.s.jobs.submit('a', self.a.id, self.env(), IntegrationSpec(((1,2),(4,5)), (0,2), name, signal_id, version))

    def wait(self, job):
        return self.s.jobs.wait('a', job.id, 5)

    def block(self):
        entered, release = threading.Event(), threading.Event()
        read = self.s.repository.read
        def blocked(*args, **kwargs):
            entered.set()
            release.wait(3)
            return read(*args, **kwargs)
        self.s.repository.read = blocked
        self.addCleanup(release.set)
        return entered, release

    def test_new_signal_calculation_preserves_image_choice(self):
        image = self.a.image_signal_id
        entered, release = self.block()
        job = self.submit()
        self.assertTrue(entered.wait(2))
        row = self.state().signals[-1]
        self.assertIsNone(row.recipe)
        self.assertEqual(row.id, job.signal_id)
        release.set()
        self.assertEqual(self.wait(job).status, 'succeeded')
        a = self.state()
        self.assertEqual(a.image_signal_id, image)
        self.assertIn(row.id, a.profile_signal_ids)
        self.assertEqual(a.signals[-1].recipe_version, 1)

    def test_rename_and_roi_during_job_survive_commit(self):
        entered, release = self.block()
        job = self.submit()
        self.assertTrue(entered.wait(2))
        self.s.explore.apply('a', self.a.id, CommandEnvelope(str(uuid4()), self.state().revision, self.a.dataset.generation, {'type':'rename_signal','signal_id':job.signal_id,'name':'Renamed'}))
        self.s.explore.apply('a', self.a.id, CommandEnvelope(str(uuid4()), self.state().revision, self.a.dataset.generation, {'type':'set_roi','roi':[1,1,0,0]}))
        release.set()
        self.assertEqual(self.wait(job).status, 'succeeded')
        self.assertEqual(self.state().signals[-1].name, 'Renamed')
        self.assertEqual(self.state().roi, (1,1,0,0))

    def test_retry_reuses_pending_row_and_job(self):
        env = self.env()
        spec = IntegrationSpec(((1,2),), (0,2), 'Ti')
        job = self.s.jobs.submit('a', self.a.id, env, spec)
        again = self.s.jobs.submit('a', self.a.id, env, spec)
        self.assertEqual(again.id, job.id)
        self.assertEqual(self.wait(job).status, 'succeeded')
        self.assertEqual(len(self.state().signals), 2)
        with self.assertRaises(ValueError):
            self.submit(signal_id=job.signal_id, version=0)

    def test_failed_update_retains_committed_values(self):
        first = self.submit()
        self.assertEqual(self.wait(first).status, 'succeeded')
        old = self.state().signals[-1]
        read = self.s.repository.read
        def fail(*args, **kw):
            raise ValueError('injected read failure')
        self.s.repository.read = fail
        # Change bounds to avoid hitting the previously cached result.
        job = self.s.jobs.submit('a', self.a.id, self.env(), IntegrationSpec(((2,3),), (0,2), 'New name', old.id, 1))
        self.assertEqual(self.wait(job).status, 'failed')
        row = self.state().signals[-1]
        self.assertEqual(row.recipe, old.recipe)
        self.assertEqual(row.name, old.name)
        self.assertEqual(row.recipe_version, 1)
        self.s.repository.read = read

    def test_delete_replace_close_and_supersede_discard_late_results(self):
        entered, release = self.block()
        job = self.submit()
        self.assertTrue(entered.wait(2))
        self.s.explore.apply('a', self.a.id, CommandEnvelope(str(uuid4()), self.state().revision, self.a.dataset.generation, {'type':'remove_signal','signal_id':job.signal_id}))
        release.set()
        self.assertIn(self.wait(job).status, ('cancelled','obsolete'))
        self.assertEqual(len(self.state().signals), 1)

    def test_failed_pending_and_hidden_records_cannot_bypass_quota(self):
        from dataclasses import replace
        self.s.analyses.settings = replace(self.settings, signals_per_analysis=2)
        entered, release = self.block()
        job = self.submit()
        self.assertTrue(entered.wait(2))
        with self.assertRaises(ValueError):
            self.submit(name='extra')
        self.s.jobs.cancel('a', job.id)
        release.set()
        self.assertEqual(self.wait(job).status, 'cancelled')
        self.assertIsNone(self.state().signals[-1].recipe)
        retry = self.submit(signal_id=job.signal_id, version=0)
        self.assertEqual(self.wait(retry).status, 'succeeded')
        self.assertEqual(len(self.state().signals), 2)
        self.s.analyses.close('a', self.a.id)
        self.assertEqual(self.s.cache.budget.users.get('a', 0), 0)

    def test_replacement_and_close_discard_late_results(self):
        for action in ('replace', 'close'):
            with self.subTest(action=action):
                a = self.s.analyses.create_analysis('a', self.s.repository.open('a', 'a.h5'))
                self.a = a
                entered, release = self.block()
                job = self.submit()
                self.assertTrue(entered.wait(2))
                if action == 'replace':
                    # Initial stored channel is already cached, so replacement
                    # need not enter the blocked raw-data reader.
                    self.s.analyses.replace('a', a.id, self.s.repository.open('a', 'a.h5'), self.state().revision)
                else:
                    self.s.analyses.close('a', a.id)
                release.set()
                self.assertIn(self.wait(job).status, ('cancelled', 'obsolete'))

    def test_hidden_signal_update_preserves_visibility_and_does_not_pin_array(self):
        first = self.submit()
        self.assertEqual(self.wait(first).status, 'succeeded')
        a = self.state()
        self.s.explore.apply('a', a.id, CommandEnvelope(str(uuid4()),a.revision,a.dataset.generation,{'type':'set_profile_visible','signal_id':first.signal_id,'visible':False}))
        updated = self.submit(signal_id=first.signal_id, version=1)
        self.assertEqual(self.wait(updated).status, 'succeeded')
        self.assertNotIn(first.signal_id, self.state().profile_signal_ids)
        self.assertNotIn(first.signal_id, self.s.analyses.entry('a',a.id).leases)

    def test_removal_cancels_queued_jobs_and_frees_admission_immediately(self):
        from dataclasses import replace
        self.s.jobs.settings = replace(self.settings, jobs_per_analysis=2)
        entered, release = self.block()
        first = self.submit(name='Running')
        self.assertTrue(entered.wait(2))
        queued = self.submit(name='Queued')
        self.assertEqual(self.s.jobs.get('a', queued.id).status, 'queued')
        a = self.state()
        self.s.explore.apply('a', a.id, CommandEnvelope(str(uuid4()),a.revision,a.dataset.generation,{'type':'remove_signal','signal_id':queued.signal_id}))
        self.assertEqual(self.s.jobs.get('a', queued.id).status, 'cancelled')
        self.assertNotIn(queued.signal_id, self.s.analyses.entry('a',a.id).tokens)
        third = self.submit(name='Replacement')
        release.set()
        self.assertEqual(self.wait(first).status, 'succeeded')
        self.assertEqual(self.wait(third).status, 'succeeded')

    def test_history_pruning_preserves_referenced_terminal_jobs(self):
        retained = self.submit(name='Retained')
        self.assertEqual(self.wait(retained).status, 'succeeded')
        changing = self.submit(name='Changing')
        self.assertEqual(self.wait(changing).status, 'succeeded')
        for version in range(1,261):
            changing = self.submit(name='Changing',signal_id=changing.signal_id,version=version)
            self.assertEqual(self.wait(changing).status, 'succeeded')
        self.assertEqual(self.s.jobs.get('a', retained.id).status, 'succeeded')
        self.assertLessEqual(len(self.s.jobs.jobs), 258)
        a = self.state()
        self.s.explore.apply('a',a.id,CommandEnvelope(str(uuid4()),a.revision,a.dataset.generation,{'type':'remove_signal','signal_id':retained.signal_id}))
        final = self.submit(name='Changing',signal_id=changing.signal_id,version=261)
        self.assertEqual(self.wait(final).status,'succeeded')
        with self.assertRaises(KeyError):
            self.s.jobs.get('a',retained.id)
