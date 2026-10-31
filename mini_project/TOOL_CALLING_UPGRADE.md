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
- Added deterministic response verification against successful tool evidence.
- Added warnings for unsupported gene tokens, missing clinical caveats, and
  treatment language without drug-resistance evidence.
- Changed pathway and resistance tools to accept structured arrays for
  function-calling requests, including nested mutation validation.
- Preserved comma-separated genes and JSON-string mutation inputs for legacy
  callers.
- Added `test/test_agentic_tools.py` covering contracts, provenance,
  verification, legacy compatibility, and mocked Gemini function calling.
- Added declared local source files to each tool and included them in
  execution provenance.
- Added `drug_prediction/contracts.py` with the versioned `MutationInput`
  contract and shared `normalize_mutations()` boundary validation.
- Routed the tool layer and all four pipeline agents through the same mutation
  contract, including uppercase gene normalization, default VAF handling, and
  VAF range validation.
- Added the mutation schema version to tool provenance so analysis inputs can
  be reproduced after future contract changes.
- Added `drug_prediction/analysis_run.py` and attached an `analysis_run`
  record to the full pipeline response. It captures the run ID, normalized
  inputs, timestamps, pipeline/application versions, and SHA-256 fingerprints
  for the model and data artifacts used by the pipeline.
- Added `drug_prediction/evidence.py` and attached explicit evidence records
  to ranked drugs. Current records are labeled `computational_local`, include
  the local source and reasoning, and explicitly state that clinical
  validation, approval status, citations, and variant-level evidence have not
  been assessed.
- Added `drug_prediction/evidence_repository.py` and the empty
  `data/evidence/curated_records.json` repository format. Curated records are
  schema-validated and matched by drug, gene, cancer type, and optional
  variant; unmatched results continue to receive the explicit local
  computational evidence record.
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
- Mutation contract checks passed for:
  - canonical gene/VAF normalization
  - preservation of variant metadata
  - rejection of invalid VAF values

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
The provenance also identifies the local datasets and model artifacts used by
the tool, making the result auditable without implying external clinical
validation.

The `/chat-tools` response also includes `verification`. A `verified` status
means the deterministic checks found no warnings; `review` means the response
should be reviewed before being treated as reliable clinical decision support.
