# Визуальный стиль и доступный диалог

Основной экран намеренно практический: одна задача, крупная кнопка микрофона,
последний вопрос, повтор и отмена. Пользователи, каталог и аналитика не вынесены
в основной сценарий. Текстовый резерв, протокол реплик и JSON свёрнуты в details.
В приложении нет декоративных растровых картинок и рекламного блока.

Презентация использует ту же синюю палитру и локальный Manrope с кириллицей.
Схема архитектуры, таблица альтернатив, диалог и метрики — редактируемые HTML/CSS,
а не сгенерированные изображения с числами. Семь слайдов объясняют предметную
область, альтернативы, решение, сценарий, технику, результаты и вывод.

## Происхождение ресурсов

- app/static/assets/assistive-context.png — оригинальная иллюстрация ImageGen
  для предметной области на первом слайде. Концепт, не фото участника исследования.
- app/static/assets/erd.svg — векторная ER-диаграмма из метаданных SQLAlchemy,
  генератор scripts/render_erd.py. Все 9 сущностей, 45 атрибутов и 9 связей;
  названия, типы, nullable, PK/FK/UQ берутся из ORM. Вставлена на слайд 5.
- output/diagrams/massive-erd.png — экспорт схемы 3360×1700 для вставки в другие
  презентации. Для увеличения без потери чёткости предпочтителен SVG.
- fonts/manrope-*.ttf — локальный Manrope, лицензия SIL OFL в fonts/OFL.txt.
- icons.svg и favicon.svg — оригинальные SVG исходного проекта.
- dialogue-core.png, missing-context.png, future-connections.png, app-dialogue.png —
  сохранённые ресурсы предыдущего оформления, в актуальных страницах не используются.

Промпт assistive-context:

Use case: illustration-story. Asset type: respectful editorial illustration for an academic presentation about assistive voice technology for blind adults. Show a blind adult at home comfortably using a small smart speaker by voice, wearing a simple single-ear headset, with a folded white mobility cane resting beside their armchair. No sunglasses caricature. A phone is on the table with its screen turned away, not being looked at. A sculptural speech bubble and a simple clock in the scene suggest an alarm-setting conversation and spoken confirmation. Premium restrained 3D editorial clay illustration, warm ivory background, navy and cobalt blue with subtle amber accents, soft studio daylight, human dignity and independence, no pity or medical setting. Landscape 3:2 composition with all objects fully within frame and generous margins. No text, no numbers, no logos, no fake charts, no watermark. Concept illustration, not a photo of a usability study.

## Доступность и ограничения

Кнопки имеют текстовые имена, поля — label, ошибки — role=alert, новые сообщения —
role=status/aria-live. Все действия доступны с клавиатуры, фокус заметен, состояние
дублируется словами. Микрофон отключается во время TTS, чтобы не распознавать голос
самого помощника. Собственный TTS можно выключить при работе с экранным диктором.
Микрофон не включается при загрузке/восстановлении диалога.

Речь зависит от Web Speech API, браузера, сервиса ASR и установленных голосов ОС.
Микросервис получает только текст. Соответствие WCAG и удобство для незрячих участников
не заявляются без отдельной проверки. Ориентиры: W3C Status Messages и MDN Web Speech API,
ссылки приведены на последнем слайде.

Экспорт: A4 landscape, один слайд на страницу. Управление: стрелки, Home/End,
PageUp/PageDown и кнопки. Временные снимки — output/playwright, финальный PDF —
output/pdf/massive-presentation.pdf.
