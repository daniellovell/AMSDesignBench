## SKY130 PDK Setup and Gm/ID Table Generation

This guide explains how to install the actual SKY130 PDK models and generate real Gm/ID lookup tables.

---

## Quick Start

```bash
# 1. Install SKY130 PDK (one-time, ~10 minutes)
cd /Users/kesvis/justbedaniel_2/AMSDesignBench/pdk/skywater130
./install_pdk.sh

# 2. Test the installation
cd models
ngspice -b test_sky130.sp

# 3. Generate Gm/ID tables (~5-10 minutes)
cd ../gm_id_tables
python generate_gmid_tables_sky130.py
```

---

## Detailed Instructions

### A) Install the PDK Models (via open_pdks)

The `install_pdk.sh` script automates the installation process:

```bash
cd /Users/kesvis/justbedaniel_2/AMSDesignBench/pdk/skywater130
./install_pdk.sh
```

This will:
1. Clone the open_pdks repository
2. Configure with SKY130 enabled
3. Build the PDK
4. Install to `/usr/local/share/pdk/sky130A/`

**Manual Installation (if script fails):**

```bash
# Prerequisites
# macOS: Xcode command line tools should be installed
xcode-select --install

# Clone and build
cd /tmp
git clone --depth 1 https://github.com/RTimothyEdwards/open_pdks.git
cd open_pdks
./configure --enable-sky130-pdk --prefix=/usr/local
make -j$(sysctl -n hw.ncpu)
sudo make install
```

**Installation Path:**
- PDK root: `/usr/local/share/pdk/sky130A/`
- ngspice models: `/usr/local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice`

---

### B) Test the Installation

A test netlist is provided to verify the PDK works:

```bash
cd models
ngspice -b test_sky130.sp
```

Expected output:
- Should complete without errors
- Creates `gmId_nm.csv` with VGS, ID, gm, gds data

**If you see errors:**

1. **Path wrong?** Verify the PDK file exists:
   ```bash
   ls /usr/local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice
   ```

2. **Different install prefix?** Update the `.lib` path in `test_sky130.sp`

3. **Device handle errors?** The script uses `@m.xmn.msky130_fd_pr__nfet_01v8[...]` which is the correct handle for SKY130 subcircuits.

---

### C) Generate Gm/ID Lookup Tables

Once the PDK is installed, generate comprehensive Gm/ID tables:

```bash
cd gm_id_tables
python generate_gmid_tables_sky130.py
```

**Options:**

```bash
# Generate for specific corner
python generate_gmid_tables_sky130.py --corner tt   # typical (default)
python generate_gmid_tables_sky130.py --corner ff   # fast
python generate_gmid_tables_sky130.py --corner ss   # slow

# Custom PDK path
python generate_gmid_tables_sky130.py --pdk-path /custom/path/sky130.lib.spice

# Custom output directory
python generate_gmid_tables_sky130.py --output-dir /path/to/output
```

**What it does:**
1. Sweeps VGS from 0 to 1.8V (NMOS) or 0 to -1.8V (PMOS)
2. Sweeps VDS at multiple bias points (0.3V to 1.8V)
3. Characterizes 6 channel lengths: 150nm, 200nm, 300nm, 500nm, 1µm, 2µm
4. Extracts: ID, gm, gds, Vth, Vdsat, Gm/ID, ft, gm/gds
5. Saves to JSON files: `nfet_gmid_lut_tt.json`, `pfet_gmid_lut_tt.json`

**Time:** ~5-10 minutes total (depends on your CPU)

**Output files:**
```
gm_id_tables/
├── nfet_gmid_lut_tt.json    # NMOS typical corner
├── pfet_gmid_lut_tt.json    # PMOS typical corner
├── nfet_gmid_lut.json       # Symlink to tt (default)
└── pfet_gmid_lut.json       # Symlink to tt (default)
```

---

## SKY130 Device Information

### Common Device Names

```spice
* NMOS (1.8V core device)
XMN d g s b sky130_fd_pr__nfet_01v8 L=0.5u W=1u nf=1

* PMOS (1.8V core device)
XMP d g s b sky130_fd_pr__pfet_01v8 L=0.5u W=1u nf=1
```

**Other variants available:**
- `sky130_fd_pr__nfet_01v8_lvt` - Low Vth NMOS
- `sky130_fd_pr__pfet_01v8_lvt` - Low Vth PMOS  
- `sky130_fd_pr__nfet_01v8_hvt` - High Vth NMOS
- `sky130_fd_pr__pfet_01v8_hvt` - High Vth PMOS
- `sky130_fd_pr__nfet_g5v0d10v5` - 5V/10.5V NMOS
- `sky130_fd_pr__pfet_g5v0d10v5` - 5V/10.5V PMOS

### Typical Parameters (tt corner, 27°C)

| Parameter | NMOS | PMOS |
|-----------|------|------|
| Min L | 150nm | 150nm |
| Vth (1.8V devices) | ~0.4V | ~-0.4V |
| Supply | 1.8V | 1.8V |
| Max VDS | 1.95V | -1.95V |
| Max VGS | 2.0V | -2.0V |

### Process Corners

Select corner via the `.lib` directive:

```spice
.lib /usr/local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice tt
*.lib ... ff  (fast-fast)
*.lib ... ss  (slow-slow)
*.lib ... sf  (slow-fast) 
*.lib ... fs  (fast-slow)
```

**Corner characteristics:**
- **tt** (typical-typical): Nominal process
- **ff** (fast-fast): Fastest transistors, lowest Vth
- **ss** (slow-slow): Slowest transistors, highest Vth
- **sf/fs**: Mixed corners for worst-case analysis

---

## Using the Models in Netlists

### Basic Template

```spice
* Your circuit name
.lib /usr/local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice tt
.temp 27
.option numdgt=7

* Supply
VDD vdd 0 DC 1.8

* Your transistors (L/W in meters!)
XM1 d1 g1 s1 b1 sky130_fd_pr__nfet_01v8 L=0.5u W=10u nf=1
XM2 d2 g2 s2 b2 sky130_fd_pr__pfet_01v8 L=0.5u W=20u nf=1

* Analysis
.dc ...
.ac ...
.tran ...

.control
run
plot ...
.endc

.end
```

### Key Points

1. **Units**: L and W are in **meters** in ngspice
   - `L=0.5u` = 500nm
   - `W=10u` = 10µm

2. **Subcircuits**: SKY130 devices are subcircuits, not primitives
   - Use `X` prefix for instances
   - Must use exact subcircuit names

3. **Device handles**: Access internal parameters with
   ```
   @m.x<inst>.m<subckt_name>[param]
   ```
   Example: `@m.xm1.msky130_fd_pr__nfet_01v8[gm]`

4. **Temperature**: Set with `.temp 27` (Celsius)

---

## Verifying Generated Tables

Check that tables were generated correctly:

```python
import json

# Load NMOS table
with open('nfet_gmid_lut_tt.json', 'r') as f:
    nmos = json.load(f)

print(f"Device: {nmos['device_type']}")
print(f"Corner: {nmos['corner']}")
print(f"L values: {nmos['L_values']}")
print(f"Data keys: {list(nmos['data'].keys())}")

# Check one L value
L_500nm = nmos['data']['L_5e-07']
print(f"\nL=500nm data points: {len(L_500nm['vgs'])}")
print(f"VGS range: {min(L_500nm['vgs']):.2f} to {max(L_500nm['vgs']):.2f} V")
print(f"Gm/ID range: {min(L_500nm['gmid']):.1f} to {max(L_500nm['gmid']):.1f} S/A")
```

**Expected output:**
- Device: nfet
- Corner: tt
- 6 L values (150nm to 2µm)
- ~300-600 data points per L
- VGS: 0 to 1.8V
- Gm/ID: ~4 to 28 S/A (higher for longer L)

---

## Troubleshooting

### Installation Issues

**Error: "configure: command not found"**
- Make sure you're in the `open_pdks` directory
- Try: `./configure --enable-sky130-pdk`

**Error: "make: command not found"**
- Install Xcode command line tools: `xcode-select --install`

**Error: "Permission denied" during make install**
- Use `sudo make install` (will prompt for password)

### Simulation Issues

**Error: "Can't find file sky130.lib.spice"**
- Verify PDK path: `ls /usr/local/share/pdk/sky130A/libs.tech/ngspice/`
- Update path in netlist if installed to different location

**Error: "Unknown subckt sky130_fd_pr__nfet_01v8"**
- PDK may not be fully installed
- Check `.lib` line includes corner: `.lib ... tt`

**Error: "@m.xm1... not found"**
- Device handle depends on instance name and subcircuit name
- Run `.op` first and check output for actual handle names

### Table Generation Issues

**Error: "No valid data points"**
- Check simulation output for convergence errors
- Try narrower VGS/VDS ranges
- Verify PDK is correctly installed

**Tables seem incorrect**
- Compare with test_sky130.sp output
- Check corner is correct (tt/ff/ss)
- Verify ngspice version (>= 34 recommended)

---

## Next Steps

After generating tables:

1. **Test the design system:**
   ```bash
   cd /Users/kesvis/justbedaniel_2/AMSDesignBench
   python scripts/design_smoke_test.py
   ```

2. **Run design evaluation:**
   ```bash
   python harness/run_design_eval.py --model openai:gpt-4o-mini --designs ota001
   ```

3. **Generate tables for other corners (optional):**
   ```bash
   cd pdk/skywater130/gm_id_tables
   python generate_gmid_tables_sky130.py --corner ff
   python generate_gmid_tables_sky130.py --corner ss
   ```

---

## References

- **SKY130 PDK**: https://github.com/google/skywater-pdk
- **open_pdks**: https://github.com/RTimothyEdwards/open_pdks
- **ngspice**: http://ngspice.sourceforge.net/
- **Gm/ID methodology**: B. Murmann, "Systematic Design of Analog CMOS Circuits"

---

## Support

If you encounter issues:

1. Check this README's troubleshooting section
2. Verify ngspice works: `ngspice --version`
3. Test with `test_sky130.sp` before generating full tables
4. Check PDK installation: `ls /usr/local/share/pdk/sky130A/`

For design verification questions, see the main documentation:
- [DESIGN_VERIFICATION_README.md](../../DESIGN_VERIFICATION_README.md)
- [QUICKSTART_DESIGN.md](../../QUICKSTART_DESIGN.md)

