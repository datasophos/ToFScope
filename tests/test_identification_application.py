"""Identification must preserve labels, ownership, exact counts and captured scope."""
import unittest
from uuid import uuid4
from service_fixture import setup_case
from tofscope.api.app import build_services
from tofscope.api.schemas import RevisionEnvelope
from tofscope.application.commands import CommandEnvelope


class IdentificationTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.s = build_services(self.settings)
        self.addCleanup(self.s.jobs.shutdown)
        self.addCleanup(self.s.analyses.close_all)
        self.dataset = self.s.repository.open('a', 'a.h5')
        self.a = self.s.analyses.create_analysis('a', self.dataset)

    def send(self, **command):
        a = self.s.analyses.get('a', self.a.id)
        return self.s.explore.apply('a', a.id, CommandEnvelope(str(uuid4()), a.revision, a.dataset.generation, command))

    def measure(self, ids):
        a = self.s.analyses.get('a', self.a.id)
        env = RevisionEnvelope(request_id=str(uuid4()), expected_revision=a.revision, dataset_generation=a.dataset.generation)
        job = self.s.identification.measure('a', a.id, env, ids)
        self.assertEqual(self.s.identification.measure('a', a.id, env, ids).id, job.id)
        self.assertEqual(self.s.jobs.wait('a', job.id).status, 'succeeded')
        return self.s.identification.result('a', a.id)

    def test_candidates_preserve_provenance_polarity_and_owner(self):
        rows = self.s.identification.candidates('a', self.a.id, 26.981, .01, 'Th', (1,))
        self.assertEqual(rows.candidates[0].isotope.symbol, 'Al')
        self.assertEqual(rows.candidates[0].charge, 1)
        self.assertTrue(rows.catalog.records_sha256)
        negative = self.s.identification.candidates('a', self.a.id, 26.9821, .01, 'Th', (-1,))
        self.assertEqual(negative.candidates[0].charge, -1)
        with self.assertRaises(KeyError):
            self.s.identification.candidates('b', self.a.id, 27, 1, 'Th', (1,))

    def test_annotation_preserves_file_labels_recipe_and_independent_analysis(self):
        original = self.a.signals[0]
        other = self.s.analyses.create_analysis('a', self.dataset)
        a = self.send(type='annotate_signal', signal_id=original.id, candidate_id='C-14:+1')
        self.assertEqual(a.signals[0].assignment.isotope.mass_number, 14)
        self.assertIsNone(a.signals[0].assignment.isotope.abundance_low)
        self.assertEqual(a.signals[0].name, original.name)
        self.assertEqual(a.signals[0].recipe, original.recipe)
        self.assertIsNone(self.s.analyses.get('a', other.id).signals[0].assignment)
        with self.assertRaises(ValueError):
            self.send(type='annotate_signal', signal_id=original.id, candidate_id='C-999:+1')
        a = self.send(type='annotate_signal', signal_id=original.id, candidate_id=None)
        self.assertIsNone(a.signals[0].assignment)

    def test_measurement_original_sums_overlap_and_stale_retention(self):
        a = self.send(type='add_stored_signal', index=0)
        result = self.measure([s.id for s in a.signals])
        self.assertEqual([r.measurement.summed_intensity for r in result.rows], [75., 15.])
        self.assertTrue(all(r.measurement.observed_fraction is None for r in result.rows))
        self.assertFalse(result.out_of_date)
        self.send(type='set_display', log=False, relative=False)
        self.assertFalse(self.s.identification.result('a', a.id).out_of_date)
        changed = self.send(type='set_roi', roi=[1, 1, 0, 0])
        self.assertTrue(changed.isotope_measurement.out_of_date)
        stale = self.s.identification.result('a', a.id)
        self.assertTrue(stale.out_of_date)
        self.assertEqual(stale.rows, result.rows)
        self.assertEqual([r.measurement.summed_intensity for r in self.measure([s.id for s in a.signals]).rows], [39., 9.])

    def test_common_coverage_and_no_common_frames(self):
        a = self.send(type='add_stored_signal', index=0, frames=[1, 2])
        result = self.measure([s.id for s in a.signals])
        self.assertEqual([r.measurement.actual_frames for r in result.rows], [(1, 2), (1, 2)])
        self.assertEqual([r.measurement.summed_intensity for r in result.rows], [54., 14.])
        self.send(type='set_stored_coverage', signal_id=a.signals[0].id, frames=[0, 0])
        result = self.measure([s.id for s in a.signals])
        self.assertTrue(all(r.measurement.actual_frames is None for r in result.rows))

    def test_unknown_ids_duplicates_and_empty_selection_rejected(self):
        for ids in [[], ['unknown'], [self.a.signals[0].id] * 2]:
            with self.assertRaises(ValueError):
                self.measure(ids)

    def test_identified_comparison_uses_existing_bounded_integration_job(self):
        from tofscope.application.jobs import IntegrationSpec
        a = self.s.analyses.get('a', self.a.id)
        env = RevisionEnvelope(request_id=str(uuid4()), expected_revision=a.revision, dataset_generation=a.dataset.generation)
        spec = IntegrationSpec(((1., 2.),), (0, 2), 'C-14', candidate_id='C-14:+1')
        job = self.s.jobs.submit('a', a.id, env, spec)
        self.assertEqual(self.s.jobs.wait('a', job.id).status, 'succeeded')
        new = self.s.analyses.get('a', a.id).signals[-1]
        self.assertEqual(new.assignment.candidate_id, 'C-14:+1')
        result = self.measure([new.id])
        # Three raw counts at x=0 per frame, plus 0+1+2 at x=1; divide by four waveforms.
        self.assertEqual(result.rows[0].measurement.summed_intensity, 3.0)
        self.assertEqual(result.rows[0].measurement.observed_fraction, 1.)
        self.assertIsNone(result.rows[0].assignment.isotope.abundance_low)

    def test_saved_copy_restores_annotations_and_measurement_with_fresh_ids(self):
        a = self.send(type='annotate_signal', signal_id=self.a.signals[0].id, candidate_id='Al-27:+1')
        result = self.measure([a.signals[0].id])
        a = self.s.analyses.get('a', a.id)
        env = RevisionEnvelope(request_id=str(uuid4()), expected_revision=a.revision, dataset_generation=a.dataset.generation)
        job = self.s.saves.submit('a', a.id, env, 'identified.h5')
        saved = self.s.jobs.wait('a', job.id)
        self.assertEqual(saved.status, 'succeeded')
        dataset = self.s.repository.open('a', saved.saved_file.id, 'saved')
        restored = self.s.analyses.create_analysis('a', dataset)
        self.assertNotEqual(restored.signals[0].id, a.signals[0].id)
        self.assertEqual(restored.signals[0].assignment.candidate_id, 'Al-27:+1')
        measurement = self.s.identification.result('a', restored.id)
        self.assertFalse(measurement.out_of_date)
        self.assertEqual(measurement.rows[0].signal_id, restored.signals[0].id)
        self.assertEqual(measurement.rows[0].measurement.summed_intensity, 75.)
        self.assertEqual(measurement.dataset_generation, result.dataset_generation)
        from tofscope.storage.analysis_document import encode_document
        self.assertEqual(encode_document(restored).isotope_measurement.rows[0].measurement.recipe_id,
                         restored.signals[0].recipe.id)

    def test_saved_measurement_rejects_false_scope_and_nonfinite_values(self):
        from tofscope.storage.analysis_document import encode_document, SavedAnalysisDocument
        self.measure([self.a.signals[0].id])
        document = encode_document(self.s.analyses.get('a', self.a.id)).model_dump(mode='json')
        import copy
        for change in ('roi', 'sum', 'candidate'):
            value = copy.deepcopy(document)
            if change == 'roi':
                value['isotope_measurement']['roi'] = [1, 1, 0, 0]
            elif change == 'sum':
                value['isotope_measurement']['rows'][0]['measurement']['summed_intensity'] = float('nan')
            else:
                value['signals'][0]['assignment'] = dict(candidate_id='fake', isotope=dict(symbol='Al', mass_number=27, neutral_mass_u=26.98153853, abundance_low=1., abundance_high=1., source_id='fixture'), charge=0, predicted_mz=27., catalog=dict(records_sha256='fake', retrieved='today', sources_json='{}'))
            with self.subTest(change=change), self.assertRaises(ValueError):
                SavedAnalysisDocument.model_validate(value)

    def test_job_history_preserves_current_measurement_for_each_analysis(self):
        result = self.measure([self.a.signals[0].id])
        first = self.a
        self.a = self.s.analyses.create_analysis('a', self.dataset)
        for _ in range(260):
            self.measure([self.a.signals[0].id])
        self.assertEqual(self.s.jobs.get('a', result.job_id).status, 'succeeded')
        self.assertLessEqual(len(self.s.jobs.jobs), 258)
        self.assertEqual(self.s.analyses.get('a', first.id).isotope_job_id, result.job_id)

    def test_assignment_and_exports_retain_measured_error_and_reference_uncertainty(self):
        import csv
        import io
        import json
        from tofscope.presentation.isotopes import isotope_csv
        candidates = self.s.identification.candidates('a', self.a.id, 47.95, .01, 'Th', (1,))
        ti = next(c for c in candidates.candidates if c.isotope.symbol == 'Ti' and c.isotope.mass_number == 48)
        a = self.send(type='annotate_signal', signal_id=self.a.signals[0].id, candidate_id='Ti-48:+1', measured_mz=47.95)
        self.assertEqual(a.signals[0].assignment.error_ppm, ti.error_ppm)
        self.assertNotEqual(ti.error_ppm, 0.)
        self.measure([a.signals[0].id])
        a = self.s.analyses.get('a', a.id)
        rows = list(csv.DictReader(io.StringIO(isotope_csv(a).decode())))
        self.assertEqual(float(rows[0]['reference_abundance_uncertainty']), .0003)
        self.assertEqual(rows[0]['reference_source_id'], 'NIST-2015-CIAAW-2024')
        self.assertEqual(float(rows[0]['error_ppm']), ti.error_ppm)
        self.assertEqual(rows[0]['observed_selected_set_fraction'], '1.0')
        settings = json.loads(self.s.exports.render('a', a.id, 'json').content)
        self.assertEqual(settings['signals'][0]['assignment']['measured_mz'], 47.95)

    def test_superseded_measurement_cancels_its_reader_before_new_work(self):
        from threading import Event
        from unittest.mock import patch
        entered, release = Event(), Event()
        self.addCleanup(release.set)
        original = self.s.cache.load
        observed = []
        def blocked(*args, **kwargs):
            if not entered.is_set():
                entered.set()
                if not release.wait(3):
                    raise TimeoutError('Reader barrier timed out')
                observed.append(kwargs['cancel']())
            return original(*args, **kwargs)
        def submit():
            a = self.s.analyses.get('a', self.a.id)
            env = RevisionEnvelope(request_id=str(uuid4()), expected_revision=a.revision, dataset_generation=a.dataset.generation)
            return self.s.identification.measure('a', a.id, env, [a.signals[0].id])
        with patch.object(self.s.cache, 'load', side_effect=blocked):
            old = submit()
            self.assertTrue(entered.wait(2))
            new = submit()
            release.set()
            self.assertEqual(self.s.jobs.wait('a', old.id).status, 'obsolete')
            self.assertEqual(self.s.jobs.wait('a', new.id).status, 'succeeded')
        self.assertEqual(observed, [True])
        self.assertEqual(self.s.identification.result('a', self.a.id).job_id, new.id)
