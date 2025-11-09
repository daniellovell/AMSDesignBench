#!/bin/bash
# Run filter evaluation with real judge model

cd /Users/kesvis/justbedaniel_2/AMSDesignBench
source ../venv/bin/activate

echo "Running filter design evaluation with real judge (gpt-4o-mini)..."
echo "This will evaluate dummy model responses with a real LLM judge."
echo ""

# Use 'yes' to auto-confirm
echo "y" | python3 -m harness.run_eval \
    --model dummy \
    --judge-model openai:gpt-4o-mini \
    --split dev \
    --family design \
    --max-items 5

echo ""
echo "Evaluation complete! Check outputs/ for results."

