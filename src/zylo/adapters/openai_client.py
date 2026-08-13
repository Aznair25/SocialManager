"""OpenAI implementation of the `ChatClient` port.

The SDK import and the client construction are deferred to the first call, so
the package imports cleanly without openai installed and the API's /api/config
endpoint can report `api_key_set: false` rather than failing to start.
"""
import os
from typing import Sequence

from ..domain.errors import GenerationError
from ..prompts.builder import Message, as_dicts

MAX_COMPLETION_TOKENS = 8000


class OpenAIChatClient:
    """One chat completion, JSON mode, returning raw text.

    Reasoning models (gpt-5*) reject `max_tokens` and only accept the default
    temperature, so neither is sent.
    """

    def __init__(self, model: str, client=None, max_completion_tokens: int = MAX_COMPLETION_TOKENS):
        self._model = model
        self._client = client
        self._max_completion_tokens = max_completion_tokens

    @property
    def model(self) -> str:
        return self._model

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError:
            raise GenerationError("Missing dependency: pip install -r requirements.txt") from None
        if not os.environ.get("OPENAI_API_KEY"):
            raise GenerationError("OPENAI_API_KEY not set — cp .env.example .env and add your key")
        self._client = OpenAI()
        return self._client

    def complete(self, messages: Sequence[Message]) -> str:
        response = self._ensure_client().chat.completions.create(
            model=self._model,
            messages=as_dicts(messages),
            response_format={"type": "json_object"},
            max_completion_tokens=self._max_completion_tokens,
        )
        return response.choices[0].message.content or ""
