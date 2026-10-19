import unittest
from uuid import uuid4
from service_fixture import setup_case
from tofscope.application.workspaces import WorkspaceService
from tofscope.application.explore import ExploreService
from tofscope.application.commands import CommandEnvelope


class SignalWorkspaceTests(unittest.TestCase):
    def setUp(self):
        setup_case(self, signals_per_analysis=3)
        self.ws = WorkspaceService(self.repo, self.settings)
        self.explore = ExploreService(self.ws, self.repo)
        self.a = self.ws.create_analysis('a', self.ws.create('a').id, self.dataset)

    def send(self, **command):
        s = self.ws.get('a', self.a.id)
        self.a = self.explore.apply('a', s.id, CommandEnvelope(str(uuid4()), s.revision, s.dataset.generation, command))
        return self.a

    def add(self, **kw):
        return self.send(type='add_stored_signal', index=0, **kw)

    def test_stored_add_deduplicates_unless_explicit_duplicate(self):
        self.add()
        count = len(self.a.signals)
        self.add()
        self.assertEqual(len(self.a.signals), count)
        self.add(duplicate=True)
        self.assertEqual(len(self.a.signals), count + 1)
        self.assertEqual(len({s.id for s in self.a.signals}), count + 1)

    def test_display_selection_preserves_signal_identity(self):
        old = self.a.signals[0]
        self.add(duplicate=True)
        new = self.a.signals[-1]
        self.send(type='select_image_signal', signal_id=new.id)
        self.assertEqual(self.a.signals[0], old)
        self.assertIn(old.id, self.a.profile_signal_ids)
        with self.assertRaises(ValueError):
            self.send(type='set_profile_visible', signal_id=new.id, visible=False)

    def test_disjoint_coverage_and_image_removal(self):
        first = self.a.signals[0]
        with self.assertRaises(ValueError):
            self.send(type='remove_signal', signal_id=first.id)
        self.add(duplicate=True)
        other = self.a.signals[-1]
        self.send(type='set_stored_coverage', signal_id=other.id, frames=[2, 2])
        self.send(type='set_depth', depth={'mode': 'frame', 'index': 0})
        self.send(type='select_image_signal', signal_id=other.id)
        self.assertEqual(self.a.depth.index, 2)
        self.send(type='remove_signal', signal_id=other.id)
        self.assertEqual(self.a.image_signal_id, first.id)
        self.assertEqual(self.a.signals[0].recipe.frames, (0, 2))

    def test_names_and_styles_survive_selection_and_removal(self):
        self.add(duplicate=True)
        row = self.a.signals[-1]
        self.send(type='rename_signal', signal_id=row.id, name='  Titanium  ')
        for name in ['', ' ', 'x' * 129]:
            with self.assertRaises(ValueError):
                self.send(type='rename_signal', signal_id=row.id, name=name)
        self.send(type='select_image_signal', signal_id=row.id)
        self.send(type='remove_signal', signal_id=self.a.signals[0].id)
        self.assertEqual(self.a.signals[0].name, 'Titanium')
        self.assertEqual(self.a.signals[0].style_index, row.style_index)

    def test_hidden_and_pending_signals_count_toward_limits(self):
        self.add(duplicate=True)
        self.send(type='set_profile_visible', signal_id=self.a.signals[-1].id, visible=False)
        self.add(duplicate=True)
        with self.assertRaises(ValueError):
            self.add(duplicate=True)
        self.assertEqual(len(self.ws.get('a', self.a.id).signals), 3)

    def test_owner_and_same_file_analysis_isolation(self):
        other = self.ws.create_analysis('a', self.ws.create('a').id, self.dataset)
        self.add(duplicate=True)
        self.assertEqual(len(self.ws.get('a', other.id).signals), 1)
        with self.assertRaises(KeyError):
            self.ws.get('b', self.a.id)
        with self.assertRaises(ValueError):
            self.send(type='select_image_signal', signal_id=other.signals[0].id)
