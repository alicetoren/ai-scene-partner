from typing import Protocol

from openai import OpenAI
from pydantic import ValidationError

from app.config import get_openai_api_key, get_openai_model
from app.models import Scene


PARSER_INSTRUCTIONS = """You extract spoken dialogue from a plain-text acting script.
Return only the requested scene JSON. Identify each speaking character and preserve every
dialogue line's wording, punctuation, and order faithfully. Do not invent dialogue,
characters, or missing text. Exclude stage directions, scene headings, and non-dialogue
text. Use consecutive line IDs starting at 1. Use a clear scene title from the source only
when present; otherwise use 'Uploaded Scene'."""


class ScriptParser(Protocol):
    def parse(self, script_text: str) -> Scene: ...


class OpenAIScriptParser:
    """Converts script text to a validated Scene through the OpenAI Responses API."""

    def __init__(self, client: OpenAI | None = None) -> None:
        self._client = client

    def parse(self, script_text: str) -> Scene:
        client = self._client or OpenAI(api_key=get_openai_api_key())
        response = client.responses.create(
            model=get_openai_model(),
            instructions=PARSER_INSTRUCTIONS,
            input=script_text,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "scene",
                    "strict": True,
                    "schema": Scene.model_json_schema(),
                }
            },
        )

        try:
            return Scene.model_validate_json(response.output_text)
        except ValidationError as error:
            raise ValueError("The AI response did not match the expected scene format.") from error


def get_script_parser() -> ScriptParser:
    return OpenAIScriptParser()
