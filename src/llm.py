

import os
import requests
import json
from typing import List, Optional

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
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "AIzaSyC5t_zEJJ3C_dY5V9Od2Z9Hholg84yZKiE")
        self.gemini_model = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
        self.ollama_default_model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

    def call_ollama(self, prompt: str, model: Optional[str] = None, max_tokens: int = 512) -> str:
        models_to_try = [model or self.ollama_default_model, "phi3:mini", "llama3.1:8b"]
        tried = set()
        for m in models_to_try:
            if m in tried:
                continue
            tried.add(m)
            url = f"{self.ollama_url}/api/generate"
            payload = {
                "model": m,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens}
            }
            try:
                resp = requests.post(url, json=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                if "response" in data:
                    return data["response"]
            except requests.exceptions.Timeout:
                print(f"Ollama model '{m}' timed out.")
            except Exception as e:
                print(f"Ollama model '{m}' failed: {e}")
        return "[Ollama error: All local LLMs failed or timed out.]"

    def call_gemini(self, prompt: str, model: Optional[str] = None, max_tokens: int = 512) -> str:
        if not _HAS_GENAI:
            raise ImportError("google-genai is not installed. Please install with 'pip install google-genai'.")
        model_name = model or self.gemini_model or "gemini-3-flash-preview"
        try:
            client = genai.Client()
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {e}")

    def generate_purpose_statement(self, code: str, docstring: Optional[str] = None, prefer_fast: bool = True) -> str:
        # Use Gemini Flash or phi3:mini for bulk, llama3.1:8b for higher quality
        budget = ContextWindowBudget()
        tokens = budget.estimate_tokens(code)
        prompt = self._purpose_prompt(code, docstring)
        if prefer_fast and tokens < 6000 and self.gemini_api_key:
            try:
                return self.call_gemini(prompt, model="gemini-3-flash-preview", max_tokens=256)
            except Exception as e:
                # Fallback to Ollama phi3:mini for any Gemini error
                return self.call_ollama(prompt, model="phi3:mini", max_tokens=256)
        elif prefer_fast and tokens < 6000:
            return self.call_ollama(prompt, model="phi3:mini", max_tokens=256)
        else:
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
