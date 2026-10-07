import json
import os

from app.schemas import AssistantAnswer, AssistantContext, AssistantRequest

SYSTEM_PROMPT = (
    "Administrative workflow only. Do not diagnose, treat, invent status, or exceed supplied facts."
)


def _missing(name: str, detail: str) -> RuntimeError:
    return RuntimeError(f"{name} assistant requires {detail}.")


def _gemini_model():
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise _missing("Gemini", "GOOGLE_API_KEY or GEMINI_API_KEY in the environment")
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise _missing("Gemini", "langchain-google-genai (reinstall project dependencies)") from exc
    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
        google_api_key=api_key,
        temperature=0,
        max_output_tokens=512,
        timeout=60,
        max_retries=1,
    )


def _openai_model():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise _missing("OpenAI", "OPENAI_API_KEY in the environment")
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise _missing("OpenAI", "langchain-openai (reinstall project dependencies)") from exc
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
        temperature=0,
        max_tokens=512,
        timeout=60,
        max_retries=1,
    )


class LLMAssistantProvider:
    """LangChain chat model (Gemini or OpenAI) answering only from supplied facts."""

    def __init__(self, provider: str) -> None:
        self._model = {"gemini": _gemini_model, "openai": _openai_model}[provider]()
        self._label = provider.capitalize() if provider == "gemini" else "OpenAI"

    def answer(self, request: AssistantRequest, context: AssistantContext) -> AssistantAnswer:
        if not context.facts:
            return AssistantAnswer(
                answer="Access is unavailable for that administrative record.",
                facts_used=[],
                freshness=context.freshness,
                may_be_stale=context.stale,
            )
        facts_json = json.dumps(context.facts, indent=2, default=str)
        freshness = context.freshness.isoformat() if context.freshness else "unknown"
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            "Rules:\n"
            "- Use only the provided facts.\n"
            "- If the question asks for diagnosis, treatment, medication, symptoms, or clinical risk, "
            "reply that this assistant supports administrative coordination only.\n"
            "- Keep answer to at most three short sentences.\n"
            "- Mention if context may be stale when stale is true.\n\n"
            f"Question: {request.question}\n"
            f"Patient filter: {request.patient_id or 'none'}\n"
            f"Projection freshness timestamp: {freshness}\n"
            f"May be stale: {context.stale}\n"
            f"Facts (JSON):\n{facts_json}"
        )
        try:
            response = self._model.invoke(prompt)
        except Exception as exc:
            raise RuntimeError(f"{self._label} request failed: {str(exc)[:300]}") from exc
        content = response.content
        if isinstance(content, list):
            content = "\n".join(str(item) for item in content)
        return AssistantAnswer(
            answer=str(content).strip(),
            facts_used=context.facts,
            freshness=context.freshness,
            may_be_stale=context.stale,
        )
