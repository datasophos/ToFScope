"""Measurement CSV includes captured numerical scope and reference provenance."""
import csv
import io
import json
from tofscope.application.identification import current_result


def isotope_csv(snapshot):
    result = current_result(snapshot)
    if result is None:
        raise ValueError('Measure isotope signals before exporting.')
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['signal_id', 'name', 'candidate_id', 'charge', 'predicted_mz',
        'measured_mz', 'error_Th', 'error_ppm', 'reference_abundance_low', 'reference_abundance_high', 'mass_uncertainty_u', 'reference_abundance_uncertainty',
        'reference_source_id', 'summed_intensity', 'observed_selected_set_fraction', 'ambiguous', 'status',
        'requested_first', 'requested_last', 'actual_first', 'actual_last', 'roi',
        'intervals_Th', 'dataset_generation', 'out_of_date', 'records_sha256', 'retrieved', 'sources_json', 'interpretation'])
    for row in result.rows:
        a, m = row.assignment, row.measurement
        isotope = a.isotope if a else None
        writer.writerow([row.signal_id, row.name, a.candidate_id if a else '',
            a.charge if a else '', a.predicted_mz if a else '',
            a.measured_mz if a else '', a.error_Th if a else '', a.error_ppm if a else '',
            isotope.abundance_low if isotope else '', isotope.abundance_high if isotope else '',
            isotope.mass_uncertainty_u if isotope else '', isotope.abundance_uncertainty if isotope else '',
            isotope.source_id if isotope else '', m.summed_intensity, m.observed_fraction, m.ambiguous, m.status,
            *m.requested_frames, *(m.actual_frames or ('', '')), json.dumps(result.roi), json.dumps(row.intervals),
            result.dataset_generation, result.out_of_date, result.catalog.records_sha256, result.catalog.retrieved,
            result.catalog.sources_json, result.interpretation])
    return output.getvalue().encode()
