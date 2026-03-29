---
description: Generate a custom checklist for the current feature based on user requirements.
---

## Core Concept: Unit Tests for Requirements

Checklists are **unit tests for requirements writing**. They validate the quality, clarity, and completeness of requirements -- NOT the implementation.

**What checklists are NOT:**
- "Verify the button clicks correctly"
- "Test error handling works"
- "Confirm the API returns 200"
- Checking if code/implementation matches the spec

**What checklists ARE:**
- "Are visual hierarchy requirements defined for all card types?" (completeness)
- "Is 'prominent display' quantified with specific sizing/positioning?" (clarity)
- "Are hover state requirements consistent across all interactive elements?" (consistency)
- "Are accessibility requirements defined for keyboard navigation?" (coverage)
- "Does the spec define what happens when logo image fails to load?" (edge cases)

If your spec is code written in English, the checklist is its unit test suite. Test whether the requirements are well-written, complete, unambiguous, and ready for implementation -- NOT whether the implementation works.

---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

---

## Execution Steps

### Step 1: Setup

Run `.specify/scripts/bash/check-prerequisites.sh --json` from repo root. Parse JSON for `FEATURE_DIR` and `AVAILABLE_DOCS` list. All file paths must be absolute.

For single quotes in args (e.g., "I'm Groot"), use escape syntax: `'I'\''m Groot'` or double-quote: `"I'm Groot"`.

### Step 2: Clarify Intent

Derive up to THREE initial contextual clarifying questions (no pre-baked catalog). Each question MUST:
- Be generated from the user's phrasing + extracted signals from spec/plan/tasks.
- Only ask about information that materially changes checklist content.
- Be skipped if already unambiguous in `$ARGUMENTS`.
- Prefer precision over breadth.

**Question generation algorithm:**
1. Extract signals: feature domain keywords (e.g., auth, latency, UX, API), risk indicators ("critical", "must", "compliance"), stakeholder hints ("QA", "review", "security team"), explicit deliverables ("a11y", "rollback", "contracts").
2. Cluster signals into candidate focus areas (max 4), ranked by relevance.
3. Identify probable audience and timing (author, reviewer, QA, release) if not explicit.
4. Detect missing dimensions: scope breadth, depth/rigor, risk emphasis, exclusion boundaries, measurable acceptance criteria.
5. Formulate questions from these archetypes:
   - **Scope refinement**: "Should this include integration touchpoints with X and Y or stay limited to local module correctness?"
   - **Risk prioritization**: "Which of these potential risk areas should receive mandatory gating checks?"
   - **Depth calibration**: "Is this a lightweight pre-commit sanity list or a formal release gate?"
   - **Audience framing**: "Will this be used by the author only or peers during PR review?"
   - **Boundary exclusion**: "Should we explicitly exclude performance tuning items this round?"
   - **Scenario class gap**: "No recovery flows detected -- are rollback / partial failure paths in scope?"

**Question formatting rules:**
- If presenting options, generate a compact table: Option | Candidate | Why It Matters.
- Limit to A-E options maximum; omit the table if a free-form answer is clearer.
- Never ask the user to restate what they already said.
- If uncertain, ask explicitly: "Confirm whether X belongs in scope."

**Defaults when interaction is impossible:**
- Depth: Standard
- Audience: Reviewer (PR) if code-related; Author otherwise
- Focus: Top 2 relevance clusters

Output questions labeled Q1/Q2/Q3. After answers: if >=2 scenario classes (Alternate / Exception / Recovery / Non-Functional domain) remain unclear, ask up to TWO more targeted follow-ups (Q4/Q5) with a one-line justification each (e.g., "Unresolved recovery path risk"). Do not exceed five total questions. Skip escalation if user explicitly declines.

### Step 3: Understand User Request

Combine `$ARGUMENTS` + clarifying answers:
- Derive checklist theme (e.g., security, review, deploy, ux).
- Consolidate explicit must-have items mentioned by user.
- Map focus selections to category scaffolding.
- Infer missing context from spec/plan/tasks (do NOT hallucinate).

### Step 4: Load Feature Context

Read from FEATURE_DIR:
- `spec.md`: Feature requirements and scope.
- `plan.md` (if exists): Technical details, dependencies.
- `tasks.md` (if exists): Implementation tasks.

**Context loading strategy:**
- Load only portions relevant to active focus areas (avoid full-file dumping).
- Summarize long sections into concise scenario/requirement bullets.
- Use progressive disclosure: add follow-on retrieval only if gaps detected.
- For large source docs, generate interim summary items instead of embedding raw text.

### Step 5: Generate Checklist

Create the checklist as "Unit Tests for Requirements":

1. Create `FEATURE_DIR/checklists/` directory if it does not exist.
2. Generate unique checklist filename using a short descriptive name based on domain. Format: `[domain].md` (e.g., `ux.md`, `api.md`, `security.md`).
3. File handling:
   - If file does NOT exist: Create new file; number items starting from CHK001.
   - If file exists: Append new items, continuing from the last CHK ID (e.g., if last item is CHK015, start at CHK016).
   - Never delete or replace existing content -- always preserve and append.

**Core Principle -- Test the Requirements, Not the Implementation:**

Every checklist item MUST evaluate the REQUIREMENTS THEMSELVES for:
- **Completeness**: Are all necessary requirements present?
- **Clarity**: Are requirements unambiguous and specific?
- **Consistency**: Do requirements align with each other?
- **Measurability**: Can requirements be objectively verified?
- **Coverage**: Are all scenarios/edge cases addressed?

**Category structure -- group items by requirement quality dimensions:**
- Requirement Completeness (Are all necessary requirements documented?)
- Requirement Clarity (Are requirements specific and unambiguous?)
- Requirement Consistency (Do requirements align without conflicts?)
- Acceptance Criteria Quality (Are success criteria measurable?)
- Scenario Coverage (Are all flows/cases addressed?)
- Edge Case Coverage (Are boundary conditions defined?)
- Non-Functional Requirements (Performance, Security, Accessibility -- are they specified?)
- Dependencies and Assumptions (Are they documented and validated?)
- Ambiguities and Conflicts (What needs clarification?)

**How to write checklist items:**

WRONG (testing implementation):
- "Verify landing page displays 3 episode cards"
- "Test hover states work on desktop"
- "Confirm logo click navigates home"

CORRECT (testing requirements quality):
- "Are the exact number and layout of featured episodes specified?" [Completeness]
- "Is 'prominent display' quantified with specific sizing/positioning?" [Clarity]
- "Are hover state requirements consistent across all interactive elements?" [Consistency]
- "Are keyboard navigation requirements defined for all interactive UI?" [Coverage]
- "Is the fallback behavior specified when logo image fails to load?" [Edge Cases]
- "Are loading states defined for asynchronous episode data?" [Completeness]
- "Does the spec define visual hierarchy for competing UI elements?" [Clarity]

**Item structure:**
- Question format asking about requirement quality.
- Focus on what is WRITTEN (or not written) in the spec/plan.
- Include quality dimension in brackets: [Completeness/Clarity/Consistency/etc.]
- Reference spec section `[Spec S-X.Y]` when checking existing requirements.
- Use `[Gap]` marker when checking for missing requirements.

**Examples by quality dimension:**

Completeness:
- "Are error handling requirements defined for all API failure modes? [Gap]"
- "Are accessibility requirements specified for all interactive elements? [Completeness]"
- "Are mobile breakpoint requirements defined for responsive layouts? [Gap]"

Clarity:
- "Is 'fast loading' quantified with specific timing thresholds? [Clarity, Spec S-NFR-2]"
- "Are 'related episodes' selection criteria explicitly defined? [Clarity, Spec S-FR-5]"
- "Is 'prominent' defined with measurable visual properties? [Ambiguity, Spec S-FR-4]"

Consistency:
- "Do navigation requirements align across all pages? [Consistency, Spec S-FR-10]"
- "Are card component requirements consistent between landing and detail pages? [Consistency]"

Coverage:
- "Are requirements defined for zero-state scenarios (no episodes)? [Coverage, Edge Case]"
- "Are concurrent user interaction scenarios addressed? [Coverage, Gap]"
- "Are requirements specified for partial data loading failures? [Coverage, Exception Flow]"

Measurability:
- "Are visual hierarchy requirements measurable/testable? [Acceptance Criteria, Spec S-FR-1]"
- "Can 'balanced visual weight' be objectively verified? [Measurability, Spec S-FR-2]"

**Scenario classification and coverage (requirements quality focus):**
- Check if requirements exist for: Primary, Alternate, Exception/Error, Recovery, Non-Functional scenarios.
- For each scenario class, ask: "Are [scenario type] requirements complete, clear, and consistent?"
- If scenario class missing: "Are [scenario type] requirements intentionally excluded or missing? [Gap]"
- Include resilience/rollback when state mutation occurs: "Are rollback requirements defined for migration failures? [Gap]"

**Traceability requirements:**
- MINIMUM: >=80% of items MUST include at least one traceability reference.
- Each item should reference: spec section `[Spec S-X.Y]`, or use markers: `[Gap]`, `[Ambiguity]`, `[Conflict]`, `[Assumption]`.
- If no ID system exists: "Is a requirement and acceptance criteria ID scheme established? [Traceability]"

**Surface and resolve issues (requirements quality problems):**
- Ambiguities: "Is the term 'fast' quantified with specific metrics? [Ambiguity, Spec S-NFR-1]"
- Conflicts: "Do navigation requirements conflict between S-FR-10 and S-FR-10a? [Conflict]"
- Assumptions: "Is the assumption of 'always available podcast API' validated? [Assumption]"
- Dependencies: "Are external podcast API requirements documented? [Dependency, Gap]"
- Missing definitions: "Is 'visual hierarchy' defined with measurable criteria? [Gap]"

**Content consolidation:**
- Soft cap: If raw candidate items > 40, prioritize by risk/impact.
- Merge near-duplicates checking the same requirement aspect.
- If >5 low-impact edge cases, create one item: "Are edge cases X, Y, Z addressed in requirements? [Coverage]"

**PROHIBITED -- these make it an implementation test, not a requirements test:**
- Any item starting with "Verify", "Test", "Confirm", "Check" + implementation behavior
- References to code execution, user actions, system behavior
- "Displays correctly", "works properly", "functions as expected"
- "Click", "navigate", "render", "load", "execute"
- Test cases, test plans, QA procedures
- Implementation details (frameworks, APIs, algorithms)

**REQUIRED patterns -- these test requirements quality:**
- "Are [requirement type] defined/specified/documented for [scenario]?"
- "Is [vague term] quantified/clarified with specific criteria?"
- "Are requirements consistent between [section A] and [section B]?"
- "Can [requirement] be objectively measured/verified?"
- "Are [edge cases/scenarios] addressed in requirements?"
- "Does the spec define [missing aspect]?"

### Step 6: Structure Reference

Generate the checklist following the canonical template in `.specify/templates/checklist-template.md` for title, meta section, category headings, and ID formatting. If the template is unavailable, use: H1 title, purpose/created meta lines, `##` category sections containing `- [ ] CHK### <requirement item>` lines with globally incrementing IDs starting at CHK001.

### Step 7: Report

Output the full path to the checklist file, item count, and whether the run created a new file or appended to an existing one. Summarize:
- Focus areas selected
- Depth level
- Actor/timing
- Any explicit user-specified must-have items incorporated

**Note**: Each `/speckit.checklist` invocation uses a short, descriptive filename and either creates a new file or appends to an existing one. This allows:
- Multiple checklists of different types (e.g., `ux.md`, `test.md`, `security.md`)
- Simple, memorable filenames indicating checklist purpose
- Easy identification and navigation in the `checklists/` folder

To avoid clutter, use descriptive types and clean up obsolete checklists when done.

---

## Example Checklist Types and Sample Items

**UX Requirements Quality:** `ux.md`
- "Are visual hierarchy requirements defined with measurable criteria? [Clarity, Spec S-FR-1]"
- "Is the number and positioning of UI elements explicitly specified? [Completeness, Spec S-FR-1]"
- "Are interaction state requirements (hover, focus, active) consistently defined? [Consistency]"
- "Are accessibility requirements specified for all interactive elements? [Coverage, Gap]"
- "Is fallback behavior defined when images fail to load? [Edge Case, Gap]"
- "Can 'prominent display' be objectively measured? [Measurability, Spec S-FR-4]"

**API Requirements Quality:** `api.md`
- "Are error response formats specified for all failure scenarios? [Completeness]"
- "Are rate limiting requirements quantified with specific thresholds? [Clarity]"
- "Are authentication requirements consistent across all endpoints? [Consistency]"
- "Are retry/timeout requirements defined for external dependencies? [Coverage, Gap]"
- "Is versioning strategy documented in requirements? [Gap]"

**Performance Requirements Quality:** `performance.md`
- "Are performance requirements quantified with specific metrics? [Clarity]"
- "Are performance targets defined for all critical user journeys? [Coverage]"
- "Are performance requirements under different load conditions specified? [Completeness]"
- "Can performance requirements be objectively measured? [Measurability]"
- "Are degradation requirements defined for high-load scenarios? [Edge Case, Gap]"

**Security Requirements Quality:** `security.md`
- "Are authentication requirements specified for all protected resources? [Coverage]"
- "Are data protection requirements defined for sensitive information? [Completeness]"
- "Is the threat model documented and requirements aligned to it? [Traceability]"
- "Are security requirements consistent with compliance obligations? [Consistency]"
- "Are security failure/breach response requirements defined? [Gap, Exception Flow]"

---

## Anti-Examples

**WRONG -- testing implementation, not requirements:**

```markdown
- [ ] CHK001 - Verify landing page displays 3 episode cards [Spec S-FR-001]
- [ ] CHK002 - Test hover states work correctly on desktop [Spec S-FR-003]
- [ ] CHK003 - Confirm logo click navigates to home page [Spec S-FR-010]
- [ ] CHK004 - Check that related episodes section shows 3-5 items [Spec S-FR-005]
```

**CORRECT -- testing requirements quality:**

```markdown
- [ ] CHK001 - Are the number and layout of featured episodes explicitly specified? [Completeness, Spec S-FR-001]
- [ ] CHK002 - Are hover state requirements consistently defined for all interactive elements? [Consistency, Spec S-FR-003]
- [ ] CHK003 - Are navigation requirements clear for all clickable brand elements? [Clarity, Spec S-FR-010]
- [ ] CHK004 - Is the selection criteria for related episodes documented? [Gap, Spec S-FR-005]
- [ ] CHK005 - Are loading state requirements defined for asynchronous episode data? [Gap]
- [ ] CHK006 - Can "visual hierarchy" requirements be objectively measured? [Measurability, Spec S-FR-001]
```

**Key differences:**
- Wrong: Tests if the system works correctly
- Correct: Tests if the requirements are written correctly
- Wrong: Verification of behavior
- Correct: Validation of requirement quality
- Wrong: "Does it do X?"
- Correct: "Is X clearly specified?"
