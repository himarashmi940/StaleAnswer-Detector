import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from openai import APIStatusError
from answer_verifier import ClaimVerificationError, verify_claim
from bifrost_client import (
    ModelResponseError,
    create_bifrost_client,
    parse_json_object,
)
from claim_extractor import ClaimExtractionError, extract_claims
from pdf_generator import generate_pdf
from web_research import research_claim


def _completion(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def _status_error(status_code):
    request = Mock()
    request.method = "POST"
    request.url = "http://localhost/v1/chat/completions"
    response = Mock()
    response.request = request
    response.status_code = status_code
    response.headers = {}
    return APIStatusError(
        "sensitive gateway response",
        response=response,
        body=None,
    )


class BifrostClientTests(unittest.TestCase):
    def test_client_uses_virtual_key_and_normalizes_gateway_url(self):
        configuration = {
            "BIFROST_API_KEY": "test-api-key",
            "BIFROST_VIRTUAL_KEY": "test-virtual-key",
            "BIFROST_BASE_URL": "http://localhost:8080/",
            "BIFROST_MODEL_NAME": "gemini/gemini-3.6-flash",
        }
        with patch.dict(os.environ, configuration, clear=True):
            with patch("bifrost_client.OpenAI") as openai_factory:
                client, model = create_bifrost_client()

        self.assertIs(client, openai_factory.return_value)
        self.assertEqual(model, "gemini/gemini-3.6-flash")
        self.assertEqual(
            openai_factory.call_args.kwargs["base_url"],
            "http://localhost:8080/v1",
        )
        self.assertEqual(
            openai_factory.call_args.kwargs["default_headers"],
            {"x-bf-vk": "test-virtual-key"},
        )

    def test_json_parser_accepts_fences_and_surrounding_text(self):
        parsed = parse_json_object(
            'Result:\n```json\n{"claims": ["A fact"]}\n```',
            "Claim extraction",
        )

        self.assertEqual(parsed, {"claims": ["A fact"]})

    def test_json_parser_rejects_empty_and_invalid_responses(self):
        for content in ("", "   ", "not json"):
            with self.subTest(content=content):
                with self.assertRaises(ModelResponseError):
                    parse_json_object(content, "Claim extraction")


class PipelineHelperTests(unittest.TestCase):
    def test_extraction_retries_503_then_succeeds_with_backoff(self):
        create = Mock(
            side_effect=[
                _status_error(503),
                _completion('{"claims":["A factual claim."]}'),
            ]
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        with patch(
            "claim_extractor.create_bifrost_client",
            return_value=(client, "gemini/test"),
        ):
            with patch("claim_extractor.time.sleep") as sleep:
                claims = extract_claims("An example answer.")

        self.assertEqual(claims, ["A factual claim."])
        self.assertEqual(create.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_extraction_stops_after_three_429_attempts_without_leaking_error(self):
        create = Mock(
            side_effect=[_status_error(429), _status_error(429), _status_error(429)]
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        with patch(
            "claim_extractor.create_bifrost_client",
            return_value=(client, "gemini/test"),
        ):
            with patch("claim_extractor.time.sleep") as sleep:
                with self.assertRaises(ClaimExtractionError) as error:
                    extract_claims("An example answer.")

        self.assertEqual(create.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(1), call(2)])
        self.assertIn("after 3 attempts", str(error.exception))
        self.assertNotIn("sensitive gateway response", str(error.exception))

    def test_extraction_rejects_empty_or_invalid_json_safely(self):
        for content in (None, "not JSON"):
            with self.subTest(content=content):
                client = SimpleNamespace(
                    chat=SimpleNamespace(
                        completions=SimpleNamespace(
                            create=Mock(return_value=_completion(content))
                        )
                    )
                )
                with patch(
                    "claim_extractor.create_bifrost_client",
                    return_value=(client, "gemini/test"),
                ):
                    with self.assertRaises(ModelResponseError):
                        extract_claims("An example answer.")

    def test_mocked_workflow_produces_verification_report(self):
        extraction_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **_: _completion(
                        '{"claims":["The moon orbits Earth."]}'
                    )
                )
            )
        )
        verification_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **_: _completion(
                        '{"status":"Verified","explanation":"The source '
                        'supports the claim.","freshness_note":"Source is '
                        'current."}'
                    )
                )
            )
        )
        search_client = SimpleNamespace(
            search=lambda **_: {
                "results": [
                    {
                        "title": "Astronomy source",
                        "url": "https://example.com/astronomy",
                        "content": "The Moon orbits Earth.",
                    }
                ],
                "answer": "",
            }
        )

        with patch(
            "claim_extractor.create_bifrost_client",
            return_value=(extraction_client, "gemini/test"),
        ):
            claims = extract_claims("The moon orbits Earth.")
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
            with patch("web_research.TavilyClient", return_value=search_client):
                research = research_claim(claims[0])
        with patch(
            "answer_verifier.create_bifrost_client",
            return_value=(verification_client, "gemini/test"),
        ):
            verification = verify_claim(claims[0], research)

        verification["sources"] = research["sources"]
        report = generate_pdf([verification], freshness_score=100)
        self.assertEqual(verification["status"], "Verified")
        self.assertIn("https://example.com/astronomy", str(verification["sources"]))
        self.assertTrue(report.startswith(b"%PDF-"))

    def test_extraction_normalizes_and_deduplicates_claims(self):
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **_: SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(
                                    content=(
                                        '{"claims":["  Earth is round.  ",'
                                        '"earth IS ROUND.","","A second fact."]}'
                                    )
                                )
                            )
                        ]
                    )
                )
            )
        )
        with patch(
            "claim_extractor.create_bifrost_client",
            return_value=(client, "gemini/test"),
        ):
            claims = extract_claims("An example answer.")

        self.assertEqual(claims, ["Earth is round.", "A second fact."])

    def test_verifier_does_not_verify_without_sources(self):
        result = verify_claim("A factual claim.", {"sources": []})

        self.assertEqual(result["status"], "Unable to verify")
        self.assertIn("No source evidence", result["explanation"])

    def test_verification_retries_429_and_503_with_increasing_backoff(self):
        create = Mock(
            side_effect=[
                _status_error(429),
                _status_error(503),
                _completion(
                    '{"status":"Verified","explanation":"Evidence supports it.",'
                    '"freshness_note":"Evidence is recent."}'
                ),
            ]
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        research = {
            "sources": [
                {
                    "title": "Source",
                    "url": "https://example.com/source",
                    "content": "Evidence.",
                }
            ]
        }
        with patch(
            "answer_verifier.create_bifrost_client",
            return_value=(client, "gemini/test"),
        ):
            with patch("answer_verifier.time.sleep") as sleep:
                result = verify_claim("A factual claim.", research)

        self.assertEqual(result["status"], "Verified")
        self.assertEqual(create.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(1), call(2)])

    def test_verification_exhaustion_is_clear_and_does_not_expose_details(self):
        create = Mock(
            side_effect=[_status_error(503), _status_error(503), _status_error(503)]
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        research = {"sources": [{"title": "Source", "url": "https://example.com"}]}
        with patch(
            "answer_verifier.create_bifrost_client",
            return_value=(client, "gemini/test"),
        ):
            with patch("answer_verifier.time.sleep") as sleep:
                with self.assertRaises(ClaimVerificationError) as error:
                    verify_claim("A factual claim.", research)

        self.assertEqual(create.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(1), call(2)])
        self.assertIn("after 3 attempts", str(error.exception))
        self.assertNotIn("sensitive gateway response", str(error.exception))

    def test_verification_rejects_empty_or_invalid_json_safely(self):
        research = {"sources": [{"title": "Source", "url": "https://example.com"}]}
        for content in (None, "not JSON"):
            with self.subTest(content=content):
                client = SimpleNamespace(
                    chat=SimpleNamespace(
                        completions=SimpleNamespace(
                            create=Mock(return_value=_completion(content))
                        )
                    )
                )
                with patch(
                    "answer_verifier.create_bifrost_client",
                    return_value=(client, "gemini/test"),
                ):
                    with self.assertRaises(ModelResponseError):
                        verify_claim("A factual claim.", research)

    def test_research_handles_empty_results(self):
        client = SimpleNamespace(
            search=lambda **_: {"results": [], "answer": ""},
        )
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
            with patch("web_research.TavilyClient", return_value=client):
                result = research_claim("A claim to investigate.")

        self.assertEqual(result["sources"], [])

    def test_research_failure_does_not_expose_api_key(self):
        client = SimpleNamespace(
            search=lambda **_: (_ for _ in ()).throw(RuntimeError("failure")),
        )
        with patch.dict(os.environ, {"TAVILY_API_KEY": "sensitive-test-key"}):
            with patch("web_research.TavilyClient", return_value=client):
                with self.assertRaises(RuntimeError) as error:
                    research_claim("A claim to investigate.")

        self.assertNotIn("sensitive-test-key", str(error.exception))

    def test_pdf_escapes_special_characters_and_is_valid(self):
        pdf = generate_pdf(
            [
                {
                    "claim": "A <fact> & a symbol \U0001f600",
                    "status": "Verified",
                    "explanation": "Evidence says <yes> & no.",
                    "freshness_note": "Checked now.",
                    "sources": [
                        {
                            "title": "Source & title",
                            "url": "https://example.com/?a=1&b=2",
                        }
                    ],
                }
            ],
            freshness_score=100,
        )

        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreater(len(pdf), 500)


if __name__ == "__main__":
    unittest.main()
