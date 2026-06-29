from typing import Protocol


class LLMProvider(Protocol):
    def generate_json(self, *, system_prompt: str, user_prompt: str) -> str:
        ...