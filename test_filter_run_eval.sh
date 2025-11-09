#!/bin/bash
# Test script to run filter design evaluation with run_eval

cd /Users/kesvis/justbedaniel_2/AMSDesignBench
source ../venv/bin/activate

echo "========================================================================"
echo "Running Filter Design Evaluation with run_eval"
echo "========================================================================"

# Run evaluation on all design tasks (includes filters)
python3 -m harness.run_eval \
    --model dummy \
    --judge-model dummy \
    --split dev \
    --family design \
    --max-items 20

echo ""
echo "========================================================================"
echo "Checking Filter Results"
echo "========================================================================"

# Count and list filters
cat outputs/run_*/combined_results.jsonl | python3 -c "
import sys
import json
filters = []
for line in sys.stdin:
    data = json.loads(line)
    if 'filter' in data['item_id']:
        filters.append((data['item_id'], data['scores']['pass'], data['scores']['raw']))

print(f'Found {len(filters)} filter evaluations:')
for fid, passed, score in sorted(filters):
    status = '✅' if passed else '❌'
    print(f'  {status} {fid:12s} - Score: {score:.2f}')
"

echo ""
echo "========================================================================"
echo "Results saved to outputs/"
echo "========================================================================"
echo ""
echo "To run ALL design tasks (OTAs + filters + feedback):"
echo "  python3 -m harness.run_eval --model dummy --judge-model dummy --split dev --family design"

