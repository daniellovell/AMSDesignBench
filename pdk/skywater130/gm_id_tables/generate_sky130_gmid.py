#!/usr/bin/env python3
"""
Generate Gm/ID lookup tables from SKY130 PDK using ngspice.

This script:
1. Creates ngspice test decks for NFET and PFET devices
2. Runs simulations across L, W, VGS, VDS sweeps
3. Parses the raw output files
4. Computes gm numerically from ID data
5. Generates comprehensive Gm/ID lookup tables in JSON format
"""

import subprocess
import struct
import numpy as np
import json
import os
from pathlib import Path

# Get the pdk directory
PDK_DIR = Path(__file__).parent.parent
CELLS_DIR = PDK_DIR / "cells"

def create_spice_deck(device_type, L, W, vgs_start, vgs_end, vgs_step, 
                      vds_start, vds_end, vds_step, output_file):
    """Create a SPICE deck for device characterization."""
    
    if device_type == 'nfet':
        model_path = "nfet_01v8/sky130_fd_pr__nfet_01v8__tt.corner.spice"
        model_name = "sky130_fd_pr__nfet_01v8"
        vdd = vds_end
        param_prefix = "nfet_01v8"
    else:  # pfet
        model_path = "pfet_01v8/sky130_fd_pr__pfet_01v8__tt.corner.spice"
        model_name = "sky130_fd_pr__pfet_01v8"
        vdd = abs(vds_start)
        param_prefix = "pfet_01v8"
    
    spice_content = f"""* SKY130 {device_type.upper()} Gm/ID characterization L={L}u W={W}u
.option scale=1.0u

* Define required slope parameters for {device_type}
.param sky130_fd_pr__{param_prefix}__toxe_slope = 0
.param sky130_fd_pr__{param_prefix}__toxe_slope1 = 0
.param sky130_fd_pr__{param_prefix}__vth0_slope = 0  
.param sky130_fd_pr__{param_prefix}__vth0_slope1 = 0
.param sky130_fd_pr__{param_prefix}__voff_slope = 0
.param sky130_fd_pr__{param_prefix}__voff_slope1 = 0
.param sky130_fd_pr__{param_prefix}__nfactor_slope = 0
.param sky130_fd_pr__{param_prefix}__nfactor_slope1 = 0
.param sky130_fd_pr__{param_prefix}__lint_diff = 0
.param sky130_fd_pr__{param_prefix}__wint_diff = 0
.param sky130_fd_pr__{param_prefix}__wlod_diff = 0
.param sky130_fd_pr__{param_prefix}__kvth0_diff = 0
.param sky130_fd_pr__{param_prefix}__llodvth_diff = 0
.param sky130_fd_pr__{param_prefix}__lkvth0_diff = 0
.param sky130_fd_pr__{param_prefix}__wkvth0_diff = 0
.param sky130_fd_pr__{param_prefix}__ku0_diff = 0
.param sky130_fd_pr__{param_prefix}__lku0_diff = 0
.param sky130_fd_pr__{param_prefix}__wku0_diff = 0
.param sky130_fd_pr__{param_prefix}__pku0_diff = 0
.param sky130_fd_pr__{param_prefix}__tku0_diff = 0
.param sky130_fd_pr__{param_prefix}__kvsat_diff = 0
.param sky130_fd_pr__{param_prefix}__llodku0_diff = 0
.param sky130_fd_pr__{param_prefix}__wlodku0_diff = 0
.param sky130_fd_pr__{param_prefix}__kvth0_slope = 0

* Include SKY130 model
.include cells/{model_path}

* Test circuit - proper biasing for characterization
Vdd vdd 0 DC {vdd}
Vss vss 0 DC 0
Vgs vgs vss DC 0
Vds vd vss DC 0

* Device under test: Drain=vd, Gate=vgs, Source=vss, Bulk=vss
XM1 vd vgs vss vss {model_name} L={L} W={W} nf=1

* Two-dimensional sweep: VGS and VDS
.dc Vgs {vgs_start} {vgs_end} {vgs_step} Vds {vds_start} {vds_end} {vds_step}

.control
run
write {output_file}
quit
.endc

.end
"""
    return spice_content

def parse_ngspice_raw(filename):
    """Parse ngspice binary raw file."""
    with open(filename, 'rb') as f:
        # Read ASCII header
        header_lines = []
        while True:
            line = f.readline().decode('latin-1').strip()
            header_lines.append(line)
            if line.startswith('Binary:'):
                break
        
        # Parse header
        n_vars = 0
        n_points = 0
        var_names = []
        var_types = []
        
        for line in header_lines:
            if line.startswith('No. Variables:'):
                n_vars = int(line.split(':')[1].strip())
            elif line.startswith('No. Points:'):
                n_points = int(line.split(':')[1].strip())
            elif '\t' in line and len(line.split('\t')) >= 3:
                parts = line.split('\t')
                if len(parts) >= 3 and parts[1].strip():
                    var_names.append(parts[1].strip())
                    var_types.append(parts[2].strip())
        
        # Read binary data
        data = np.zeros((n_points, n_vars))
        for i in range(n_points):
            for j in range(n_vars):
                bytes_data = f.read(8)  # double precision
                if len(bytes_data) < 8:
                    break
                data[i, j] = struct.unpack('d', bytes_data)[0]
        
        return var_names, var_types, data

def compute_gm_id_table(device_type='nfet'):
    """
    Generate comprehensive Gm/ID table for SKY130 device.
    
    Returns a dictionary with lookup table data.
    """
    print(f"\n{'='*60}")
    print(f"Generating Gm/ID table for SKY130 {device_type.upper()}")
    print('='*60)
    
    # Define sweep ranges with 5mV VGS resolution
    if device_type == 'nfet':
        # NFET minimum length is 0.15um
        L_values = [0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0]  # um
        W_values = [1.0, 5.0, 10.0]  # um
        vgs_start, vgs_end, vgs_step = 0, 1.8, 0.005  # 5mV steps
        vds_start, vds_end, vds_step = 0.1, 1.8, 0.3
    else:  # pfet
        # PFET minimum length is 0.35um  
        L_values = [0.35, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0]  # um
        W_values = [1.0, 5.0, 10.0]  # um
        vgs_start, vgs_end, vgs_step = 0, -1.8, -0.005  # 5mV steps
        vds_start, vds_end, vds_step = -0.1, -1.8, -0.3
    
    gmid_table = {
        'device_type': device_type,
        'pdk': 'skywater130',
        'corner': 'tt',
        'model': f'sky130_fd_pr__{device_type}_01v8',
        'data': []
    }
    
    temp_dir = PDK_DIR / 'gm_id_tables' / 'temp'
    temp_dir.mkdir(exist_ok=True)
    
    for L in L_values:
        for W in W_values:
            print(f"\nProcessing L={L}um, W={W}um...")
            
            # Create SPICE deck
            spice_file = temp_dir / f'{device_type}_L{L}_W{W}.sp'
            raw_file = temp_dir / f'{device_type}_L{L}_W{W}.raw'
            
            spice_content = create_spice_deck(
                device_type, L, W,
                vgs_start, vgs_end, vgs_step,
                vds_start, vds_end, vds_step,
                str(raw_file)
            )
            
            with open(spice_file, 'w') as f:
                f.write(spice_content)
            
            # Run ngspice (must run from PDK_DIR for relative includes to work)
            try:
                # Use absolute path for spice file
                result = subprocess.run(
                    ['ngspice', '-b', str(spice_file.absolute())],
                    capture_output=True,
                    text=True,
                    cwd=str(PDK_DIR),  # Run from PDK root so .include paths work
                    timeout=30
                )
                
                if result.returncode != 0:
                    print(f"  Warning: ngspice returned error code {result.returncode}")
                    print(f"  stderr: {result.stderr[:200]}")
                    continue
                
                # Parse results
                if not raw_file.exists():
                    print(f"  Error: Raw file not created")
                    continue
                
                var_names, var_types, data = parse_ngspice_raw(raw_file)
                
                # Find relevant columns
                vgs_idx = next(i for i, name in enumerate(var_names) if 'v(vgs)' in name.lower() or 'vgs' == name.lower())
                vd_idx = next(i for i, name in enumerate(var_names) if 'v(vd)' in name.lower() or name.lower() == 'v(vd)')
                id_idx = next((i for i, name in enumerate(var_names) if 'i(vds)' in name.lower() or 'vds#branch' in name.lower()), 
                              next(i for i, name in enumerate(var_names) if 'current' in var_types[i] and 'vds' in name.lower()))
                
                vgs_data = data[:, vgs_idx]
                vds_data = data[:, vd_idx]
                id_data = np.abs(data[:, id_idx])
                
                # Fix numerical precision: round to 5 decimal places (0.1mV precision)
                vgs_data = np.round(vgs_data, 5)
                vds_data = np.round(vds_data, 5)
                
                # Compute gm numerically: gm = dId/dVgs
                gm_data = np.gradient(id_data, vgs_data)
                
                # Compute gm/Id
                gmid_data = np.zeros_like(gm_data)
                valid_mask = id_data > 1e-12
                gmid_data[valid_mask] = gm_data[valid_mask] / id_data[valid_mask]
                
                # Store data
                gmid_table['data'].append({
                    'L': L,
                    'W': W,
                    'VGS': vgs_data.tolist(),
                    'VDS': vds_data.tolist(),
                    'ID': id_data.tolist(),
                    'GM': gm_data.tolist(),
                    'GMID': gmid_data.tolist()
                })
                
                print(f"  ✓ Successfully characterized ({len(vgs_data)} points)")
                print(f"    ID range: {id_data.min():.2e} to {id_data.max():.2e} A")
                print(f"    Gm/ID range: {gmid_data[valid_mask].min():.2f} to {gmid_data[valid_mask].max():.2f} S/A")
                
            except subprocess.TimeoutExpired:
                print(f"  Error: Simulation timed out")
                continue
            except Exception as e:
                print(f"  Error: {e}")
                continue
    
    return gmid_table

def main():
    """Generate Gm/ID tables for both NFET and PFET."""
    print("\n" + "="*60)
    print("SKY130 Gm/ID Table Generation")
    print("Using Official SkyWater 130nm PDK")
    print("="*60)
    
    # Generate NFET table
    nfet_table = compute_gm_id_table('nfet')
    
    # Save NFET table
    output_file = PDK_DIR / 'gm_id_tables' / 'sky130_nfet_gmid_lut.json'
    with open(output_file, 'w') as f:
        json.dump(nfet_table, f, indent=2)
    
    print(f"\n✓ NFET Gm/ID table saved to: {output_file}")
    print(f"  Total geometries: {len(nfet_table['data'])}")
    
    # Generate PFET table
    pfet_table = compute_gm_id_table('pfet')
    
    # Save PFET table
    output_file = PDK_DIR / 'gm_id_tables' / 'sky130_pfet_gmid_lut.json'
    with open(output_file, 'w') as f:
        json.dump(pfet_table, f, indent=2)
    
    print(f"\n✓ PFET Gm/ID table saved to: {output_file}")
    print(f"  Total geometries: {len(pfet_table['data'])}")
    
    print("\n" + "="*60)
    print("SUCCESS: SKY130 Gm/ID tables generated!")
    print("="*60 + "\n")

if __name__ == '__main__':
    main()

