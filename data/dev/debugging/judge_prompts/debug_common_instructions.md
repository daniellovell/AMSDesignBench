## Instructions

**IMPORTANT: The rubric Answer Key section below contains GROUND TRUTH (the correct answer) for this debugging question.**

### Understanding the CONTEXT payload

The CONTEXT payload contains two fields:
- **answer_to_evaluate**: The student's submitted answer that you are grading
- **inventory**: Valid element IDs and circuit structure from the artifact

### Your Task

Compare the student's **answer_to_evaluate** field against the ground truth in the **rubric Answer Key** section. Use the criteria and Answer Key below to determine how well the student identified the bug and proposed a fix.

### Output Format
- Output JSON only: `{"scores": {"<criterion_id>": <float 0..1>, ...}, "overall": <0..1>}`.
- Do not include any extra keys or prose.
- If a criterion is omitted in your output, treat it as 0 before computing the weighted overall.

### Scoring Guidelines
- Award **full credit** when the student's answer matches the ground truth in the rubric Answer Key (e.g., correctly identifies {runtime:swapped_id}, {runtime:bug_type})
- Award **partial credit** for partially correct or incomplete answers
- Award **zero credit** when the answer contradicts the ground truth or is completely incorrect
- Check specific answer key fields as indicated in the Answer Key section below
