"""LLM reasoning agent – Week 3 module.

Responsibilities:
- Accept a suspect function + its git evidence bundle.
- Call the local Ollama/Mistral model (or Claude Haiku when hosted).
- Return a structured Verdict with confidence score and rationale.

Provider is chosen via the LLM_PROVIDER env variable:
  LLM_PROVIDER=ollama  (default, local)
  LLM_PROVIDER=anthropic  (hosted demo)
"""

# TODO (Week 3): implement using LangChain + Ollama / Anthropic adapters
