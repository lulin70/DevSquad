---
name: prioritization-frameworks
description: "Apply structured prioritization using RICE, ICE, or WSJF frameworks to rank features, opportunities, or initiatives objectively."
---

# Prioritization Frameworks

## Purpose
Apply a structured prioritization framework to rank features, opportunities, or initiatives objectively, reducing bias and politics in decision-making.

## Context
Use this when you have a list of potential features or initiatives and need to decide what to work on first. Especially useful when stakeholders disagree on priorities.

## Instructions

1. **Choose a Framework**

   **RICE Score** (most comprehensive):
   - **Reach**: How many users will this impact per month? (number)
   - **Impact**: How much will this impact each user? (0.25=minimal, 0.5=low, 1=medium, 2=high, 3=massive)
   - **Confidence**: How confident are you in your estimates? (100%=high, 80%=medium, 50%=low)
   - **Effort**: How many person-months will this take? (number)
   - **Score** = (Reach × Impact × Confidence) / Effort

   **ICE Score** (quick and dirty):
   - **Impact**: How much will this move the metric? (1-10)
   - **Confidence**: How sure are you? (1-10)
   - **Ease**: How easy is this to implement? (1-10)
   - **Score** = Impact × Confidence × Ease

   **WSJF** (for sequenced work):
   - **Cost of Delay** = User/Business Value + Time Criticality + Risk Reduction
   - **Job Size**: Relative effort estimate
   - **Score** = Cost of Delay / Job Size

2. **Score Each Item**
   - List all items in a table
   - Score each dimension independently (don't look at other scores)
   - Calculate composite score

3. **Rank and Review**
   - Sort by score (highest first)
   - Review the top 5 — do they make sense?
   - If not, check your estimates (not the framework)

4. **Present Results**
   - Show the full scoring table
   - Highlight top 3 with rationale
   - Flag items where confidence is low (need research)

## Notes
- The framework doesn't make the decision — it structures the conversation
- Low-confidence scores are signals to gather more data, not to guess
- Don't spend more than 30 minutes scoring — speed matters more than precision
- If two frameworks give different rankings, discuss WHY, not which is "right"
- Always include a "Do Nothing" option as a baseline
