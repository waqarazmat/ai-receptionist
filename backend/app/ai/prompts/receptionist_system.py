def get_system_prompt(org_config: dict, voice_mode: bool = False) -> str:
    """Build the full system prompt from an org's saved config.

    org_config keys (all optional except org_name):
        org_name: str
        greeting: str | None
        personality: str | None
        escalation_rules: str | None
        custom_system_prompt: str | None — free-form org-authored block (from
            the setup wizard's Custom System Prompt field). Injected verbatim
            after the structured sections but BEFORE the knowledge context, so
            it can add brand-voice rules, industry guardrails, or overrides
            the generic guidelines. Empty/None = skipped.
        knowledge_context: str  — retrieved chunks, already formatted, "" if none
        customer_name: str | None

    voice_mode: the caller is a phone call (Retell), not text chat — the
    customer hears this response spoken aloud via TTS, with no screen to
    glance back at, so it adds guidelines against anything that only makes
    sense written down (lists, markdown, long sentences).
    """
    org_name = org_config.get("org_name") or "the business"
    personality = org_config.get("personality") or "friendly, professional, and helpful"
    greeting = org_config.get("greeting") or f"Hi! Welcome to {org_name}."
    escalation_rules = (
        org_config.get("escalation_rules")
        or "Escalate to a human whenever the customer explicitly asks for one, or seems upset."
    )
    custom_system_prompt = (org_config.get("custom_system_prompt") or "").strip()
    knowledge_context = org_config.get("knowledge_context") or ""
    customer_name = org_config.get("customer_name")

    lines = [
        f"You are the AI receptionist for {org_name}.",
        "",
        f"Personality and tone: {personality}",
        "",
    ]

    # The greeting is spoken as the response_id=0 opening frame before the LLM
    # is ever called on a voice call, so re-injecting it into the system prompt
    # is dead weight for that channel. Text channels (webchat/WhatsApp) still
    # need it — the LLM produces the first turn there.
    if not voice_mode:
        lines += [
            f"Your greeting style (use naturally, don't repeat verbatim every message): {greeting}",
            "",
        ]

    lines += [
        f"Escalation rules — when to hand off to a human: {escalation_rules}",
        "",
        "Guidelines:",
        # Merged from two previously-overlapping bullets: the "only answer
        # from the knowledge below" rule and the "never invent prices/hours/
        # policies" rule are the same guardrail phrased two ways — one bullet
        # covers both without weakening either.
        "- Only answer from the knowledge provided below — never invent prices, hours, or policies. "
        "If you don't know, say so honestly and offer to connect them with staff.",
        "- Keep responses concise and conversational — this is a chat, not an essay.",
    ]

    if customer_name:
        lines.append(f"- The customer's name is {customer_name}. Use it naturally, not in every message.")

    if voice_mode:
        # Compressed from two bullets to one. Load-bearing content is
        # preserved: no lists/markdown/headings, 1-2 short sentences, and
        # numbers/times spelled the way a person would speak them.
        lines.append(
            "- This is a live phone call — no lists, markdown, bullet points, or headings; "
            "keep replies to one or two short sentences; speak numbers, times, and prices as "
            "a person would say them (e.g. \"nine AM\", not \"9:00 AM\")."
        )

    if custom_system_prompt:
        # Injected verbatim so orgs can add brand-voice rules, industry
        # guardrails, or override the generic guidelines above. Placed AFTER
        # the guidelines so it wins on conflicts (later instructions in a
        # system prompt take precedence in practice for Claude/GPT/Cohere).
        lines += ["", "Additional instructions from the business:", custom_system_prompt]

    if knowledge_context:
        lines += ["", "Relevant knowledge for this conversation:", knowledge_context]
    else:
        lines += [
            "",
            "No specific knowledge was found for this question — be honest that you're not sure "
            "and offer to connect them with staff.",
        ]

    return "\n".join(lines)
