from __future__ import annotations

import unittest

from gim.compiled_policy import COMPILED_DOCTRINE_PROMPT
from gim.core.policy import LLM_POLICY_PROMPT_TEMPLATE


class PolicyPromptTests(unittest.TestCase):
    def test_llm_prompt_avoids_conservative_use_sparingly_language(self) -> None:
        prompt = LLM_POLICY_PROMPT_TEMPLATE.lower()
        self.assertNotIn("use sparingly", prompt)
        self.assertIn("proportional to the severity of the geopolitical situation", prompt)

    def test_compiled_doctrine_prompt_avoids_use_sparingly_language(self) -> None:
        self.assertNotIn("use sparingly", COMPILED_DOCTRINE_PROMPT.lower())


if __name__ == "__main__":
    unittest.main()
