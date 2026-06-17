# Drishti AI SDK

[![PyPI](https://img.shields.io/pypi/v/drishti-ai-sdk)](https://pypi.org/project/drishti-ai-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **India's AI Agent Observability SDK** — See inside your AI agent. 2 lines of code. INR-native. Zero config.

Drishti is a lightweight, high-performance observability tool designed specifically for AI agents and LLM applications. It allows developers to monitor step-by-step agent execution, track token usage, calculate precise API costs automatically in Indian Rupees (INR), and capture error traces seamlessly—all without blocking your application's execution.

Access your complete dashboard and analytics at [drishtiai.dev](https://drishtiai.dev).

---

## 🚀 Installation

Install the Drishti SDK via pip:

```bash
pip install drishti-ai-sdk
```

## ⚡ Quick Start

Integrating Drishti takes just two lines of code. Here is the raw Python quick start:

```python
from drishti import Drishti

# 1. Initialize the client
drishti = Drishti(api_key="dk_your_api_key_here")

# 2. Wrap your agent execution
with drishti.trace("my_agent") as trace:
    result = agent.run(user_query)
    trace.set_output(result)

# Done! The trace is automatically sent to your dashboard in the background.
```

> **Note:** Replace `dk_your_api_key_here` with your actual API key from the dashboard. 

## 🔍 Step-by-Step Tracing

For deeper visibility into complex pipelines (like RAG), trace individual steps such as vector database lookups and direct LLM API calls.

```python
with drishti.trace("rag_pipeline", input=question) as trace:
    
    # Trace a specific step (e.g., retrieving context)
    with trace.step("memory_lookup", "memory") as step:
        context = vector_db.search(question, top_k=5)
        step.set_output({"chunks": len(context)})
    
    # Trace an LLM generation step
    with trace.step("llm_call", "llm") as step:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": question}]
        )
        # Automatically calculate costs and record token usage
        step.record_llm(
            model="gpt-4o-mini",
            tokens_input=response.usage.prompt_tokens,
            tokens_output=response.usage.completion_tokens
        )
    
    trace.set_output(response.choices[0].message.content)
```

## 💰 INR Cost Tracking

Every trace automatically calculates your cost natively in ₹ (INR)—no manual currency conversion logic needed.

Drishti supports 28+ leading models out of the box:
- **OpenAI**: GPT-4o, GPT-4o-mini, o1, o3-mini
- **Anthropic**: Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku
- **Google**: Gemini 2.0 Flash, Gemini 1.5 Pro
- **DeepSeek**: DeepSeek-V3, DeepSeek-R1
- **Meta**: Llama 3.3 70B, Llama 3.1 series
- **Mistral**: Mistral Large, Mistral Small, Mixtral

*Using an unsupported model name still works—Drishti will apply a standard fallback estimate.*

## 🛡️ Zero Overhead & Graceful Failure

If the Drishti ingestion servers are unreachable or your network drops, **your agent keeps working**. 
All trace telemetry is sent asynchronously via a background thread, ensuring absolutely zero blocking overhead on your critical path.

## ⚙️ Configuration

You can configure Drishti via environment variables instead of hardcoding credentials:

```env
DRISHTI_API_KEY=dk_live_your_key_here
# DRISHTI_ENDPOINT=https://drishti-backend-3fks.onrender.com  # Optional for custom endpoints
```

## 📊 Dashboard

Get your API key and view your Agent's analytics live at **[drishtiai.dev](https://drishtiai.dev)**.

---

Built with ❤️ for developers.
