from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.models import Scene
from app.services.script_extraction import MAX_UPLOAD_BYTES, ScriptUploadError, extract_script_text
from app.services.script_parser import ScriptParser, get_script_parser


router = APIRouter(prefix="/api/scenes", tags=["scenes"])


@router.post("/parse", response_model=Scene)
def parse_scene(
    script_file: UploadFile,
    parser: Annotated[ScriptParser, Depends(get_script_parser)],
) -> Scene:
    try:
        # A sync route keeps PDF extraction and the existing blocking SDK off the event loop.
        contents = script_file.file.read(MAX_UPLOAD_BYTES + 1)
        script_text = extract_script_text(script_file.filename, contents)
    except ScriptUploadError as error:
        raise HTTPException(error.status_code, str(error)) from error
    finally:
        script_file.file.close()

    try:
        return parser.parse(script_text)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Script analysis could not be completed. Please try again.",
        ) from error
