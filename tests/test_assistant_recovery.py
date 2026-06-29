"""Assistant robustness: recover text-embedded tool calls (Ollama) and route the
DeepSeek provider to the right endpoint (the 401-on-openai.com bug)."""
from __future__ import annotations

import unittest

import gim.assistant as A
from gim.assistant import AssistantConfig, run_assistant_turn


class TextToolCallRecoveryTests(unittest.TestCase):
    def test_extracts_bare_json_tool_call(self) -> None:
        calls = A._extract_text_tool_calls('{"name": "run_whatif", "arguments": {"question": "X", "horizon": 5}}')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "run_whatif")
        self.assertEqual(calls[0]["function"]["arguments"]["horizon"], 5)

    def test_extracts_from_markdown_and_prose(self) -> None:
        content = 'Конечно:\n```json\n{"name":"run_composed","arguments":{"question":"cyber attack"}}\n```'
        calls = A._extract_text_tool_calls(content)
        self.assertEqual([c["function"]["name"] for c in calls], ["run_composed"])

    def test_ignores_unknown_tool_names(self) -> None:
        self.assertEqual(A._extract_text_tool_calls('{"name":"rm_rf","arguments":{}}'), [])

    def test_braces_inside_strings_do_not_break_parsing(self) -> None:
        calls = A._extract_text_tool_calls('{"name":"run_whatif","arguments":{"question":"a } brace { in text"}}')
        self.assertEqual(calls[0]["function"]["arguments"]["question"], "a } brace { in text")

    def test_loop_runs_recovered_tool(self) -> None:
        # Simulate an Ollama model that returns the tool call as text, then narrates.
        turns = iter([
            {"content": '{"name": "run_whatif", "arguments": {"question": "war 5y", "horizon": 5}}'},
            {"content": "Готово."},
        ])
        original = A._chat
        A._chat = lambda cfg, convo: next(turns)
        try:
            ran: list[str] = []
            events: list[str] = []
            run_assistant_turn(
                [{"role": "user", "content": "что будет?"}],
                AssistantConfig(provider="ollama"),
                lambda name, args: (ran.append(name), {"summary": "ok", "result": {"mode": "whatif"}})[1],
                lambda ev, data: events.append(ev),
            )
        finally:
            A._chat = original
        self.assertEqual(ran, ["run_whatif"])
        self.assertIn("run_result", events)


class DeepSeekRoutingTests(unittest.TestCase):
    def test_deepseek_provider_hits_deepseek_not_openai(self) -> None:
        if not A.REQUESTS_AVAILABLE:
            self.skipTest("requests not available")
        captured: dict[str, object] = {}

        class FakeResp:
            def raise_for_status(self) -> None: ...
            def json(self) -> dict:
                return {"choices": [{"message": {"content": "ok"}}]}

        def fake_post(url, headers=None, json=None, timeout=None):  # noqa: A002
            captured["url"] = url
            captured["model"] = json["model"]
            captured["auth"] = headers["Authorization"]
            return FakeResp()

        original = A.requests.post
        A.requests.post = fake_post
        try:
            A._chat(AssistantConfig(provider="deepseek", api_key="sk-deepseek-test"),
                    [{"role": "user", "content": "hi"}])
        finally:
            A.requests.post = original

        self.assertEqual(captured["url"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(captured["model"], "deepseek-chat")
        self.assertEqual(captured["auth"], "Bearer sk-deepseek-test")


if __name__ == "__main__":
    unittest.main()
