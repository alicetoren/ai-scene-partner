from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.models import Scene
from app.services.script_parser import ScriptParser, get_script_parser


router = APIRouter(prefix="/api/scenes", tags=["scenes"])


@router.post("/parse", response_model=Scene)
async def parse_scene(
    script_file: UploadFile,
    parser: Annotated[ScriptParser, Depends(get_script_parser)],
) -> Scene:
    if not script_file.filename or not script_file.filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only plain-text (.txt) scripts are supported.",
        )

    contents = await script_file.read()
    try:
        script_text = contents.decode("utf-8")
    except UnicodeDecodeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The script must be UTF-8 encoded text.",
        ) from error

    if not script_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded script is empty.",
        )

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
