"""Controlled Gemini function-calling adapter for the local analysis tools."""

import json
import logging
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

try:
    from .ai_tools import TOOLS, execute_tool_result
    from .response_verifier import verify_response
except ImportError:
    from ai_tools import TOOLS, execute_tool_result
    from response_verifier import verify_response

logger = logging.getLogger(__name__)

DEFAULT_MODELS = ('gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash')
MAX_TOOL_CALLS = 6


def _function_declarations() -> List[types.FunctionDeclaration]:
    """Convert the local registry schemas into Gemini declarations."""
    declarations = []
    for tool in TOOLS.values():
        declarations.append(types.FunctionDeclaration(
            name=tool['name'],
            description=tool['description'],
            parametersJsonSchema=tool['input_schema'],
        ))
    return declarations


def _function_calls(response: Any) -> List[Any]:
    """Extract function calls without depending on response model internals."""
    calls = []
    for candidate in getattr(response, 'candidates', []) or []:
        content = getattr(candidate, 'content', None)
        for part in getattr(content, 'parts', []) or []:
            function_call = getattr(part, 'functionCall', None)
            if function_call and getattr(function_call, 'name', None):
                calls.append(function_call)
    return calls


def _text(response: Any) -> str:
    value = getattr(response, 'text', None)
    return value.strip() if isinstance(value, str) else ''


class GeminiToolAgent:
    """Runs a bounded Gemini tool-calling loop over trusted local tools."""

    def __init__(self, api_key: str, models: tuple[str, ...] = DEFAULT_MODELS,
                 max_tool_calls: int = MAX_TOOL_CALLS):
        if not api_key:
            raise ValueError('Gemini API key is required')
        if max_tool_calls < 1:
            raise ValueError('max_tool_calls must be at least 1')
        self.client = genai.Client(api_key=api_key)
        self.models = models
        self.max_tool_calls = max_tool_calls

    def run(self, message: str, context: str = '') -> Dict[str, Any]:
        if not message or not message.strip():
            raise ValueError('Message is required')

        prompt = message.strip()
        if context.strip():
            prompt = f'Current analysis context:\n{context.strip()}\n\nUser request:\n{prompt}'

        contents: List[Any] = [prompt]
        tool = types.Tool(functionDeclarations=_function_declarations())
        tool_log = []
        last_error: Optional[str] = None

        for model_name in self.models:
            try:
                contents_for_model = list(contents)
                for call_number in range(self.max_tool_calls + 1):
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=contents_for_model,
                        config=types.GenerateContentConfig(
                            systemInstruction=(
                                'You are an oncology genomics assistant. Use local tools for '
                                'all calculations and database lookups. Do not invent mutation '
                                'evidence, drug scores, clinical trials, or treatment advice. '
                                'Explain that outputs are computational and require clinician '
                                'validation. Call at most one or more available tools as needed.'
                            ),
                            temperature=0.2,
                            maxOutputTokens=2048,
                            tools=[tool],
                        ),
                    )

                    calls = _function_calls(response)
                    if not calls:
                        answer = _text(response)
                        if not answer:
                            raise RuntimeError('Gemini returned neither text nor a function call')
                        verification = verify_response(answer, tool_log)
                        return {
                            'ok': True,
                            'model': model_name,
                            'answer': answer,
                            'tool_calls': tool_log,
                            'verification': verification,
                        }

                    if call_number >= self.max_tool_calls:
                        raise RuntimeError('Maximum tool-call limit reached')

                    contents_for_model.append(
                        getattr(response.candidates[0], 'content')
                    )
                    for call in calls:
                        name = getattr(call, 'name', '')
                        arguments = getattr(call, 'args', {}) or {}
                        if name not in TOOLS:
                            result = {
                                'ok': False,
                                'tool': name,
                                'error': 'Tool is not permitted',
                            }
                        else:
                            result = execute_tool_result(name, arguments)
                        tool_log.append({
                            'tool': name,
                            'arguments': arguments,
                            'ok': result.get('ok', False),
                            'result': result.get('result', ''),
                            'provenance': result.get('provenance'),
                        })
                        contents_for_model.append(types.Content(
                            role='user',
                            parts=[types.Part(functionResponse=types.FunctionResponse(
                                name=name,
                                response=result,
                            ))],
                        ))
                raise RuntimeError('Gemini tool loop ended unexpectedly')
            except Exception as exc:
                last_error = str(exc)
                logger.warning('Gemini tool model %s failed: %s', model_name, exc)
                if '429' not in last_error and 'not found' not in last_error.lower():
                    break

        raise RuntimeError(last_error or 'All Gemini models failed')
