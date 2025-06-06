# features/llm/chat.py
"""
Wrapper around Azure OpenAI chat completion with optional RAG context.

v2.8.3
• Fix: Completely removed duplicate tool definitions
• Use only consolidated tools from tools.py
"""
from __future__ import annotations

import json
from typing import Sequence, Any

from openai import AzureOpenAI, OpenAIError

from config.settings import settings
from .prompts import build_system_prompt
from .tools import TOOLS

# --------------------------------------------------------------------------- #
# Azure OpenAI client (singleton)                                             #
# --------------------------------------------------------------------------- #
client = AzureOpenAI(
    api_key=settings.API_KEY,
    api_version=settings.API_VERSION,
    azure_endpoint=settings.BASE_ENDPOINT,
)

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _format_ctx_docs(docs: Sequence) -> str:
    """Make a single context string with [filename p.X] prefixes."""
    lines: list[str] = []
    for d in docs:
        src = d.metadata.get("source", "PDF")
        page = d.metadata.get("page", "?")
        lines.append(f"[{src} p.{page}]\n{d.page_content}")
    return "\n\n".join(lines)


def _json_bytes_safe(obj: Any) -> int:
    """
    len(json.dumps(obj)) even when obj contains pydantic/OpenAI models.
    """
    def _to_dict(x):
        if isinstance(x, dict):
            return x
        try:
            return x.model_dump()
        except AttributeError:
            return {"raw": str(x)}

    try:
        return len(json.dumps(obj))
    except TypeError:
        return len(json.dumps([_to_dict(i) for i in obj]))

# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #
def ask_llm(
    messages: list,
    vectorstore=None,
    user_input: str = "",
    *,
    top_k: int = 6,
):
    """Call Azure ChatGPT, adding RAG context + tool list."""
    sys_prompt = build_system_prompt()

    # Inject PDF-similarity context
    if vectorstore and user_input.strip():
        ctx_docs = vectorstore.similarity_search(user_input, k=top_k)
        ctx = _format_ctx_docs(ctx_docs)
        if ctx:
            sys_prompt = build_system_prompt(ctx)

    # Tell the model explicitly when to call the Excel tools
    sys_prompt += (
        "\n\nIf the user requests data that lives in the uploaded Excel "
        "workbook, call the `get_excel_data` or `get_fund_series` functions as appropriate. "
        "If you receive an error about sheet names, immediately retry with one of the "
        "available sheet names mentioned in the error message. Do not give up after "
        "the first error - always attempt to use the correct sheet names."
    )

    messages_openai = [{"role": "system", "content": sys_prompt}] + messages

    # ---------------- DEBUG payload summary -------------------------------- #
    tool_names = [t["function"]["name"] for t in TOOLS]
    print("TOOLS SENT TO OPENAI :", tool_names)
    print("MESSAGE COUNT        :", len(messages_openai))
    print("JSON BYTES (approx)  :", _json_bytes_safe(messages_openai))
    # ----------------------------------------------------------------------- #

    try:
        return client.chat.completions.create(
            model=settings.CHAT_DEPLOYMENT,
            messages=messages_openai,
            tools=TOOLS,
            tool_choice="auto",
        )

    except OpenAIError as err:
        # Dump HTTP error details for diagnosis
        resp = getattr(err, "response", None)
        if resp is not None:
            print("AZURE API STATUS:", resp.status_code)
            try:
                print("AZURE API BODY   :", resp.json())
            except Exception:
                print("AZURE API BODY (raw):", resp.text)
        raise 