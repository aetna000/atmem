"""Offline contract checks; these tests never contact a provider."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('azure_sol_cli', Path(__file__).parents[1] / 'scripts/openrouter_azure_sol.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class AzureSolTests(unittest.TestCase):
    def response(self):
        return {'provider': 'Azure', 'model': cli.MODEL,
                'choices': [{'finish_reason': 'stop', 'message': {'content': '{"status":"AZURE_SOL_OK"}'}}],
                'usage': {'prompt_tokens': 20, 'completion_tokens': 30, 'cost': 0.00068}}

    def test_routing_is_exclusive_and_preserves_settings(self):
        request = cli.smoke_request()
        self.assertEqual(request['provider']['only'], ['azure'])
        self.assertFalse(request['provider']['allow_fallbacks'])
        self.assertTrue(request['provider']['require_parameters'])
        self.assertEqual(request['reasoning_effort'], 'medium')
        self.assertEqual(request['max_completion_tokens'], 8000)
        self.assertEqual(request['response_format'], {'type': 'json_object'})

    def test_valid_response(self):
        self.assertEqual(cli.validate_response(self.response())['prompt_tokens'], 20)

    def test_other_provider_rejected(self):
        response = self.response()
        response['provider'] = 'OpenAI'
        with self.assertRaises(ValueError):
            cli.validate_response(response)

    def test_pro_or_different_model_rejected(self):
        for model in ('openai/gpt-5.6-sol-pro', 'openai/gpt-5.6-luna'):
            response = self.response()
            response['model'] = model
            with self.assertRaises(ValueError):
                cli.validate_response(response)

    def test_missing_or_nonfinite_cost_rejected(self):
        for cost in (None, float('nan'), -1, True):
            response = copy.deepcopy(self.response())
            response['usage']['cost'] = cost
            with self.assertRaises(ValueError):
                cli.validate_response(response)

    def test_incomplete_or_wrong_json_rejected(self):
        response = self.response()
        response['choices'][0]['finish_reason'] = 'length'
        with self.assertRaises(ValueError):
            cli.validate_response(response)
        response = self.response()
        response['choices'][0]['message']['content'] = '{"status":"wrong"}'
        with self.assertRaises(ValueError):
            cli.validate_response(response)
