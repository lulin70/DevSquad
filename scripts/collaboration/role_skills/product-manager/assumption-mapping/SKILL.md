---
name: assumption-mapping
description: "Identify and prioritize assumptions across risk categories (Value, Usability, Feasibility, Viability) using Impact × Uncertainty matrix."
---

# Assumption Mapping

## Purpose
Systematically identify and prioritize the assumptions underlying a product idea, so you can validate the riskiest ones before investing in development.

## Context
Use this when you have a product idea or feature proposal and need to understand what must be true for it to succeed. Critical before writing a PRD or starting development.

## Instructions

1. **List All Assumptions**
   For the product/feature idea, identify assumptions across 4 risk categories:

   - **Value Risk**: Will users want this?
     - "Users have this problem"
     - "Users will pay for this solution"
     - "Users will switch from current workaround"

   - **Usability Risk**: Can users figure it out?
     - "Users will understand how to use this"
     - "The workflow matches user mental models"
     - "Users can complete the core task in <N steps"

   - **Feasibility Risk**: Can we build it?
     - "We have the technical capability"
     - "We can integrate with existing systems"
     - "We can deliver within constraints"

   - **Viability Risk**: Does the business case work?
     - "Revenue will exceed cost"
     - "This fits our business model"
     - "Legal/compliance requirements are met"

2. **Map on Impact × Uncertainty Matrix**
   For each assumption, score:
   - **Impact** (1-5): How bad is it if this assumption is wrong?
   - **Uncertainty** (1-5): How unsure are we that this assumption is true?

   Plot on a 2D matrix:
   ```
   High Impact │  INVESTIGATE  │  VALIDATE FIRST
               │               │
   Low Impact  │   MONITOR     │    RESEARCH
               └───────────────┴──────────────
                 Low Uncertainty  High Uncertainty
   ```

3. **Identify Leap-of-Faith Assumptions**
   - High Impact + High Uncertainty = **Validate first**
   - These are your "leap of faith" assumptions
   - If any of these are wrong, the entire idea fails

4. **Prioritize Validation Order**
   - Start with the highest Impact × Uncertainty score
   - Group related assumptions that can be tested together
   - Sequence: cheapest/quickest validation first

5. **Output Format**
   Present as a table:
   | # | Assumption | Category | Impact | Uncertainty | Priority | Validation Method |

## Notes
- Every product idea has assumptions — the question is whether you know what they are
- Be honest about uncertainty — overconfidence is the #1 killer of products
- If you can't identify any high-uncertainty assumptions, you're not looking hard enough
- Assumption mapping is a team sport — get diverse perspectives
- Inspired by Teresa Torres and Alberto Savoia's Pretotyping
