# AtMem dashboard design language

This is the canonical visual reference for the local AtMem dashboard
(`atmem/control/assets/app.{html,css,js}`). It exists so future changes stay
recognizably "AtMem" instead of drifting card-by-card. If you are about to add
a new section, button, or state to the dashboard, check here first.

## Who this page serves

The dashboard is read by four different people, often in the same week:

| Persona | What they came for | What they must never have to do |
|---|---|---|
| **New user** | "Is this safe to turn on?" | Read a spec before trusting the first screen |
| **Power user** | "What changed since I last looked, and can I ask my memory something right now?" | Hunt through a long page for the one thing that matters |
| **Manager** | "Is everything under control, in one glance?" | Parse a hash chain or a storage diagram |
| **Auditor** | "Prove it." | Trust an unverifiable claim, or lose a thread mid-investigation |

Every layout and component decision below serves one of these first. If a
change makes the page prettier but harder for one of these four, it's the
wrong change.

## Principles

1. **One signal, not five.** A user should be able to tell "is everything
   fine?" from a single element, not by reconciling a header chip, a banner,
   a card, and a badge that could disagree. The status banner is the single
   source of truth for "is everything OK" on the whole page.
2. **Memory-first, not database-first.** Storage diagrams, hash chains, and
   record categories are real and important, but they are *evidence*, not
   *status*. They live in the Evidence view, one click away — never on the
   page a manager glances at.
3. **Progressive disclosure.** Show the headline. Let the reader open the
   technical detail. Every card should be understandable from its heading and
   first line alone; the `<details class="technical">` pattern already used
   in the audit drawer is the model for the rest of the page.
4. **Consistent, not decorative.** One icon means one thing, everywhere. A
   checkmark never means "approved" in one card and "verified" in another —
   it always means "this is good." Reuse over invention.
5. **Calm.** No walls of text, no more than one accent color fighting for
   attention on screen at once. Motion is used only to communicate state
   (loading, thinking) — never for flourish.

## The memory mark

AtMem's memory motif is three linked nodes — a small cluster, not a literal
brain. It reads as "connected recall" without being a cliché organ icon, and
it scales down to a loading dot or up to an empty-state illustration without
losing meaning.

```
      ●            the memory mark (`#i-node` in the icon sprite)
     ╱ ╲            apex node = the question / the model turn
    ●───●           base nodes = the memories that answer it
```

It appears in exactly three places, deliberately not more:
- the eyebrow of the memory-chat hero ("Ask governed memory")
- every loading indicator (as three pulsing dots — see Motion)
- empty states, dimmed, where there is nothing to show yet

It is never used as a generic decorative bullet. If you want a bullet, use
the `.eyebrow:before` dot instead.

## Color

Built on the existing token set in `app.css` (`light-dark()`-based, one
definition per token, no duplicated theme blocks — keep it that way).

| Token | Role | Use it for |
|---|---|---|
| `--ink` / `--muted` / `--line` | Text and structure | Body copy, borders |
| `--card` / `--card-raised` / `--bg` | Surfaces | Cards sit on `--card`; the memory-chat hero and chat bubbles sit one step up on `--card-raised` |
| `--brand` / `--brand-soft` | Chrome and primary actions | Buttons, active tab, eyebrow pills |
| `--good` / `--warn` / `--bad` (+ `-soft`) | **Status only** | Verified/healthy, needs review, failed. Never used decoratively |
| `--signal` / `--signal-soft` (new) | **AtBot / memory intelligence only** | The companion chip, the chat composer focus ring, the memory mark. This is the one color reserved for "this came from AI reasoning, not raw governance state" — keeping it scarce is what makes it memorable |
| `--danger-action` | Destructive confirmation | Restore/reject buttons only |

Rule: if you're tempted to add a new color, check whether `--signal` or a
status color already means what you want first. A new hue is a last resort,
not a first instinct.

## Typography

System stack, no web fonts (the dashboard is offline-first and loopback-only
by design — see `ui.py`'s docstring). One scale, used consistently:

| Role | Size / weight | Where |
|---|---|---|
| Hero headline | `clamp(28px,4vw,48px)` / 800 | Memory-chat question only |
| Page title (`h1` in `.pageheading`) | 34px / 800, `-0.04em` tracking | One per view |
| Card title (`h2`) | 19px / 770 | Every card |
| Body | 14px / 1.5 | Default |
| Eyebrow / label | 10.5px / 800, uppercase, `0.08em` tracking | Section context, never more than one per card |
| Mono | `ui-monospace` stack | IDs, hashes, paths — anything a reader might copy |

## Iconography

A single hand-drawn stroke-icon set lives inline in `app.html` as an SVG
`<symbol>` sprite (`#i-*` ids) — no external icon font, no network request.
Every icon is 24×24, 1.75px stroke, round caps/joins, `currentColor`.

Static markup icons (placed with `<svg class="icon"><use href="#i-name"/></svg>`):

| Icon | Meaning | Used in |
|---|---|---|
| `i-node` | Memory / AtMem itself | Chat hero eyebrow |
| `i-grid` | Status | Status tab |
| `i-flag` | Needs a decision | Decisions tab, review card |
| `i-shield-check` | Evidence / verified | Evidence tab, audit card |
| `i-search` | Search | Memory search card |
| `i-archive` | Recorded sessions | Black Box archive card |
| `i-pulse` | Recent activity | Activity feed |
| `i-users` | Agents & workspaces | Agent overview |
| `i-database` | Storage | Storage overview |
| `i-link` | Audit chain | Chain / integrity chips |
| `i-download` | Export | Export links |
| `i-power` | Activate / restore | Switch button |
| `i-chevron-right` | Drill in | Section nav |
| `i-sun` / `i-moon` | Theme | Theme toggle |

State icons (only two exist, applied via CSS `mask-image` so JavaScript never
has to know about icons — it only ever toggles the existing `.bad` / `.warn`
/ `.pending` classes it already toggles, and CSS paints the right icon):

- **check** — everything in this row/card/banner is good.
- **alert** — this needs a look. Color (amber vs. red) carries severity;
  the shape never changes. One "something's off" glyph, not three.

Never introduce a third state icon. If a new state doesn't fit good/attention,
it's a copy problem, not an icon problem — write a clearer headline instead.

## Motion

- **Loading**: three dots (built on the memory mark), staggered pulse,
  ~1.1s cycle. This is the *only* loading indicator in the product — the
  chat "thinking" indicator and every inline loading state use the same
  animation, just resized. Respect `prefers-reduced-motion`.
- **Transitions**: 120–150ms ease on hover/focus/tab changes. Nothing longer.
- **No entrance animations** on page load beyond the existing tab fade — a
  professional tool should feel instantly present, not choreographed.

## Layout

### Views, not scroll depth

Three tabs — **Status, Decisions, Evidence** — map directly to the three
questions in the persona table. Nothing is duplicated across them: a card
lives in exactly one view, chosen by what job it does, not by when it was
added.

- **Status**: is everything OK, right now? Status banner, agent coverage,
  recent activity. Nothing that requires interpreting a hash or a diagram.
- **Decisions**: what's waiting on me? Activation/restore, the review queue,
  the readiness checklist.
- **Evidence**: prove it. Search first, then sessions, storage, and the full
  audit trail — all technical detail lives here, behind a click, never on
  Status.

### Card anatomy

Every card follows the same skeleton:

```
[icon] EYEBROW                    ← optional, one per card, uppercase
Card title                         ← h2, always present
One sentence of sub-copy           ← .sub, optional but preferred
[ the card's actual content ]
```

Cards that are reference material rather than daily-glance status (storage
diagrams, record-category breakdowns, the static "what changes" explainer)
are wrapped in `<details>` so they're available but collapsed by default —
present for the auditor, invisible to everyone else.

### Spacing

8px grid. Card padding 24px, gaps between stacked cards 20–22px, gaps inside
a card's internal grid 8–12px. Don't introduce an odd value without a reason.

## Voice

Short sentence, then one supporting line if needed. No exclamation points.
State the fact, then the one thing the reader can do about it
("N memories need your decision" → "Review memories"). This is already the
pattern in `updateStatusBanner()` — keep extending it, don't regress to
paragraphs.

## Extending this system

Adding a new card? Answer these before writing markup:

1. Which of the three views does this belong to — Status, Decisions, or
   Evidence? (If you're unsure, it's Evidence.)
2. Does it need progressive disclosure (`<details>`), or is it genuinely
   glanceable?
3. Which existing icon already means what you need? (Don't add a new one
   unless none of the sprite's icons fit.)
4. Does its "OK" / "needs attention" state map to the existing check/alert
   pattern, or are you inventing a third state? (Don't.)

This document should be updated in the same change that changes the system
it describes — a design language nobody updates is just a screenshot of a
decision that already rotted.
