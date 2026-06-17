# drishti-ai-sdk

> **India's AI Agent Observability SDK** — See inside your AI agent. 2 lines of code. INR-native. Zero config.

[![PyPI](https://img.shields.io/pypi/v/drishti-ai-sdk)](https://pypi.org/project/drishti-ai-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Installation

```bash
pip install drishti-ai-sdk
```

## Quick Start

```python
from drishti import Drishti

drishti = Drishti(api_key="dk_live_...")

with drishti.trace("handle_user_query", input=user_query) as trace:
    result = agent.run(user_query)
    trace.set_output(result)
# Done! Trace appears in your dashboard at drishti.dev
```

## Step-by-Step Tracing

```python
with drishti.trace("rag_pipeline", input=question) as trace:
    
    with trace.step("memory_lookup", "memory") as step:
        context = vector_db.search(question, top_k=5)
        step.set_output({"chunks": len(context)})
    
    with trace.step("llm_call", "llm") as step:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": question}]
        )
        step.record_llm(
            model="gpt-4o-mini",
            tokens_input=response.usage.prompt_tokens,
            tokens_output=response.usage.completion_tokens
        )
    
    trace.set_output(response.choices[0].message.content)
```

## Decorator Pattern

```python
@drishti.watch
def run_agent(query: str) -> str:
    return agent.run(query)

# Auto-traced on every call
result = run_agent("What is the weather in Mumbai?")
```

## INR Cost Tracking

Every trace automatically shows cost in ₹ — no manual calculation needed.

Supported models:
- **OpenAI**: GPT-4o, GPT-4o-mini, O1, O3-mini, and more
- **Anthropic**: Claude Opus 4, Claude Sonnet 4, Claude Haiku 4
- **Google**: Gemini 2.0 Flash, Gemini 2.5 Pro
- **DeepSeek**: DeepSeek V3, R1
- **Meta**: Llama 3.3, 3.1 series
- **Mistral**: Mistral Large, Small, Mixtral

## Environment Variables

```env
DRISHTI_API_KEY=dk_live_your_key_here
DRISHTI_ENDPOINT=https://drishti-backend-3fks.onrender.com  # optional
```

## Graceful Failure

If Drishti's server is down, **your agent keeps working**. All sends are async in a background thread and never block your code.

## Dashboard

Get your API key at [drishti.dev](https://drishti.dev)

---

Built with ❤️ for Indian developers.
