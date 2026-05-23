# CALPHAD TDB files — provenance

All TDB files in this directory are **open-source** or public-domain. They are
bundled verbatim (no modifications) and are sourced from the pycalphad test
suite, which ships them under the BSD-3-Clause licence that covers the pycalphad
package as a whole.

| File | System | Original source |
|---|---|---|
| `cost507_al_alloys.tdb` | Al-Cu-Fe-Mg-Mn-Si-Zn-Cr-Ti-Ni-Mo-... (27-element) | COST507 scientific project (EU), Dinsdale et al. 1998, hosted in pycalphad |
| `mc_fecocrnbti_steels.tdb` | Fe-Co-Cr-Ni-Ti-Nb-Mo-Si-C... | MatCalc open database mc_fecocrnbti, hosted in pycalphad |
| `cfe_binary.tdb` | C-Fe binary | Broshe et al. (reference C-Fe assessment) |
| `alcocrni_nibase.tdb` | Al-Co-Cr-Ni quaternary | Open assessment, pycalphad test suite |
| `alcrni_nibase.tdb` | Al-Cr-Ni ternary | Open assessment, pycalphad test suite |
| `alzn_binary.tdb` | Al-Zn binary | Mey et al. (reference binary assessment) |
| `alni_binary.tdb` | Al-Ni binary | Dupin et al. 2001 |

## Coverage

| System | TDB used | Notes |
|---|---|---|
| Al-alloys (1xxx–8xxx) | `cost507_al_alloys.tdb` | 27-element; covers most commercial Al alloys |
| Austenitic / ferritic steel | `mc_fecocrnbti_steels.tdb` | Fe-Cr-Ni-C-Mn-Mo-Si |
| Ni superalloys | `mc_fecocrnbti_steels.tdb` | Ni-Cr-Co-Al-Ti-Nb |
| C-Fe binary | `cfe_binary.tdb` | Iron-carbon phase diagram |
| 7xxx Al-Zn | `cost507_al_alloys.tdb` (preferred) | Falls back to `alzn_binary.tdb` |

## Extending with commercial TDBs

Drop any `.tdb` file into this directory and register it in
`apps/api/ml/calphad/databases.py` under `_USER_REGISTRY`. Commercial TDBs
(TCAL, TCFE, TCNi, TCTi from Thermo-Calc; PanAl, PanFe from CompuTherm) will
be picked up automatically if the element coverage is better than the bundled
open-source databases.
