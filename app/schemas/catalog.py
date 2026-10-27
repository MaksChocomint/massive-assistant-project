from pydantic import BaseModel, ConfigDict, Field


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
    code: str = Field(min_length=2, max_length=50, pattern=r"^[a-z_]+$", examples=["alarm_snooze"])
    name: str = Field(min_length=2, max_length=100, examples=["Отложить будильник"])
    scenario_id: int = Field(gt=0, examples=[1])
    is_active: bool = True


class IntentUpdate(BaseModel):
    """Все поля необязательны: меняются только переданные."""

    name: str | None = Field(default=None, min_length=2, max_length=100)
    scenario_id: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class IntentRead(BaseModel):
    id: int
    code: str
    name: str
    scenario_id: int
    is_active: bool
    utterances: int = Field(default=0, description="Сколько фраз-примеров в датасете")
