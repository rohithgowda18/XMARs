# Tool-calling upgrade

## Scope

This change adds a controlled Gemini function-calling adapter while preserving the
existing deterministic XMARs pipeline and legacy tool executor.

## Changes made

- Added JSON-style input schemas to all registered tools in
  `drug_prediction/ai_tools.py`.
- Added required-argument and basic type validation.
- Added `execute_tool_result()` for structured machine-readable results.
- Preserved `execute_tool()` for existing callers and legacy string arguments.
- Added `drug_prediction/gemini_tool_agent.py`.
- Converted the registered local tools into Gemini function declarations.
- Added a bounded tool-calling loop with a maximum of six tool calls.
- Restricted Gemini to the registered local tools.
- Added explicit tool execution logs to the response.
- Added provenance metadata to every tool result, including execution ID,
  timestamp, registry version, description, and input schema.
- Added fallback across the configured Gemini model names.
- Kept ML, SHAP, pathway, and drug calculations deterministic; Gemini only
  selects tools and explains returned results.

## Validation

- Python syntax compilation passed for the updated modules.
- Tool registry checks passed for:
  - schema registration
  - missing required arguments
  - legacy string execution
  - structured dictionary execution

## Usage

The Flask endpoint is:

```text
POST /chat-tools
```

Request:

```json
{
  "message": "Analyze EGFR and TP53 and explain relevant drug resistance.",
  "context": ""
}
```

The endpoint requires `GEMINI_API_KEY`. The existing `/chat` and `/predict-ai`
endpoints remain available.

## Safety boundary

The LLM is not allowed to directly calculate scores, execute arbitrary Python,
or create clinical recommendations outside the returned tool data. Results are
computational decision support and require clinical validation.

Each tool result includes provenance metadata so a response can be traced to
the exact local tool execution. The metadata is an execution trace, not a
claim that the underlying knowledge base is clinically validated or current.
