import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from drug_prediction import ai_tools
from drug_prediction.response_verifier import verify_response
from drug_prediction import gemini_tool_agent
from drug_prediction.contracts import normalize_mutations
from drug_prediction.analysis_run import finish_analysis_run, start_analysis_run
from drug_prediction.evidence import build_drug_evidence, evidence_review_status
from drug_prediction.evidence_repository import EvidenceRepository
from tempfile import TemporaryDirectory
from pathlib import Path
from pathlib import Path


class ToolContractTests(unittest.TestCase):
    def test_computational_evidence_requires_clinical_review(self):
        status = evidence_review_status([{
            'clinically_validated': False,
            'evidence_level': 'computational_local',
        }])

        self.assertEqual(status['status'], 'clinical_review_required')
        self.assertTrue(status['clinical_review_required'])

    def test_evidence_repository_validates_and_matches_curated_records(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / 'records.json'
            path.write_text(json.dumps({'records': [{
                'evidence_id': 'civic:1',
                'drug': 'example-drug',
                'gene': 'EGFR',
                'variant': 'p.L858R',
                'cancer_type': 'NSCLC',
                'effect': 'sensitivity',
                'evidence_level': 'clinical',
                'source': 'Test source',
                'citation': 'PMID:1',
                'last_reviewed': '2026-10-31',
            }]}), encoding='utf-8')
            repository = EvidenceRepository(path)

            matches = repository.find(
                'EXAMPLE-DRUG',
                ['EGFR'],
                variant='p.L858R',
            )

        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0]['clinically_validated'])

    def test_local_evidence_is_explicitly_not_clinical_validation(self):
        evidence = build_drug_evidence(
            'example-drug',
            {'targets': ['EGFR'], 'pathway': 'EGFR signaling'},
            [{'gene': 'egfr', 'vaf': 0.45}],
            ['EGFR mutation predicts target sensitivity'],
        )

        self.assertEqual(evidence[0]['evidence_level'], 'computational_local')
        self.assertFalse(evidence[0]['clinically_validated'])
        self.assertEqual(evidence[0]['genes'], ['EGFR'])
        self.assertIsNone(evidence[0]['citation'])
        self.assertTrue(evidence[0]['limitations'])

    def test_analysis_run_records_input_and_artifact_fingerprints(self):
        run = start_analysis_run(
            [{'gene': 'egfr', 'vaf': 0.45}],
            Path(__file__).parent.parent,
        )
        completed = finish_analysis_run(run, 'completed', 0.12)

        self.assertEqual(completed['analysis_run_schema_version'], '1.0')
        self.assertTrue(completed['analysis_run_id'])
        self.assertEqual(completed['input']['mutations'][0]['gene'], 'EGFR')
        self.assertEqual(completed['status'], 'completed')
        self.assertTrue(completed['completed_at'])
        self.assertTrue(any(
            artifact['path'].endswith('pathway_reference.json')
            and artifact['available']
            and artifact['sha256']
            for artifact in completed['components']['artifacts']
        ))

    def test_mutation_contract_normalizes_and_preserves_variant_fields(self):
        mutations = normalize_mutations([{
            'gene': ' egfr ',
            'variant': 'p.L858R',
            'protein_mutation': 'L858R',
            'vaf': '0.45',
        }])

        self.assertEqual(mutations, [{
            'gene': 'EGFR',
            'vaf': 0.45,
            'variant': 'p.L858R',
            'protein_mutation': 'L858R',
        }])

    def test_mutation_contract_rejects_invalid_vaf(self):
        with self.assertRaises(ValueError):
            normalize_mutations([{'gene': 'EGFR', 'vaf': 1.1}])

    def test_structured_resistance_input_and_provenance(self):
        result = ai_tools.execute_tool_result(
            'predict_drug_resistance',
            {'mutations_json': [{'gene': 'EGFR', 'vaf': 0.45}]},
        )

        self.assertTrue(result['ok'])
        self.assertEqual(result['provenance']['tool'], 'predict_drug_resistance')
        self.assertTrue(result['provenance']['execution_id'])
        self.assertEqual(result['provenance']['registry_version'], '1.1')
        self.assertEqual(result['provenance']['mutation_schema_version'], '1.0')
        self.assertIn(
            'data/processed/03_compounds_cleaned.csv',
            result['provenance']['source_files'],
        )

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
    def test_response_with_computational_ranking_requires_review(self):
        result = verify_response(
            'This computational ranking requires clinical review and is not a treatment recommendation.',
            [{
                'tool': 'predict_drug_resistance',
                'ok': True,
                'result': '{"evidence_status":{"status":"clinical_review_required"}}',
                'provenance': {'execution_id': 'execution-3'},
            }],
        )

        self.assertEqual(result['status'], 'verified')

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
