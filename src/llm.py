

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
        # Only try each model once, in order, and stop after the first attempt for each
        models_to_try = []
        if model:
            models_to_try.append(model)
        if self.ollama_default_model not in models_to_try:
            models_to_try.append(self.ollama_default_model)
        for fallback in ["phi3:mini", "llama3.1:8b"]:
            if fallback not in models_to_try:
                models_to_try.append(fallback)
        errors = []
        for m in models_to_try:
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
                errors.append(f"Ollama model '{m}' timed out.")
            except Exception as e:
                errors.append(f"Ollama model '{m}' failed: {e}")
            # Stop after first attempt for this model, do not retry
        return f"[Ollama error: All local LLMs failed or timed out. Details: {'; '.join(errors)}]"

    def call_gemini(self, prompt: str, model: Optional[str] = None, max_tokens: int = 512) -> str:
        # Only try Gemini once per request, no retries
        if not _HAS_GENAI:
            return "[Gemini error: google-genai is not installed. Please install with 'pip install google-genai'.]"
        model_name = model or self.gemini_model or "gemini-3-flash-preview"
        try:
            client = genai.Client()
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            return f"[Gemini error: {e}]"

    def generate_purpose_statement(self, code: str, docstring: Optional[str] = None, prefer_fast: bool = True) -> str:
        budget = ContextWindowBudget()
        tokens = budget.estimate_tokens(code)
        prompt = self._purpose_prompt(code, docstring)
        errors = []

        # 1. Try Gemini once if conditions met
        if prefer_fast and tokens < 6000 and self.gemini_api_key:
            gemini_result = self.call_gemini(prompt, model="gemini-3-flash-preview", max_tokens=256)
            if not gemini_result.startswith("[Gemini error"):
                return gemini_result
            errors.append(gemini_result)
        # 2. Try each Ollama model only once, in order, and stop after first attempt for each
        ollama_models = ["phi3:mini", "llama3.1:8b"]
        for ollama_model in ollama_models:
            ollama_result = self.call_ollama(prompt, model=ollama_model, max_tokens=256)
            if not ollama_result.startswith("[Ollama error"):
                return ollama_result
            errors.append(ollama_result)
        # Try the default model if it's not one of the above
        default_model = self.ollama_default_model
        if default_model not in ollama_models:
            ollama_result3 = self.call_ollama(prompt, model=default_model, max_tokens=256)
            if not ollama_result3.startswith("[Ollama error"):
                return ollama_result3
            errors.append(ollama_result3)
        # 3. All models failed → return placeholder sentence
        placeholder = "Unable to generate purpose statement due to LLM unavailability."
        # Optionally log errors here if needed, but return only the placeholder
        return placeholder

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
