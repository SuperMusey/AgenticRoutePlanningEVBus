"""
Unit tests for the NewsParsingAgent.

Tests classification, extraction, and error handling capabilities.
"""

import json
import unittest
from unittest.mock import Mock, patch

from news_parser_agent import NewsParsingAgent


class TestNewsParsingAgent(unittest.TestCase):
    """Test NewsParsingAgent functionality."""

    def setUp(self):
        """Set up test fixtures with a patched generative model."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            self.agent = NewsParsingAgent(api_key='test-key')

    # ------------------------------------------------------------------ #
    # Initialization
    # ------------------------------------------------------------------ #

    def test_agent_initialization(self):
        """Agent is created and holds a model instance."""
        self.assertIsNotNone(self.agent)
        self.assertIsNotNone(self.agent.model)

    def test_agent_missing_api_key_raises(self):
        """Omitting the API key (and env var) should raise ValueError."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'), \
             patch.dict('os.environ', {}, clear=True):
            # Temporarily remove env var if present
            import os
            os.environ.pop('GENAI_API_KEY', None)
            with self.assertRaises(ValueError):
                NewsParsingAgent()

    # ------------------------------------------------------------------ #
    # parse_json helper
    # ------------------------------------------------------------------ #

    def test_parse_json_plain(self):
        """parse_json handles plain JSON strings."""
        result = self.agent.parse_json('{"key": "value"}')
        self.assertEqual(result['key'], 'value')

    def test_parse_json_strips_markdown_fences(self):
        """parse_json strips ```json ... ``` fences before parsing."""
        fenced = "```json\n{\"key\": \"value\"}\n```"
        result = self.agent.parse_json(fenced)
        self.assertEqual(result['key'], 'value')

    def test_parse_json_invalid_raises(self):
        """parse_json raises json.JSONDecodeError on bad input."""
        with self.assertRaises(json.JSONDecodeError):
            self.agent.parse_json("not valid json")

    # ------------------------------------------------------------------ #
    # parse_article — guard clauses
    # ------------------------------------------------------------------ #

    def test_parse_article_empty_string_returns_none(self):
        """Empty string article returns None without calling the model."""
        result = self.agent.parse_article("")
        self.assertIsNone(result)

    def test_parse_article_whitespace_only_returns_none(self):
        """Whitespace-only article returns None."""
        result = self.agent.parse_article("   \n\t  ")
        self.assertIsNone(result)

    def test_parse_article_none_returns_none(self):
        """None article returns None."""
        result = self.agent.parse_article(None)
        self.assertIsNone(result)

    # ------------------------------------------------------------------ #
    # classify_subagent
    # ------------------------------------------------------------------ #

    def test_classify_subagent_returns_true_for_disruption(self):
        """classify_subagent returns classification=True for a disruption article."""
        mock_response = Mock()
        mock_response.text = json.dumps({
            "classification": "True",
            "explanation": "Route 28 is blocked due to an accident.",
            "confidence": 0.95
        })
        self.agent.model.generate_content = Mock(return_value=mock_response)

        result = self.agent.classify_subagent("Route 28 is blocked due to an accident.")
        self.assertEqual(result['classification'], 'True')
        self.assertGreater(result['confidence'], 0.5)

    def test_classify_subagent_returns_false_for_non_disruption(self):
        """classify_subagent returns classification=False for an irrelevant article."""
        mock_response = Mock()
        mock_response.text = json.dumps({
            "classification": "False",
            "explanation": "Article is about a local sports event.",
            "confidence": 0.9
        })
        self.agent.model.generate_content = Mock(return_value=mock_response)

        result = self.agent.classify_subagent("The Steelers won yesterday.")
        self.assertEqual(result['classification'], 'False')

    def test_classify_subagent_error_returns_false(self):
        """classify_subagent returns a safe False dict when the model raises."""
        self.agent.model.generate_content = Mock(side_effect=Exception("API error"))

        result = self.agent.classify_subagent("Some article text.")
        self.assertEqual(result['classification'], 'False')
        self.assertEqual(result['confidence'], 0)

    # ------------------------------------------------------------------ #
    # disruption_data_subagent
    # ------------------------------------------------------------------ #

    def _make_classify_json(self, explanation="Road is blocked."):
        return {
            "classification": "True",
            "explanation": explanation,
            "confidence": 0.9
        }

    def test_disruption_data_subagent_returns_dict(self):
        """disruption_data_subagent returns a dict with expected keys."""
        mock_response = Mock()
        mock_response.text = json.dumps({
            "event_type": "road closure",
            "roads_affected": ["Route 28"],
            "intersections": ["16th Street Bridge"],
            "neighborhoods": ["Downtown"],
            "area_description": "Northbound lanes blocked on Route 28",
            "severity": "high",
            "duration_hours_estimate": 2.0,
            "confidence": 0.92,
            "source_quote": "Route 28 near 16th Street Bridge completely blocked",
            "additional_info": "Emergency responders on scene."
        })
        self.agent.model.generate_content = Mock(return_value=mock_response)

        result = self.agent.disruption_data_subagent(
            "Route 28 near 16th Street Bridge completely blocked due to accident.",
            self._make_classify_json()
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['event_type'], 'road closure')
        self.assertIn('Route 28', result['roads_affected'])
        self.assertEqual(result['severity'], 'high')
        self.assertAlmostEqual(result['confidence'], 0.92)

    def test_disruption_data_subagent_error_returns_none(self):
        """disruption_data_subagent returns None when the model raises."""
        self.agent.model.generate_content = Mock(side_effect=Exception("API error"))

        result = self.agent.disruption_data_subagent(
            "Some article.", self._make_classify_json()
        )
        self.assertIsNone(result)

    # ------------------------------------------------------------------ #
    # parse_article — full pipeline (mocked)
    # ------------------------------------------------------------------ #

    def test_parse_article_not_a_disruption_returns_none(self):
        """parse_article returns None when the article is not a road disruption."""
        classify_resp = Mock()
        classify_resp.text = json.dumps({
            "classification": "False",
            "explanation": "Sports article.",
            "confidence": 0.88
        })
        self.agent.model.generate_content = Mock(return_value=classify_resp)

        result = self.agent.parse_article("The Pirates beat the Cubs last night.")
        self.assertIsNone(result)

    def test_parse_article_low_classify_confidence_returns_none(self):
        """parse_article returns None when classification confidence is below threshold."""
        classify_resp = Mock()
        classify_resp.text = json.dumps({
            "classification": "True",
            "explanation": "Maybe traffic related.",
            "confidence": 0.1   # below 0.2 threshold
        })
        self.agent.model.generate_content = Mock(return_value=classify_resp)

        result = self.agent.parse_article("Vague article mentioning roads.")
        self.assertIsNone(result)

    def test_parse_article_low_extraction_confidence_returns_none(self):
        """parse_article returns None when extracted disruption confidence is below threshold."""
        classify_resp = Mock()
        classify_resp.text = json.dumps({
            "classification": "True",
            "explanation": "Traffic mentioned.",
            "confidence": 0.85
        })

        extraction_resp = Mock()
        extraction_resp.text = json.dumps({
            "event_type": "traffic",
            "roads_affected": [],
            "intersections": [],
            "neighborhoods": [],
            "area_description": "unclear",
            "severity": "low",
            "duration_hours_estimate": None,
            "confidence": 0.1,   # below 0.2 threshold
            "source_quote": "traffic",
            "additional_info": ""
        })

        self.agent.model.generate_content = Mock(
            side_effect=[classify_resp, extraction_resp]
        )

        result = self.agent.parse_article("Article with a vague traffic mention.")
        self.assertIsNone(result)

    def test_parse_article_success(self):
        """parse_article returns a disruption dict for a clear road disruption article."""
        classify_resp = Mock()
        classify_resp.text = json.dumps({
            "classification": "True",
            "explanation": "Route 28 is completely blocked.",
            "confidence": 0.97
        })

        extraction_resp = Mock()
        extraction_resp.text = json.dumps({
            "event_type": "road closure",
            "roads_affected": ["Route 28"],
            "intersections": ["16th Street Bridge"],
            "neighborhoods": ["Downtown"],
            "area_description": "Northbound Route 28 blocked near 16th Street Bridge",
            "severity": "high",
            "duration_hours_estimate": 2.0,
            "confidence": 0.95,
            "source_quote": "Route 28 near 16th Street Bridge completely blocked",
            "additional_info": "Alternate routes recommended via Strip District."
        })

        self.agent.model.generate_content = Mock(
            side_effect=[classify_resp, extraction_resp]
        )

        article = (
            "Pittsburgh Traffic Alert: Major accident on Route 28 near 16th Street Bridge. "
            "Northbound lanes completely blocked. Estimated 2-hour closure."
        )
        result = self.agent.parse_article(article)

        self.assertIsNotNone(result)
        self.assertEqual(result['event_type'], 'road closure')
        self.assertIn('Route 28', result['roads_affected'])
        self.assertEqual(result['severity'], 'high')
        self.assertAlmostEqual(result['confidence'], 0.95)

    def test_parse_article_invalid_classification_key_returns_none(self):
        """parse_article returns None when classification JSON has unexpected structure."""
        bad_resp = Mock()
        # Missing 'classification' and 'confidence' keys entirely
        bad_resp.text = json.dumps({"result": "yes", "score": 0.9})
        self.agent.model.generate_content = Mock(return_value=bad_resp)

        result = self.agent.parse_article("Some article text.")
        self.assertIsNone(result)

    # ------------------------------------------------------------------ #
    # call_with_retry
    # ------------------------------------------------------------------ #

    def test_call_with_retry_succeeds_on_first_attempt(self):
        """call_with_retry returns parsed JSON on a clean first response."""
        mock_response = Mock()
        mock_response.text = '{"status": "ok"}'
        self.agent.model.generate_content = Mock(return_value=mock_response)

        result = self.agent.call_with_retry("Some prompt")
        self.assertEqual(result['status'], 'ok')

    def test_call_with_retry_succeeds_on_second_attempt(self):
        """call_with_retry retries and succeeds when first response is malformed JSON."""
        bad_response = Mock()
        bad_response.text = "not valid json at all"

        good_response = Mock()
        good_response.text = '{"status": "ok"}'

        self.agent.model.generate_content = Mock(
            side_effect=[bad_response, good_response]
        )

        result = self.agent.call_with_retry("Some prompt")
        self.assertEqual(result['status'], 'ok')

    def test_call_with_retry_raises_after_two_failures(self):
        """call_with_retry raises JSONDecodeError when both attempts return bad JSON."""
        bad_response = Mock()
        bad_response.text = "still not json"

        self.agent.model.generate_content = Mock(return_value=bad_response)

        with self.assertRaises(json.JSONDecodeError):
            self.agent.call_with_retry("Some prompt")


if __name__ == '__main__':
    unittest.main()
