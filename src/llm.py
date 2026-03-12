

import os
import requests
import json
from typing import List, Optional

# Gemini official client
try:
    from google import genai
    _HAS_GENAI = True
except ImportError:
    _HAS_GENAI = False

# Load .env if present (ensures env vars are available even if LLMClient is used standalone)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class ContextWindowBudget:
    """
    Tracks token usage and selects appropriate LLM based on context size and cost discipline.
    """
    def __init__(self, max_tokens: int = 8192):
        self.max_tokens = max_tokens
        self.cumulative_tokens = 0

    def estimate_tokens(self, text: str) -> int:
        # Simple heuristic: 1 token ≈ 4 chars (adjust as needed)
        return max(1, len(text) // 4)

    def can_fit(self, text: str) -> bool:
        return self.estimate_tokens(text) <= self.max_tokens

    def spend(self, text: str):
        self.cumulative_tokens += self.estimate_tokens(text)

class LLMClient:
    def __init__(self, ollama_url: Optional[str] = None, gemini_api_key: Optional[str] = None):
        self.ollama_url = ollama_url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "AIzaSyBLMHl0R4AiuTkmePvuEPmZW80pPmhUXc8")
        self.gemini_model = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
        self.ollama_default_model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

    def call_ollama(self, prompt: str, model: Optional[str] = None, max_tokens: int = 512) -> str:
        model = model or self.ollama_default_model
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens}
        }
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")

    def call_gemini(self, prompt: str, model: Optional[str] = None, max_tokens: int = 512) -> str:
        if not _HAS_GENAI:
            raise ImportError("google-genai is not installed. Please install with 'pip install google-generativeai'.")
        api_key = self.gemini_api_key
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        os.environ["GEMINI_API_KEY"] = api_key  # Ensure env var is set for client
        client = genai.Client()
        model = model or self.gemini_model
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                generation_config={"max_output_tokens": max_tokens}
            )
            return response.text
        except Exception as e:
            return f"[Gemini API error: {e}]"

    def generate_purpose_statement(self, code: str, docstring: Optional[str] = None, prefer_fast: bool = True) -> str:
        # Use Gemini Flash or phi3:mini for bulk, llama3.1:8b for higher quality
        budget = ContextWindowBudget()
        tokens = budget.estimate_tokens(code)
        if prefer_fast and tokens < 6000 and self.gemini_api_key:
            prompt = self._purpose_prompt(code, docstring)
            return self.call_gemini(prompt, model="gemini-3-flash-preview", max_tokens=256)
        elif prefer_fast and tokens < 6000:
            prompt = self._purpose_prompt(code, docstring)
            return self.call_ollama(prompt, model="phi3:mini", max_tokens=256)
        else:
            prompt = self._purpose_prompt(code, docstring)
            return self.call_ollama(prompt, model="llama3.1:8b", max_tokens=256)

    def _purpose_prompt(self, code: str, docstring: Optional[str]) -> str:
        prompt = (
            "You are a senior software engineer. "
            "Given the following module code, write a 2-3 sentence purpose statement that explains the business function (not implementation details). "
            "If a docstring is provided, cross-check it and flag any discrepancies as 'Documentation Drift'.\n"
        )
        if docstring:
            prompt += f"\nDocstring:\n{docstring}\n"
        prompt += f"\nCode:\n{code}\n"
        prompt += "\nPurpose Statement:"
        return prompt
