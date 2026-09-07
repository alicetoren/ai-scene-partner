from io import BytesIO
from unittest.mock import MagicMock

from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject
import pytest

from app.main import app
from app.models import DialogueLine, Scene
from app.routes import parse_scene
from app.services.script_extraction import MAX_UPLOAD_BYTES, ScriptUploadError, extract_script_text
from app.services.script_parser import get_script_parser


SCRIPT = "JANE: Where have you been?\nJOHN: I told you I'd be late."


def make_pdf(pages, *, encrypted=False, image_only=False):
    """Build small real PDFs in memory; no external files or document-generation dependency."""
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        if text:
            font = DictionaryObject({
                NameObject('/Type'): NameObject('/Font'),
                NameObject('/Subtype'): NameObject('/Type1'),
                NameObject('/BaseFont'): NameObject('/Helvetica'),
                NameObject('/Encoding'): NameObject('/WinAnsiEncoding'),
            })
            page[NameObject('/Resources')] = DictionaryObject({
                NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)}),
            })
            stream = DecodedStreamObject()
            operations = ['BT /F1 12 Tf 16 TL 72 720 Td']
            for line in text.split('\n'):
                escaped = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
                operations.append(f'({escaped}) Tj T*')
            stream.set_data(('\n'.join(operations) + '\nET').encode('ascii'))
            page[NameObject('/Contents')] = writer._add_object(stream)
        if image_only:
            image = DecodedStreamObject()
            image.set_data(b'\x80')
            image.update({
                NameObject('/Type'): NameObject('/XObject'),
                NameObject('/Subtype'): NameObject('/Image'),
                NameObject('/Width'): NumberObject(1),
                NameObject('/Height'): NumberObject(1),
                NameObject('/BitsPerComponent'): NumberObject(8),
                NameObject('/ColorSpace'): NameObject('/DeviceGray'),
            })
            page[NameObject('/Resources')] = DictionaryObject({
                NameObject('/XObject'): DictionaryObject({NameObject('/Im1'): writer._add_object(image)}),
            })
            stream = DecodedStreamObject()
            stream.set_data(b'q 500 0 0 700 50 50 cm /Im1 Do Q')
            page[NameObject('/Contents')] = writer._add_object(stream)
    if encrypted:
        writer.encrypt('test-password', algorithm='RC4-128')
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def parser():
    fake = MagicMock()
    fake.parse.return_value = Scene(
        title='Uploaded Scene', characters=['JANE', 'JOHN'],
        lines=[DialogueLine(id=1, character='JANE', text='Where have you been?')],
    )
    app.dependency_overrides[get_script_parser] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


def test_txt_preserves_utf8_text_and_whitespace():
    text = '  JANE: Café?\r\nJOHN: Yes!\n'
    assert extract_script_text('SCENE.TXT', text.encode('utf-8')) == text


def test_pdf_extracts_text_in_page_order():
    pdf = make_pdf(['JANE: Where have you been?', "JOHN: I told you I'd be late."])
    text = extract_script_text('scene.PDF', pdf)
    assert text.index('JANE:') < text.index('JOHN:')
    assert text.split('\n\n')[0].strip() == 'JANE: Where have you been?'
    assert text.split('\n\n')[-1].strip() == "JOHN: I told you I'd be late."


@pytest.mark.parametrize('extension', ['txt', 'pdf'])
def test_both_formats_use_the_existing_parser_and_scene_response(parser, extension):
    content = SCRIPT.encode() if extension == 'txt' else make_pdf([SCRIPT])
    response = TestClient(app).post('/api/scenes/parse', files={'script_file': (f'scene.{extension}', content)})
    assert response.status_code == 200
    assert response.json() == parser.parse.return_value.model_dump()
    parser.parse.assert_called_once()
    text = parser.parse.call_args.args[0]
    assert isinstance(text, str)
    assert text.strip() == SCRIPT
    if extension == 'txt':
        assert text == SCRIPT


@pytest.mark.parametrize('filename, content, message', [
    ('empty.pdf', b'', 'empty'),
    ('no-pages.pdf', make_pdf([]), 'no pages'),
    ('blank.pdf', make_pdf([None]), 'Image-only/scanned'),
    ('scan.pdf', make_pdf([None], image_only=True), 'Image-only/scanned'),
    ('whitespace.pdf', make_pdf(['   ']), 'No usable text'),
    ('broken.pdf', b'%PDF-1.7\nnot a valid document', 'could not be read'),
    ('renamed.pdf', b'JANE: This is plain text.', 'could not be read'),
    ('locked.pdf', make_pdf([SCRIPT], encrypted=True), 'Encrypted'),
    ('non-utf8.txt', b'\xff\xfe', 'UTF-8'),
    ('empty.txt', b' \n\t', 'empty'),
])
def test_invalid_upload_never_reaches_parser(parser, filename, content, message):
    response = TestClient(app).post('/api/scenes/parse', files={'script_file': (filename, content)})
    assert response.status_code == 422
    assert message in response.json()['detail']
    parser.parse.assert_not_called()


@pytest.mark.parametrize('filename', ['scene.docx', 'scene.png', 'scene', 'scene.pdf.exe'])
def test_unsupported_extensions_are_rejected(parser, filename):
    response = TestClient(app).post('/api/scenes/parse', files={'script_file': (filename, b'text')})
    assert response.status_code == 415
    parser.parse.assert_not_called()


def test_pdf_page_extraction_failure_is_controlled(parser, monkeypatch):
    from pdfplumber.page import Page
    def unreadable(*args, **kwargs):
        raise ValueError('Internal PDF details')
    monkeypatch.setattr(Page, 'extract_text', unreadable)
    response = TestClient(app).post('/api/scenes/parse', files={'script_file': ('scene.pdf', make_pdf([SCRIPT]))})
    assert response.status_code == 422
    assert 'could not be read' in response.json()['detail']
    assert 'Internal PDF details' not in response.text
    parser.parse.assert_not_called()


def test_missing_filename_is_rejected():
    with pytest.raises(ScriptUploadError) as error:
        extract_script_text(None, b'text')
    assert error.value.status_code == 415


def test_upload_limit_is_inclusive():
    contents = b'x' * MAX_UPLOAD_BYTES
    assert len(extract_script_text('scene.txt', contents)) == MAX_UPLOAD_BYTES
    with pytest.raises(ScriptUploadError) as error:
        extract_script_text('scene.txt', contents + b'x')
    assert error.value.status_code == 413


@pytest.mark.parametrize('extension', ['txt', 'pdf'])
def test_oversized_upload_is_bounded_closed_and_never_parsed(extension):
    class TrackingStream(BytesIO):
        def read(self, size=-1):
            self.read_size = size
            return super().read(size)
    stream = TrackingStream(b'x' * (MAX_UPLOAD_BYTES + 10))
    parser = MagicMock()
    with pytest.raises(HTTPException) as error:
        parse_scene(UploadFile(stream, filename=f'scene.{extension}'), parser)
    assert error.value.status_code == 413
    assert stream.read_size == MAX_UPLOAD_BYTES + 1
    assert stream.closed
    parser.parse.assert_not_called()


def make_positioned_word_pdf(first_speaker, second_speaker):
    """Synthetic fixture for browser-exported PDFs with a text object per word/glyph.

    Mirrored page/text matrices and independent BT/ET blocks reproduce the real
    extraction failure without embedding the user's audition script in the repo.
    """
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Courier'),
        NameObject('/Encoding'): NameObject('/WinAnsiEncoding'),
    })
    page[NameObject('/Resources')] = DictionaryObject({
        NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)}),
    })
    rows = [
        [f'{first_speaker}:', ' ', 'Can', ' ', 'we', ' ', 'talk?'],
        [],
        [f'{second_speaker}:', ' ', 'Y', 'ou', ' ', 'can', "'", 't', ' ', 'leave.'],
        ['[quietly]'],
        ['   ', 'W', 'e', ' ', 'need', ' ', 'a', ' ', 'plan.'],
    ]
    operations = ['1 0 0 -1 0 792 cm']
    for row, chunks in enumerate(rows):
        operations.append(f'q 1 0 0 1 72 {72 + row * 18} cm')
        x = 0
        for chunk in chunks:
            operations.append(f'BT /F1 12 Tf 1 0 0 -1 0 0 Tm {x} -12 Td ({chunk}) Tj ET')
            x += len(chunk) * 7.2  # Courier's fixed glyph width at 12 points.
        operations.append('Q')
    stream = DecodedStreamObject()
    stream.set_data('\n'.join(operations).encode('ascii'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize('speakers', [('A', 'M'), ('ALICE', 'MORGAN')])
def test_positioned_words_become_visual_lines_without_losing_boundaries(speakers):
    pdf = make_positioned_word_pdf(*speakers)
    raw = PdfReader(BytesIO(pdf)).pages[0].extract_text()
    # Verify that the fixture actually triggers the original failure mode.
    assert 'Can\n \nwe\n \ntalk?' in raw
    assert "Y\nou\n \ncan\n'\nt" in raw
    text = extract_script_text('positioned.pdf', pdf)
    assert [line.strip() for line in text.splitlines() if line.strip()] == [
        f'{speakers[0]}: Can we talk?', f"{speakers[1]}: You can't leave.",
        '[quietly]', 'We need a plan.',
    ]
    assert '\n\n' in text  # A visual paragraph break is not flattened away.
    assert text.splitlines()[-1].startswith('   ')  # Indentation survives.


def test_parser_receives_reconstructed_lines_for_positioned_pdf(parser):
    response = TestClient(app).post('/api/scenes/parse', files={
        'script_file': ('positioned.pdf', make_positioned_word_pdf('A', 'M')),
    })
    assert response.status_code == 200
    parser.parse.assert_called_once()
    text = parser.parse.call_args.args[0]
    assert text.startswith('A: Can we talk?')
    assert "M: You can't leave." in text
    assert '[quietly]' in text
    assert 'Can\n' not in text


def test_txt_is_not_subject_to_pdf_reconstruction():
    text = "A:\n \nCan\n \nwe\n \ntalk?\r\nM: Y ou can't.\n\n  [quietly]\n"
    assert extract_script_text('scene.txt', text.encode()) == text


@pytest.mark.parametrize('speakers', [('ARCHIE', 'JUGHEAD'), ('A', 'M')])
def test_screenplay_drawing_order_does_not_change_visual_turn_order(parser, speakers):
    """Real positioned PDF: later editing appends headers outside reading order."""
    first, second = speakers
    rows = [
        '55.', 'INT. ROOM - NIGHT', 'Someone sets down a cup.',
        second, 'Would have gone a long way with me.',
        first, 'I was actually thinking...', '(putting it out there)',
        '...I would maybe write her a song...to',
        'explain, exactly, how much she means to me...',
        'Someone looks out the window.', f"{first} (CONT\u2019D)",
        'Did you hear?', second, 'Not yet.', '(then)', 'Tell me more.',
        first, 'Tomorrow.', 'Someone leaves.',
    ]
    reader = PdfReader(BytesIO(make_pdf(['placeholder'])))
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    operations = []
    # Paint bottom-to-top, independently positioned, as can happen after edits.
    for index in reversed(range(len(rows))):
        line = rows[index]
        x = 250 if line in (first, second, f"{first} (CONT\u2019D)") else 100
        escaped = line.replace('(', '\\(').replace(')', '\\)')
        operations.append(f'BT /F1 12 Tf 1 0 0 1 {x} {740-index*24} Tm ({escaped}) Tj ET')
    stream = DecodedStreamObject()
    stream.set_data('\n'.join(operations).encode('cp1252'))
    writer.pages[0][NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    pdf = output.getvalue()
    assert PdfReader(BytesIO(pdf)).pages[0].extract_text().startswith('Someone leaves.')
    response = TestClient(app).post('/api/scenes/parse', files={'script_file': ('scene.pdf', pdf)})
    assert response.status_code == 200
    text = parser.parse.call_args.args[0]
    assert [line.strip() for line in text.splitlines() if line.strip()] == rows
