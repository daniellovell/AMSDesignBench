"""
Gm/ID Lookup Table Helper

Provides functions to query Gm/ID tables and help with transistor sizing.
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple
from scipy import interpolate

class GmIdLookup:
    """Helper class for querying Gm/ID lookup tables."""
    
    def __init__(self, lut_path: Path):
        """Initialize with path to lookup table JSON file."""
        with open(lut_path, 'r') as f:
            self.lut = json.load(f)
        self.device_type = self.lut['device_type']
        
    def query(self, L: float, gmid: float, vds: float = 0.9) -> Optional[Dict]:
        """
        Query the lookup table for operating point parameters.
        
        Args:
            L: Channel length in meters
            gmid: Target Gm/ID ratio (S/A)
            vds: Drain-source voltage in volts
            
        Returns:
            Dictionary with {vgs, id, gm, gds, vth, ft} or None if not found
        """
        # Find closest L value
        L_key = self._find_closest_L(L)
        if not L_key:
            return None
        
        data = self.lut['data'][L_key]
        
        # Find closest VDS
        vds_values = np.array(data['vds'])
        gmid_values = np.array(data['gmid'])
        
        # Filter for target VDS region
        vds_mask = np.abs(vds_values - vds) < 0.3
        if not np.any(vds_mask):
            return None
        
        # Find closest Gm/ID
        valid_gmid = gmid_values[vds_mask]
        valid_indices = np.where(vds_mask)[0]
        
        if len(valid_gmid) == 0:
            return None
        
        closest_idx = valid_indices[np.argmin(np.abs(valid_gmid - gmid))]
        
        return {
            'vgs': data['vgs'][closest_idx],
            'vds': data['vds'][closest_idx],
            'id': data['id'][closest_idx],
            'gm': data['gm'][closest_idx],
            'gds': data['gds'][closest_idx],
            'vth': data['vth'][closest_idx],
            'gmid': data['gmid'][closest_idx],
            'ft': data['ft'][closest_idx] if 'ft' in data else None,
            'gm_gds': data['gm_gds'][closest_idx] if 'gm_gds' in data else None
        }
    
    def get_width_for_gm(self, L: float, gm_target: float, gmid: float, vds: float = 0.9) -> Optional[float]:
        """
        Calculate required W to achieve target Gm.
        
        Args:
            L: Channel length in meters
            gm_target: Target transconductance in Siemens
            gmid: Target Gm/ID ratio
            vds: Operating VDS in volts
            
        Returns:
            Required width in meters, or None if not feasible
        """
        op_point = self.query(L, gmid, vds)
        if not op_point:
            return None
        
        # gm scales with W, so:  W = gm_target / gm_unit_width
        # where gm_unit_width is gm for W=10um (from characterization)
        W_ref = 10e-6  # Reference width used in characterization
        gm_ref = op_point['gm']
        
        if gm_ref == 0:
            return None
        
        W_required = (gm_target / gm_ref) * W_ref
        return W_required
    
    def get_sizing(self, L: float, id_target: float, gmid: float, vds: float = 0.9) -> Optional[Dict]:
        """
        Get complete transistor sizing for target current.
        
        Args:
            L: Channel length in meters
            id_target: Target drain current in Amperes
            gmid: Target Gm/ID ratio
            vds: Operating VDS in volts
            
        Returns:
            Dictionary with {W, L, vgs, gm, id, vth}
        """
        op_point = self.query(L, gmid, vds)
        if not op_point:
            return None
        
        # Current scales with W
        W_ref = 10e-6
        id_ref = op_point['id']
        
        if id_ref == 0:
            return None
        
        W = (id_target / id_ref) * W_ref
        gm = id_target * gmid
        
        return {
            'W': W,
            'L': L,
            'vgs': op_point['vgs'],
            'gm': gm,
            'id': id_target,
            'vth': op_point['vth'],
            'vdsat': op_point['vgs'] - op_point['vth']
        }
    
    def _find_closest_L(self, L: float) -> Optional[str]:
        """Find the closest L value in the lookup table."""
        L_values = [float(k.split('_')[1]) for k in self.lut['data'].keys()]
        if not L_values:
            return None
        closest_L = min(L_values, key=lambda x: abs(x - L))
        return f'L_{closest_L}'
    
    def get_available_L_values(self) -> list:
        """Return list of available L values in the table."""
        return [float(k.split('_')[1]) for k in self.lut['data'].keys()]


def load_pdk_tables(pdk_path: Path) -> Tuple[GmIdLookup, GmIdLookup]:
    """
    Load both NMOS and PMOS Gm/ID lookup tables.
    
    Args:
        pdk_path: Path to PDK directory
        
    Returns:
        Tuple of (nfet_lut, pfet_lut)
    """
    tables_path = pdk_path / "gm_id_tables"
    
    nfet_lut = GmIdLookup(tables_path / "nfet_gmid_lut.json")
    pfet_lut = GmIdLookup(tables_path / "pfet_gmid_lut.json")
    
    return nfet_lut, pfet_lut

