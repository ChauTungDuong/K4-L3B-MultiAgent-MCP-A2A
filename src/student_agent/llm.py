from __future__ import annotations

import json
from typing import Any
import httpx2


async def call_local_qwen(
    prompt: str,
    system_prompt: str = "You are an expert e-commerce claim investigation assistant.",
    model: str = "qwen2.5-3b-instruct",
    endpoint: str = "http://localhost:1234/v1/chat/completions",
    timeout: float = 8.0,
) -> dict[str, Any] | None:
    """Call the local Qwen 2.5 3B model via OpenAI-compatible endpoint."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    try:
        async with httpx2.AsyncClient(timeout=timeout) as client:
            resp = await client.post(endpoint, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                # Try extracting JSON if model wrapped in markdown code fence
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                try:
                    return json.loads(content)
                except Exception:
                    return {"raw_text": content}
    except Exception:
        pass
    return None
