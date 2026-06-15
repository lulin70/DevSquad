---
name: experiment-design
description: "Design validation experiments using XYZ hypothesis format, with clear success criteria, minimum viable tests, and decision frameworks."
---

# Experiment Design

## Purpose
Design structured experiments to validate product assumptions quickly and cheaply, before investing in full development.

## Context
Use this after assumption mapping, when you've identified your riskiest assumptions and need to design tests to validate or invalidate them.

## Instructions

1. **Formulate XYZ Hypothesis**
   For each assumption to validate, write:
   - **If** [we do X]
   - **Then** [we expect Y outcome]
   - **Because** [we believe Z reason]

   Example: "If we add a 'Save for Later' button, then 30% of users will use it within 7 days, because users currently abandon carts when they're not ready to buy."

2. **Choose Experiment Type**
   Pick the cheapest test that can validate your hypothesis:

   | Type | Cost | Fidelity | When to Use |
   |------|------|----------|-------------|
   | **Fake Door** | Low | Low | Test demand before building |
   | **Landing Page** | Low | Low | Test value proposition |
   | **Concierge MVP** | Medium | Medium | Test with manual service |
   | **Prototype Test** | Medium | Medium | Test usability |
   | **A/B Test** | High | High | Test with real implementation |

3. **Define Success Criteria**
   - **Primary metric**: The single number that proves the hypothesis
   - **Minimum success threshold**: The lowest result that would justify proceeding
   - **Target**: The result you're hoping for
   - **Timeframe**: How long to run the experiment

4. **Design the Experiment**
   - Describe the setup step by step
   - Define who participates (segment, sample size)
   - Specify what data to collect
   - Plan for confounding variables

5. **Define Decision Framework**
   Before running the experiment, commit to:
   - **If result ≥ target**: Proceed to next phase (build full solution)
   - **If result between threshold and target**: Iterate (modify and retest)
   - **If result < threshold**: Kill or pivot (assumption is wrong)

6. **Output Format**
   ```
   ## Experiment: [Name]
   **Hypothesis**: If X, then Y, because Z
   **Type**: [Fake Door / Landing Page / Prototype / A/B Test]
   **Duration**: [N days/weeks]
   **Sample Size**: [N users]

   ### Success Criteria
   | Metric | Threshold | Target | Actual |
   |--------|-----------|--------|--------|
   | [Primary] | [min] | [goal] | TBD |

   ### Decision Framework
   - Proceed if: [criteria]
   - Iterate if: [criteria]
   - Kill/Pivot if: [criteria]
   ```

## Notes
- Run the cheapest experiment that can invalidate your hypothesis
- Define success criteria BEFORE running the experiment (avoid post-hoc rationalization)
- A failed experiment is a successful learning — don't spin negative results
- Don't run more than 2-3 experiments simultaneously
- Timebox experiments — 2 weeks max for most validation tests
- Inspired by Alberto Savoia's Pretotyping and Eric Ries' Lean Startup
