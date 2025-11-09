"""Unit tests for the GoogleAdapter simplifying API usage."""

from __future__ import annotations

import importlib
import os
import types as py_types
import unittest
import unittest.mock
from typing import Any, Dict, List


class _FakePart:
    def __init__(self, *, text: str | None = None):
        self.text = text


class _FakeContent:
    def __init__(self, *, role: str, parts: List[_FakePart]):
        self.role = role
        self.parts = parts


class _FakeThinkingConfig:
    def __init__(self, *, thinking_budget: int):
        self.thinking_budget = thinking_budget


class _FakeGenerateContentConfig:
    def __init__(self, **kwargs: Any):
        self.temperature = None
        self.max_output_tokens = None
        self.system_instruction = None
        self.thinking_config = None
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeModels:
    error_to_raise: Exception | None = None
    response_text: str = "Model output"

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if _FakeModels.error_to_raise is not None:
            raise _FakeModels.error_to_raise
        return py_types.SimpleNamespace(text=_FakeModels.response_text)


class _FakeClient:
    last_instance: "_FakeClient" | None = None

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.models = _FakeModels()
        _FakeClient.last_instance = self


class GoogleAdapterTest(unittest.TestCase):
    """Tests for the google adapter end-to-end request building."""

    def setUp(self) -> None:
        """Patch environment and SDK modules so each test starts clean."""
        super().setUp()
        from harness.adapters import google as google_module

        # Ensure env vars required by the adapter are available.
        self._env_patch = unittest.mock.patch.dict(
            os.environ,
            {
                "GOOGLE_API_KEY": "unit-test-key",
                "GOOGLE_THINKING_BUDGET": "77",
            },
            clear=False,
        )
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)

        # Reload module to reset singletons before monkeypatching.
        self.google_module = importlib.reload(google_module)
        self.addCleanup(lambda: importlib.reload(google_module))

        fake_types = py_types.SimpleNamespace(
            ThinkingConfig=_FakeThinkingConfig,
            GenerateContentConfig=_FakeGenerateContentConfig,
            Content=_FakeContent,
            Part=_FakePart,
        )
        self.google_module.genai = py_types.SimpleNamespace(Client=_FakeClient)
        self.google_module.types = fake_types
        self.google_module.HttpOptions = None

    def _build_sample_item(self) -> Dict[str, Any]:
        """Return a minimal eval item used by most test cases."""
        return {
            "prompt": "Provide the final answer.",
            "inventory_ids": ["inv-1"],
            "question": {
                "require_sections": ["Answer"],
                "modality": "spice_netlist",
            },
            "artifact": "R1 out in 1k",
        }

    def test_predict_sends_structured_payload_and_config(self) -> None:
        """Ensure predict sends proper contents + config and surfaces text."""
        adapter = self.google_module.GoogleAdapter(
            model="gemini-2.5-pro-test", temperature=0.25, max_tokens=42
        )

        outputs = adapter.predict([self._build_sample_item()])
        self.assertEqual(outputs, ["Model output"])

        fake_client = _FakeClient.last_instance
        self.assertIsNotNone(fake_client)
        assert fake_client is not None
        self.assertEqual(fake_client.kwargs["api_key"], "unit-test-key")

        call = fake_client.models.calls[-1]
        self.assertEqual(call["model"], "gemini-2.5-pro-test")

        contents = call["contents"]
        self.assertIsInstance(contents, list)
        self.assertEqual(len(contents), 1)
        message = contents[0]
        self.assertIsInstance(message, _FakeContent)
        self.assertEqual(message.role, "user")
        self.assertEqual(len(message.parts), 1)
        user_text = message.parts[0].text
        self.assertIn("Artifact modality: SPICE netlist.", user_text)
        self.assertIn("Inventory IDs you may cite: inv-1", user_text)
        self.assertIn("Required sections: Answer", user_text)

        config = call["config"]
        self.assertIsInstance(config, _FakeGenerateContentConfig)
        self.assertEqual(config.temperature, 0.25)
        self.assertEqual(config.max_output_tokens, 42)
        self.assertIsInstance(config.thinking_config, _FakeThinkingConfig)
        self.assertEqual(config.thinking_config.thinking_budget, 77)
        self.assertIsInstance(config.system_instruction, _FakeContent)
        self.assertEqual(config.system_instruction.parts[0].text, self.google_module.SYS_PROMPT)

    def test_adapter_does_not_retry_on_parameter_errors(self) -> None:
        """Verify we surface parameter errors immediately without retries."""
        adapter = self.google_module.GoogleAdapter(model="gemini-2.5-pro-test")
        _FakeModels.error_to_raise = TypeError("unexpected keyword argument 'config'")

        with self.assertRaises(TypeError):
            adapter.predict([self._build_sample_item()])

        fake_client = _FakeClient.last_instance
        self.assertIsNotNone(fake_client)
        assert fake_client is not None
        self.assertEqual(len(fake_client.models.calls), 1)

        _FakeModels.error_to_raise = None


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
