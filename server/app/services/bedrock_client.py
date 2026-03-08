"""AWS Bedrock client — supports both Bearer Token (API Key) and IAM auth.

Bearer token auth uses direct HTTP requests to the Bedrock REST API.
IAM auth uses boto3's Converse API.
Both are model-agnostic (works with Nova, Claude, Titan, etc.).
"""
import json
import logging

import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_boto_client = None


def _get_boto_client():
    global _boto_client
    if _boto_client is None:
        import boto3
        kwargs = {"region_name": settings.AWS_REGION}
        if settings.AWS_ACCESS_KEY_ID:
            kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        _boto_client = boto3.client("bedrock-runtime", **kwargs)
    return _boto_client


def _invoke_bearer_token(
    system_prompt: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    model_id: str,
) -> str:
    """Invoke Bedrock via REST API with Bearer Token (API Key) auth."""
    region = settings.AWS_REGION
    url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/converse"

    # Build Converse API request body
    converse_messages = [
        {"role": msg["role"], "content": [{"text": msg["content"]}]}
        for msg in messages
    ]

    payload = {
        "system": [{"text": system_prompt}],
        "messages": converse_messages,
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.AWS_BEARER_TOKEN_BEDROCK}",
    }

    response = httpx.post(url, json=payload, headers=headers, timeout=60.0)
    response.raise_for_status()
    result = response.json()

    return result["output"]["message"]["content"][0]["text"]


def _invoke_boto(
    system_prompt: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    model_id: str,
) -> str:
    """Invoke Bedrock via boto3 Converse API with IAM auth."""
    client = _get_boto_client()

    converse_messages = [
        {"role": msg["role"], "content": [{"text": msg["content"]}]}
        for msg in messages
    ]

    response = client.converse(
        modelId=model_id,
        system=[{"text": system_prompt}],
        messages=converse_messages,
        inferenceConfig={
            "maxTokens": max_tokens,
            "temperature": temperature,
        },
    )
    return response["output"]["message"]["content"][0]["text"]


def invoke_bedrock(
    system_prompt: str,
    messages: list[dict],
    max_tokens: int | None = None,
    temperature: float = 0.3,
    model_id: str | None = None,
) -> str:
    """Invoke a Bedrock model. Auto-selects auth method:
    - Bearer token (API Key) if AWS_BEARER_TOKEN_BEDROCK is set
    - IAM credentials (boto3) otherwise

    Args:
        system_prompt: System-level instructions for the model.
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts.
        max_tokens: Max tokens to generate (defaults to config value).
        temperature: Sampling temperature.
        model_id: Override model ID (e.g. use Pro for summarization).

    Returns:
        The assistant's text response.
    """
    max_tokens = max_tokens or settings.BEDROCK_MAX_TOKENS
    resolved_model = model_id or settings.BEDROCK_MODEL_ID

    try:
        if settings.AWS_BEARER_TOKEN_BEDROCK:
            return _invoke_bearer_token(system_prompt, messages, max_tokens, temperature, resolved_model)
        else:
            return _invoke_boto(system_prompt, messages, max_tokens, temperature, resolved_model)
    except Exception as e:
        logger.error("Bedrock invocation failed: %s", e)
        raise
