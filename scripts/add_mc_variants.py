#!/usr/bin/env python3
"""
Update questions.yaml files to include multiple-choice variants.
Adds a second question for each existing question with prompt_variant: multiple_choice.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any
import copy


def add_mc_variant(questions_data: Dict[str, List[Dict]], item_dir: Path, track: str, family: str) -> bool:
    """Add MC variants to questions if they don't already exist."""
    
    questions = questions_data.get('questions', [])
    if not questions:
        return False
    
    modified = False
    new_questions = []
    
    for q in questions:
        # Add the original question
        new_questions.append(q)
        
        # Check if MC variant already exists
        mc_id = q['id'] + "_mc"
        if any(nq['id'] == mc_id for nq in questions):
            continue  # MC variant already exists
        
        # Create MC variant
        mc_q = copy.deepcopy(q)
        mc_q['id'] = mc_id
        
        # Update prompt template to MC version
        prompt_template = q.get('prompt_template', '')
        
        if track == "debugging":
            if "device_swap" in prompt_template or "device_swap" in str(q.get('meta', {})):
                mc_q['prompt_template'] = '../prompts/debug_device_swap_mc.txt'
            elif "feedback_polarity" in prompt_template or "polarity" in str(q.get('meta', {})):
                mc_q['prompt_template'] = '../prompts/debug_feedback_polarity_mc.txt'
            else:
                continue  # Unknown debugging type
        
        elif track == "analysis":
            aspect = q.get('meta', {}).get('aspect', '')
            
            if family == "ota":
                if "gain_dc" in aspect:
                    mc_q['prompt_template'] = '../prompts/ota_dc_gain_mc.txt'
                elif "gbw" in aspect:
                    mc_q['prompt_template'] = '../prompts/ota_gbw_mc.txt'
                elif "psrr" in aspect:
                    mc_q['prompt_template'] = '../prompts/ota_psrr_mc.txt'
                elif "rout" in aspect:
                    mc_q['prompt_template'] = '../prompts/ota_rout_mc.txt'
                elif "swing" in aspect:
                    mc_q['prompt_template'] = '../prompts/ota_swing_mc.txt'
                elif "power" in aspect:
                    mc_q['prompt_template'] = '../prompts/ota_power_mc.txt'
                elif "noise" in aspect:
                    mc_q['prompt_template'] = '../prompts/ota_noise_mc.txt'
                else:
                    # Skip if no template defined
                    print(f"Warning: No MC template for aspect '{aspect}' in {family}, skipping")
                    continue
            
            elif family == "feedback":
                mc_q['prompt_template'] = '../prompts/feedback_analysis_mc.txt'
            
            elif family == "filters":
                mc_q['prompt_template'] = '../prompts/identify_tf_mc.txt'
            
            else:
                continue  # Unknown analysis family
        
        elif track == "design":
            # Design tasks don't get MC variants (they're already objective)
            continue
        
        else:
            continue  # Unknown track
        
        # Add prompt_variant metadata
        if 'meta' not in mc_q:
            mc_q['meta'] = {}
        mc_q['meta']['prompt_variant'] = 'multiple_choice'
        
        # Original question gets short_form variant
        if 'meta' not in q:
            q['meta'] = {}
        q['meta']['prompt_variant'] = 'short_form'
        
        new_questions.append(mc_q)
        modified = True
    
    if modified:
        questions_data['questions'] = new_questions
    
    return modified


def main():
    data_dir = Path(__file__).parent.parent / "data" / "dev"
    
    count = 0
    
    # Process debugging OTA
    for item_dir in (data_dir / "debugging" / "ota").iterdir():
        if not item_dir.is_dir():
            continue
        
        questions_file = item_dir / "questions.yaml"
        if not questions_file.exists():
            continue
        
        with open(questions_file) as f:
            questions_data = yaml.safe_load(f)
        
        if add_mc_variant(questions_data, item_dir, "debugging", "ota"):
            with open(questions_file, 'w') as f:
                yaml.dump(questions_data, f, default_flow_style=False, sort_keys=False)
            print(f"Updated {questions_file}")
            count += 1
    
    # Process debugging feedback
    for item_dir in (data_dir / "debugging" / "feedback").iterdir():
        if not item_dir.is_dir():
            continue
        
        questions_file = item_dir / "questions.yaml"
        if not questions_file.exists():
            continue
        
        with open(questions_file) as f:
            questions_data = yaml.safe_load(f)
        
        if add_mc_variant(questions_data, item_dir, "debugging", "feedback"):
            with open(questions_file, 'w') as f:
                yaml.dump(questions_data, f, default_flow_style=False, sort_keys=False)
            print(f"Updated {questions_file}")
            count += 1
    
    # Process analysis OTA
    for item_dir in (data_dir / "analysis" / "ota").iterdir():
        if not item_dir.is_dir():
            continue
        
        questions_file = item_dir / "questions.yaml"
        if not questions_file.exists():
            continue
        
        with open(questions_file) as f:
            questions_data = yaml.safe_load(f)
        
        if add_mc_variant(questions_data, item_dir, "analysis", "ota"):
            with open(questions_file, 'w') as f:
                yaml.dump(questions_data, f, default_flow_style=False, sort_keys=False)
            print(f"Updated {questions_file}")
            count += 1
    
    # Process analysis feedback
    for item_dir in (data_dir / "analysis" / "feedback").iterdir():
        if not item_dir.is_dir():
            continue
        
        questions_file = item_dir / "questions.yaml"
        if not questions_file.exists():
            continue
        
        with open(questions_file) as f:
            questions_data = yaml.safe_load(f)
        
        if add_mc_variant(questions_data, item_dir, "analysis", "feedback"):
            with open(questions_file, 'w') as f:
                yaml.dump(questions_data, f, default_flow_style=False, sort_keys=False)
            print(f"Updated {questions_file}")
            count += 1
    
    # Process analysis filters
    for item_dir in (data_dir / "analysis" / "filters").iterdir():
        if not item_dir.is_dir():
            continue
        
        questions_file = item_dir / "questions.yaml"
        if not questions_file.exists():
            continue
        
        with open(questions_file) as f:
            questions_data = yaml.safe_load(f)
        
        if add_mc_variant(questions_data, item_dir, "analysis", "filters"):
            with open(questions_file, 'w') as f:
                yaml.dump(questions_data, f, default_flow_style=False, sort_keys=False)
            print(f"Updated {questions_file}")
            count += 1
    
    print(f"\nUpdated {count} questions.yaml files with MC variants")


if __name__ == "__main__":
    main()

