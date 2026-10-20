import json
import unittest
from dataclasses import replace
from uuid import uuid4
import h5py
import numpy as np
from service_fixture import setup_case
from tofscope.application.workspaces import WorkspaceService
from tofscope.application.models import SignalSnapshot, DisplaySettings
from tofscope.application.commands import DepthWindow
from tofscope.science.signals import SignalRecipe
from tofscope.storage.analysis_document import encode_document, read_document, restore_snapshot


class DocumentTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        ws = WorkspaceService(self.repo, self.settings)
        self.initial = ws.create_analysis('a', ws.create('a').id, self.dataset)

    def write(self, payload, **attrs):
        path = self.settings.data_root / 'a.h5'
        with h5py.File(path, 'r+') as h:
            if 'ToFScope/Analysis' in h:
                del h['ToFScope/Analysis']
            group = h.require_group('ToFScope/Analysis')
            group.attrs.update(schema_version=1, complete=True, **attrs)
            group.create_dataset('state_json', data=np.frombuffer(json.dumps(payload).encode(), dtype='uint8'))
        return path

    def test_document_round_trip_and_fresh_service_ids(self):
        first = self.initial.signals[0]
        hidden = SignalSnapshot(str(uuid4()), 'Hidden raw', 6, SignalRecipe(intervals=((1., 2.), (3., 4.)), frames=(1, 2)))
        s = replace(self.initial, signals=(first, hidden), loaded_frames=(1, 2), roi=(1, 1, 0, 0), depth=DepthWindow(mode='window', first=1, last=2), next_style_index=7, display=DisplaySettings(False, False, 'sims', False))
        doc = encode_document(s)
        payload = doc.model_dump(mode='json')
        text = json.dumps(payload)
        for forbidden in ('workspace_id', 'owner', 'job_id', 'generation', 'relative_path'):
            self.assertNotIn(forbidden, text)
        read = read_document(self.write(payload), self.settings)
        fresh = replace(self.initial, id=str(uuid4()), owner='fresh-owner')
        restored = restore_snapshot(read, fresh)
        self.assertEqual(restored.owner, 'fresh-owner')
        self.assertEqual(restored.id, fresh.id)
        self.assertEqual(restored.display, s.display)
        self.assertEqual(restored.roi, s.roi)
        self.assertEqual(restored.depth, s.depth)
        self.assertEqual(restored.loaded_frames, s.loaded_frames)
        self.assertEqual([x.name for x in restored.signals], [x.name for x in s.signals])
        self.assertEqual([x.style_index for x in restored.signals], [x.style_index for x in s.signals])
        self.assertTrue(set(x.id for x in restored.signals).isdisjoint(x.id for x in s.signals))
        self.assertEqual(restored.image_signal_id, restored.signals[0].id)
        self.assertNotIn(restored.signals[1].id, restored.profile_signal_ids)
        self.assertEqual(restored.signals[1].recipe.intervals, hidden.recipe.intervals)
        self.assertIsNotNone(restored.signals[1].materialization_id)

    def test_plain_acquisition_has_no_document(self):
        self.assertIsNone(read_document(self.settings.data_root / 'a.h5', self.settings))

    def test_invalid_metadata_fails_explicitly(self):
        base = encode_document(self.initial).model_dump(mode='json')
        changes = [dict(schema_version=99), dict(signals=[]), dict(image_signal_id=str(uuid4())), dict(loaded_frames=[0, 999]), dict(roi=[0, 999, 0, 0]), dict(owner='injected'), dict(shape=[True, 1, 2, 2]), dict(signals=[base['signals'][0], base['signals'][0]])]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                doc = read_document(self.write(base | change), self.settings)
                restore_snapshot(doc, self.initial)
        with h5py.File(self.write(base), 'r+') as h:
            h['ToFScope/Analysis'].attrs['complete'] = False
        with self.assertRaises(ValueError):
            read_document(self.settings.data_root / 'a.h5', self.settings)

    def test_oversized_metadata_rejected_before_read(self):
        path = self.write(encode_document(self.initial).model_dump(mode='json'))
        with h5py.File(path, 'r+') as h:
            del h['ToFScope/Analysis/state_json']
            h.create_dataset('ToFScope/Analysis/state_json', shape=(1024 * 1024 + 1,), dtype='uint8')
        with self.assertRaises(ValueError):
            read_document(path, self.settings)

    def test_pending_signal_is_not_a_committed_document(self):
        pending = SignalSnapshot(str(uuid4()), 'Pending', 2, None, job_id='work')
        with self.assertRaises(ValueError):
            encode_document(replace(self.initial, signals=(*self.initial.signals, pending)))

    def test_spectrum_scale_commands_preserve_existing_choice(self):
        from tofscope.application.explore import ExploreService
        from tofscope.application.commands import CommandEnvelope
        ws = WorkspaceService(self.repo, self.settings)
        s = ws.create_analysis('a', ws.create('a').id, self.dataset)
        service = ExploreService(ws, self.repo)
        for index, extra in enumerate(({'spectrum_log': False}, {})):
            s = service.apply('a', s.id, CommandEnvelope(str(index), s.revision, s.dataset.generation,
                dict(type='set_display', log=True, relative=True, image='sims', **extra)))
            self.assertFalse(s.display.spectrum_log)
