---
name: create-prd
description: "Create a Product Requirements Document using a comprehensive 8-section template covering problem, objectives, segments, value propositions, solution, and release planning."
---

# Create a Product Requirements Document

## Purpose
You are creating a comprehensive Product Requirements Document (PRD). This document serves as the authoritative specification for the product or feature, aligning stakeholders and guiding development.

## Context
A well-structured PRD clearly communicates the what, why, and how of a product initiative. Use this framework when writing a PRD, documenting product requirements, preparing a feature spec, or reviewing an existing PRD.

## Instructions

1. **Gather Information**: If the user provides files, read them carefully. If they mention research, URLs, or customer data, gather additional context.

2. **Think Step by Step**: Before writing, analyze:
   - What problem are we solving?
   - Who are we solving it for?
   - How will we measure success?
   - What are our constraints and assumptions?

3. **Apply the PRD Template**: Create a document with these 8 sections:

   **1. Summary** (2-3 sentences)
   - What is this document about?

   **2. Contacts**
   - Name, role, and comment for key stakeholders

   **3. Background**
   - Context: What is this initiative about?
   - Why now? Has something changed?
   - Is this something that just recently became possible?

   **4. Objective**
   - What's the objective? Why does it matter?
   - How will it benefit the company and customers?
   - How does it align with vision and strategy?
   - Key Results: How will you measure success? (Use SMART OKR format)

   **5. Market Segment(s)**
   - For whom are we building this?
   - What constraints exist?
   - Note: Markets are defined by people's problems/jobs, not demographics

   **6. Value Proposition(s)**
   - What customer jobs/needs are we addressing?
   - What will customers gain?
   - Which pains will they avoid?
   - Which problems do we solve better than competitors?

   **7. Solution**
   - 7.1 UX/Prototypes (wireframes, user flows)
   - 7.2 Key Features (detailed feature descriptions)
   - 7.3 Technology (optional, only if relevant)
   - 7.4 Assumptions (what we believe but haven't proven)

   **8. Release**
   - How long could it take?
   - What goes in the first version vs. future versions?
   - Avoid exact dates; use relative timeframes

4. **Use Accessible Language**: Write for a primary school graduate. Avoid jargon. Use clear, short sentences.

5. **Structure Output**: Present the PRD as a well-formatted markdown document with clear headings and sections.

## Notes
- Be specific and data-driven where possible
- Link each section back to the overall strategy
- Flag assumptions clearly so the team can validate them
- Keep the document concise but complete
- Non-goals are as important as goals — they prevent scope creep
- Success metrics must be specific: "improve NPS from 32 to 45 within 90 days" not "improve NPS"

## Seam-First Design (Matt to-prd)

Matt Pocock's to-prd principle (P1-5): before designing features, identify the
**seams** in the system — the variable points where behaviour can be swapped,
extended, or replaced. Designing features around seams keeps the PRD honest
about what is fixed vs. what is a decision deferred to implementation, and it
produces a document that survives engineering surprises.

A **seam** is a place where two parts of a system meet and where one side can
be replaced without forcing the other side to change (Michael Feathers'
definition). PRDs that name seams explicitly let architects and engineers
reason about extensibility *before* code is written.

### Seams Identification (PRD subsection template)

Insert this subsection under **7. Solution** (or as **7.0** before 7.1):

```
### 7.0 Seams Identification

| Seam | Current Choice | Alternatives Considered | Why Defer / Swap |
|------|----------------|--------------------------|-------------------|
| <seam name> | <default> | <option B>, <option C> | <rationale> |

- **Seam name**: a short noun phrase for the variable point
  (e.g., `auth-provider`, `notification-channel`, `storage-backend`).
- **Current choice**: the recommended default for v1.
- **Alternatives considered**: at least one other viable option, so the
  decision is visibly a choice rather than an accident.
- **Why defer / swap**: the trigger that would cause us to switch
  (e.g., "switch to OAuth if enterprise SSO lands in Q3").
```

### Worked example — login feature

Designing a login feature? First identify the **auth-provider seam**:

| Seam | Current Choice | Alternatives Considered | Why Defer / Swap |
|------|----------------|--------------------------|-------------------|
| `auth-provider` | username + password | OAuth (Google/GitHub), SAML SSO | Adopt OAuth when social sign-in is requested; adopt SAML when an enterprise customer lands. |
| `password-storage` | bcrypt | argon2id, PBKDF2 | Migrate to argon2id when FIPS compliance is required. |
| `session-store` | signed cookie | Redis, JWT | Move to Redis when horizontal scaling beyond 2 instances. |

Only after the seams are named should the PRD specify the login UX, error
messages, and rate-limiting — those features hang off the seams rather than
baking a single provider into the design.

### DevSquad Consensus integration

Seam identification is **not** a solo PM activity. In DevSquad's multi-role
workflow:

1. The **PM** drafts the seams table as part of the PRD (using this skill).
2. The **architect** role must review the seams table via the Consensus
   mechanism before the PRD leaves the design phase. An architect "approve"
   vote means the seams are real variable points (not over-engineering) and
   that the current-choice vs. alternatives trade-off is sound.
3. If Consensus fails (architect rejects), the PM revises the seams table
   before re-submitting. The rejection reason is recorded so the seam
   rationale is auditable.
4. Approved seams become the contract for downstream roles: the **coder**
   writes the seam as an interface/protocol, the **tester** writes
   parameterised tests across the alternatives, and **devops** provisions
   each alternative behind a feature flag.

This mirrors the existing DevSquad Gate flow: seams without architect sign-off
block progression, just like a missing test plan or security review.
