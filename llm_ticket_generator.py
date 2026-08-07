"""LLM-backed ticket generator.

Wraps the Hugging Face model `ai-in-projectmanagement/ProjectManagementLLM` and
turns a free-form Delivery Manager prompt into structured ticket dicts that
match the schema used by `tickets_config.json` and `generate_tickets.py`.

The model is loaded lazily on first use so the CLI / rest of the app is not
penalized when the LLM feature is unused. Loading requires `transformers`,
`torch`, and (optionally) `accelerate`.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional


DEFAULT_MODEL_ID = "ai-in-projectmanagement/ProjectManagementLLM"


class PMLLMTicketGenerator:
    """Generate ticket dicts from a free-form prompt using a Hugging Face LLM.

    The output is a list of dicts shaped like a `tickets_config.json` ticket:
        {id, title, type, owner, description, acceptance_criteria, tags}

    The caller can pass these directly into `generate_tickets.generate_ticket`
    to produce fully-rendered tickets.
    """

    def __init__(self, model_id: Optional[str] = None, hf_token: Optional[str] = None) -> None:
        self.model_id = model_id or DEFAULT_MODEL_ID
        self.hf_token = hf_token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN")
        self._pipe = None
        self._load_error: Optional[str] = None

    @property
    def is_ready(self) -> bool:
        return self._pipe is not None

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def _ensure_loaded(self) -> None:
        if self._pipe is not None:
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

            kwargs: Dict[str, Any] = {}
            if self.hf_token:
                kwargs["token"] = self.hf_token

            tokenizer = AutoTokenizer.from_pretrained(self.model_id, **kwargs)
            model_kwargs: Dict[str, Any] = dict(kwargs)
            if torch.cuda.is_available():
                model_kwargs["torch_dtype"] = torch.float16
                model_kwargs["device_map"] = "auto"
            model = AutoModelForCausalLM.from_pretrained(self.model_id, **model_kwargs)

            self._pipe = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                device_map="auto" if torch.cuda.is_available() else None,
            )
        except Exception as e:
            self._load_error = f"{type(e).__name__}: {e}"
            raise

    def _build_prompt(
        self,
        user_prompt: str,
        source: str,
        env: str,
        role_label: str,
        existing_titles: List[str],
    ) -> str:
        existing_block = "\n".join(f"- {t}" for t in existing_titles[:20]) or "- (none)"
        return f"""You are a Delivery Manager assistant. Produce additional Azure DevOps
user-story tickets to complement an existing backlog.

Context:
- Source system: {source}
- Environment: {env}
- Primary workstream: {role_label}

Delivery Manager request:
{user_prompt.strip()}

Existing ticket titles (do NOT duplicate):
{existing_block}

Return ONLY a JSON array. Each element MUST be an object with these keys:
- "id": short code (e.g. "AI-01")
- "title": string, may use "{{SOURCE}}" and "{{ENV}}" placeholders
- "type": "User Story"
- "owner": job title (e.g. "Data Engineer", "BI Developer", "UX Designer")
- "description": markdown string, may use "{{SOURCE}}" and "{{ENV}}"
- "acceptance_criteria": array of 3-6 concise strings
- "tags": array of 2-5 short lowercase strings

Respond with the JSON array only. No prose, no code fences.

JSON:
"""

    def generate_ticket_configs(
        self,
        prompt: str,
        source: str,
        env: str,
        role_label: str = "Data Engineer",
        existing_titles: Optional[List[str]] = None,
        max_new_tokens: int = 1024,
        temperature: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """Return a list of ticket-config dicts inferred from the prompt.

        Empty or whitespace-only prompts return an empty list without loading
        the model.
        """
        if not prompt or not prompt.strip():
            return []

        self._ensure_loaded()
        assert self._pipe is not None

        full_prompt = self._build_prompt(prompt, source, env, role_label, existing_titles or [])
        raw = self._pipe(
            full_prompt,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=temperature,
            top_p=0.9,
            return_full_text=False,
        )[0]["generated_text"]

        return self._parse_tickets(raw)

    @staticmethod
    def _parse_tickets(text: str) -> List[Dict[str, Any]]:
        """Extract a JSON array of tickets from a model response.

        Falls back to a single "review this" ticket wrapping the raw text if
        no valid JSON array is found — the DM can always edit it downstream.
        """
        m = re.search(r"\[\s*{.*}\s*]", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                if isinstance(data, list):
                    return [
                        _normalize_ticket(item, idx)
                        for idx, item in enumerate(data, 1)
                        if isinstance(item, dict) and item.get("title")
                    ]
            except json.JSONDecodeError:
                pass

        raw = text.strip()
        if not raw:
            return []
        return [
            {
                "id": "AI-RAW",
                "title": "[AI-Suggested] Review LLM-generated content",
                "type": "User Story",
                "owner": "Delivery Manager",
                "description": (
                    "The LLM returned content that could not be parsed as structured tickets. "
                    "Review and refine manually.\n\n---\n\n" + raw
                ),
                "acceptance_criteria": [
                    "Delivery Manager reviews the raw LLM output",
                    "Content is broken into concrete tickets and re-imported",
                ],
                "tags": ["ai-generated", "review"],
            }
        ]


def _normalize_ticket(item: Dict[str, Any], idx: int) -> Dict[str, Any]:
    """Coerce an LLM-produced ticket dict into the expected schema."""
    ac = item.get("acceptance_criteria") or []
    if isinstance(ac, str):
        ac = [line.strip("-*• ").strip() for line in ac.splitlines() if line.strip()]
    tags = item.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[,;]", tags) if t.strip()]
    return {
        "id": str(item.get("id") or f"AI-{idx:02d}"),
        "title": str(item.get("title") or f"AI-Suggested Ticket {idx}"),
        "type": str(item.get("type") or "User Story"),
        "owner": str(item.get("owner") or "Data Engineer"),
        "description": str(item.get("description") or ""),
        "acceptance_criteria": [str(x) for x in ac],
        "tags": [str(x) for x in tags],
    }
