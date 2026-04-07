# Reflective Development — Reframe Design Spec

**Date:** 2026-04-07

## Context

The project uses the term **Organic Development** to describe its development
paradigm — agents develop through real work, not configuration. While
"organic" captures the natural, non-prescriptive feel, it has become overloaded
(every SaaS landing page claims "organic growth") and doesn't capture what
actually makes Culture's approach distinctive.

This spec reframes **Organic Development** as **Reflective Development** — a
name that captures three concrete mechanisms at the heart of the project.

## Why "Reflective"

The word "reflective" carries three meanings, each mapping to a real mechanism
in Culture:

### 1. Self-reflection — agents and humans examining their own work

The lifecycle (Introduce → Educate → Join → Mentor → Promote) is built on
reflection. Mentoring means returning to an agent and reflecting on what changed.
Promote means reviewing an agent's track record — reflecting on its accuracy and
helpfulness. Agents on the mesh reflect on each other's findings (use case 04:
knowledge propagation). The observer reflects on the culture itself (use case 05).

This is the **culturing** sense — a community that grows by examining itself.

### 2. The documentation loop — generating docs, consuming them, growing

Culture's development process is inherently reflective: work produces
documentation (specs, plans, changelogs, CLAUDE.md updates). That documentation
becomes context for the next session. The agent reads what was written, reflects
it into new work, and produces more documentation. The project grows through
this reflective cycle.

This is the **NLM (Natural Language Memory)** sense — agents use generated docs
as durable memory. Each session reads the accumulated reflection of prior
sessions and extends it. The docs aren't a byproduct of development; they *are*
the development medium. A spec becomes a plan becomes code becomes a changelog
entry becomes context for the next spec.

### 3. Source-to-target reflection — the Assimilai pattern

The `packages/` directory contains reference implementations that are reflected
(copied, adapted) into target directories. Code reflects from source to target,
carrying knowledge across boundaries. When you improve a component in
`packages/`, you reflect that improvement to all backends. The pattern is
literally reflective: source mirrors into target.

This connects "Reflective Development" to the existing Assimilai pattern in
CLAUDE.md — code that reflects from reference to implementation.

## What Changes

### Terminology

| Current | New |
|---|---|
| Organic Development | Reflective Development |
| Organic Lifecycle | Reflective Lifecycle |
| "Simple, organic, transparent" (comparison table) | "Simple, reflective, transparent" |

### Conceptual Framing

The **Organic Development** section in README.md and docs/index.md currently
says:

> Culture follows the **Organic Development** paradigm — agents develop through
> real work, not configuration. The lifecycle is continuous, not graduated.

Replace with:

> Culture follows the **Reflective Development** paradigm — agents develop by
> reflecting on real work, not by configuration. Documentation flows back as
> context. Code reflects from reference to implementation. The lifecycle is
> continuous, not graduated.

This single sentence captures all three senses without belaboring them.

### CLAUDE.md — Assimilai Pattern

The current description uses "organic code":

> Internal packages are NOT installed as dependencies — they are assimilated
> into target projects as organic code

Replace "organic code" with "reflected code":

> Internal packages are NOT installed as dependencies — they are reflected
> into target projects as native code, placed in the correct folder and
> location as if written directly in the target project.

This aligns the Assimilai pattern language with Reflective Development. "Native
code" replaces "organic code" for the placement concept (it lives in the target
as if it were always there), while "reflected" captures the mechanism (it came
from the reference source).

## Files to Change

### README.md

- **Line 39:** Feature table row → `🎓 **Reflective Lifecycle** | Introduce → Educate → Join → Mentor → Promote. Members develop through real work, not configuration.`
- **Line 63:** Philosophy comparison → `Simple, reflective, transparent`
- **Lines 117–123:** Section heading + description:
  - `## Organic Development` → `## Reflective Development`
  - Replace description paragraph (see "Conceptual Framing" above)

### docs/index.md

- **Line 35:** Feature table row → `🎓 **Reflective Lifecycle** | Introduce → Educate → Join → Mentor → Promote. Members develop through real work, not configuration.`
- **Lines 113–121:** Section heading + description (same changes as README.md)

### CLAUDE.md

- **Line 14:** Replace "assimilated into target projects as organic code" with
  "reflected into target projects as native code"

### docs/superpowers/specs/2026-04-05-docs-speak-culture-design.md

- **Line 128:** Feature table → `Reflective Lifecycle` (currently says "keep —
  already good" for Organic Lifecycle)

### docs/superpowers/specs/2026-04-05-lifecycle-reframe-design.md

- **Line 142:** `Powered by **Organic Development**.` → `Powered by **Reflective Development**.`
- **Line 143:** Feature table row → `Reflective Lifecycle`
- **Line 147:** `Organic Development section` → `Reflective Development section`

### docs/superpowers/plans/2026-04-05-docs-speak-culture.md

- **Lines 564, 610, 612, 651, 686:** All references to "Organic Development"
  and "Organic Lifecycle" → "Reflective Development" / "Reflective Lifecycle"

## What Does NOT Change

- **The lifecycle itself** — Introduce → Educate → Join → Mentor → Promote is
  unchanged. The paradigm name changes, not the phases.
- **"organic" in non-paradigm contexts** — "emerged organically" in use case 09,
  "organically created" in the design spec for rooms — these describe emergent
  behavior and are fine. The reframe targets the formal paradigm name, not every
  use of the word "organic."
- **Assimilai pattern name** — stays "Assimilai." Only the description of what
  the code does (reflected vs organic) changes.
- **No code changes** — this is purely docs/framing.

## Future Consideration

A dedicated `docs/reflective-development.md` page could expand on the three
senses of "reflective" — self-reflection, the documentation loop, and
source-to-target reflection. This would give the paradigm a proper home beyond
the brief section in README.md. Out of scope for this reframe; noted for a
follow-up.

## Verification

1. **Grep scan:** Search all `.md` files for "Organic Development" and
   "Organic Lifecycle" — should only appear in historical specs/plans that
   describe the *previous* state (not as current terminology).
2. **Link integrity:** No files renamed, so no broken links.
3. **Markdownlint:** Run on all changed files.
4. **Read-through:** Read the README.md "Reflective Development" section and
   verify all three senses are implied without being heavy-handed.
