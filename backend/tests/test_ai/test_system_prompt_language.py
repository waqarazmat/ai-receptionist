"""Reply-language matching: text/WhatsApp replies mirror the customer's language
so a single-language knowledge base still serves customers in any language. The
voice channel enforces language via its own menu instruction, so it must NOT get
this (potentially conflicting) rule."""

from app.ai.prompts.receptionist_system import get_system_prompt


class TestReplyLanguageInstruction:
    def test_text_prompt_tells_llm_to_match_customer_language(self):
        prompt = get_system_prompt({"org_name": "Acme Clinic"})
        assert "SAME language" in prompt
        assert "customer's language" in prompt

    def test_voice_prompt_omits_reply_language_rule(self):
        prompt = get_system_prompt({"org_name": "Acme Clinic"}, voice_mode=True)
        assert "SAME language" not in prompt

    def test_instruction_present_regardless_of_knowledge_context(self):
        # KB in Dutch, no chunks, etc. — the rule is always there for text.
        prompt = get_system_prompt({"org_name": "Acme", "knowledge_context": "Wij zijn open van 9 tot 17."})
        assert "answer in the customer's language" in prompt
