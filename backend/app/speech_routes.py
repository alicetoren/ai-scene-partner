from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from app.services.speech import SpeechGenerationError, SpeechService, get_speech_service


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=4096)
    voice_index: int = Field(default=0, ge=0, strict=True)


router = APIRouter(prefix="/api", tags=["speech"])


@router.post("/speech", response_class=Response)
def generate_speech(
    request: SpeechRequest,
    service: Annotated[SpeechService, Depends(get_speech_service)],
) -> Response:
    # A sync route keeps the blocking SDK call off the async event loop.
    try:
        audio = service.generate(request.text, request.voice_index)
    except RuntimeError as error:
        raise HTTPException(503, "Speech is not configured on the server.", headers={"X-Speech-Retryable": "false"}) from error
    except SpeechGenerationError as error:
        raise HTTPException(
            502, "Speech generation failed. Please retry this line.",
            headers={"X-Speech-Retryable": str(error.retryable).lower()},
        ) from error
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})
