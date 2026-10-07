from typing import Protocol

from app.schemas import AssistantAnswer, AssistantContext, AssistantRequest


class AssistantProvider(Protocol):
    def answer(self, request: AssistantRequest, context: AssistantContext) -> AssistantAnswer: ...
