# Offline atomic-isotope reference

`isotopes.json` contains 3,352 neutral isotope masses extracted from the
user-supplied `NIST_abundances.html`, combined with CIAAW's 2024 reference
abundances. The app reads only the JSON; saved HTML and its scripts are never
loaded into the application. App startup performs no network requests.

Sources:

- [NIST Atomic Weights and Isotopic Compositions](https://www.nist.gov/pml/atomic-weights-and-isotopic-compositions-relative-atomic-masses), January 2015 database; isotope masses from AME2012. Retain quoted mass uncertainties and the `#` estimated-mass indicator.
- [CIAAW Isotopic Compositions of the Elements 2024](https://ciaaw.org/isotopic-abundances.htm). Interval endpoints remain intervals; a single representative abundance retains its published uncertainty. Missing values remain null. The newer CIAAW values replace the older compositions included in the saved NIST table.
- [CODATA 2022 electron mass in u](https://physics.nist.gov/cgi-bin/cuu/Value?meu%7Csearch_for=electron-neutron): 0.0005485799090441 u.

The JSON metadata records retrieval date, source-file SHA256 values, reference
revisions, a checksum of the normalized numerical records, and the redistribution
review. These are attributed factual numerical values, with no copied source
scripts, artwork or prose; no open-license claim is made for CIAAW's collection.
The original saved HTML remains untouched outside the bundled reference.

Ionic mass convention: `m/z = (neutral_mass_u - signed_charge * electron_mass_u)
/ abs(signed_charge)`. Positive ions lose electrons, negative ions gain them.
Electronic binding/ionization-energy mass corrections are omitted. These are
atomic-ion suggestions for charges ±1–3, not molecular identifications or
confidence probabilities. Estimated masses remain explicitly marked.

Rebuild manually from saved official source pages:

```sh
uv run python scripts/update_isotope_reference.py --nist NIST_abundances.html --ciaaw /path/to/ciaaw-isotopic-abundances.html
```

NIST's source is linearized ASCII within HTML `<pre>`. The CIAAW importer
handles the published page's implicit row/cell closures; malformed numeric
records fail validation. Before replacing a catalog, review source changes and
run `tests/test_isotopes.py`. Exact isotope masses, standard atomic weights,
and nominal masses are distinct quantities.
