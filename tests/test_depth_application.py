"""Prototype calibrated profile/front assertions through the application boundary."""
import csv
import io
import json
import unittest
from dataclasses import replace
import numpy as np
from service_fixture import setup_case
from tofscope.api.app import build_services
from tofscope.application.commands import CommandEnvelope
from tofscope.storage.analysis_document import encode_document, restore_snapshot, SavedAnalysisDocument


class DepthApplicationTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.s = build_services(self.settings)
        self.addCleanup(self.s.jobs.shutdown)
        self.addCleanup(self.s.analyses.close_all)
        self.a = self.s.analyses.create_analysis('a', self.s.repository.open('a', 'a.h5'))

    def command(self, command, owner='a', analysis=None):
        a = self.s.analyses.get(owner, analysis or self.a.id)
        return self.s.explore.apply(owner, a.id, CommandEnvelope(str(a.revision), a.revision, a.dataset.generation, command))

    def anchors(self, rows):
        return self.command(dict(type='set_depth_anchors', anchors=[dict(frame=f, depth_nm=d) for f,d in rows]))

    def physical(self, unit='nm'):
        return self.command(dict(type='set_depth_display', unit=unit, coordinates='depth'))

    def test_validation_atomicity_fixed_origin_and_removal(self):
        a = self.anchors([(1,100)])
        self.assertEqual([(x.frame,x.depth_nm) for x in a.depth_anchors], [(0,0),(1,100)])
        self.physical()
        for rows in [[(0,4),(1,100)], [(1,100),(2,99)], [(1,0)], [(1,100),(1,101)], [(3,100)], [(True,1)], [(1,float('inf'))]]:
            before = self.s.analyses.get('a', a.id)
            with self.subTest(rows=rows), self.assertRaises(ValueError): self.anchors(rows)
            self.assertEqual(self.s.analyses.get('a',a.id), before)
        a = self.anchors([])
        self.assertEqual(a.depth_coordinates, 'frame')
        with self.assertRaises(ValueError): self.physical()
        d = self.s.presenter.snapshot('a',a.id,{'front','profile'})
        self.assertEqual(d.panels['profile'].axes[0].values,[0,1,2])
        self.assertEqual(d.panels['front'].axes[1].unit,'frame')

    def test_partial_calibration_preserves_original_values_frames_and_export(self):
        before = self.s.presenter.snapshot('a', self.a.id)
        self.anchors([(1,100)])
        self.physical('um')
        after = self.s.presenter.snapshot('a', self.a.id)
        profile, front = after.panels['profile'], after.panels['front']
        self.assertEqual(profile.axes[0].values,[0,.1])
        self.assertEqual(profile.acquisition_frames,[0,1])
        self.assertEqual(profile.omitted_frames,1)
        self.assertEqual(profile.series[0].values,before.panels['profile'].series[0].values[:2])
        self.assertEqual(front.values,before.panels['front'].values[:2])
        self.assertEqual(front.acquisition_frames,[0,1])
        self.assertEqual(after.panels['ion'].values,before.panels['ion'].values)
        rows = list(csv.DictReader(io.StringIO(self.s.exports.render('a',self.a.id,'csv').content.decode())))
        self.assertEqual([r['depth_nm'] for r in rows],['0.0','100.0',''])
        for unit in ['nm','mm']:
            self.physical(unit)
            self.assertEqual(self.s.presenter.snapshot('a',self.a.id,{'front'}).panels['front'].values,front.values)
            self.assertEqual(list(csv.DictReader(io.StringIO(self.s.exports.render('a',self.a.id,'csv').content.decode()))),rows)
        self.command(dict(type='set_depth',depth=dict(mode='frame',index=2)))
        self.assertEqual(self.s.analyses.get('a',self.a.id).depth.index,2)
        json.dumps(after.to_dict(),allow_nan=False)

    def test_viewing_range_preserves_full_profile_and_limits_csv_rows(self):
        before = self.s.presenter.snapshot('a', self.a.id, {'profile', 'front'})
        self.command(dict(type='set_depth', depth=dict(mode='window', first=1, last=2)))
        after = self.s.presenter.snapshot('a', self.a.id, {'profile', 'front'})
        self.assertEqual(after.panels['profile'].acquisition_frames, [0, 1, 2])
        self.assertEqual(after.panels['profile'].series, before.panels['profile'].series)
        self.assertEqual(after.panels['front'].values, before.panels['front'].values)
        rows = list(csv.DictReader(io.StringIO(self.s.exports.render('a', self.a.id, 'csv').content.decode())))
        self.assertEqual([row['frame'] for row in rows], ['1', '2'])
        self.assertNotIn('loaded_frames', vars(self.s.analyses.get('a', self.a.id)))

    def test_analysis_isolation_and_document_legacy_defaults(self):
        b = self.s.analyses.create_analysis('a',self.a.dataset)
        self.anchors([(1,100)])
        a = self.physical('mm')
        self.assertEqual(b.depth_coordinates,'frame')
        with self.assertRaises(KeyError): self.command(dict(type='set_depth_anchors',anchors=[]),owner='b')
        document = encode_document(a)
        self.assertEqual(document.schema_version,2)
        restored = restore_snapshot(SavedAnalysisDocument.model_validate_json(document.model_dump_json()),b)
        self.assertEqual(restored.depth_anchors,a.depth_anchors)
        self.assertEqual(restored.depth_unit,'mm')
        self.assertEqual(restored.depth_coordinates,'depth')
        old = document.model_dump()
        old['schema_version'] = 1
        for key in ['depth_anchors','depth_unit','depth_coordinates']: old.pop(key)
        legacy = restore_snapshot(SavedAnalysisDocument.model_validate(old), b)
        self.assertEqual(legacy.depth_coordinates,'frame')
        self.assertEqual(len(legacy.depth_anchors),1)
        bad = document.model_dump()
        bad['depth_anchors']=[dict(frame=0,depth_nm=2),dict(frame=1,depth_nm=100)]
        with self.assertRaises(ValueError): SavedAnalysisDocument.model_validate(bad)

    def test_full_domain_anchor_kink_and_block_mean_coordinates(self):
        from tofscope.presentation.coordinates import block_depths
        from tofscope.science.depth_calibration import DepthAnchor
        s = replace(self.a, shape=(301,1,2,2),
                    depth_anchors=(DepthAnchor(0,0),DepthAnchor(100,50),DepthAnchor(200,150)),depth_coordinates='depth')
        from tofscope.presentation.coordinates import depth_samples
        frames, depths, unit, omitted = depth_samples(s)
        np.testing.assert_array_equal(frames,np.arange(201))
        np.testing.assert_array_equal(depths[100:103],[50,51,52])
        self.assertEqual(omitted,100)
        s = replace(s,depth_anchors=(DepthAnchor(0,0),DepthAnchor(2,20),DepthAnchor(4,60)))
        self.assertEqual(block_depths(s,[[2,3]]),[30])
        self.assertTrue(np.isnan(block_depths(s,[[4,5]])[0]))

    def test_saved_copy_roundtrip_and_legacy_file_on_disk(self):
        from threading import Event
        from tofscope.storage.saved_files import SavedFileStore
        from tofscope.storage.analysis_document import read_document
        import h5py
        import hashlib
        path=self.settings.data_root/'a.h5'
        digest=hashlib.sha256(path.read_bytes()).digest()
        self.anchors([(1,100)])
        a=self.physical('um')
        store=SavedFileStore(replace(self.settings,output_root=self.settings.data_root/'output'))
        saved=store.publish_copy('a',path,encode_document(a),lambda _: iter(()),'depth.h5',Event(),lambda *a:None,lambda:None)
        saved_path=store.path('a',saved.id)
        doc=read_document(saved_path,self.settings)
        self.assertEqual(restore_snapshot(doc,self.a).depth_anchors,a.depth_anchors)
        self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),digest)
        # Simulate an actual version-1 document created before calibration existed.
        with h5py.File(saved_path,'r+') as h:
            group=h['ToFScope/Analysis']
            old=json.loads(group['state_json'][:].tobytes())
            old['schema_version']=1
            for key in ['depth_anchors','depth_unit','depth_coordinates']:old.pop(key)
            del group['state_json']
            group.create_dataset('state_json',data=np.frombuffer(json.dumps(old).encode(),dtype='uint8'))
            group.attrs['schema_version']=1
        restored=restore_snapshot(read_document(saved_path,self.settings),self.a)
        self.assertEqual(restored.depth_coordinates,'frame')
        self.assertEqual(len(restored.depth_anchors),1)

    def test_unrelated_panels_do_not_allocate_depth_coordinates(self):
        from unittest.mock import patch
        with patch('tofscope.presentation.explore.depth_samples',side_effect=AssertionError('unadmitted depth allocation')):
            self.s.presenter.snapshot('a',self.a.id,{'spectrum','ion'})

    def test_presenter_nonzero_frames_partial_profiles_and_exact_front_values(self):
        import h5py
        path=self.settings.data_root/'b.h5'
        values=np.broadcast_to(np.arange(301,dtype='float32')[:,None,None,None],(301,1,2,2)).copy()
        with h5py.File(path,'r+') as h:
            del h['PeakData/PeakData']
            h.create_dataset('PeakData/PeakData',data=values)
        a=self.s.analyses.create_analysis('a',self.s.repository.open('a','b.h5'))
        before=self.s.presenter.snapshot('a',a.id,{'profile','front'})
        a=self.command(dict(type='set_depth_anchors',anchors=[dict(frame=100,depth_nm=50),dict(frame=200,depth_nm=150)]),analysis=a.id)
        a=self.command(dict(type='set_depth_display',unit='nm',coordinates='depth'),analysis=a.id)
        after=self.s.presenter.snapshot('a',a.id,{'profile','front'})
        self.assertEqual(after.panels['profile'].acquisition_frames,list(range(201)))
        self.assertEqual(after.panels['profile'].axes[0].values[100:103],[50,51,52])
        self.assertEqual(after.panels['profile'].series[0].values,before.panels['profile'].series[0].values[:201])
        np.testing.assert_array_equal(after.panels['front'].values,before.panels['front'].values[:201])
        self.assertEqual(after.panels['front'].omitted_frames,100)
        self.command(dict(type='set_depth', depth=dict(mode='frame', index=200)), analysis=a.id)
        selected=self.s.presenter.snapshot('a',a.id,{'profile'}).panels['profile']
        self.assertEqual(selected.series[0].values, list(range(201)))
        self.assertEqual(selected.acquisition_frames, list(range(201)))
