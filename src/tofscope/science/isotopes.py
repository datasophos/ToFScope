"""Offline atomic-isotope candidates with explicit charge and provenance."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import math
import re

ELECTRON_MASS_U=0.0005485799090441  # CODATA2022, NIST electron mass in u.
from importlib.resources import files
CATALOG_PATH=files('tofscope.resources').joinpath('reference/isotopes.json')


@dataclass(frozen=True)
class IsotopeRecord:
    symbol: str
    mass_number: int
    neutral_mass_u: float
    abundance_low: float | None
    abundance_high: float | None
    source_id: str
    mass_uncertainty_u: float | None = None
    mass_estimated: bool = False
    abundance_uncertainty: float | None = None

    def __post_init__(self):
        if not re.fullmatch(r'[A-Z][a-z]{0,2}',self.symbol) or type(self.mass_number) is not int or self.mass_number<1:
            raise ValueError('Invalid isotope identity.')
        if not math.isfinite(self.neutral_mass_u) or self.neutral_mass_u<=0 or not self.source_id:
            raise ValueError('Invalid isotope mass or source.')
        lo,hi=self.abundance_low,self.abundance_high
        if (lo is None)!=(hi is None) or (lo is not None and not (math.isfinite(lo) and math.isfinite(hi) and 0<=lo<=hi<=1)):
            raise ValueError('Invalid reference abundance interval.')
        for value in (self.mass_uncertainty_u,self.abundance_uncertainty):
            if value is not None and (not math.isfinite(value) or value<0):raise ValueError('Invalid reference uncertainty.')


@dataclass(frozen=True)
class IonCandidate:
    isotope: IsotopeRecord
    charge: int
    predicted_mz: float
    error_Th: float
    error_ppm: float

    @property
    def id(self):return f'{self.isotope.symbol}-{self.isotope.mass_number}:{self.charge:+d}'


def ion_mz(record,charge: int):
    if type(charge) is not int or charge not in (-3,-2,-1,1,2,3):raise ValueError('Atomic charge must be ±1, ±2 or ±3.')
    return (record.neutral_mass_u-charge*ELECTRON_MASS_U)/abs(charge)


def find_candidates(mz,tolerance,tolerance_unit,charges,catalog):
    if not math.isfinite(mz) or mz<=0:raise ValueError('Measured m/z must be positive and finite.')
    if not math.isfinite(tolerance) or tolerance<0:raise ValueError('Tolerance must be finite and nonnegative.')
    if tolerance_unit not in ('Th','ppm'):raise ValueError('Tolerance units must be Th or ppm.')
    if not charges:raise ValueError('Select at least one charge state.')
    for charge in charges:
        if type(charge) is not int or charge not in (-3,-2,-1,1,2,3):raise ValueError('Atomic charge must be ±1, ±2 or ±3.')
    candidates=[]
    for isotope in catalog:
        for charge in sorted(set(charges)):
            predicted=ion_mz(isotope,charge);error=mz-predicted;ppm=error/predicted*1e6
            if abs(error if tolerance_unit=='Th' else ppm)<=tolerance:
                candidates.append(IonCandidate(isotope,charge,predicted,error,ppm))
    return sorted(candidates,key=lambda r:(abs(r.error_Th),r.isotope.symbol,r.isotope.mass_number,r.charge))


def records_checksum(records):
    return hashlib.sha256(json.dumps(records,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def load_catalog(path=None):
    data=json.loads(Path(path or CATALOG_PATH).read_text())
    meta=data['metadata'];records=data['isotopes']
    if meta.get('schema_version')!=1 or not meta.get('sources') or not meta.get('retrieved') or not meta.get('redistribution_review'):
        raise ValueError('Reference provenance is incomplete.')
    if records_checksum(records)!=meta['records_sha256']:raise ValueError('Isotope reference checksum mismatch.')
    result=tuple(IsotopeRecord(**row) for row in records)
    keys=[(r.symbol,r.mass_number) for r in result]
    if len(set(keys))!=len(keys):raise ValueError('Duplicate isotope reference identity.')
    return result
