"""Captured atomic assignments and isotope measurement provenance."""
from dataclasses import dataclass
import json
import math
import re
from tofscope.science.isotopes import IsotopeRecord, IonCandidate, ion_mz
from tofscope.science.abundance import IsotopeMeasurement


@dataclass(frozen=True)
class CatalogProvenance:
    records_sha256: str
    retrieved: str
    sources_json: str
    convention: str = 'Neutral isotope mass minus signed electron mass; binding energies omitted.'

    def __post_init__(self):
        if not re.fullmatch(r'[0-9a-f]{64}', self.records_sha256) or not self.retrieved or not self.convention:
            raise ValueError('Incomplete catalog provenance.')
        if not json.loads(self.sources_json):
            raise ValueError('Missing catalog sources.')


@dataclass(frozen=True)
class AtomicAssignment:
    candidate_id: str
    isotope: IsotopeRecord
    charge: int
    predicted_mz: float
    catalog: CatalogProvenance
    measured_mz: float | None = None
    error_Th: float | None = None
    error_ppm: float | None = None

    def __post_init__(self):
        expected = ion_mz(self.isotope, self.charge)
        identity = f'{self.isotope.symbol}-{self.isotope.mass_number}:{self.charge:+d}'
        if self.candidate_id != identity or not math.isclose(self.predicted_mz, expected, rel_tol=1e-12):
            raise ValueError('Inconsistent atomic assignment.')
        if self.measured_mz is None:
            if self.error_Th is not None or self.error_ppm is not None:
                raise ValueError('Mass errors require a measured mass.')
        elif (not math.isfinite(self.measured_mz) or self.measured_mz <= 0 or
              self.error_Th is None or self.error_ppm is None or
              not math.isclose(self.error_Th, self.measured_mz - expected, abs_tol=1e-12) or
              not math.isclose(self.error_ppm, (self.measured_mz - expected) / expected * 1e6, abs_tol=1e-9)):
            raise ValueError('Inconsistent measured mass error.')


@dataclass(frozen=True)
class CandidateResult:
    candidates: tuple[IonCandidate, ...]
    catalog: CatalogProvenance


@dataclass(frozen=True)
class MeasuredSignal:
    signal_id: str
    name: str
    assignment: AtomicAssignment | None
    intervals: tuple[tuple[float, float], ...]
    measurement: IsotopeMeasurement


@dataclass(frozen=True)
class MeasurementResult:
    job_id: str
    dataset_generation: str
    roi: tuple[int, int, int, int]
    frames: tuple[int, int]
    dependency_key: str
    rows: tuple[MeasuredSignal, ...]
    catalog: CatalogProvenance
    out_of_date: bool = False
    interpretation: str = 'Selected-set signal fractions; not quantitative composition.'
