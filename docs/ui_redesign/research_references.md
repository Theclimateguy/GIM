# UI/UX Reference Research for GIM17 Redesign

**Goal:** Extract concrete, reusable UI/UX patterns for redesigning the interface of GIM17 (a geopolitical world-simulation model) for a *decision-maker* (ЛПР) and lay users — not analysts/engineers. Target: a clean, native, immediately-understandable, single-operator local desktop web app with a **dark, restrained** aesthetic, capable of scenario exploration including LLM-role-played countries (e.g. an LLM given context to behave like Trump, playing as the USA).

This document characterizes nine reference classes, then synthesizes them into **A. Principles**, **B. Concrete UI patterns**, **C. Anti-patterns**, **D. Look-&-feel notes**, plus a **Sources** list.

---

## Part 1 — Reference tools, characterized

### 1. Climate Interactive **En-ROADS** / **C-ROADS** — the gold standard
- **What it is:** A real-time, system-dynamics climate-policy simulator. Built by Climate Interactive + MIT Sloan + Ventana Systems. The reference design for "decision-maker explores a complex model on one screen."
- **Audience:** Policymakers, C-suite/boards, investors, advocates, educators, general public. Explicitly "simple enough for anyone to explore without significant training."
- **Layout (studied carefully):**
  - **Single screen, no scrolling required.** Two large graphs side-by-side at top (default: *Global Sources of Primary Energy* and *Greenhouse Gas Net Emissions*), plus a prominent **textual temperature readout** ("expected temperature increase by 2100", e.g. 3.3 °C) as the single headline number.
  - **~19 action sliders** grouped by category (energy supply: coal/oil/gas/renewables/nuclear; energy efficiency; electrification; land use; non-CO₂ GHGs), arranged down the sides of the central graphs.
  - **Every chart draws two lines: Baseline vs. Current scenario** — so the user always sees "what I changed" against "what would have happened." This is the single most important comprehension device.
  - **Instant feedback:** graphs and the temperature number recompute *live as the slider is dragged* (no "Run" button for the basic loop). A **"Replay Last Change"** control re-animates the most recent edit so the cause→effect is legible.
- **Patterns that make it work for non-experts:**
  1. **One headline metric** (°C by 2100) anchors everything — you always know "am I winning?"
  2. **Baseline-vs-current dual line on every graph** — change is always shown relative to a reference.
  3. **Live recompute on drag** — manipulate-and-see, zero round-trips, no run-config step.
  4. **Progressive disclosure:** each slider is a simple single handle by default; "advanced settings" (start/end year, stringency, three-dots menu, detail graph) are hidden behind a disclosure triangle / kebab menu.
  - **Scenario presets & sharing:** scenarios are a first-class object — share a **scenario link** that reopens with all slider settings + the last graphs viewed; compare your scenario vs. NDCs vs. Baseline.
- **One thing to avoid:** Even En-ROADS has 100+ available output graphs; it avoids overwhelm by **defaulting to two** and tucking the rest behind the graph-title picker. Do not expose the full output catalog up front.

### 2. **Our World in Data**, **Gapminder** (Hans Rosling), **Dollar Street**
- **What:** Tools/portals that make global statistical data legible. Gapminder's animated bubble chart (Trendalyzer); Dollar Street replaces abstract income numbers with **photographs of real homes** sorted by income.
- **Audience:** General public, students, journalists, classrooms — "fight global misconceptions."
- **Patterns:**
  1. **Sensible defaults + one obvious story first:** the chart opens on a curated, meaningful view (not a blank query builder); exploration is optional, layered on top.
  2. **Concrete over abstract** (Dollar Street): translate a number (income) into a tangible, human image. For GIM17: translate index values into plain consequences ("bread costs X", "border closes").
  3. **Animation as narrative** (Gapminder play button): time advances and bubbles move — the *trajectory* is the insight, not the snapshot.
  4. **Color = a stable categorical encoding** (region/continent) reused everywhere, so the eye learns it once.
- **Avoid:** Do not require the user to pick axes/encodings before they see anything. Lead with a story, let them deviate.

### 3. Bret Victor / **Nicky Case** explorable explanations
- **What:** Interactive model storytelling — *The Evolution of Trust* (game theory), *Parable of the Polygons* (Schelling segregation). explorabl.es.
- **Audience:** Curious lay readers; the explicit aim is "help people understand complex systems."
- **Named design patterns (directly reusable):**
  - **Ladder of abstraction / concrete-first:** "start on the ground — give the reader a concrete experience" (drag shapes, play a round) *before* any abstraction or parameter.
  - **Logical-connective pacing ("therefore / but"):** chain ideas with narrative causality and plot twists, not a settings list. Reveal complexity one step at a time (low cognitive load through iterative revelation).
  - **"Place Your Bets":** make the user predict the outcome *before* revealing it — the real result lands harder and is remembered.
  - **"Role Play":** put the reader in the decision-maker's seat in a scenario with no clear right answer — exactly GIM17's "play as a country" frame.
  - **Sandbox Mode (always last):** after the guided path, hand over an open simulator with the user's own questions — but ease in from the "shallow end," never open on a full sandbox.
- **Avoid:** Opening cold on a complex free sandbox. Guide first, free-explore second.

### 4. NYT / FiveThirtyEight / The Upshot election & policy interactives
- **What:** "The Needle" (live election-night gauge), live forecast dials, "build-your-own" budget/electoral-map tools.
- **Audience:** Mass news readers under stress, non-statisticians.
- **Patterns:**
  1. **Plain-language probability:** the Needle pairs the number with words — 65% becomes "**likelier than not**." Always gloss probability in words for ЛПР.
  2. **A single, glanceable verdict object** (a gauge/needle) that maps a complex model to one position on a scale.
  3. **"Build your own":** let the reader flip swing states / move budget line-items and watch the headline total update — agency creates understanding.
- **Avoid (a real, documented failure):** the 2016 Needle's **jitter/quiver animation** (meant to show margin of error) read as panic, not uncertainty. **Do not animate uncertainty as nervous motion.** Show ranges as static bands and words instead.

### 5. **PolicyEngine** (+ Tax Foundation / IMF / OECD / World Bank dashboards)
- **What:** Open-source tax-benefit microsimulation; design a reform, see population- and household-level effects.
- **Audience:** Non-economists, journalists, advocates, and (separately) researchers — a deliberately **multi-tier** product.
- **Patterns:**
  1. **Two altitudes, one model:** a simple "household calculator" path for novices and a full "population reform" path for experts, sharing one engine. (GIM17: a "quick scenario" mode vs. "advanced.")
  2. **Before/After is the core view:** results land you straight on a *Net income* page showing with-reform vs. without-reform.
  3. **Drill-down on demand ("expand to trace the change"):** the top-line answer is shown first; the user can expand sections to see *why* the number changed. Explanation is pull, not push.
  4. **Reform-as-shareable-object:** a reform/"blueprint" is a URL you can hand to someone to reproduce the exact run.
- **Avoid:** Forcing novices through the researcher-grade configuration. Default to the simplest viable path.

### 6. Epidemic simulators — **Gabriel Goh "Epidemic Calculator"**
- **What:** Browser SEIR model; sliders (R₀, incubation, etc.) → live epidemic curves.
- **Audience:** Pandemic-era general public + press.
- **Patterns:**
  1. **Sliders → curve, instantly, on one screen** (same core loop as En-ROADS).
  2. **Make sensitivity visible:** the demo's whole point is "move R₀ from 2.2 to 2.6 and watch peak load jump by thousands" — the tool teaches *how sensitive* the system is. GIM17 should let the user feel which levers are knife-edge.
  3. **Log/linear and annotation toggles** for the same data without leaving the page.
- **Avoid:** Exposing every epidemiological parameter with equal visual weight — it flattens the few that actually matter.

### 7. War-gaming / strategy: **Democracy 4**, Civilization, Crusader Kings / Hearts of Iron, **Meta CICERO**
- **Democracy 4** — *the* model for "everything affects everything else":
  - Main screen is a **node graph of policies and their causal links** — no map; the message is "A→B→C→back to A."
  - **Policy icons as radial dials:** a circular segmented outline shows how much you *can* push a slider given available **political capital** (cost shown as clockwise segments for +, anticlockwise for −). The *cost/affordability of an action is encoded in the control itself.*
  - **Honest uncertainty:** the new-policy screen gives *hints* about effects on each voter group, "but not exact details… you won't really know until you try." A model that admits it can't perfectly predict.
  - **Advisors** as an onboarding "guiding hand" for the first hour.
- **Paradox games (CK/HOI/Civ):** "play as a nation" via a **diplomacy screen** (per-actor relationship + available actions toward that actor) and **decision cards** (discrete, optional, contextual actions surfaced when relevant) plus **advisor slots**. Decisions are framed as cards with cost/effect, not buried in menus.
- **Meta CICERO** (AI playing Diplomacy) — *the key reference for an AI playing an actor*:
  - The AI's persona is **surfaced entirely as in-character chat**: it negotiates, reassures allies, discusses strategy, even chit-chats, in natural language addressed to other players.
  - Under the hood it's **intent-controlled dialogue**: a strategic engine computes an "intent" (planned move), and the language model is *conditioned on that intent* so its words and its actions stay consistent. For GIM17: the LLM-country should have a visible **declared intent / posture** that its messages are generated from — never free-floating chatter.
  - A **human-compatibility constraint** keeps it from drifting into alien behavior. Lesson: give the persona explicit guardrails/character so it stays legible.
- **Patterns to take:**
  1. **Decision cards** — discrete, contextual, cost-and-effect-on-the-face actions.
  2. **Per-actor diplomacy panel** — one screen per counterpart showing stance + available moves.
  3. **Cost encoded in the control** (Democracy 4 radial capital segments).
  4. **AI actor = declared intent + in-character message** (CICERO), so the user can read *what it's trying to do* alongside *what it says*.
- **Avoid:** Democracy 4's full node-spaghetti as the *first* screen for a lay user — it's iconic but intimidating; reserve the causal-graph view as an optional "explain" layer.

### 8. **Bloomberg Terminal** — explicit ANTI-pattern
- **What:** The dense, command-driven financial workstation. ~30,000 functions; 4-letter function codes; keyboard-first, mouse-optional; multi-panel amber/black density.
- **Why it intimidates:** "intimidating," "easy to feel lost"; **3–6 months** to proficiency; most users touch ~20% of it. The grammar of cryptic codes (`GP`, `WEI`, …) is a *learned expert language* — fast for pros, a wall for newcomers. Its tradeoff is explicit: **speed + information-per-screen + keyboard control, at the expense of discoverability and visual minimalism.**
- **Anti-patterns to avoid in GIM17:**
  - Cryptic command codes / memorized invocations instead of visible affordances.
  - Maximum information density per screen as a default.
  - Discoverability sacrificed for expert speed.
  - Many small panels competing for attention with equal weight.
  - A long mandatory learning curve before first useful result.
- **The one thing worth stealing:** Bloomberg *does* "conceal complexity" behind a consistent grammar — but for ЛПР the equivalent is **progressive disclosure + plain labels**, not a code language.

### 9. AI persona / character-card UIs — **character.ai**, **SillyTavern**, AI Dungeon
- **What:** Config screens for defining an AI role-play persona.
- **character.ai fields (clean, minimal):** **Name, Avatar, Tagline (one-line subtitle), Greeting (first message), Tags, Description, Definition (behavior/rules).** A persona is presented to the user as a **card**: avatar + name + one-line tagline sets the tone *before* any chat.
- **SillyTavern fields:** Name (only required), **Description** (always-in-prompt facts/world), **Personality**, **First Message** (sets style/length — the model imitates it most), **Scenario** (initial context), **Example Messages**; **Advanced Definitions** (token limits, system prompt) hidden behind an "Advanced" button. Personas are browsed in a **gallery of cards**.
- **Patterns to take:**
  1. **Persona = a card** (avatar + name + one-line tagline) — selectable from a gallery, legible at a glance.
  2. **A small fixed set of fields**, not a free-form prompt box: identity, behavior/rules, opening posture, scenario context.
  3. **The "first message" sets the voice** — define the actor's opening declaration to anchor its style.
  4. **Advanced (raw system prompt / limits) hidden behind a disclosure** — novices never see it.
- **Avoid:** A single giant free-text "system prompt" as the only configuration surface. Structure the persona into named, guided fields.

---

## A. Top design principles (ranked) for a decision-maker simulation UI

1. **One screen, one headline metric.** Anchor the whole UI on a single glanceable verdict (En-ROADS °C-by-2100; NYT Needle). *[En-ROADS, NYT Needle]*
2. **Manipulate-and-see, live.** The default loop is drag-a-control → graph/number updates instantly; no run-config ceremony for basic exploration. *[En-ROADS, Epidemic Calculator]*
3. **Always show change against a baseline.** Every result is "current vs. baseline/before vs. after," never an absolute in a vacuum. *[En-ROADS dual line, PolicyEngine before/after]*
4. **Concrete before abstract.** Open with a tangible experience or plain-language consequence, not parameters. *[Nicky Case ladder-of-abstraction, Dollar Street, Gapminder]*
5. **Progressive disclosure.** Simple control by default; advanced settings behind a disclosure triangle / "Advanced" button / kebab. *[En-ROADS sliders, SillyTavern Advanced, character.ai Definition]*
6. **Sensible defaults + one story first; sandbox last.** Open on a curated meaningful view, ease the user in, hand over the free sandbox only at the end. *[Gapminder defaults, Nicky Case Sandbox-from-shallow-end]*
7. **Probability in plain words, uncertainty shown calmly.** Gloss every probability ("likelier than not"); show ranges as static bands, never nervous animation. *[NYT Needle plain language; 2016 jitter anti-pattern]*
8. **Explanation is pull, not push.** Show the top-line answer; let the user expand to trace *why* it changed. *[PolicyEngine "expand to trace the change"; Democracy 4 hints]*
9. **Scenarios/personas/reforms are first-class, shareable, reproducible objects** (a link / a card that reopens the exact state). *[En-ROADS scenario links, PolicyEngine blueprints, character.ai cards]*
10. **Make sensitivity feel-able.** Let the user discover which levers are knife-edge by moving them. *[Epidemic Calculator R₀ demo, Democracy 4 interconnections]*
11. **Honest about model limits.** Surface that effects are estimates, not certainties — it builds trust with sophisticated ЛПР. *[Democracy 4 "you won't really know until you try"]*
12. **Stable, learned-once visual grammar.** One categorical color scheme, consistent control shapes, reused everywhere. *[Gapminder region colors; Bloomberg's consistency — minus the cryptic codes]*

## B. Concrete UI patterns (grouped)

**(1) Scenario setup / presets**
- **Preset gallery as cards** (title + one-line description + thumbnail), à la character.ai persona cards / Gapminder curated views. Click = load full state.
- **A short "quick scenario" path vs. an "advanced" path** sharing one engine (PolicyEngine two-tier).
- Scenario is a **named, shareable object** with a link that restores every setting + the last view (En-ROADS).

**(2) "What-if" controls & live feedback**
- **Grouped sliders by category** (En-ROADS), each a single handle by default; numeric direct-entry on click; detail/start-end/stringency behind a disclosure triangle.
- **Live recompute on drag**; **"Replay last change"** to re-animate the most recent edit's effect (En-ROADS).
- **Cost-encoded controls** where an action has a budget (Democracy 4 radial political-capital segments) — show what you *can afford* in the control itself.

**(3) Running / progress**
- For the fast inner loop, **no explicit run step** (live). For an expensive LLM turn, show an honest **per-actor "thinking/declaring intent" indicator** rather than a generic spinner (CICERO intent → message).
- Turn-based pacing surfaced as a clear **"advance turn"** action, with the world-state delta highlighted after (Gapminder time-step + En-ROADS replay).

**(4) Results & decision-brief presentation**
- **One headline number/verdict** up top (°C / Needle gauge).
- **Two charts max by default**, the rest behind a title picker (En-ROADS).
- **Before/after as the spine**; **expand-to-trace-why** sections beneath the headline (PolicyEngine).
- Translate raw indices into **plain consequences** (Dollar Street concreteness).

**(5) Uncertainty / probability visualization**
- **Number + plain-language gloss** ("likelier than not"); a single gauge for the top-line verdict.
- **Static range bands / fan charts**, NOT animated jitter (NYT 2016 anti-pattern).
- Optionally **"Place your bets"**: ask the ЛПР to predict before revealing (Nicky Case) — strong for briefings.

**(6) Comparison of runs / scenarios**
- **Overlay current vs. baseline vs. a saved scenario** on the same axes (En-ROADS dual/triple line).
- **Side-by-side scenario cards** with their headline metrics for quick A/B.
- Saved scenarios shareable/reproducible via link (En-ROADS / PolicyEngine).

**(7) "Play as an actor" + AI-persona configuration** *(the core GIM17 differentiator)*
- **Actor = a card:** avatar/flag + name + one-line tagline (e.g. "USA — Trump persona: transactional, unpredictable, base-first") — selectable from a gallery (character.ai / SillyTavern card model).
- **A small fixed set of persona fields, not one prompt box.** Map directly onto WarAgent's country-profile schema, which is purpose-built for LLM nation-agents:
  - **Leadership / political system & leader traits** (the "Trump persona" lives here)
  - **Military capability**, **Resources** (GDP/population/geography), **Historical background** (grievances/alliances), **Key policy / strategic objective**, **Public morale**.
  - Plus character.ai/SillyTavern fields: **Greeting / opening declaration** (sets the actor's voice), **rules/guardrails** (Definition), **Advanced raw system prompt** behind a disclosure.
- **Declared intent alongside in-character message (CICERO):** for each AI turn, show the actor's **posture/intent** ("seeking alliance with X; pressuring Y") next to the **message it sends**, so the ЛПР reads goal *and* rhetoric. Keep generated dialogue conditioned on that intent so words and moves stay consistent.
- **Per-actor diplomacy panel:** one panel per counterpart showing current stance/relationship and the **available moves toward that actor** (Paradox diplomacy screen).
- **Decision cards:** discrete, contextual actions with cost+effect on the face of the card, surfaced when relevant (Paradox decisions) — better than menu trees.
- **Observable vs. secret state** (WarAgent Board/Stick + partial knowledge): show the ЛПР what an actor *publicly* knows vs. its private state — a clean way to model fog-of-war and keep the screen honest.

## C. Anti-patterns (what makes analyst tools intimidating)

- **Cryptic command codes / memorized invocations** instead of visible, labeled affordances (Bloomberg function codes).
- **Maximum information density by default** — many equal-weight panels competing for attention (Bloomberg).
- **Discoverability sacrificed for expert speed**; a multi-month learning curve before a first useful result (Bloomberg 3–6 months).
- **Blank query-builder / "pick your axes first"** before the user sees anything meaningful (the opposite of Gapminder defaults).
- **Opening cold on a full free sandbox** with no guided on-ramp (violates Nicky Case "shallow end first").
- **Uncertainty rendered as nervous animation** (NYT 2016 Needle jitter) — reads as panic, erodes trust.
- **Exposing every parameter with equal visual weight**, hiding which 3 levers actually matter (Epidemic Calculator counter-example).
- **A single giant free-text system-prompt box** as the only persona config (vs. structured character-card fields).
- **The full causal node-graph as the first screen** for a lay user (Democracy 4 spaghetti) — keep it as an optional "explain" layer.
- **Run-configuration ceremony** (forms, modal dialogs, "Run" buttons) blocking the fast manipulate-and-see loop.
- **Absolute numbers with no baseline/reference** — change must always be shown relative to something.

## D. Look-&-feel notes (the best examples' tendencies)

1. **Restrained palette, one categorical color system learned once.** Gapminder reuses region colors everywhere; En-ROADS keeps charts to a small consistent set (baseline vs. current as two clearly distinct lines). For a **dark** GIM17: near-black background, 1–2 accent hues for "current" vs. a muted grey for "baseline," reserve saturated color for the single headline verdict and for per-actor identity (flags/accent per country). Avoid Bloomberg's amber-on-black high-density wall.
2. **Generous typographic hierarchy with one dominant number.** The best tools (En-ROADS °C, NYT Needle) make **one big number/verdict** typographically dominant, with charts secondary and controls tertiary. Clean sans-serif, plenty of negative space — the opposite of terminal density. (GIM17 already uses DejaVu sans for its paper; a humanist sans for UI fits.)
3. **Single-screen, two-pane, no-scroll layout with progressive disclosure.** Controls down the side(s), 1–2 large charts center, headline metric pinned top; everything else (advanced settings, extra graphs, raw persona prompt, causal-graph "explain" view) tucked behind disclosure triangles, kebab menus, and an "Advanced" button. Calm, native, immediately legible.

---

## Sources

**En-ROADS / C-ROADS**
- https://www.climateinteractive.org/en-roads/
- https://docs.climateinteractive.org/projects/en-roads/en/latest/guide/tutorial.html
- https://docs.climateinteractive.org/projects/en-roads/en/latest/guide/baseline.html
- https://en-roads.climateinteractive.org/
- https://mitsloan.mit.edu/ideas-made-to-matter/digital-tool-helps-business-leaders-visualize-climate-actions
- https://www.nature.com/articles/s44168-026-00348-4 (En-ROADS spurs climate action among decision-makers)
- https://medium.com/agile-outside-the-box/visualizing-possible-world-climate-futures-with-en-roads-80168229a4e2

**Our World in Data / Gapminder / Dollar Street**
- https://www.gapminder.org/
- https://www.gapminder.org/dollar-street/about
- https://link.springer.com/chapter/10.1007/978-3-031-20748-8_8 (Gapminder Tools in action)

**Explorable explanations (Nicky Case / Bret Victor)**
- https://blog.ncase.me/how-i-make-an-explorable-explanation/
- https://blog.ncase.me/explorable-explanations-4-more-design-patterns/
- https://ncase.me/projects/

**NYT / FiveThirtyEight / Upshot election interactives**
- https://www.poynter.org/tech-tools/2024/ny-times-election-needle/
- https://reutersinstitute.politics.ox.ac.uk/news/moving-needle-how-new-york-times-aims-guide-readers-through-americas-most-uncertain-election
- https://www.fastcompany.com/90459366/the-most-hated-data-visualization-in-politics-is-back-to-spike-your-blood-pressure
- https://flowingdata.com/2018/03/14/needle-of-uncertainty/

**PolicyEngine**
- https://www.policyengine.org/us
- https://www.policyengine.org/uk/research/from-idea-to-impact-scoring-a-policy-reform-on-the-new-policyengine-uk
- https://www.citizencodex.com/case-studies/transforming-tax-policy-analysis-with-policyengine

**Epidemic Calculator**
- https://gabgoh.github.io/COVID/
- https://news.ycombinator.com/item?id=22593996

**War-gaming / strategy / AI agents**
- https://www.positech.co.uk/cliffsblog/2019/11/09/democracy-4-gui-update/ (Democracy 4 GUI)
- https://www.jumpdashroll.com/article/first-impressions-democracy-4
- https://ai.meta.com/research/cicero/ (Meta CICERO)
- https://ai.meta.com/blog/cicero-ai-negotiates-persuades-and-cooperates-with-people/
- https://arxiv.org/html/2403.13433v2 (WarAgent: LLM multi-agent world-war simulation — country-profile schema)
- https://arxiv.org/html/2407.06813v1 (Richelieu: self-evolving LLM agents for AI Diplomacy)
- https://arxiv.org/pdf/2401.03408 (Escalation risks from LLMs in military/diplomatic decision-making)

**Bloomberg Terminal (anti-pattern)**
- https://www.bloomberg.com/company/stories/how-bloomberg-terminal-ux-designers-conceal-complexity/
- https://nownews.dev/blog/bloomberg-terminal-alternatives-2026 (learning-curve comparison)
- https://news.ycombinator.com/item?id=19153875

**AI persona / character-card UIs**
- https://book.character.ai/character-guide/user-personas
- https://support.character.ai/hc/en-us/articles/50608794517915-1-Welcome-to-the-Creator-Guide (Name/Avatar/Greeting/Tags/Description/Definition)
- https://docs.sillytavern.app/usage/core-concepts/characterdesign/
- https://shapes.inc/geopoliticalsim (commercial geopolitical role-play assistant)
