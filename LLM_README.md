# Brownfield Cartographer LLM Integration

This system supports multiple LLM backends for the Semanticist agent:

- **Local Ollama** (default: llama3.1:8b, phi3:mini)
- **Gemini API** (default: gemini-3-flash-preview)

## Configuration

Set the following environment variables as needed:

- `OLLAMA_URL` (default: http://localhost:11434)
- `OLLAMA_MODEL` (default: llama3.1:8b)
- `GEMINI_API_KEY` (required for Gemini)
- `GEMINI_MODEL` (default: gemini-3-flash-preview)

## Model Selection Logic

- For bulk module summarization, the system prefers fast/cheap models (Gemini Flash, phi3:mini).
- For larger or more complex contexts, or when higher quality is needed, it uses llama3.1:8b (Ollama) or Gemini.

## Usage

- The Semanticist agent will automatically select the best model based on context size and availability.
- You can override defaults by setting the environment variables above.

## Adding More LLMs

- Extend `src/llm.py` with new API clients as needed.
- Add new environment variables for API keys and model names.
