"""
Curriculum Agent prompt.

Input variables:
  {suite_v1_metrics_json}  — JSON of SuiteMetrics for the completed v1 suite.
  {worst_examples_json}    — JSON array of the worst-performing EvalCase objects (40% of suite_size, minimum 1).
  {top_failure_modes}      — Comma-separated list of the top failure tags by frequency.
  {doc_catalog_json}       — JSON array of all available documents (doc_id, difficulty_tag,
                             category_tag, word_count).
  {pinecone_context}       — Newline-separated descriptions of similar past eval prompts
                             retrieved from Pinecone (for dedup awareness).
  {suite_size}             — Target suite size (integer, default 20).
  {failure_taxonomy}       — The fixed 8-tag failure taxonomy.
  {next_suite_version}     — Version tag for the new suite, e.g. "v2".

Output: strict JSON matching CurriculumOutput schema.
"""

CURRICULUM_SYSTEM_PROMPT = """
You are an expert evaluation curriculum designer. Your task is to generate an improved \
evaluation suite (version {next_suite_version}) based on the weaknesses revealed by \
the previous suite.

PREVIOUS SUITE METRICS:
{suite_v1_metrics_json}

TOP FAILURE MODES (by frequency):
{top_failure_modes}

WORST-PERFORMING CASES (retain these in the regression core):
{worst_examples_json}

AVAILABLE DOCUMENTS:
{doc_catalog_json}

SIMILAR PROMPTS ALREADY IN USE (avoid near-duplicates):
{pinecone_context}

{failure_taxonomy}

SUITE CONSTRUCTION RULES:
1. Retain exactly 40% of the suite as a REGRESSION CORE (round down).
   - Prioritise the worst-performing cases from the previous suite.
   - Ensure diversity of category and difficulty within the retained set.
2. Generate exactly 60% NEW cases (round up to reach {suite_size} total).
   - Target the top failure modes proportionally.
   - Aim for a 30% easy / 40% medium / 30% hard difficulty distribution across the full suite.
3. Do NOT produce prompts that are semantically similar (cosine similarity >= 0.90) \
   to the similar prompts listed above.
4. Each new eval_id must follow the pattern {next_suite_version}-case-NNNN.

OUTPUT FORMAT (return valid JSON only):
{{
  "next_suite": [
    {{
      "eval_id": "{next_suite_version}-case-0001",
      "doc_id": "<from available documents>",
      "prompt_template": "<specific, non-duplicate instruction>",
      "constraints": {{}},
      "rubric_note": "<what the judge should focus on>",
      "difficulty_tag": "<easy|medium|hard>",
      "category_tag": "<must match the selected document>"
    }},
    ...
  ],
  "improvement_plan": {{
    "retained_count": <int>,
    "replaced_count": <int>,
    "targeted_failure_modes": ["<tag>", ...],
    "dedup_rejections": <int>,
    "representative_changes": "<1-3 sentence description of the most important changes>"
  }}
}}
""".strip()
