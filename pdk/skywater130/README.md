# SkyWater 130nm PDK for AMSDesignBench

Official SkyWater 130nm Process Design Kit integration for analog circuit design verification.

## Status: ✅ PRODUCTION READY

Both **NFET** and **PFET** Gm/ID lookup tables successfully generated from official SKY130 models.

## Quick Stats

| Device | Geometries | Length Range | Widths | Data Points | File Size |
|--------|------------|--------------|---------|-------------|-----------|
| **NFET** | 33 | 0.15 - 2.0 µm (11 steps) | 1, 5, 10 µm | 7,326 | 934 KB |
| **PFET** | 24 | 0.35 - 2.0 µm (8 steps) | 1, 5, 10 µm | 5,328 | 694 KB |
| **Total** | **57** | Min to 2 µm | 3 widths | **12,654** | **1.6 MB** |

## Files

```
pdk/skywater130/
├── cells/                              # 127 device cells (official PDK)
├── models/                             # Corner files (tt, ff, ss, fs, sf)
├── gm_id_tables/
│   ├── sky130_nfet_gmid_lut.json      # ✅ NFET table (33 geometries)
│   ├── sky130_pfet_gmid_lut.json      # ✅ PFET table (24 geometries)
│   ├── generate_sky130_gmid.py        # Main generation script
│   └── gmid_helper.py                 # Helper functions for querying
├── test_working.sp                     # Verified test deck
└── README.md                           # This file
```

## Length Coverage

### NFET (N-Channel)
- **Minimum**: 0.15 µm
- **Sub-micron**: 0.15, 0.2, 0.25, 0.3 µm
- **Mid-range**: 0.4, 0.5, 0.6, 0.8 µm
- **Long-channel**: 1.0, 1.5, 2.0 µm

### PFET (P-Channel)
- **Minimum**: 0.35 µm
- **Sub-micron**: 0.35, 0.4 µm
- **Mid-range**: 0.5, 0.6, 0.8 µm
- **Long-channel**: 1.0, 1.5, 2.0 µm

## Usage

### Load Tables
```python
import json

nfet = json.load(open('pdk/skywater130/gm_id_tables/sky130_nfet_gmid_lut.json'))
pfet = json.load(open('pdk/skywater130/gm_id_tables/sky130_pfet_gmid_lut.json'))
```

### Design for Target Gm/ID
```python
# Find L=0.5um, W=5um geometry
geom = [x for x in nfet['data'] if x['L'] == 0.5 and x['W'] == 5.0][0]

# Target Gm/ID = 15 S/A (moderate inversion)
target = 15
idx = min(range(len(geom['GMID'])), key=lambda i: abs(geom['GMID'][i] - target))

vgs = geom['VGS'][idx]
id_current = geom['ID'][idx]
gm = geom['GM'][idx]

print(f"VGS = {vgs:.3f}V, ID = {id_current:.2e}A, gm = {gm:.2e}S")
```

## Verification

Test the PDK installation:
```bash
cd /Users/kesvis/justbedaniel_2/AMSDesignBench/pdk/skywater130
ngspice -b test_working.sp
```

Expected output: Successful DC sweep with realistic current values.

## Regenerate Tables

If needed, regenerate the Gm/ID tables:
```bash
cd /Users/kesvis/justbedaniel_2/AMSDesignBench
source ../venv/bin/activate
python3 pdk/skywater130/gm_id_tables/generate_sky130_gmid.py
```

This will take ~10-15 minutes to generate all 57 geometries.

## Dependencies

- **ngspice**: 45.2+ (tested and working)
- **Python**: 3.12+ with numpy, scipy
- **SKY130 PDK**: Included (no external download needed)

## Data Quality

✅ **Official Models**: BSIM4v5 from SkyWater  
✅ **Real Data**: ID ranges from 10⁻¹³ to 10⁻³ A  
✅ **Realistic Gm/ID**: 5-30 S/A for NFET, 5-40 S/A for PFET  
✅ **Full Coverage**: Subthreshold to strong inversion  
✅ **Two-Dimensional**: VGS × VDS sweeps for accurate lookups  

## Documentation

See also:
- `SKY130_PDK_INTEGRATION_COMPLETE.md` - Installation details
- `SKY130_GMID_TABLES_COMPLETE.md` - Comprehensive table documentation
- `README_SKY130.md` - Detailed setup guide

---

**Last Updated**: October 25, 2025  
**PDK Version**: SkyWater 130nm (main branch)  
**Status**: Production Ready for OTA Design Verification
