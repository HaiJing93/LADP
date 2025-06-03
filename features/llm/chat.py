"""
Wrapper around Azure OpenAI chat completion with optional RAG context.

*Upgrade*: retrieved PDF chunks are prefixed with **[filename p.X]**
so the model can keep multiple statements separate.
"""

from __future__ import annotations

import json
from typing import Sequence, Any

from openai import AzureOpenAI, OpenAIError

from config.settings import settings
from .prompts import build_system_prompt
from .tools import TOOLS


# --------------------------------------------------------------------------- #
# Azure OpenAI client (kept alive across calls)                               #
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
    """Return context string with [filename p.X] prefixes for each chunk."""
    lines: list[str] = []
    for d in docs:
        src = d.metadata.get("source", "PDF")
        page = d.metadata.get("page", "?")
        lines.append(f"[{src} p.{page}]\n{d.page_content}")
    return "\n\n".join(lines)


def _json_bytes_safe(obj: Any) -> int:
    """
    Return len(json.dumps(obj)) even when obj contains OpenAI objects.

    Non-dict items are converted via .model_dump() if present, else str().
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
    """Call Azure OpenAI chat, injecting *top_k* similarity matches from PDFs."""
    sys_prompt = build_system_prompt()

    # Inject similarity context from PDFs
    if vectorstore and user_input.strip():
        ctx_docs = vectorstore.similarity_search(user_input, k=top_k)
        ctx = _format_ctx_docs(ctx_docs)
        if ctx:
            sys_prompt = build_system_prompt(ctx)
            print(ctx)  # optional: inspect injected PDF text

    messages_openai = [{"role": "system", "content": sys_prompt}] + messages

    # Ensure OpenAI API always receives string content
    for m in messages_openai:
        if m.get("content") is None:
            m["content"] = ""
        else:
            m["content"] = str(m["content"])

    # ---------------- DEBUG payload summary -------------------------------- #
    tool_names = [t["function"]["name"] for t in TOOLS]
    print("TOOLS SENT TO OPENAI:", tool_names)
    print("MESSAGE COUNT       :", len(messages_openai))
    print("JSON BYTES (approx) :", _json_bytes_safe(messages_openai))
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
                print("AZURE API BODY :", resp.json())
            except Exception:
                print("AZURE API BODY (raw):", resp.text)
        raise
