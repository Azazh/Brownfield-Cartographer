

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
        self.token_log = []  # [(call_type, tokens, model, file, line_range)]

    def estimate_tokens(self, text: str) -> int:
        # Simple heuristic: 1 token ≈ 4 chars (adjust as needed)
        return max(1, len(text) // 4)

    def can_fit(self, text: str) -> bool:
        return self.estimate_tokens(text) <= self.max_tokens

    def spend(self, text: str, call_type: str = '', model: str = '', file: str = '', line_range: str = ''):
        tokens = self.estimate_tokens(text)
        self.cumulative_tokens += tokens
        self.token_log.append({'call_type': call_type, 'tokens': tokens, 'model': model, 'file': file, 'line_range': line_range})

    def report(self):
        return {'cumulative_tokens': self.cumulative_tokens, 'calls': self.token_log}

class LLMClient:
    def call_openrouter(self, prompt: str, model: Optional[str] = None, max_tokens: int = 512, messages: Optional[list] = None, reasoning: bool = False) -> dict:
        """
        Call OpenRouter API. If messages is None, use single prompt. If reasoning is True, enable reasoning in payload.
        Returns a dict with at least 'content' and optionally 'reasoning_details'.
        """
        api_key = os.environ.get("OPENROUTER_API_KEY")
        base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
        model_name = model or os.environ.get("OPENROUTER_MODEL", "openrouter/free")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        if messages is None:
            messages = [{"role": "user", "content": prompt}]
        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens
        }
        if reasoning:
            payload["reasoning"] = {"enabled": True}
        try:
            resp = requests.post(base_url, headers=headers, data=json.dumps(payload), timeout=30)
            print(f"[LLM DEBUG] OpenRouter response status: {resp.status_code}")
            print(f"[LLM DEBUG] OpenRouter response body: {resp.text[:500]}")
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                return {"content": "[OpenRouter error: Malformed response]"}
            if "choices" in data and data["choices"]:
                message = data["choices"][0]["message"]
                result = {"content": message.get("content")}
                if "reasoning_details" in message:
                    result["reasoning_details"] = message["reasoning_details"]
                return result
            return {"content": f"[OpenRouter error: No choices in response]"}
        except Exception as e:
            print(f"[LLM DEBUG] OpenRouter failed: {e}")
            return {"content": f"[OpenRouter error: {e}]"}

    def call_groq(self, prompt: str, model: Optional[str] = None, max_tokens: int = 512) -> str:
        api_key = os.environ.get("GROQ_API_KEY")
        base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1/chat/completions")
        model_name = model or os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens
        }
        try:
            resp = requests.post(base_url, headers=headers, json=payload, timeout=30)
            print(f"[LLM DEBUG] Groq response status: {resp.status_code}")
            print(f"[LLM DEBUG] Groq response body: {resp.text[:500]}")
            resp.raise_for_status()
            data = resp.json()
            if "choices" in data and data["choices"]:
                return data["choices"][0]["message"]["content"]
            return f"[Groq error: No choices in response]"
        except Exception as e:
            print(f"[LLM DEBUG] Groq failed: {e}")
            return f"[Groq error: {e}]"
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
            print(f"[LLM DEBUG] Calling Ollama at {url} with model '{m}'...")
            try:
                resp = requests.post(url, json=payload, timeout=30)
                print(f"[LLM DEBUG] Ollama response status: {resp.status_code}")
                print(f"[LLM DEBUG] Ollama response body: {resp.text[:500]}")
                resp.raise_for_status()
                data = resp.json()
                if "response" in data:
                    print(f"[LLM DEBUG] Ollama returned response: {data['response'][:200]}")
                    return data["response"]
            except requests.exceptions.Timeout:
                print(f"[LLM DEBUG] Ollama model '{m}' timed out.")
                errors.append(f"Ollama model '{m}' timed out.")
            except Exception as e:
                print(f"[LLM DEBUG] Ollama model '{m}' failed: {e}")
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

    def generate_purpose_statement(self, code: str, docstring: Optional[str] = None, prefer_fast: bool = True, file: str = '', line_range: str = '') -> str:
        budget = ContextWindowBudget()
        tokens = budget.estimate_tokens(code)
        prompt = self._purpose_prompt(code, docstring)
        errors = []

        # Model selection based on token budget
        fast_limit = 3000
        expensive_limit = 6000
        if tokens < fast_limit:
            model_choice = 'openrouter'
        elif tokens < expensive_limit:
            model_choice = 'groq'
        else:
            model_choice = 'none'  # Would fallback to chunking or error

        # 1. Try OpenRouter first if in budget
        if model_choice == 'openrouter':
            openrouter_result = self.call_openrouter(prompt, model=None, max_tokens=256)
            budget.spend(code, call_type='purpose', model='openrouter', file=file, line_range=line_range)
            if not openrouter_result.startswith("[OpenRouter error"):
                return openrouter_result
            errors.append(openrouter_result)
        # 2. Fallback to Groq if OpenRouter fails or if in higher budget
        if model_choice in ['openrouter', 'groq']:
            groq_result = self.call_groq(prompt, model=None, max_tokens=256)
            budget.spend(code, call_type='purpose', model='groq', file=file, line_range=line_range)
            if not groq_result.startswith("[Groq error"):
                return groq_result
            errors.append(groq_result)
        # 3. If both fail, stop and return placeholder
        return "Unable to generate purpose statement due to LLM unavailability (OpenRouter and Groq failed)."

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
