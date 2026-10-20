import unittest
from dataclasses import replace
from threading import Event
from unittest.mock import patch
from service_fixture import setup_case
from tofscope.api.app import build_services
from tofscope.application.commands import CommandEnvelope


class SaveJobTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.settings = replace(self.settings, output_root=self.settings.data_root / 'outputs')
        self.s = build_services(self.settings)
        self.addCleanup(self.s.jobs.shutdown)
        self.addCleanup(self.s.analyses.close_all)
        self.a = self.s.analyses.create_analysis('a', self.s.repository.open('a', 'a.h5'))

    def submit(self, name='copy.h5', request='save'):
        a = self.s.analyses.get('a', self.a.id)
        envelope = CommandEnvelope(request, a.revision, a.dataset.generation, {'type': 'set_depth', 'depth': {'mode': 'all'}})
        return self.s.saves.submit('a', a.id, envelope, name)

    def test_save_is_revision_bound_idempotent_and_owner_scoped(self):
        job = self.submit()
        done = self.s.jobs.wait('a', job.id, 4)
        self.assertEqual(done.status, 'succeeded', done.safe_error)
        self.assertEqual(done.kind, 'save')
        self.assertEqual(done.saved_revision, self.a.revision)
        self.assertEqual(self.submit().id, job.id)
        self.assertEqual(self.s.analyses.get('a', self.a.id).revision, self.a.revision)
        self.assertEqual(self.s.analyses.get('a', self.a.id).saved_revision, self.a.revision)
        self.assertEqual(len(self.s.saves.files.list('a')), 1)
        with self.assertRaises(KeyError): self.s.jobs.get('other', job.id)
        ref = self.s.repository.open('a', done.saved_file.id, location='saved')
        self.assertEqual(ref.name, 'copy.h5')
        self.assertEqual(self.s.cache.budget.users['a'], 0)

    def test_edit_during_save_leaves_no_published_output(self):
        original = self.s.saves.files._verify
        def edit(*args):
            original(*args)
            a = self.s.analyses.get('a', self.a.id)
            self.s.explore.apply('a', a.id, CommandEnvelope('edit', a.revision, a.dataset.generation, {'type': 'set_roi', 'roi': [1, 1, 0, 0]}))
        with patch.object(self.s.saves.files, '_verify', side_effect=edit):
            done = self.s.jobs.wait('a', self.submit().id, 4)
        self.assertIn(done.status, ('obsolete', 'failed'))
        self.assertEqual(self.s.saves.files.list('a'), [])
        self.assertEqual(self.s.cache.budget.users['a'], 0)

    def test_cancellation_and_quota_share_the_job_scheduler(self):
        entered, release = Event(), Event()
        original = self.s.saves.files._verify
        def pause(*args):
            entered.set(); release.wait(3); return original(*args)
        self.addCleanup(release.set)
        with patch.object(self.s.saves.files, '_verify', side_effect=pause):
            job = self.submit()
            self.assertTrue(entered.wait(2))
            self.s.jobs.cancel('a', job.id)
            release.set()
            self.assertEqual(self.s.jobs.wait('a', job.id, 4).status, 'cancelled')
        self.assertEqual(self.s.saves.files.list('a'), [])

    def test_save_and_integration_share_admission_and_busy_save_rejection(self):
        from tofscope.application.jobs import IntegrationSpec
        from tofscope.application.analyses import CapacityError
        self.s.jobs.settings = replace(self.settings, jobs_per_analysis=1)
        entered, release = Event(), Event()
        original = self.s.saves.files._verify
        def pause(*args):
            entered.set(); release.wait(3); return original(*args)
        self.addCleanup(release.set)
        with patch.object(self.s.saves.files, '_verify', side_effect=pause):
            save = self.submit()
            self.assertTrue(entered.wait(2))
            a = self.s.analyses.get('a', self.a.id)
            env = CommandEnvelope('integrate', a.revision, a.dataset.generation, {'type': 'set_depth', 'depth': {'mode': 'all'}})
            with self.assertRaises(CapacityError):
                self.s.jobs.submit('a', a.id, env, IntegrationSpec(((1., 2.),), (0, 2), 'Raw'))
            release.set()
            self.assertEqual(self.s.jobs.wait('a', save.id, 4).status, 'succeeded')
        entered.clear(); release.clear()
        read = self.s.repository.read
        def hold(*args, **kwargs):
            entered.set(); release.wait(3); return read(*args, **kwargs)
        with patch.object(self.s.repository, 'read', side_effect=hold):
            job = self.s.jobs.submit('a', a.id, env, IntegrationSpec(((1., 2.),), (0, 2), 'Raw'))
            self.assertTrue(entered.wait(2))
            with self.assertRaisesRegex(ValueError, 'calculations'):
                self.submit('after.h5', 'busy')
            release.set()
            self.assertEqual(self.s.jobs.wait('a', job.id, 4).status, 'succeeded')
