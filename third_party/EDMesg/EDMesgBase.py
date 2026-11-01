from abc import ABC
from pydantic import BaseModel
from typing import Any


class EDMesgAction(BaseModel, ABC):
    pass


class EDMesgWelcomeAction(EDMesgAction):
    pass


class EDMesgEvent(BaseModel, ABC):
    pass


class EDMesgEnvelope(BaseModel):
    type: str
    data: dict[str, Any]
