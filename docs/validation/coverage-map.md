# Prototype assertion disposition

The frozen reference ran 87 tests. Migrated scientific/storage suites execute in
the replacement without widgets or Python Plotly. This table accounts for every
method in archived mixed UI/figure files; it does not claim deferred UI cases
run in the pilot. Exact old code is retained as text so no unsupported feature
can disappear silently. Current numerical cases assert exact custom union,
normalization, ROI rounding (including ties), SE means/absence, front XZ sums,
partial comparison coverage and display-invariant exports.

| Original assertion | Replacement or explicit completion owner |
| --- | --- |
| `test_calibrated_profiles.py.txt:test_profile_preserves_intensities_and_absolute_frames` | test_depth_application: partial/nonzero-domain presenter profiles preserve exact means and original frame IDs; calibration.spec.ts covers unit/navigation behavior. |
| `test_calibrated_profiles.py.txt:test_one_calibrated_sample_is_visible` | test_depth_application single-sample presenter assertions; calibration.spec.ts single/empty domain workflow; renderer shows a marker for one known sample. |
| `test_calibrated_profiles.py.txt:test_controller_export_partial_depth_and_anchor_validation` | test_depth_application partial CSV blanks, units, fixed-origin validation, removal and saved/legacy documents; test_api calibration command/owner checks. |
| `test_calibrated_views.py.txt:test_sections_and_front_keep_values_and_original_frames` | test_depth_application nonzero-domain front values/frame IDs restored for Explore; section assertions remain Task 3. |
| `test_calibrated_views.py.txt:test_volume_pooling_averages_physical_coordinates_across_anchor_kinks` | test_depth_application block means across anchor kinks and test_volume_layers preserve numerical geometry; volume renderer remains Task 4. |
| `test_calibrated_views.py.txt:test_volume_omits_unknown_frames_before_pooling` | test_volume_layers retains clipping before pooling; volume renderer remains Task 4. |
| `test_calibrated_views.py.txt:test_single_calibrated_plane_does_not_claim_known_thickness` | Single/empty Explore sample handling covered by test_depth_application/calibration.spec.ts; spatial thickness/aspect assertions remain Task 4. |
| `test_calibrated_views.py.txt:test_layered_previews_clip_and_use_common_physical_depth` | Core layered-preview assertions remain test_volume_layers; layered renderer assertions remain Task 4. |
| `test_calibrated_views.py.txt:test_controller_updates_all_views_and_physical_markers` | test_depth_application and calibration.spec.ts cover Explore front/profile updates, original-frame markers, units and removal; sections/volume remain Tasks 3/4. |
| `test_comparisons.py.txt:test_add_many_remove_individually_and_preserve_primary` | test_explore_data/test_jobs/test_signal_recipes and Explore Playwright; original values, ROI and missing comparison coverage. |
| `test_comparisons.py.txt:test_custom_partial_frames_align_and_recompute_for_roi` | test_explore_data/test_jobs/test_signal_recipes and Explore Playwright; original values, ROI and missing comparison coverage. |
| `test_comparisons.py.txt:test_profiles_normalize_independently_without_changing_arrays` | test_explore_data/test_jobs/test_signal_recipes and Explore Playwright; original values, ROI and missing comparison coverage. |
| `test_comparisons.py.txt:test_same_mass_different_frame_ranges_have_unique_names_and_csv_columns` | test_explore_data/test_jobs/test_signal_recipes and Explore Playwright; original values, ROI and missing comparison coverage. |
| `test_comparisons.py.txt:test_one_frame_comparison_has_a_visible_point` | test_explore_data/test_jobs/test_signal_recipes and Explore Playwright; original values, ROI and missing comparison coverage. |
| `test_comparisons.py.txt:test_front_projection_sums_all_selected_y_rows_and_preserves_depth` | test_explore_data/test_jobs/test_signal_recipes and Explore Playwright; original values, ROI and missing comparison coverage. |
| `test_file_browser.py.txt:test_filter_sort_page_and_hidden_files` | test_file_browser (listing cases); test_acquisition_repository/test_analysis_state/test_api and browser empty/error/open states (controller cases). |
| `test_file_browser.py.txt:test_thousands_never_open_hdf5` | test_file_browser (listing cases); test_acquisition_repository/test_analysis_state/test_api and browser empty/error/open states (controller cases). |
| `test_file_browser.py.txt:test_permissions_and_disappearing_entries` | test_file_browser (listing cases); test_acquisition_repository/test_analysis_state/test_api and browser empty/error/open states (controller cases). |
| `test_file_browser.py.txt:test_unloaded_and_failed_open_preserve_state` | test_file_browser (listing cases); test_acquisition_repository/test_analysis_state/test_api and browser empty/error/open states (controller cases). |
| `test_file_browser.py.txt:test_invalid_peak_metadata_does_not_replace_loaded_state` | test_file_browser (listing cases); test_acquisition_repository/test_analysis_state/test_api and browser empty/error/open states (controller cases). |
| `test_file_browser.py.txt:test_render_failure_preserves_previous_dataset_and_plots` | test_file_browser (listing cases); test_acquisition_repository/test_analysis_state/test_api and browser empty/error/open states (controller cases). |
| `test_interval_editor.py.txt:test_add_select_edit_remove_only_changes_the_target_draft` | selection/gesture Vitest; explore/renderer Playwright; integration union tests. Drafts are now client-local. |
| `test_interval_editor.py.txt:test_rejected_edits_preserve_rows_and_active_signal` | selection/gesture Vitest; explore/renderer Playwright; integration union tests. Drafts are now client-local. |
| `test_interval_editor.py.txt:test_apply_uses_all_rows_and_merges_overlap_only_when_applied` | selection/gesture Vitest; explore/renderer Playwright; integration union tests. Drafts are now client-local. |
| `test_peak_helper.py.txt:test_candidates_annotations_and_empty_matches` | `test_identification_application.py`, `test_identification_api.py`, `identification.spec.ts`; core isotope/abundance math remains in test_isotopes/test_abundance. |
| `test_peak_helper.py.txt:test_annotation_retains_measured_error_and_csv_uncertainty` | `test_identification_application.py`, `test_identification_api.py`, `identification.spec.ts`; core isotope/abundance math remains in test_isotopes/test_abundance. |
| `test_peak_helper.py.txt:test_explicit_measurement_export_and_stale_annotation_rejection` | `test_identification_application.py`, `test_identification_api.py`, `identification.spec.ts`; core isotope/abundance math remains in test_isotopes/test_abundance. |
| `test_server_config.py.txt:test_default_and_explicit_startup` | test_cli/test_acquisition_repository/test_auth/test_api; adjacent example fallback intentionally removed. |
| `test_server_config.py.txt:test_paths_symlinks_and_sibling_prefix` | test_cli/test_acquisition_repository/test_auth/test_api; adjacent example fallback intentionally removed. |
| `test_server_config.py.txt:test_startup_without_adjacent_example_directory` | test_cli/test_acquisition_repository/test_auth/test_api; adjacent example fallback intentionally removed. |
| `test_server_config.py.txt:test_controller_rejects_forged_open_and_preserves_dataset` | test_cli/test_acquisition_repository/test_auth/test_api; adjacent example fallback intentionally removed. |
| `test_signal_recipes.py.txt:test_composite_excludes_gap_and_reads_each_frame_once` | test_explore_data/test_jobs/test_signal_recipes and Explore Playwright; original values, ROI and missing comparison coverage. |
| `test_signal_recipes.py.txt:test_one_interval_matches_existing_integrator_and_never_reads_extra_write` | test_explore_data/test_jobs/test_signal_recipes and Explore Playwright; original values, ROI and missing comparison coverage. |
| `test_signal_recipes.py.txt:test_reader_crops_stored_and_custom_to_absolute_frames` | test_explore_data/test_jobs/test_signal_recipes and Explore Playwright; original values, ROI and missing comparison coverage. |
| `test_signal_recipes.py.txt:test_comparison_missing_on_both_sides_with_nonzero_frame_origin` | test_explore_data/test_jobs/test_signal_recipes and Explore Playwright; original values, ROI and missing comparison coverage. |
| `test_signal_recipes.py.txt:test_invalid_input_and_source_unchanged` | test_explore_data/test_jobs/test_signal_recipes and Explore Playwright; original values, ROI and missing comparison coverage. |
| `test_signal_recipes.py.txt:test_controller_applies_composite_and_exports_every_interval` | test_explore_data/test_jobs/test_signal_recipes and Explore Playwright; original values, ROI and missing comparison coverage. |
| `test_signal_recipes.py.txt:test_comparison_union_and_partial_coverage_survive_primary_switch` | test_explore_data/test_jobs/test_signal_recipes and Explore Playwright; original values, ROI and missing comparison coverage. |
| `test_volume_figures.py.txt:test_overlay_and_tile_styles_and_shared_scale` | Completion Task 4; core volume math remains in test_volume_layers/test_data. |
| `test_volume_figures.py.txt:test_thin_and_zero_selections` | Completion Task 4; core volume math remains in test_volume_layers/test_data. |
| `test_volume_figures.py.txt:test_controller_layers_styles_and_paging` | Completion Task 4; core volume math remains in test_volume_layers/test_data. |
| `test_volume_figures.py.txt:test_tile_pages_bound_scene_count_and_keep_layer_identity` | Completion Task 4; core volume math remains in test_volume_layers/test_data. |
| `test_volume_figures.py.txt:test_single_covered_plane_inside_larger_grid_uses_visible_points` | Completion Task 4; core volume math remains in test_volume_layers/test_data. |
| `test_workspace_writeback.py.txt:test_preview_is_readonly_save_reopens_and_stale_session_rejected` | Completion Task 5; low-level write protection remains in test_dataset_writeback/test_vendor_export/test_integration_store. No pilot write route. |
| `test_workspace_writeback.py.txt:test_readonly_partial_disjoint_and_forged_identity` | Completion Task 5; low-level write protection remains in test_dataset_writeback/test_vendor_export/test_integration_store. No pilot write route. |
| `test_workspace_writeback.py.txt:test_bad_saved_calibration_preserves_active_data_and_recipe` | Completion Task 5; low-level write protection remains in test_dataset_writeback/test_vendor_export/test_integration_store. No pilot write route. |
