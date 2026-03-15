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
        Call OpenRouter API using requests. Uses .env for API key and model.
        Always returns the full parsed JSON response (not just content), like call_groq.
        """
        api_key = os.environ.get("OPENROUTER_API_KEY")
        url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
        model_name = model or os.environ.get("OPENROUTER_MODEL", "openrouter/free")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        if messages is None:
            messages = [{"role": "user", "content": prompt}]
        data = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens
        }
        if reasoning:
            data["reasoning"] = {"enabled": True}
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=30)
            print(f"[LLM DEBUG] OpenRouter response status: {resp.status_code}")
            print(f"[LLM DEBUG] OpenRouter response body: {resp.text[:500]}")
            resp.raise_for_status()
            result = resp.json()
            return result
        except Exception as e:
            print(f"[LLM DEBUG] OpenRouter failed: {e}")
            return {"error": f"[OpenRouter error: {e}]"}

    def call_groq(self, prompt: str, model: Optional[str] = None, max_tokens: int = 512) -> dict:
        """
        Calls Groq API and returns the full parsed JSON response (not just content).
        """
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
            return data
        except Exception as e:
            print(f"[LLM DEBUG] Groq failed: {e}")
            return {"error": f"[Groq error: {e}]"}
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
    def generate_day_one_answers(self, prompt: str, evidence: dict = None, max_tokens: int = 1024) -> dict:
        """
        Calls Groq, extracts and parses the LLM content, and returns a dict with q1-q5 and evidence.
        Ensures onboarding_brief.md is always populated with valid answers or clear error messages.
        """
        import logging
        import re
        logger = logging.getLogger("llm_debug")
        errors = []
        try:
            groq_api = self.call_groq(prompt, max_tokens=max_tokens)
            logger.warning(f"[LLM DEBUG] Raw Groq API response: {groq_api}")
            if isinstance(groq_api, dict) and "choices" in groq_api and groq_api["choices"]:
                content = groq_api["choices"][0]["message"]["content"]
                cleaned = content.strip()
                # Remove triple backtick code block (```json ... ``` or ``` ... ```), allowing for leading whitespace/newlines
                codeblock_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
                if codeblock_match:
                    cleaned = codeblock_match.group(1).strip()
                # Fallback: extract first {...} block if code block not found
                if not codeblock_match:
                    brace_start = cleaned.find('{')
                    brace_end = cleaned.rfind('}')
                    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
                        cleaned = cleaned[brace_start:brace_end+1]
                try:
                    parsed = json.loads(cleaned)
                except Exception as e:
                    logger.error(f"[LLM DEBUG] Groq content not valid JSON: {e}")
                    # Fallback: extract q1-q5 answers using regex
                    import re
                    fallback = {}
                    for k in ['q1', 'q2', 'q3', 'q4', 'q5']:
                        # Match: "q1": "..." (allow multiline)
                        m = re.search(r'"%s"\s*:\s*"([^"]*)"' % k, cleaned, re.DOTALL)
                        if m:
                            fallback[k] = m.group(1).replace('\\n', '\n').strip()
                        else:
                            fallback[k] = 'No answer available (Groq parse fallback).'
                    if evidence and 'evidence' not in fallback:
                        fallback['evidence'] = evidence
                    fallback['raw_response'] = cleaned
                    return fallback
                for k in ['q1', 'q2', 'q3', 'q4', 'q5']:
                    if k not in parsed:
                        parsed[k] = 'No answer available.'
                if evidence and 'evidence' not in parsed:
                    parsed['evidence'] = evidence
                parsed['raw_response'] = cleaned
                return parsed
            elif isinstance(groq_api, dict) and "error" in groq_api:
                logger.error(f"[LLM DEBUG] Groq API error: {groq_api['error']}")
                errors.append(groq_api["error"])
            else:
                logger.error(f"[LLM DEBUG] Unexpected Groq API response: {groq_api}")
                errors.append(str(groq_api))
        except Exception as e:
            logger.error(f"[LLM DEBUG] Exception in generate_day_one_answers: {e}")
            errors.append(f"Groq: {e}")
        return {
            'q1': 'No answer available (Groq error).',
            'q2': 'No answer available (Groq error).',
            'q3': 'No answer available (Groq error).',
            'q4': 'No answer available (Groq error).',
            'q5': 'No answer available (Groq error).',
            'evidence': evidence or {},
            'raw_response': '; '.join(errors)
        }