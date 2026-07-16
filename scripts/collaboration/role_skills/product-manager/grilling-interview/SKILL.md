---
name: grilling-interview
description: One-question-at-a-time requirements interview with recommended answers and GLOSSARY auto-generation
---

# Grilling Interview

## Leading Words

Interview stakeholders one question at a time, provide a recommended answer for each question, and automatically extract glossary term candidates from the transcript — because multi-question barrages confuse users and undocumented interviews lose knowledge.

## Vocabulary (from GLOSSARY.md)

- **Grilling**: A requirements interview technique where only one question is asked at a time. The interviewer provides a recommended answer to help the user respond efficiently.
- **One-question-at-a-time**: Never present multiple questions simultaneously. Ask, wait for response, then ask the next.
- **Recommended answer**: For each question, the interviewer suggests a likely answer based on codebase analysis or domain knowledge. The user can accept, modify, or reject it.
- **Explore-before-ask**: Before asking a question, search the codebase for existing answers. Only ask if the answer is not already available.
- **GLOSSARY candidates**: Terms extracted from the interview transcript (CamelCase, hyphenated, or quoted expressions) that should be added to the project's GLOSSARY.md.
- **Stateless mode**: A grilling session that does not depend on a codebase. Used when the codebase is unavailable or the interview is domain-level.

## Interview Process

### Step 1: Initialize Grilling Session

```python
from scripts.collaboration.rule_collector import RuleCollector

collector = RuleCollector()
grilling = collector.grilling_mode()
```

For sessions without codebase access (e.g., domain-level interviews):

```python
from scripts.collaboration.rule_collector import GrillingMode

grilling = GrillingMode.stateless_mode()
assert grilling.is_stateless() is True
```

### Step 2: Prepare Questions

Add questions one at a time, each with a recommended answer:

```python
grilling.add_question(
    question="What is the expected response time for the login API?",
    recommended_answers=["Under 500ms for 95th percentile"],
)

grilling.add_question(
    question="Should the system support multi-tenant isolation?",
    recommended_answers=["Yes, at the database schema level"],
)
```

### Step 3: Conduct Interview (One at a Time)

```python
# Get the next question
question = grilling.next_question()
# Returns: GrillingQuestion(question="...", recommended_answers=[...])

# The user provides an answer
grilling.answer_current("Login should be under 200ms")
```

**Rule**: Never present the next question until the current one is answered. If the user can't answer, record "unknown" and move on.

### Step 4: Explore Before Ask

Before adding a question, check if the codebase already contains the answer:

- Search for existing configuration files, ADRs, or documentation
- Check if a similar question was answered in a previous session
- Only ask the user if the answer is genuinely unknown

### Step 5: Extract Glossary Candidates

After the interview, extract terms that should be documented:

```python
result = grilling.get_summary()
# result.glossary_candidates contains extracted terms

for term in result.glossary_candidates:
    print(f"Add to GLOSSARY.md: {term}")
```

The extractor identifies:
- **CamelCase terms**: `DeepModule`, `PrematureSeam`
- **Hyphenated terms**: `pass-through`, `one-adapter`
- **Quoted expressions**: `"seam"`, `"deletion test"`

### Step 6: Generate Interview Summary

```python
result = grilling.get_summary()
# result.questions — all questions asked
# result.explored_answers — all user answers
# result.glossary_candidates — terms for GLOSSARY.md
```

## Failure Modes

- **"Let me ask all questions at once"**: Presenting multiple questions simultaneously overwhelms the user. Ask one at a time.
- **"I know the answer, I'll fill it in"**: The recommended answer is a suggestion, not a substitute for the user's input. Let the user confirm or modify.
- **"The codebase doesn't matter"**: Always explore the codebase before asking. The answer may already exist.
- **"We'll document later"**: Extract glossary candidates during the interview, not after. Knowledge is freshest in the moment.
- **"Every term is a glossary entry"**: Only extract terms that are domain-specific or ambiguous. Common terms like "function" or "variable" don't belong in the glossary.

## Anti-Patterns

- Asking 5 questions in a single message and expecting the user to answer all
- Providing a recommended answer and auto-accepting it without user confirmation
- Skipping the codebase exploration step ("I'll just ask")
- Forgetting to extract glossary candidates after the interview
- Using stateless mode when a codebase is available (loses explore-before-ask benefit)

## Verification Requirements

- Every question must have at least one recommended answer
- Only one question must be active at any time (next_question returns None when no more)
- Glossary candidates must be extracted and reviewed before adding to GLOSSARY.md
- Stateless mode must be explicitly requested (default mode uses codebase)
- Interview summary must include all questions, answers, and glossary candidates
