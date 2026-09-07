from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.main import app
from app.models import DialogueLine, Scene
from app.services.script_parser import OpenAIScriptParser, get_script_parser


class FakeScriptParser:
    def parse(self, script_text: str) -> Scene:
        assert script_text == "JANE: Where have you been?\nJOHN: I told you I'd be late."
        return Scene(
            title="Uploaded Scene",
            characters=["JANE", "JOHN"],
            lines=[
                DialogueLine(id=1, character="JANE", text="Where have you been?"),
                DialogueLine(id=2, character="JOHN", text="I told you I'd be late."),
            ],
        )


client = TestClient(app)


def setup_function() -> None:
    app.dependency_overrides[get_script_parser] = lambda: FakeScriptParser()


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_health_check_remains_available() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"message": "AI Scene Partner backend is running"}


def test_parse_scene_returns_validated_scene() -> None:
    response = client.post(
        "/api/scenes/parse",
        files={"script_file": ("scene.txt", b"JANE: Where have you been?\nJOHN: I told you I'd be late.", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "title": "Uploaded Scene",
        "characters": ["JANE", "JOHN"],
        "lines": [
            {"id": 1, "character": "JANE", "text": "Where have you been?"},
            {"id": 2, "character": "JOHN", "text": "I told you I'd be late."},
        ],
    }


def test_parse_scene_rejects_unsupported_file_type() -> None:
    response = client.post(
        "/api/scenes/parse",
        files={"script_file": ("scene.docx", b"not a text script", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert response.json()["detail"] == "Only TXT (.txt) and PDF (.pdf) scripts are supported."


def test_parse_scene_rejects_empty_script() -> None:
    response = client.post(
        "/api/scenes/parse",
        files={"script_file": ("scene.txt", b" \n\t", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "The uploaded script is empty."


def test_scene_validation_rejects_nonconsecutive_line_ids() -> None:
    with pytest.raises(ValidationError):
        Scene(
            title="Uploaded Scene",
            characters=["JANE"],
            lines=[DialogueLine(id=2, character="JANE", text="Hello.")],
        )


def test_openai_parser_validates_structured_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    class FakeResponse:
        output_text = '''{
            "title": "Uploaded Scene",
            "characters": ["JANE"],
            "lines": [{"id": 1, "character": "JANE", "text": "Hello."}]
        }'''

    class FakeResponses:
        def create(self, **kwargs: object) -> FakeResponse:
            assert kwargs["model"] == "test-model"
            assert kwargs["text"] == {"format": {
                "type": "json_schema",
                "name": "scene",
                "strict": True,
                "schema": Scene.model_json_schema(),
            }}
            return FakeResponse()

    class FakeOpenAIClient:
        responses = FakeResponses()

    scene = OpenAIScriptParser(client=FakeOpenAIClient()).parse("JANE: Hello.")  # type: ignore[arg-type]

    assert scene.lines[0].text == "Hello."


def test_screenplay_contract_at_mocked_openai_boundary():
    """Tests transport/validation, not the model's ability to obey instructions.

    Actual semantic grouping is additionally checked with a bounded manual live parse.
    """
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app.services.script_parser import PARSER_INSTRUCTIONS

    source = '''INT. ROOM - NIGHT
Someone sets down a cup.
    JUGHEAD
Would’ve gone a long way with me.
    ARCHIE
I was actually thinking...
    (putting it out there)
...I would maybe write her a song...to
explain, exactly, how much she means to me...
Someone looks out the window.
55.
    ARCHIE (CONT’D)
Did you hear?
    JUGHEAD
Not yet.
    (then)
Tell me more.
    ARCHIE
Tomorrow.
Someone leaves.'''
    expected = Scene(title='Uploaded Scene', characters=['JUGHEAD', 'ARCHIE'], lines=[
        DialogueLine(id=1, character='JUGHEAD', text='Would’ve gone a long way with me.'),
        DialogueLine(id=2, character='ARCHIE', text='I was actually thinking... ...I would maybe write her a song...to explain, exactly, how much she means to me...'),
        DialogueLine(id=3, character='ARCHIE', text='Did you hear?'),
        DialogueLine(id=4, character='JUGHEAD', text='Not yet. Tell me more.'),
        DialogueLine(id=5, character='ARCHIE', text='Tomorrow.'),
    ])
    create = Mock(return_value=SimpleNamespace(output_text=expected.model_dump_json()))
    fake_client = SimpleNamespace(responses=SimpleNamespace(create=create))
    result = OpenAIScriptParser(client=fake_client).parse(source)
    assert result == expected
    assert create.call_count == 1
    request = create.call_args.kwargs
    assert request['input'] == source  # No destructive normalization or truncation.
    assert request['instructions'] == PARSER_INSTRUCTIONS
    assert 'standalone character heading starts a NEW dialogue turn' in request['instructions']
    assert '(CONT’D)' in request['instructions']
    assert 'Exclude action/stage-direction paragraphs' in request['instructions']
    assert 'Ignore standalone page numbers' in request['instructions']
    assert request['text']['format']['schema'] == Scene.model_json_schema()
