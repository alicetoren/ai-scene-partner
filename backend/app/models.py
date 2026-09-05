from pydantic import BaseModel, ConfigDict, Field, model_validator


class DialogueLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    character: str = Field(min_length=1)
    text: str = Field(min_length=1)


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    characters: list[str] = Field(min_length=1)
    lines: list[DialogueLine] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_lines(self) -> "Scene":
        character_names = set(self.characters)
        expected_ids = list(range(1, len(self.lines) + 1))

        if [line.id for line in self.lines] != expected_ids:
            raise ValueError("Dialogue line IDs must be consecutive and start at 1.")
        if any(line.character not in character_names for line in self.lines):
            raise ValueError("Every dialogue line character must be listed in characters.")
        return self
