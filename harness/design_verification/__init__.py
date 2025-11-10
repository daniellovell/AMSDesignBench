"""
Design Verification Module

This module provides automated SPICE-based verification of AI-generated
OTA designs using ngspice and LLM-based judging.
"""

from .netlist_parser import NetlistParser
from .spice_runner import SpiceRunner, SimulationResults
from .design_judge import DesignJudge, JudgmentResult

__all__ = [
    'NetlistParser',
    'SpiceRunner',
    'SimulationResults',
    'DesignJudge',
    'JudgmentResult',
]

