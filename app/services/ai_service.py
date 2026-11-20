"""AI courseware summarisation service.

Extracts text from a PDF or PPTX file and asks DeepSeek to produce a concise
list of key points in the requested language.
"""
from app.config import Config
from app.utils.text_extract import extract_pdf_text, extract_pptx_text


SYSTEM_PROMPT = (
    "You are a helpful teaching assistant. Given lecture or lab material, "
    "produce a clear, concise study summary that a student can scan quickly.\n"
    "Format rules:\n"
    "- Start with a single short title line beginning with '# '.\n"
    "- Group the content into 3 to 6 sections using '## ' headings.\n"
    "- Under each heading use short bullet points starting with '- '.\n"
    "- Use **bold** only for key terms. Keep each bullet to one line.\n"
    "- Do not use tables, code fences, numbered lists or horizontal rules.\n"
    "- Preserve key definitions and formulas. Do not invent content.\n"
    "- Aim for no more than 18 bullet points in total."
)


def summarize(resource, language="en"):
    """Summarise one courseware resource.

    Args:
        resource: a Resource model instance.
        language: "en" or "zh" for the output language.

    Returns:
        The generated summary text.

    Raises:
        RuntimeError: when the API key is missing or the request fails.
    """
    if not Config.DEEPSEEK_API_KEY:
        raise RuntimeError("DeepSeek API key is not configured.")

    from app.services import storage_service

    data = storage_service.fetch_bytes(resource)
    if resource.file_type == "pptx":
        text = extract_pptx_text(data)
    else:
        text = extract_pdf_text(data)

    if not text.strip():
        raise RuntimeError("No readable text was found in this file.")

    lang_instruction = (
        "Write the summary in Simplified Chinese."
        if language == "zh"
        else "Write the summary in English."
    )
    user_prompt = (
        f"Course: {resource.course.title}\n"
        f"Material: {resource.title}\n\n"
        f"{lang_instruction}\n\n"
        f"Material content:\n{text}"
    )

    return _call_deepseek(user_prompt)


def _chat(system_prompt, user_prompt, max_tokens=1200, response_format=None):
    """Send one chat completion request and return the assistant text.

    Keeping the HTTP call in a single helper lets every AI feature share the
    same configuration and error handling.
    """
    if not Config.DEEPSEEK_API_KEY:
        raise RuntimeError("DeepSeek API key is not configured.")

    import requests

    payload = {
        "model": Config.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format

    response = requests.post(
        f"{Config.DEEPSEEK_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def _call_deepseek(user_prompt):
    """Send a courseware-summary request to the DeepSeek API."""
    return _chat(SYSTEM_PROMPT, user_prompt)
