"""Original-intensity isotope areas, with explicit coverage and ambiguity."""
from dataclasses import dataclass,replace
import numpy as np
from contextlib import nullcontext
from tofscope.science.signals import read_signal


@dataclass(frozen=True)
class IsotopeMeasurement:
    recipe_id: str
    requested_frames: tuple[int,int]
    actual_frames: tuple[int,int] | None
    summed_intensity: float | None
    observed_fraction: float | None
    ambiguous: bool
    status: str


def measure_isotopes(path,recipes,roi,frames,*,reader=None):
    recipes=tuple(recipes)
    if not recipes:raise ValueError('Choose at least one isotope window.')
    if len(frames)!=2 or any(type(z) is not int for z in frames) or not 0<=frames[0]<=frames[1]:raise ValueError('Invalid measurement frame limits.')
    if len(roi)!=4 or any(type(z) is not int for z in roi) or not (0<=roi[0]<=roi[1] and 0<=roi[2]<=roi[3]):raise ValueError('Invalid measurement ROI.')
    first=max(frames[0],*(r.frames[0] for r in recipes));last=min(frames[1],*(r.frames[1] for r in recipes))
    ambiguous=set()
    for i,a in enumerate(recipes):
        for j,b in enumerate(recipes[:i]):
            if any(max(x0,y0)<=min(x1,y1) for x0,x1 in a.intervals for y0,y1 in b.intervals):ambiguous.update((i,j))
    if first>last:
        return [IsotopeMeasurement(r.id,tuple(frames),None,None,None,i in ambiguous,'No common frame coverage') for i,r in enumerate(recipes)]
    rows=[];x0,x1,y0,y1=roi
    for i,recipe in enumerate(recipes):
        with reader(path,recipe) if reader else nullcontext(read_signal(path,recipe)) as source:
            data = source.array if reader else source
            if x1>=data.shape[2] or y1>=data.shape[1]:raise ValueError('Measurement ROI is outside the acquisition.')
            area=float(data[first-recipe.frames[0]:last-recipe.frames[0]+1,y0:y1+1,x0:x1+1].sum(dtype=np.float64))
        status='Overlapping mass windows' if i in ambiguous else 'Ambiguous selected set' if ambiguous else 'Common frame coverage' if (first,last)!=tuple(frames) else 'Measured'
        rows.append(IsotopeMeasurement(recipe.id,tuple(frames),(first,last),area,None,i in ambiguous,status))
    total=sum(r.summed_intensity for r in rows)
    if not ambiguous and np.isfinite(total) and total>0:
        rows=[replace(r,observed_fraction=r.summed_intensity/total) for r in rows]
    return rows
