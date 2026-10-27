# ERD — структура базы данных

```mermaid
erDiagram
    scenarios ||--o{ intents : "содержит"
    intents ||--o{ utterances : "фразы-примеры"
    intents ||--o{ intent_slots : ""
    slot_types ||--o{ intent_slots : ""
    users ||--o{ commands : "отправляет"
    intents ||--o{ commands : "распознано как"
    commands ||--o{ command_slots : ""
    slot_types ||--o{ command_slots : ""

    scenarios {
        int id PK
        string code UK "alarm, weather…"
        string name
    }
    intents {
        int id PK
        string code UK "alarm_set"
        string name "индекс"
        int scenario_id FK "индекс"
        bool is_active
    }
    slot_types {
        int id PK
        string code UK "time, date…"
        string name
    }
    intent_slots {
        int intent_id PK, FK
        int slot_type_id PK, FK
        bool required
        int position "CHECK >= 0"
        string question
    }
    utterances {
        int id PK
        string external_id UK "id в MASSIVE"
        text text
        text annotated
        string partition "CHECK train/dev/test, индекс"
        int intent_id FK "индекс"
    }
    users {
        int id PK
        string username UK
        string name
        datetime created_at
    }
    commands {
        int id PK
        int user_id FK "индекс"
        text text
        int intent_id FK "индекс"
        float confidence
        string status "CHECK, индекс"
        int clarifications "CHECK >= 0"
        datetime created_at "индекс"
        datetime updated_at
    }
    command_slots {
        int id PK
        int command_id FK
        int slot_type_id FK
        string value
    }
```

## Связи

| Связь | Тип | Как реализована |
| --- | --- | --- |
| Сценарий → намерения | один-ко-многим | `intents.scenario_id` |
| Намерение → фразы | один-ко-многим | `utterances.intent_id` |
| Намерения ↔ типы параметров | **многие-ко-многим** | ассоциативная таблица `intent_slots` (с атрибутами: обязательность, порядок, вопрос) |
| Пользователь → команды | один-ко-многим | `commands.user_id` |
| Команды ↔ типы параметров | **многие-ко-многим** | `command_slots` (значение параметра в команде), `UNIQUE (command_id, slot_type_id)` |

## Ограничения целостности

- `NOT NULL` — на всех полях, кроме необязательных (их в схеме нет);
- `UNIQUE` — коды справочников, `username`, `utterances.external_id` (на нём держится идемпотентность ETL), пара `(command_id, slot_type_id)`;
- `CHECK` — допустимые `partition` и `status`, `clarifications >= 0`, `position >= 0`;
- индексы — на полях поиска и фильтрации: `intents.name`, `intents.scenario_id`, `utterances.partition`, `commands.status`, `commands.user_id`, `commands.created_at` и другие внешние ключи.
