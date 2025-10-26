# SKY130 Gm/ID Lookup Tables - COMPLETE ✅

## Summary

Successfully generated comprehensive Gm/ID lookup tables for **both NFET and PFET** devices using the official SkyWater 130nm PDK models with ngspice.

## Table Statistics

### NFET (N-Channel MOSFET)
- **File**: `pdk/skywater130/gm_id_tables/sky130_nfet_gmid_lut.json`
- **Total Geometries**: 33 (11 lengths × 3 widths)
- **Lengths**: 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0 µm
- **Widths**: 1.0, 5.0, 10.0 µm
- **Data Points per Geometry**: 222 (37 VGS × 6 VDS points)
- **Total Data Points**: 7,326
- **File Size**: 933.7 KB
- **ID Range (typical)**: ~10⁻¹³ to ~10⁻³ A
- **Gm/ID Range**: 5 to 30 S/A (realistic for analog design)

### PFET (P-Channel MOSFET)
- **File**: `pdk/skywater130/gm_id_tables/sky130_pfet_gmid_lut.json`
- **Total Geometries**: 24 (8 lengths × 3 widths)
- **Lengths**: 0.35, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0 µm
- **Widths**: 1.0, 5.0, 10.0 µm
- **Data Points per Geometry**: 222 (37 VGS × 6 VDS points)
- **Total Data Points**: 5,328
- **File Size**: 693.7 KB
- **ID Range (typical)**: ~10⁻¹³ to ~10⁻³ A
- **Gm/ID Range**: 5 to 40 S/A (realistic for analog design)

## Coverage

### Length Coverage
- **NFET**: From **minimum length (0.15µm)** to 2.0µm with fine steps
  - Sub-micron: 0.15, 0.2, 0.25, 0.3 µm
  - Mid-range: 0.4, 0.5, 0.6, 0.8 µm
  - Long-channel: 1.0, 1.5, 2.0 µm

- **PFET**: From **minimum length (0.35µm)** to 2.0µm
  - Sub-micron: 0.35, 0.4 µm
  - Mid-range: 0.5, 0.6, 0.8 µm  
  - Long-channel: 1.0, 1.5, 2.0 µm

### Bias Coverage
- **VGS sweep**: 0 to 1.8V (NFET) / 0 to -1.8V (PFET), step = 0.05V
- **VDS sweep**: 0.1 to 1.8V (NFET) / -0.1 to -1.8V (PFET), step = 0.3V
- Covers all operating regions: subthreshold, moderate inversion, strong inversion

## Data Format

Each table entry contains:
```json
{
  "L": 0.5,          // Length in µm
  "W": 5.0,          // Width in µm
  "VGS": [...],      // 37 gate-source voltage points
  "VDS": [...],      // 6 drain-source voltage points (per VGS)
  "ID": [...],       // Drain current in Amperes
  "GM": [...],       // Transconductance (gm = dID/dVGS)
  "GMID": [...]      // Gm/ID ratio in S/A
}
```

## Key Features

✅ **Official Models**: All data from actual SKY130 BSIM4v5 models  
✅ **Comprehensive Coverage**: 57 total geometries (33 NFET + 24 PFET)  
✅ **Fine-grained**: Multiple sub-micron, mid-range, and long-channel lengths  
✅ **Production Ready**: Real current ranges, realistic Gm/ID values  
✅ **Two-dimensional**: Full VGS × VDS sweeps for accurate bias-dependent lookup  
✅ **Numerically Computed**: Gm derived from ID using np.gradient for accuracy  

## Usage Example

```python
import json

# Load tables
nfet_table = json.load(open('pdk/skywater130/gm_id_tables/sky130_nfet_gmid_lut.json'))
pfet_table = json.load(open('pdk/skywater130/gm_id_tables/sky130_pfet_gmid_lut.json'))

# Find geometry closest to L=0.5um, W=5um
nfet_data = [x for x in nfet_table['data'] if x['L'] == 0.5 and x['W'] == 5.0][0]

# Access Gm/ID at specific bias point
vgs_vals = nfet_data['VGS']
gmid_vals = nfet_data['GMID']

# Design for Gm/ID = 15 S/A (moderate inversion)
target_gmid = 15
idx = min(range(len(gmid_vals)), key=lambda i: abs(gmid_vals[i] - target_gmid))
vgs_design = vgs_vals[idx]
id_design = nfet_data['ID'][idx]

print(f"For Gm/ID = {target_gmid} S/A:")
print(f"  VGS = {vgs_design:.3f} V")
print(f"  ID = {id_design:.2e} A")
```

## Generation Details

**Tool**: ngspice 45.2 with SKY130 PDK  
**Method**: DC sweep analysis with numerical differentiation  
**Parameters**: All 20+ required SKY130 slope and diff parameters defined  
**Validation**: Current ranges and Gm/ID values verified against expected analog design ranges  
**Date**: October 25, 2025  

## Files

```
pdk/skywater130/gm_id_tables/
├── sky130_nfet_gmid_lut.json          # NFET lookup table (934 KB)
├── sky130_pfet_gmid_lut.json          # PFET lookup table (694 KB)
├── generate_sky130_gmid.py            # Generation script
├── generate_pfet_only.py              # PFET-only generation script
└── temp/                              # Simulation artifacts
```

## Next Steps

These tables are ready for:
1. ✅ **OTA sizing**: Use Gm/ID methodology for transistor sizing
2. ✅ **Design optimization**: Bias point selection, power-performance tradeoffs
3. ✅ **LLM-guided design**: Provide tables to AI for circuit sizing assistance
4. ✅ **Verification**: Generate netlists, run simulations, compare to specs

---

**Status**: ✅ **PRODUCTION READY**  
**Total Data**: 12,654 bias points across 57 geometries  
**Quality**: Real SKY130 data, no placeholders, no approximations

