import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from drug_prediction import ai_tools
from drug_prediction.response_verifier import verify_response
from drug_prediction import gemini_tool_agent


class ToolContractTests(unittest.TestCase):
    def test_structured_resistance_input_and_provenance(self):
        result = ai_tools.execute_tool_result(
            'predict_drug_resistance',
            {'mutations_json': [{'gene': 'EGFR', 'vaf': 0.45}]},
        )

        self.assertTrue(result['ok'])
        self.assertEqual(result['provenance']['tool'], 'predict_drug_resistance')
        self.assertTrue(result['provenance']['execution_id'])
        self.assertEqual(result['provenance']['registry_version'], '1.1')

    def test_legacy_resistance_input_remains_supported(self):
        result = json.loads(
            ai_tools.execute_tool(
                'predict_drug_resistance',
                '[{"gene":"EGFR","vaf":0.45}]',
            )
        )

        self.assertTrue(result['ok'])

    def test_nested_arguments_are_validated(self):
        result = ai_tools.execute_tool_result(
            'predict_drug_resistance',
            {'mutations_json': [{'vaf': 0.45}]},
        )

        self.assertFalse(result['ok'])
        self.assertIn('missing', result['error'].lower())


class ResponseVerifierTests(unittest.TestCase):
    def test_supported_response_is_verified(self):
        result = verify_response(
            'EGFR is included in the computational analysis. Clinical validation is required.',
            [{
                'tool': 'get_gene_info',
                'ok': True,
                'result': '{"gene":"EGFR"}',
                'provenance': {'execution_id': 'execution-1'},
            }],
        )

        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['evidence_execution_ids'], ['execution-1'])

    def test_treatment_claim_without_drug_tool_requires_review(self):
        result = verify_response(
            'Prescribe this treatment immediately.',
            [{
                'tool': 'get_gene_info',
                'ok': True,
                'result': '{"gene":"EGFR"}',
                'provenance': {'execution_id': 'execution-2'},
            }],
        )

        self.assertEqual(result['status'], 'review')
        self.assertTrue(any('Treatment language' in warning for warning in result['warnings']))


class GeminiToolAgentTests(unittest.TestCase):
    def test_mocked_function_call_returns_verification(self):
        function_call = SimpleNamespace(
            name='get_gene_info',
            args={'gene': 'EGFR'},
        )
        function_part = SimpleNamespace(functionCall=function_call)
        function_content = SimpleNamespace(parts=[function_part])
        function_candidate = SimpleNamespace(content=function_content)

        class FakeResponse:
            def __init__(self, tool_call):
                self.candidates = [function_candidate] if tool_call else []
                self.text = '' if tool_call else (
                    'EGFR is in the computational analysis. '
                    'Clinical validation is required.'
                )

        class FakeModels:
            def __init__(self):
                self.calls = 0

            def generate_content(self, **kwargs):
                self.calls += 1
                return FakeResponse(self.calls == 1)

        class FakeClient:
            def __init__(self, api_key):
                self.models = FakeModels()

        with patch.object(gemini_tool_agent.genai, 'Client', FakeClient):
            agent = gemini_tool_agent.GeminiToolAgent(
                'test-key',
                models=('test-model',),
                max_tool_calls=2,
            )
            result = agent.run('Explain EGFR')

        self.assertTrue(result['ok'])
        self.assertEqual(result['verification']['status'], 'verified')
        self.assertEqual(result['tool_calls'][0]['tool'], 'get_gene_info')


if __name__ == '__main__':
    unittest.main()
