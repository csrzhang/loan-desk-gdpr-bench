"""Shared model configuration and thinking-compatible structured output."""

from __future__ import annotations

from typing import TypeVar

from langchain_anthropic import ChatAnthropic
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import HumanMessage, convert_to_messages
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, ValidationError

import config

T = TypeVar("T", bound=BaseModel)


def get_llm() -> ChatAnthropic:
    """Create a client using the same settings for every agent and audit memory.

    Always send an explicit thinking setting: omitting it lets DeepSeek enable
    thinking on the server, which conflicts with forced tool selection.
    """
    if config.LLM_MAX_TOKENS <= 0 or config.LLM_TIMEOUT_SECONDS <= 0:
        raise ValueError("LLM_MAX_TOKENS and LLM_TIMEOUT_SECONDS must be positive")
    if config.LLM_MAX_RETRIES < 0:
        raise ValueError("LLM_MAX_RETRIES must not be negative")

    options = {
        "model": config.LLM_MODEL,
        "api_key": config.LLM_API_KEY,
        "base_url": config.LLM_BASE_URL,
        "max_tokens": config.LLM_MAX_TOKENS,
        "timeout": config.LLM_TIMEOUT_SECONDS,
        "max_retries": config.LLM_MAX_RETRIES,
    }
    if config.LLM_THINKING:
        budget = config.LLM_THINKING_BUDGET_TOKENS
        if not 1024 <= budget < config.LLM_MAX_TOKENS:
            raise ValueError(
                "LLM_THINKING_BUDGET_TOKENS must be at least 1024 and less than LLM_MAX_TOKENS"
            )
        options["thinking"] = {"type": "enabled", "budget_tokens": budget}
        # Temperature is unsupported or ignored by thinking backends.
    else:
        options["thinking"] = {"type": "disabled"}
        options["temperature"] = config.LLM_TEMPERATURE
    return ChatAnthropic(**options)


def get_structured_llm(schema: type[T]) -> Runnable[LanguageModelInput, T]:
    """Return validated Pydantic results without incompatible tool_choice values.

    With thinking disabled, use native function calling. With thinking enabled,
    request JSON as text and validate locally; this sends no tools/tool_choice
    and does not require the backend's native JSON-schema API.
    """
    model = get_llm()
    if not config.LLM_THINKING:
        # Several agent schemas are private Python classes (_VerdictOutput,
        # _LocusFinderOutput, ...). Compatible backends sometimes drop that
        # leading underscore from the returned tool name. Advertise a stable,
        # public wire name and validate the resulting dict with the original
        # Pydantic model, rather than making protocol names Python identifiers.
        wire_schema = schema.model_json_schema()
        wire_schema["title"] = schema.__name__.lstrip("_")
        chain = (
            model.with_structured_output(wire_schema, method="function_calling")
            | RunnableLambda(schema.model_validate)
        )
    else:
        parser = PydanticOutputParser(pydantic_object=schema)
        instructions = (
            "Return exactly one JSON object as your final answer, without commentary.\n"
            + parser.get_format_instructions()
        )

        def add_schema(value: LanguageModelInput):
            messages = (
                [HumanMessage(content=value)]
                if isinstance(value, str) else convert_to_messages(value)
            )
            return [*messages, HumanMessage(content=instructions)]

        chain = RunnableLambda(add_schema) | model | parser

    # Retry malformed responses once; authentication/request failures still surface.
    validated = chain.with_retry(
        retry_if_exception_type=(OutputParserException, ValidationError),
        stop_after_attempt=2,
    )
    if config.LLM_THINKING:
        return validated

    # Some compatible endpoints return empty tool arguments for valid nested
    # schemas. Retry via plain JSON only after schema parsing failed twice.
    # Authentication/network failures do not trigger a different request mode.
    parser = PydanticOutputParser(pydantic_object=schema)
    def json_fallback_prompt(value: LanguageModelInput):
        import logging
        logging.getLogger(__name__).warning("Structured tool output invalid; using validated JSON fallback for %s", schema.__name__)
        messages = [HumanMessage(content=value)] if isinstance(value, str) else convert_to_messages(value)
        return [*messages, HumanMessage(content="Return exactly one JSON object without commentary.\n" + parser.get_format_instructions())]
    fallback = (RunnableLambda(json_fallback_prompt) | model | parser).with_retry(
        retry_if_exception_type=(OutputParserException, ValidationError), stop_after_attempt=2,
    )
    return validated.with_fallbacks([fallback], exceptions_to_handle=(OutputParserException, ValidationError))
