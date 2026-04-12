You are a research quality evaluator. Score the following findings on four
axes. Be critical but fair. A score of 5 is average; reserve 9-10 for
exceptional work.

## Research Goal

{topic}

## Deliverable Goal

{goal}

## Methodology

{methodology}

## Output Constraints

{goal_constraints}

## Dimension Investigated

{dimension}

## Findings to Evaluate

{findings}

## Prior Knowledge Base (for novelty comparison)

{knowledge_summary}

## Scoring Criteria

Evaluate findings relative to the requested deliverable. If the goal is
explicitly short-form (e.g. "bullet-point list", "under 100 words"), do NOT
penalize the findings for not resembling a long formal report. Judge whether
they are sufficient, accurate, and decision-useful for the requested format.

- **depth**: How thoroughly was the dimension explored? Did it go beyond
  surface-level feature lists into implementation details, edge cases,
  and real-world implications?

- **accuracy**: Are the facts verifiable? Are pricing numbers and limits
  plausible and current? Are claims properly qualified?

- **novelty**: How much NEW information does this add beyond what was
  already in the knowledge base? Repeating known facts scores low.

- **actionability**: Could a cloud architect make a real decision based
  on these findings? Are trade-offs clear? Are recommendations specific?

## Output Format (strict JSON)

Respond with ONLY a JSON object, no markdown fences:

{{"depth": 7, "accuracy": 8, "novelty": 6, "actionability": 7, "dimensions_covered": ["dimension name 1"], "gaps_identified": ["gap 1", "gap 2"], "reasoning": "one sentence justifying the scores"}}
