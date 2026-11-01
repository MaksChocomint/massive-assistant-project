"""Build the presentation ER diagram from ORM metadata, without connecting to the DB.

Run: python -m scripts.render_erd
"""

from html import escape
from pathlib import Path

from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.dialects import postgresql

from app import models  # noqa: F401 - register all application tables
from app.db import Base

WIDTH, HEIGHT = 1680, 850
CARD_WIDTH, HEADER, ROW = 440, 52, 25
LAYOUT = {
    "scenarios": (24, 20, "Сценарии"),
    "intents": (24, 270, "Намерения"),
    "utterances": (24, 570, "Фразы MASSIVE"),
    "intent_slots": (620, 20, "Обязательные параметры и вопросы"),
    "users": (620, 260, "Профили команд"),
    "commands": (620, 480, "Команды и собранные параметры"),
    "slot_types": (1216, 20, "Типы параметров"),
    "command_slots": (1216, 270, "Значения параметров команды"),
    "dialogue_sessions": (1216, 570, "Согласование и результат исполнения"),
}
# Routes run through gaps between cards; each key is the actual child FK column.
ROUTES = {
    ("intents", "scenario_id"): ("M244 159 V270", 244, 214),
    ("utterances", "intent_id"): ("M244 459 V570", 244, 514),
    ("intent_slots", "intent_id"): ("M464 334 H510 V84 H620", 510, 214),
    ("intent_slots", "slot_type_id"): ("M1216 84 H1145 V109 H1060", 1145, 64),
    ("commands", "user_id"): ("M840 424 V480", 840, 451),
    ("commands", "intent_id"): ("M464 334 H555 V619 H620", 555, 514),
    ("command_slots", "command_id"): ("M1060 544 H1110 V359 H1216", 1110, 479),
    ("command_slots", "slot_type_id"): ("M1436 159 V270", 1436, 214),
    ("dialogue_sessions", "command_id"): ("M1060 544 H1160 V634 H1216", 1160, 584),
}


def composite_keys(table: Table) -> list[str]:
    result = []
    if len(table.primary_key.columns) > 1:
        result.append("PK (" + ", ".join(c.name for c in table.primary_key.columns) + ")")
    result.extend(
        "UQ (" + ", ".join(c.name for c in constraint.columns) + ")"
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint) and len(constraint.columns) > 1
    )
    return result


def draw_table(table: Table) -> str:
    x, y, label = LAYOUT[table.name]
    extras = composite_keys(table)
    height = HEADER + ROW * len(table.columns) + 12 + 24 * len(extras)
    runtime = table.name in {"users", "commands", "command_slots", "dialogue_sessions"}
    color, soft = ("#176b65", "#edf6f3") if runtime else ("#284dd4", "#eef2ff")
    parts = [
        f'<g class="entity" data-table="{table.name}" aria-label="{table.name}: {label}">',
        f'<rect x="{x}" y="{y}" width="{CARD_WIDTH}" height="{height}" '
        'rx="10" fill="white" stroke="#cbd4e3" stroke-width="1.5"/>',
        f'<path d="M{x + 10} {y} H{x + CARD_WIDTH - 10} Q{x + CARD_WIDTH} {y} '
        f'{x + CARD_WIDTH} {y + 10} V{y + HEADER} H{x} V{y + 10} Q{x} {y} {x + 10} {y}" '
        f'fill="{soft}"/>',
        f'<text x="{x + 16}" y="{y + 24}" class="table-name" fill="{color}">{table.name}</text>',
        f'<text x="{x + 16}" y="{y + 43}" class="table-label">{label}</text>',
    ]
    for i, column in enumerate(table.columns):
        row_y = y + HEADER + i * ROW
        keys = []
        if column.primary_key:
            keys.append("PK")
        if column.foreign_keys:
            keys.append("FK")
        if any(
            isinstance(c, UniqueConstraint) and len(c.columns) == 1 and column.name in c.columns
            for c in table.constraints
        ):
            keys.append("UQ")
        sql_type = str(column.type.compile(dialect=postgresql.dialect()))
        sql_type = sql_type.replace("TIMESTAMP WITH TIME ZONE", "TIMESTAMPTZ")
        sql_type += " ?" if column.nullable else ""
        name_color = color if column.foreign_keys else "#1c2b48"
        parts.extend(
            [
                f'<g class="attribute" data-column="{table.name}.{column.name}">',
                f"<title>{escape(column.name)}: {escape(sql_type)}; "
                f"{escape(', '.join(keys))}</title>",
                f'<path d="M{x + 12} {row_y} H{x + CARD_WIDTH - 12}" '
                'stroke="#edf0f5" stroke-width="1"/>',
                f'<text x="{x + 15}" y="{row_y + 18}" class="key" fill="{color}">'
                f"{' '.join(keys)}</text>",
                f'<text x="{x + 79}" y="{row_y + 19}" class="column" fill="{name_color}">'
                f"{column.name}</text>",
                f'<text x="{x + CARD_WIDTH - 15}" y="{row_y + 18}" class="type" '
                f'text-anchor="end">{escape(sql_type)}</text>',
                "</g>",
            ]
        )
    for i, key in enumerate(extras):
        key_y = y + HEADER + len(table.columns) * ROW + 22 + 24 * i
        parts.append(f'<text x="{x + 16}" y="{key_y}" class="constraint">{escape(key)}</text>')
    return "\n".join([*parts, "</g>"])


def build() -> str:
    tables = Base.metadata.tables
    column_count = sum(len(table.columns) for table in tables.values())
    if set(tables) != set(LAYOUT):
        raise ValueError("The table layout must be updated to match ORM metadata")
    foreign_keys = {(t.name, fk.parent.name): fk for t in tables.values() for fk in t.foreign_keys}
    if set(foreign_keys) != set(ROUTES):
        raise ValueError("The relationship routes must be updated to match ORM foreign keys")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="erd-title erd-desc">',
        f'<title id="erd-title">ER-диаграмма MASSIVE: все {len(tables)} сущностей '
        f"и {column_count} атрибутов</title>",
        '<desc id="erd-desc">Схема PostgreSQL из SQLAlchemy-моделей. Линии связывают '
        "родительские сущности с внешними ключами. Две связи многие ко многим реализованы "
        "через intent_slots и command_slots. У команды может быть один голосовой диалог. "
        "Служебная таблица alembic_version не является сущностью предметной области.</desc>",
        """<defs>
<marker id="one" viewBox="0 0 18 18" markerWidth="18" markerHeight="18"
refX="0" refY="9" orient="auto" markerUnits="userSpaceOnUse">
<path d="M11 2 V16" fill="none" stroke="#60718f" stroke-width="2"/></marker>
<marker id="many" viewBox="0 0 28 18" markerWidth="28" markerHeight="18"
refX="28" refY="9" orient="auto" markerUnits="userSpaceOnUse">
<path d="M16 9 L28 2 M16 9 L28 16" fill="none" stroke="#60718f" stroke-width="2"/>
<circle cx="8" cy="9" r="4" fill="white" stroke="#60718f" stroke-width="2"/></marker>
<marker id="optional-one" viewBox="0 0 28 18" markerWidth="28" markerHeight="18"
refX="28" refY="9" orient="auto" markerUnits="userSpaceOnUse">
<path d="M24 2 V16" fill="none" stroke="#60718f" stroke-width="2"/>
<circle cx="8" cy="9" r="4" fill="white" stroke="#60718f" stroke-width="2"/></marker>
</defs>
<style>
text {font-family:Arial,Helvetica,sans-serif;}
.table-name {font-size:24px;font-weight:700;}
.table-label {font-size:16px;fill:#526078;}
.column {font-size:21px;}
.type {font-size:16px;fill:#526078;}
.key {font-size:12px;font-weight:700;}
.constraint {font-size:16px;fill:#526078;}
.multiplicity {font-size:15px;font-weight:700;fill:#43536e;}
.legend {font-size:17px;fill:#43536e;}
</style>""",
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="white"/>',
    ]
    labels = []
    for key, fk in foreign_keys.items():
        path, x, y = ROUTES[key]
        one_to_one = fk.parent.primary_key and len(fk.parent.table.primary_key.columns) == 1
        marker = "optional-one" if one_to_one else "many"
        cardinality = "1 : 0..1" if one_to_one else "1 : 0..N"
        parts.append(
            f'<path class="relationship" data-fk="{key[0]}.{key[1]}" '
            f'd="{path}" fill="none" stroke="#60718f" stroke-width="2" '
            f'marker-start="url(#one)" marker-end="url(#{marker})">'
            f"<title>{fk.column.table.name}.{fk.column.name} → {key[0]}.{key[1]} "
            f"({cardinality})</title></path>"
        )
        labels.append(
            f'<g><rect x="{x - 46}" y="{y - 13}" width="92" height="26" '
            f'rx="8" fill="white"/><text x="{x}" y="{y + 5}" '
            f'text-anchor="middle" class="multiplicity">{cardinality}</text></g>'
        )
    parts.extend(draw_table(tables[name]) for name in LAYOUT)
    parts.extend(labels)
    parts.append(
        '<text x="24" y="831" class="legend">PK — первичный ключ · FK — внешний ключ · '
        "UQ — уникальность · ? — допускается NULL · M:N — через intent_slots и command_slots</text>"
    )
    return "\n".join([*parts, "</svg>", ""])


if __name__ == "__main__":
    output = Path(__file__).resolve().parents[1] / "app/static/assets/erd.svg"
    output.write_text(build(), encoding="utf-8")
    tables = Base.metadata.tables
    print(
        f"Saved {output}: {len(tables)} tables, "
        f"{sum(len(t.columns) for t in tables.values())} columns, "
        f"{sum(len(t.foreign_keys) for t in tables.values())} foreign-key relationships"
    )
