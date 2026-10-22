"""Spatial payload, state, isolation and scientific regression contracts."""

import json
import unittest
from dataclasses import replace
from unittest.mock import patch
import numpy as np
from service_fixture import setup_case
from tofscope.api.app import build_services
from tofscope.application.commands import CommandEnvelope
from tofscope.storage.analysis_document import (
    encode_document,
    restore_snapshot,
    SavedAnalysisDocument,
)


class VolumeDataTests(unittest.TestCase):
    def setUp(self):
        setup_case(self)
        self.s = build_services(self.settings)
        self.addCleanup(self.s.jobs.shutdown)
        self.addCleanup(self.s.analyses.close_all)
        self.a = self.s.analyses.create_analysis(
            "a", self.s.repository.open("a", "a.h5")
        )

    def command(self, c):
        a = self.s.analyses.get("a", self.a.id)
        return self.s.explore.apply(
            "a",
            a.id,
            CommandEnvelope(str(a.revision), a.revision, a.dataset.generation, c),
        )

    def configure(self, **patches):
        a = self.s.analyses.get("a", self.a.id)
        state = a.spatial.model_dump()
        state.update(patches)
        return self.command(dict(type="set_spatial", spatial=state))

    def test_values_geometry_partial_coverage_and_owner_isolation(self):
        sid = self.a.image_signal_id
        self.configure(layers=[dict(signal_id=sid)])
        result = self.s.volumes.snapshot("a", self.a.id)
        layer = result.layers[0]
        self.assertEqual(layer.values, [10, 11, 12, 13, 14, 15])
        self.assertEqual(result.z, [0, 1, 2])
        self.assertEqual(result.total_voxels, 6)
        self.command(dict(type="set_stored_coverage", signal_id=sid, frames=(1, 2)))
        # Add another full-coverage signal; its selection does not clip the first.
        a = self.command(dict(type="add_stored_signal", index=0))
        self.configure(layers=[dict(signal_id=sid), dict(signal_id=a.signals[-1].id)])
        result = self.s.volumes.snapshot("a", a.id)
        self.assertEqual(result.layers[0].values, [None, None, 12, 13, 14, 15])
        self.assertEqual(result.layers[0].valid_counts, [0, 0, 1, 1, 1, 1])
        json.dumps(result.to_dict(), allow_nan=False)
        with self.assertRaises(KeyError):
            self.s.volumes.snapshot("other", a.id)

    def test_calibrated_unknown_frames_roi_and_original_profile(self):
        self.configure(layers=[dict(signal_id=self.a.image_signal_id)])
        self.command(
            dict(type="set_depth_anchors", anchors=[dict(frame=1, depth_nm=100)])
        )
        self.command(dict(type="set_depth_display", unit="nm", coordinates="depth"))
        self.command(dict(type="set_roi", roi=(1, 1, 0, 0)))
        result = self.s.volumes.snapshot("a", self.a.id)
        self.assertEqual(result.z, [0, 0.1])
        self.assertEqual(result.layers[0].values, [11, 13])
        self.assertEqual(result.omitted_frames, 1)
        self.assertEqual(result.z_unit, "µm")
        self.command(dict(type="set_depth", depth=dict(mode="frame", index=2)))
        self.assertEqual(self.s.volumes.snapshot("a", self.a.id).layers, [])
        self.assertEqual(
            self.s.presenter.snapshot("a", self.a.id, {"profile"})
            .panels["profile"]
            .series[0]
            .values,
            [11, 13],
        )

    def test_style_camera_reuse_document_remapping_and_validation(self):
        sid = self.a.image_signal_id
        a = self.configure(
            layers=[dict(signal_id=sid, opacity=0.3, percentile=42)], screen="volume"
        )
        doc = encode_document(a)
        self.assertEqual(doc.schema_version, 4)
        fresh = self.s.analyses.create_analysis("a", a.dataset)
        restored = restore_snapshot(
            SavedAnalysisDocument.model_validate_json(doc.model_dump_json()), fresh
        )
        self.assertNotEqual(restored.spatial.layers[0].signal_id, sid)
        self.assertEqual(restored.spatial.layers[0].signal_id, restored.image_signal_id)
        self.assertEqual(restored.spatial.layers[0].opacity, 0.3)
        self.assertEqual(restored.spatial.screen, "volume")
        for layers in [
            [dict(signal_id="unregistered")],
            [dict(signal_id=sid, opacity=2)],
            [dict(signal_id=sid), dict(signal_id=sid)],
        ]:
            with self.assertRaises(ValueError):
                self.configure(layers=layers)
        with patch.object(
            self.s.repository, "read", wraps=self.s.repository.read
        ) as reader:
            self.s.volumes.snapshot("a", a.id)
            before = reader.call_count
            self.configure(frame_stretch=2)
            self.s.volumes.snapshot("a", a.id)
            self.assertEqual(reader.call_count, before)
        self.assertEqual(fresh.spatial.layers, ())

    def test_admission_failure_releases_reservations(self):
        from tofscope.application.analyses import CapacityError

        self.configure(layers=[dict(signal_id=self.a.image_signal_id)])
        budget = self.s.cache.budget
        before = (budget.physical_bytes, budget.users["a"])
        with patch.object(
            self.s.volumes,
            "preparation_bytes",
            return_value=self.settings.global_bytes + 1,
        ):
            with self.assertRaises(CapacityError):
                self.s.volumes.snapshot("a", self.a.id)
        self.assertEqual((budget.physical_bytes, budget.users["a"]), before)

    def test_removed_signal_prunes_spatial_state_and_stale_source_rejects_data(self):
        a = self.command(dict(type="add_stored_signal", index=0))
        sid = a.signals[-1].id
        self.configure(layers=[dict(signal_id=sid)], solo=sid)
        a = self.command(dict(type="remove_signal", signal_id=sid))
        self.assertEqual(a.spatial.layers, ())
        self.assertIsNone(a.spatial.solo)
        self.configure(layers=[dict(signal_id=a.image_signal_id)])
        (self.settings.data_root / "a.h5").touch()
        with self.assertRaises(ValueError):
            self.s.volumes.snapshot("a", a.id)

    def test_spatial_api_owner_checks_transport_and_strict_commands(self):
        from fastapi.testclient import TestClient
        from tofscope.api.app import create_app

        settings = replace(
            self.settings,
            mode="proxy",
            trusted_proxies=("testclient",),
            public_origin="http://testserver",
        )
        with TestClient(create_app(settings)) as c:
            headers = {"x-tofscope-user": "a", "Origin": "http://testserver"}
            a = c.post(
                "/api/v1/analyses", headers=headers, json={"relative_path": "a.h5"}
            ).json()
            route = f"/api/v1/analyses/{a['id']}"
            spatial = dict(
                layers=[dict(signal_id=a["image_signal_id"])], screen="volume"
            )
            r = c.post(
                route + "/commands",
                headers=headers,
                json=dict(
                    request_id="spatial",
                    expected_revision=a["revision"],
                    dataset_generation=a["dataset"]["generation"],
                    command=dict(type="set_spatial", spatial=spatial),
                ),
            )
            self.assertEqual(r.status_code, 200, r.text)
            r = c.get(route + "/volumes", headers=headers)
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json()["total_voxels"], 6)
            self.assertEqual(
                c.get(
                    route + "/volumes", headers={"x-tofscope-user": "other"}
                ).status_code,
                404,
            )
            self.assertEqual(c.get(route + "/volumes").status_code, 401)

    def test_pending_signal_before_ready_layer_does_not_break_source_lookup(self):
        from tofscope.application.models import SignalSnapshot

        a = self.command(dict(type="add_stored_signal", index=0))
        sid = a.signals[-1].id
        pending = SignalSnapshot("pending", "Calculating", 99, None)
        e = self.s.analyses.entry("a", a.id)
        e.snapshot = replace(a, signals=(a.signals[0], pending, a.signals[1]))
        self.configure(layers=[dict(signal_id=sid)])
        result = self.s.volumes.snapshot("a", a.id)
        self.assertEqual(result.layers[0].values, [0, 1, 2, 3, 4, 5])

    def test_transport_holds_preparation_admission_through_serialization(self):
        from contextlib import ExitStack

        self.configure(layers=[dict(signal_id=self.a.image_signal_id)])
        budget = self.s.cache.budget
        before = budget.analyses[self.a.id]
        with ExitStack() as preparation:
            payload = self.s.volumes.snapshot("a", self.a.id, preparation=preparation)
            self.assertGreater(budget.analyses[self.a.id], before)
            json.dumps(payload.to_dict(), allow_nan=False)
        self.assertEqual(budget.analyses[self.a.id], before)
