"""
Design Judge

Uses LLM to evaluate if simulation results meet design specifications.
"""

from typing import Dict, Optional, List
from dataclasses import dataclass, field
import json


@dataclass
class JudgmentResult:
    """Container for design judgment results."""
    overall_pass: bool
    score: float  # 0-100
    spec_results: Dict[str, Dict] = field(default_factory=dict)
    reasoning: str = ""
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'overall_pass': self.overall_pass,
            'score': self.score,
            'spec_results': self.spec_results,
            'reasoning': self.reasoning,
            'recommendations': self.recommendations
        }


class DesignJudge:
    """Evaluates design performance against specifications using LLM."""
    
    def __init__(self, llm_adapter):
        """
        Initialize design judge.
        
        Args:
            llm_adapter: LLM adapter instance from harness.adapters
        """
        self.llm = llm_adapter
    
    def evaluate(self, sim_results: Dict, design_spec: Dict, 
                netlist: str = "") -> JudgmentResult:
        """
        Evaluate simulation results against design specifications.
        
        Args:
            sim_results: Dictionary of simulation metrics
            design_spec: Design specification dictionary
            netlist: Original netlist (for context)
            
        Returns:
            JudgmentResult with evaluation
        """
        # First do rule-based evaluation
        spec_results = self._rule_based_evaluation(sim_results, design_spec)
        
        # Calculate initial score
        score = self._calculate_score(spec_results, design_spec)
        
        # Use LLM for detailed analysis and recommendations
        llm_judgment = self._llm_evaluation(sim_results, design_spec, spec_results, netlist)
        
        # Combine results
        overall_pass = all(result['pass'] for result in spec_results.values())
        
        return JudgmentResult(
            overall_pass=overall_pass,
            score=score,
            spec_results=spec_results,
            reasoning=llm_judgment.get('reasoning', ''),
            recommendations=llm_judgment.get('recommendations', [])
        )
    
    def _rule_based_evaluation(self, sim_results: Dict, design_spec: Dict) -> Dict[str, Dict]:
        """
        Perform rule-based specification checking.
        
        Returns:
            Dictionary mapping spec name to {pass, value, target, margin}
        """
        results = {}
        specifications = design_spec.get('specifications', {})
        
        for spec_name, spec_def in specifications.items():
            result = {
                'pass': False,
                'value': None,
                'target': spec_def.get('target', spec_def.get('min', spec_def.get('max'))),
                'margin': None,
                'message': ''
            }
            
            # Map spec name to simulation result key
            sim_key = self._map_spec_to_sim_key(spec_name)
            
            if sim_key not in sim_results:
                result['message'] = f"Metric '{sim_key}' not found in simulation results"
                results[spec_name] = result
                continue
            
            value = sim_results[sim_key]
            result['value'] = value
            
            # Check constraints
            min_val = spec_def.get('min')
            max_val = spec_def.get('max')
            target_val = spec_def.get('target')
            
            if min_val is not None and value < min_val:
                result['pass'] = False
                result['margin'] = value - min_val
                result['message'] = f"Below minimum: {value} < {min_val}"
            elif max_val is not None and value > max_val:
                result['pass'] = False
                result['margin'] = max_val - value
                result['message'] = f"Above maximum: {value} > {max_val}"
            else:
                result['pass'] = True
                # Calculate margin to target or bounds
                if target_val is not None:
                    result['margin'] = abs(value - target_val)
                elif min_val is not None:
                    result['margin'] = value - min_val
                elif max_val is not None:
                    result['margin'] = max_val - value
                result['message'] = "Pass"
            
            results[spec_name] = result
        
        return results
    
    def _map_spec_to_sim_key(self, spec_name: str) -> str:
        """Map specification name to simulation result key."""
        mapping = {
            'dc_gain': 'dc_gain_db',
            'gbw': 'gbw_hz',
            'phase_margin': 'phase_margin_deg',
            'power': 'power_w',
            'slew_rate': 'slew_rate',
            'output_swing': 'output_swing_v',
            'input_common_mode_range': 'icmr_v'
        }
        return mapping.get(spec_name, spec_name)
    
    def _calculate_score(self, spec_results: Dict, design_spec: Dict) -> float:
        """
        Calculate overall design score (0-100) based on specifications.
        
        Uses weighted scoring from design_spec.
        """
        total_weight = 0
        weighted_score = 0
        
        specifications = design_spec.get('specifications', {})
        
        for spec_name, result in spec_results.items():
            spec_def = specifications.get(spec_name, {})
            weight = spec_def.get('weight', 0.1)
            
            if result['pass']:
                # Full points if passed
                spec_score = 100
                
                # Bonus for exceeding target
                if result['target'] and result['value']:
                    margin_pct = abs(result['margin']) / result['target'] * 100
                    if margin_pct > 10:  # More than 10% margin
                        spec_score = min(110, 100 + margin_pct / 10)
            else:
                # Partial credit based on how close
                if result['margin'] and result['target']:
                    margin_pct = abs(result['margin']) / result['target'] * 100
                    spec_score = max(0, 50 - margin_pct)
                else:
                    spec_score = 0
            
            weighted_score += spec_score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0
        
        return min(100, weighted_score / total_weight)
    
    def _llm_evaluation(self, sim_results: Dict, design_spec: Dict,
                       spec_results: Dict, netlist: str) -> Dict:
        """
        Use LLM for detailed evaluation and recommendations.
        
        Returns:
            Dictionary with 'reasoning' and 'recommendations'
        """
        # Prepare prompt for LLM
        prompt = self._create_judgment_prompt(sim_results, design_spec, spec_results, netlist)
        
        try:
            response = self.llm.generate(prompt)
            return self._parse_llm_response(response)
        except Exception as e:
            return {
                'reasoning': f"LLM evaluation failed: {str(e)}",
                'recommendations': []
            }
    
    def _create_judgment_prompt(self, sim_results: Dict, design_spec: Dict,
                                spec_results: Dict, netlist: str) -> str:
        """Create prompt for LLM judge."""
        
        # Format spec results
        spec_summary = []
        for spec_name, result in spec_results.items():
            status = "✓ PASS" if result['pass'] else "✗ FAIL"
            spec_summary.append(f"- {spec_name}: {status} (value: {result['value']}, {result['message']})")
        
        prompt = f"""You are an expert analog IC designer evaluating an AI-generated OTA design.

Design Topology: {design_spec.get('topology', 'Unknown')}
Description: {design_spec.get('description', '')}

SIMULATION RESULTS:
{json.dumps(sim_results, indent=2)}

SPECIFICATION CHECKING:
{chr(10).join(spec_summary)}

DESIGN SPECIFICATIONS:
{json.dumps(design_spec.get('specifications', {}), indent=2)}

TASK:
1. Analyze the simulation results against the specifications
2. Provide reasoning for why specifications passed or failed
3. Suggest specific design improvements if any specs failed
4. Consider trade-offs between specifications (e.g., power vs. speed)

Provide your response in the following format:

REASONING:
[Your detailed analysis of the results and any trade-offs]

RECOMMENDATIONS:
- [Specific recommendation 1]
- [Specific recommendation 2]
- [etc.]

Keep recommendations actionable and specific to the circuit topology.
"""
        return prompt
    
    def _parse_llm_response(self, response: str) -> Dict:
        """Parse LLM response into structured format."""
        reasoning = ""
        recommendations = []
        
        # Split by sections
        if "REASONING:" in response:
            parts = response.split("RECOMMENDATIONS:")
            reasoning = parts[0].replace("REASONING:", "").strip()
            
            if len(parts) > 1:
                rec_text = parts[1].strip()
                # Extract bullet points
                for line in rec_text.split('\n'):
                    line = line.strip()
                    if line.startswith('-') or line.startswith('•'):
                        recommendations.append(line[1:].strip())
        else:
            reasoning = response
        
        return {
            'reasoning': reasoning,
            'recommendations': recommendations
        }

