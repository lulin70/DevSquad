---
name: uiux-audit
description: UI/UX audit using 7 Design Pillars
---

# UI/UX Audit — 7 Design Pillars

## Leading Words

Audit UI quality using impeccable's 7 Design Pillars vocabulary. Each pillar
maps to a category in `DeterministicRuleEngine` and provides the evaluation
dimensions for any UI surface. The pillars are not a checklist — they are a
shared vocabulary for triangulating UI quality.

## Vocabulary (from GLOSSARY.md)

- **Design Pillars**: 7 design evaluation dimensions — Typography / Color /
  Spatial / Responsiveness / Interactions / Motion / UX writing. UI/UX
  evaluation vocabulary framework. Source: impeccable.
- **Deterministic Rule**: A pure if/else + AST detection rule, no LLM needed.
  46 rules organized by pillar in `DeterministicRuleEngine`.
- **Taste Dials**: Visual taste knobs (0.0-1.0) — DESIGN_VARIANCE /
  MOTION_INTENSITY / VISUAL_DENSITY — that adjust non-a11y rule thresholds.
- **OKLCH**: Perceptually uniform color space that replaces sRGB. More
  aligned with human vision than HSV.
- **4pt grid**: 4-pixel base spacing grid. Semantic spacing tokens:
  xs=4, sm=8, md=16, lg=24, xl=32.
- **Anti-pattern Bans**: 6 AI-generated UI anti-patterns that must be
  banned — border-left accent stripes, gradient text, glassmorphism overuse,
  overused fonts (Inter/Roboto/DM Sans), purple-blue gradients, nested cards.

## The 7 Design Pillars

### 1. Typography

Type system quality — line-height, font-size, heading hierarchy, font
selection, letter-spacing, weight contrast, alignment.

Detection points:
- Line-height within 1.4-1.8 for body text
- Minimum font size 14px (12px for secondary text)
- Heading levels don't skip (no h1 → h3)
- Banned overused fonts: Inter, Roboto, DM Sans
- Line length ≤80 characters
- Letter-spacing within -0.05em to 0.1em
- Heading vs body font-weight contrast ≥200
- Body text not justified

Engine integration: `DeterministicRuleEngine.get_rules_by_pillar("typography")`
returns 8 rules; pillar maps to category `"a11y"`.

### 2. Color

Color palette quality — WCAG contrast, harsh saturation, palette count,
OKLCH usage, grayscale for secondary text, background contrast.

Detection points:
- WCAG AA contrast ≥4.5:1 for normal text (a11y — never adjusted)
- WCAG AA contrast ≥3:1 for large text (a11y — never adjusted)
- WCAG AA contrast ≥3:1 for UI components (a11y — never adjusted)
- HSV saturation ≤0.6 (Morandi palette)
- Palette ≤5 distinct colors
- OKLCH color space recommended for perceptual uniformity
- Grayscale tones for secondary/supporting text
- Background-to-content contrast ≥4.5:1

Engine integration: `DeterministicRuleEngine.get_rules_by_pillar("color")`
returns 8 rules; pillar maps to category `"a11y"`. Contrast rules are NEVER
adjusted by TasteDials — accessibility is not a matter of taste.

### 3. Spatial

Spacing and layout — 4pt grid, element density, padding minimums, margin
consistency, whitespace ratio, card spacing.

Detection points:
- Spacing follows 4pt grid (multiples of 4: 4/8/12/16/20/24/28/32/...)
- Element count per viewport ≤50
- Minimum padding 8px
- ≤3 distinct margin values
- Whitespace-to-content ratio ≥30%
- Consistent card spacing (≤2 distinct values)

Engine integration: `DeterministicRuleEngine.get_rules_by_pillar("spatial")`
returns 6 rules; pillar maps to category `"layout"`.

### 4. Responsiveness

Adaptive layout — viewport overflow, touch targets, image max-width, text
overflow, breakpoint coverage, grid adaptation.

Detection points:
- No horizontal scroll (viewport overflow)
- Touch targets ≥44×44px
- Images have `max-width: 100%`
- No truncation of key content
- Breakpoints cover sm/md/lg/xl
- Grid layouts adapt via media queries

Engine integration: `DeterministicRuleEngine.get_rules_by_pillar("responsiveness")`
returns 6 rules; pillar maps to category `"layout"`.

### 5. Interactions

Interactive element quality — button size, focus visibility, hover/active
states, disabled state, loading feedback, destructive confirmation, form
validation.

Detection points:
- Buttons ≥44×44px
- Focus outline not removed (keyboard a11y)
- Interactive elements have `:hover` state
- Interactive elements have `:active` state
- Disabled elements visually distinct (opacity/cursor)
- Async operations show loading feedback
- Destructive actions require confirmation
- Forms have validation (required fields, type checks)

Engine integration: `DeterministicRuleEngine.get_rules_by_pillar("interactions")`
returns 8 rules; pillar maps to category `"interaction"`.

### 6. Motion

Animation quality — duration, easing, animated properties, glassmorphism,
reduced-motion respect.

Detection points:
- Animation duration ≤1s
- No bounce/elastic easing (use ease-out)
- No width/height animation (use `transform: scale()`)
- Glassmorphism (`backdrop-filter: blur()`) ≤2 instances
- `prefers-reduced-motion` media query respected

Engine integration: `DeterministicRuleEngine.get_rules_by_pillar("motion")`
returns 5 rules; pillar maps to category `"interaction"`.

### 7. UX Writing

Content quality — button text clarity, error messages, form labels, link
text, heading descriptiveness.

Detection points:
- Button text is actionable (not "Click Here", "Submit", "OK")
- Error messages explain what went wrong and how to fix it
- Form labels are descriptive (not "Field 1")
- Link text is descriptive (not "click here", "read more")
- Headings convey content meaning (not "Heading", "Title")

Engine integration: `DeterministicRuleEngine.get_rules_by_pillar("ux_writing")`
returns 5 rules; pillar maps to category `"ux_antipattern"`.

## Audit Workflow

### Step 1: Collect DOM Probes

Run the Playwright single-pass probe (`UIUXAnalyzer.audit(page, url)`)
to collect all DOM data in one `page.evaluate()` call. The probe script
returns structured data for a11y, interaction, layout, and ux sections.

### Step 2: Run Deterministic Rules

```python
from scripts.qa.deterministic_rule_engine import DeterministicRuleEngine
from scripts.qa.taste_dials import TasteDials

engine = DeterministicRuleEngine()
issues = engine.check(probes, dials=TasteDials(), context={})
```

Each rule gracefully degrades when probe data is missing — returns an empty
list, not an error. Fail-safe: a single rule exception does not stop other
rules.

### Step 3: Run CSS Anti-pattern Bans

For CSS-text-level detection (Task 1 of V4.1.0 P1-UI-1), call:

```python
from scripts.qa.uiux_analyzer import UIUXAnalyzer

analyzer = UIUXAnalyzer()
css_issues = analyzer.check_css_antipatterns(css_text)
```

This runs 6 taste-skill Anti-pattern Bans:
- `border_left_accent_stripes` — `border-left: Npx solid <color>` (≥2px)
- `gradient_text` — `background-clip: text` combined with `gradient()`
- `glassmorphism_overuse` — `backdrop-filter: blur()` count > 2
- `overused_fonts` — Inter / Roboto / DM Sans font-family
- `purple_blue_gradient` — purple+blue gradient backgrounds
- `nested_cards` — `.card .card` selectors

### Step 4: Run 4pt Grid Spacing Check

```python
spacing_issues = analyzer.check_4pt_grid(css_text)
```

Scans `margin`, `padding`, and `gap` declarations for values that are not
multiples of 4. Supports `px`, `rem` (1rem=16px), and `em` (1em=16px).

### Step 5: Apply OKLCH-aware Color Detection

`UIUXAnalyzer._parse_color()` accepts `rgb()`, `#hex`, and `oklch()` formats.
Use `_rgb_to_oklch()` / `_oklch_to_rgb()` for perceptual color comparison
when HSV is insufficient (HSV is non-uniform; OKLCH is perceptually uniform).

### Step 6: Adjust Thresholds via TasteDials

Non-a11y rule thresholds can be tuned with TasteDials (0.0-1.0):
- `DESIGN_VARIANCE` — how much visual variation to allow
- `MOTION_INTENSITY` — animation aggressiveness
- `VISUAL_DENSITY` — element density tolerance

```python
dials = TasteDials()
adjusted = dials.adjust_threshold("layout_density", base_threshold=50.0)
```

a11y rules (color contrast, aria label) are NEVER adjusted by TasteDials —
accessibility is not a matter of taste.

### Step 7: Sort & Report

Issues are sorted by severity (critical > warning > info). The audit report
includes the URL, all issues, and an ISO timestamp.

```python
report = UIUXAuditReport(url=url, issues=issues)
print(f"Passed: {report.passed}, Critical: {report.critical_count}")
```

## Failure Modes

- **Probe data missing**: Each rule gracefully returns `[]` when its probe
  data is absent. Do NOT assume a probe field is present.
- **CORS-restricted stylesheets**: The probe wraps stylesheet iteration in
  try/catch; cross-origin sheets are silently skipped.
- **Single-rule exception**: A buggy rule does not stop other rules — the
  engine catches and continues.
- **OKLCH approximation**: The OKLCH ↔ sRGB conversion is a simplified
  approximation, not color-management-grade. Use it for taste-skill
  detection, not for precise color matching.

## Anti-Patterns

- Treating pillar rules as a hard checklist rather than a shared vocabulary
- Adjusting a11y rule thresholds via TasteDials (contrast is never optional)
- Skipping the CSS-level anti-pattern bans when only DOM probes are available
- Using HSV for perceptual color comparison instead of OKLCH
