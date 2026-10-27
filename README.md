# Голосовой помощник: справочник команд и обработка запросов

![CI](https://github.com/MaksChocomint/massive-assistant-system/actions/workflows/ci.yml/badge.svg)

Итоговый проект по дисциплине «Разработка на Python и инженерия данных».
Информационная система на **FastAPI + PostgreSQL** на основе открытого датасета
[MASSIVE](https://github.com/alexa/massive) (русская часть, 16 521 фраза).

## Предметная область

Помощник принимает текстовую команду пользователя («поставь будильник»), определяет
**намерение** (intent) и извлекает **параметры** (slots: время, дата, город…).
Если обязательного параметра нет — команда переходит в статус «нужно уточнение»
и помощник задаёт вопрос. Пример:

```
Пользователь: поставь будильник
Помощник:     На какое время поставить будильник?            (status = needs_clarification)
Пользователь: на семь утра
Помощник:     Поставить будильник, Время = семь утра          (status = completed)
```

Справочник намерений, сценариев и параметров загружается ETL-скриптом из CSV датасета.
Распознавание — простая модель scikit-learn (TF-IDF + линейный SVM), обучается на фразах
из БД.

**Стек:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, Pydantic 2,
scikit-learn, pytest, ruff, Docker Compose, GitHub Actions.

## Запуск

### Через Docker (рекомендуется)

```bash
cp .env.example .env
docker compose up -d --build                               # БД + приложение, миграции применяются сами
docker compose exec app python -m app.etl.import_massive   # ETL: загрузка датасета
docker compose exec app python -m app.seed                 # демо-пользователи и команды
```

- веб-интерфейс: <http://localhost:8000/>
- Swagger: <http://localhost:8000/docs>

### Локально

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                 # указать DATABASE_URL своей БД
docker compose up -d db                              # или свой PostgreSQL
alembic upgrade head
python -m app.etl.import_massive
python -m app.seed
uvicorn app.main:app --reload
```

### Переменные окружения

| Переменная | Назначение | По умолчанию |
| --- | --- | --- |
| `DATABASE_URL` | подключение к PostgreSQL | `postgresql+psycopg://app:app@localhost:5432/assistant` |
| `MAX_CLARIFICATIONS` | сколько раз можно уточнять одну команду | `3` |
| `LOG_LEVEL` | уровень логирования | `INFO` |
| `DB_PORT`, `APP_PORT` | порты на хосте для `docker compose` | `5432`, `8000` |

## База данных

8 таблиц, схема и ограничения — в [docs/erd.md](docs/erd.md).

| Таблица | Что хранит |
| --- | --- |
| `scenarios` | сценарии (будильник, погода, календарь…) |
| `intents` | намерения, принадлежат сценарию (1:N) |
| `slot_types` | типы параметров (время, дата, город…) |
| `intent_slots` | **M:N** намерение ↔ параметр: обязательность, порядок, вопрос |
| `utterances` | фразы датасета с разметкой (1:N к намерению) |
| `users` | пользователи |
| `commands` | команды пользователей: намерение, уверенность, статус |
| `command_slots` | **M:N** команда ↔ параметр: найденное значение |

Ограничения: PK/FK, `NOT NULL`, `UNIQUE` (коды, `username`, `external_id`),
`CHECK` (статус, partition, неотрицательные счётчики), индексы на полях фильтрации.
Миграции Alembic обратимы: `alembic downgrade base` удаляет всё.

## Бизнес-правила

Реализованы в слое `app/services`, проверяются тестами:

1. **Команда без обязательного параметра не выполняется** — статус `needs_clarification`
   и вопрос по первому недостающему параметру (по порядку `position`).
2. **Ответ на уточнение проверяется по формату**: время и дата должны быть похожи на
   время и дату («напиши музыку» вместо времени → 400).
3. **Лимит уточнений**: после `MAX_CLARIFICATIONS` неудачных попыток команда
   переходит в `failed` (409).
4. **Уточнять и отменять можно только активную команду** — выполненную или отменённую нельзя (409).
5. **Нельзя удалить намерение, которое используется** — есть команды или фразы датасета (409).
6. **Уникальность**: код намерения и логин пользователя не повторяются (409).

## ETL

```bash
python -m app.etl.import_massive --source data/massive_ru.csv
```

| Этап | Что делается |
| --- | --- |
| Extract | чтение CSV, проверка обязательных колонок |
| Validate / Clean | пустые поля, неизвестный `partition`, повтор `id`, дубликаты фраз (без учёта регистра и пробелов), сломанная разметка `[slot : value]` — такие строки отклоняются с причиной |
| Transform | нормализация текста, названия на русском, список параметров из разметки |
| Load | сценарии, намерения, параметры, связи M:N и фразы; уже загруженные `external_id` пропускаются |

Повторный запуск **идемпотентен** — дубли не появляются:

```
первый запуск:  прочитано 16521, загружено 15642, уже в БД 0, отклонено 879 (дубликат фразы: 879)
второй запуск:  прочитано 16521, загружено 0, уже в БД 15642, отклонено 879 (дубликат фразы: 879)
```

## API

Единый формат ошибок: `{"error": {"code": "...", "message": "...", "details": [...]}}`.
Коды: 200, 201, 204, 400 (бизнес-правило), 404, 409, 422 (валидация).

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/api/intents` | список: пагинация `limit/offset`, фильтры `scenario_id`, `active`, `search`, сортировка `sort=name` / `-id` |
| GET | `/api/intents/{id}` | намерение |
| POST | `/api/intents` | создать (201) |
| PATCH | `/api/intents/{id}` | изменить |
| DELETE | `/api/intents/{id}` | удалить (204, или 409 если используется) |
| GET | `/api/scenarios` | сценарии с числом намерений |
| GET | `/api/slot-types` | типы параметров |
| POST | `/api/users` | создать пользователя |
| GET | `/api/users`, `/api/users/{id}` | пользователи |
| POST | `/api/commands` | отправить команду (распознавание + бизнес-правила) |
| GET | `/api/commands` | список: фильтры `status`, `user_id`, пагинация |
| GET | `/api/commands/{id}` | команда |
| POST | `/api/commands/{id}/clarify` | ответ на уточняющий вопрос |
| POST | `/api/commands/{id}/cancel` | отменить команду |
| GET | `/api/analytics/top-intents` | топ-N намерений и доля успешных |
| GET | `/api/analytics/status-summary` | команды по статусам |
| GET | `/api/analytics/commands-by-day` | динамика команд по дням |
| GET | `/api/analytics/dataset` | фразы датасета по сценариям |
| POST | `/api/nlu/train` | переобучить модель, точность на dev |
| GET | `/api/health` | проверка работы |

Примеры:

```bash
curl -X POST localhost:8000/api/commands -H "Content-Type: application/json" \
     -d '{"user_id": 1, "text": "поставь будильник"}'
curl -X POST localhost:8000/api/commands/1/clarify -H "Content-Type: application/json" \
     -d '{"answer": "на семь утра"}'
curl "localhost:8000/api/intents?scenario_id=1&sort=name&limit=5"
curl "localhost:8000/api/analytics/top-intents?limit=5"
```

## Веб-интерфейс

Страница `/` (HTML + JS без фреймворков, `app/static`):

- **Команды** — отправка команды, ответ на уточняющий вопрос, отмена, список с фильтром по статусу;
- **Намерения** — список с поиском и пагинацией, создание, редактирование, удаление;
- **Аналитика** — топ намерений и статусы команд.

Ошибки API показываются сообщением вверху страницы.

## Тесты

```bash
pytest          # 37 тестов, покрытие ~93 % (порог 70 %)
ruff check . && ruff format --check .
```

Тесты используют отдельную БД — SQLite в памяти (`tests/conftest.py`), данные — небольшая
выборка `tests/fixtures/sample.csv` (265 фраз, 8 намерений).

- `test_etl.py` — unit: очистка, причины отклонения, идемпотентность;
- `test_services.py` — unit: бизнес-правила;
- `test_models.py` — ограничения UNIQUE / CHECK / FK;
- `test_api.py` — интеграционные через TestClient, включая негативные сценарии.

## Структура

```
app/
  api/           роутеры FastAPI
  core/          настройки, ошибки
  models/        модели SQLAlchemy
  schemas/       схемы Pydantic (Create / Update / Read)
  repositories/  запросы к БД (чтение)
  services/      бизнес-логика, распознавание, аналитика
  etl/           импорт CSV
  static/        веб-интерфейс
  main.py, db.py, seed.py
migrations/      миграции Alembic
tests/           pytest
docs/erd.md      ERD
data/            CSV датасета
```

## Процесс разработки

- ветки `feat/*`, `docs/*` → Pull Request в защищённую `main`;
- коммиты с префиксами `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `ci:`;
- CI (GitHub Actions): ruff, pytest с покрытием ≥ 70 %, миграции вверх/вниз и ETL на PostgreSQL;
- слияние только после Approve и зелёного CI.
