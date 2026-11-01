from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScenarioRead(BaseModel):
    id: int
    code: str
    name: str
    intents: int = Field(default=0, description="Сколько намерений в сценарии")


class SlotTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class IntentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(min_length=2, max_length=50, pattern=r"^[a-z_]+$", examples=["alarm_snooze"])
    name: str = Field(min_length=2, max_length=100, examples=["Отложить будильник"])
    scenario_id: int = Field(gt=0, examples=[1])
    is_active: bool = True


class IntentUpdate(BaseModel):
    """Все поля необязательны: меняются только переданные."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=2, max_length=100)
    scenario_id: int | None = Field(default=None, gt=0)
    is_active: bool | None = None

    @model_validator(mode="after")
    def reject_null_fields(self) -> "IntentUpdate":
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"Поле {field} нельзя обнулить; не передавайте его для сохранения")
        return self


class IntentRead(BaseModel):
    id: int
    code: str
    name: str
    scenario_id: int
    is_active: bool
    utterances: int = Field(default=0, description="Сколько фраз-примеров в датасете")
