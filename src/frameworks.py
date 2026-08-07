#!/usr/bin/env python3
"""frameworks.py — narrative architectures and hook patterns for the generator.

`archetype` decides how a slide LOOKS (which template renders it). `framework`
decides how the deck ARGUES — the reason a reader keeps swiping. They are
orthogonal: a stat deck can be a Problem-Proof or a Value-Stack.

Adapted from the carousel frameworks in coreyhaines31/marketingskills
(skills/social/references/carousel-frameworks.md). The structures are kept; the
consumer/growth tone is not — everything here is re-pitched for AGENT.md rule 7
(enterprise-calm, no hype, no emojis, no exclamation marks) and for an executive
buyer rather than a founder audience.
"""

# framework -> (archetypes it suits, prompt block)
FRAMEWORKS = {
    "problemproof": (
        ("stat", "insight"),
        "FRAMEWORK: PROBLEM-PROOF. The deck opens with a claim and closes with the receipt; "
        "everything between explains the mechanism. The open loop is the engine — the reader swipes "
        "to find out whether the proof is real.\n"
        "- Cover: a specific claim, ideally carrying a number. A result, not advice.\n"
        "- Slide 2: reframe the problem. Name what is ACTUALLY going wrong, so the reader recognises "
        "their own organisation in it.\n"
        "- Middle slides: the mechanism. Named steps, named roles, named controls. Concrete beats vague.\n"
        "- Final content slide before the cta: the proof — the measurable outcome that closes the loop "
        "the cover opened.\n"
        "Failure mode: vague mechanism slides ('optimise your workflow'). If the middle does not name "
        "specifics, the proof reads as luck rather than a system. Use Zylo's real figures only "
        "(+85% operational efficiency, 3x faster deployment, -40% manual processes, 50+ companies); "
        "never invent a statistic."
    ),
    "hacklist": (
        ("insight", "stat"),
        "FRAMEWORK: HACK LIST. A contrarian opening, then numbered techniques that each re-earn the "
        "swipe on their own.\n"
        "- Cover: a claim implying most organisations get this wrong.\n"
        "- Slide 2: why the common approach fails.\n"
        "- Middle slides: one NAMED technique per slide. Naming is mandatory — 'the two-week rule' or "
        "'the reversibility test' travels and gets repeated; 'plan carefully' does not. Use the kicker "
        "for the number, the title for the name of the technique.\n"
        "- Close: one line of synthesis tying the techniques together, then the cta.\n"
        "Failure mode: techniques that are restatements of each other. Every slide must survive alone; "
        "if two collapse into one idea, merge them and ship a shorter deck."
    ),
    "valuestack": (
        ("insight", "stat"),
        "FRAMEWORK: VALUE-STACK. The cover makes a completeness promise with an exact count, and every "
        "swipe pays it down.\n"
        "- Cover: the exact count plus the exact deliverable — '[N] [things] that [outcome]'. The number "
        "MUST equal the number of slides between cover and cta. A count is a checkable promise.\n"
        "- Middle slides: one item per slide, no filler, same shape throughout.\n"
        "- Close: the cta.\n"
        "Failure mode: padding to reach a rounder number. A tight 5 beats a padded 8 — pick the count "
        "you can actually deliver, then deliver exactly it."
    ),
    "callout": (
        ("mythfact", "insight"),
        "FRAMEWORK: CALLOUT. A direct challenge to a common practice. Conviction, delivered calmly — "
        "this is a precise line drawn by a consultancy, never a rant. No sarcasm, no naming of "
        "companies or people.\n"
        "- Cover: the practice you are challenging, stated plainly enough to be disagreed with.\n"
        "- Middle slides: escalate with specifics — the actual meeting, the actual approval step, the "
        "actual cost. Show the failure; do not gesture at it.\n"
        "- Second-to-last content slide: THE FAIRNESS PIVOT. State what you are NOT attacking — "
        "'the problem is not X, it is Y'. This is what turns heat into a quotable line, and it "
        "pre-empts the obvious objection. Never skip it.\n"
        "Failure mode: skipping the pivot (reads as complaint), or attacking something Zylo itself "
        "does. Stay anti-practice, never anti-person."
    ),
}

HOOKS = (
    "HOOK PATTERNS — pick one shape and commit to it. These are structures, not phrases to copy:\n"
    "- Contrarian: the common practice, named and denied. 'Buying AI is not a strategy.'\n"
    "- Cost-of-inaction: what the current approach is quietly costing. 'Your AI pilot is a cul-de-sac.'\n"
    "- Counted promise: an exact number of things. '5 signs your operating model is the bottleneck.'\n"
    "- Corrected belief: what leaders think versus what is true. 'AI licences everywhere. Capability nowhere.'\n"
    "- Stopping number: a figure that interrupts the scroll, only if it is real and Zylo's own.\n"
    "Enterprise register throughout: no 'I was wrong about', no 'unpopular opinion', no personal "
    "anecdote — Zylo posts as a firm, not a founder."
)

PSYCHOLOGY = (
    "WHY DECKS GET FINISHED (apply, do not name these):\n"
    "- Open loop: a question raised early and answered late is what carries a reader across slides. "
    "The cover should open one; the last content slide should close it. Never resolve it on slide 2.\n"
    "- Loss aversion: the cost of staying still lands harder than the upside of moving. Prefer 'what "
    "this is costing you now' over 'what you could gain'.\n"
    "- Curse of knowledge: the reader does not have your context. Any term an operations director "
    "would have to look up is a term to replace.\n"
    "- One idea per slide. If a slide needs two sentences of setup before its point, it is two slides."
)


def framework_block(framework, archetype):
    """Prompt text for the chosen framework. 'auto' lets the model pick a fitting one."""
    if framework and framework != "auto":
        return FRAMEWORKS[framework][1]
    fits = [f"{name}\n{block}" for name, (arches, block) in FRAMEWORKS.items() if archetype in arches]
    return (
        "Choose the narrative framework that best fits this material, then follow it for the whole "
        "deck. Do not blend two. Options:\n\n" + "\n\n".join(fits)
    )


def choices():
    return ["auto"] + sorted(FRAMEWORKS)


def for_archetype(archetype):
    return ["auto"] + sorted(n for n, (a, _) in FRAMEWORKS.items() if archetype in a)
