# Frontend: React и упрощённый FSD

React 19.3.1, Vite 8.3.6. Вся разметка основного приложения создаётся компонентами React.
FastAPI раздаёт сборку из app/static/ui; в production отдельный Node-сервер не нужен.

## Структура

    src/
      app/                    # Корневой App и глобальные стили
      pages/assistant/        # Компоновка страницы
      widgets/assistant/      # Объединение функций в рабочий диалог
        ui/                   # Assistant и справка
        model/                # Координатор сценария и React-hook
      features/
        dialogue/             # API, фазы, форма, ответ, история, действия
        voice/                # ASR/TTS, микрофон, скорость, WAV/AudioWorklet
        browser-executor/     # Будильник, фон, дата/время, квитанции исполнения
      shared/
        api/                  # Общий HTTP-клиент
        lib/                  # Безопасная работа с localStorage

## Правила зависимостей

Импорты идут вниз: app → pages → widgets → features → shared. Функции одного уровня
не импортируют внутренности соседних функций. Диалог и голос связывает widget,
а VoiceSession не знает о фазах backend и не зависит от React.

index.js — публичные UI-экспорты слайса. headless.js — публичная точка входа для
логики без JSX; благодаря этому координатор тестируется обычным node:test.
Сегменты ui, model, api и lib выделяют разные обязанности внутри слайса.

Общего глобального контекста для всего приложения нет: useAssistant создаёт
координатор одного виджета и подписывает React через useSyncExternalStore.
Снимки состояния неизменяемые. useEffect подключает и очищает обработчики
клавиатуры, микрофон, речь и polling. React StrictMode включён.

## Где менять поведение

- Текст и кнопки ответа: features/dialogue/ui.
- Форма команды: features/dialogue/ui/TextEntry.jsx.
- Отображение голоса и скорости: features/voice/ui/VoiceControls.jsx.
- ASR/TTS и переключение слушать/говорить: features/voice/model/VoiceSession.js.
- Запись Firefox и формат WAV: features/voice/lib.
- API и состояния диалога: features/dialogue/api и features/dialogue/model.
- Локальные действия: features/browser-executor/model/adapters.js.
- Отсчёт и повторяемые квитанции: features/browser-executor/model/BrowserExecutor.js.
- Звуковой сигнал и разбор времени: features/browser-executor/lib.
- Связь голоса, API, polling и состояния страницы: widgets/assistant/model.
- Общая структура экрана: pages/assistant/ui/AssistantPage.jsx.
- Глобальная тема: app/styles.css.

Новая функция не должна добавляться ветками в App: выделите её в features и подключите
в нужном widget. Общую техническую утилиту переносите в shared только при реальном
переиспользовании. Дополнительный слой entities пока не требуется.

## Разработка

Сначала запустите backend на localhost:8010, затем из frontend:

```powershell
npm ci
npm run dev
```

Откройте адрес Vite, показанный в терминале. /api, /static и /presentation
проксируются в FastAPI. Адрес backend при необходимости меняется в vite.config.js.

## Сборка и проверки

Из frontend:

```powershell
npm test
npm run build
npm run format
npm run format:check
```

Сборка записывается только в app/static/ui. Эта папка и node_modules исключены из Git.
В Docker frontend собирается отдельной стадией, после чего файлы копируются
в Python-образ. package-lock.json закрепляет зависимости.

node:test проверяет границы FSD, запуск после завершённого диалога, остановку
во время приветствия, запоздалый результат ASR, скорость и двойную отправку.
Браузерные проверки отдельно проверяют компоненты и настоящий путь Firefox → Vosk.

Настройки Prettier находятся в корне: .prettierrc.json и .prettierignore.
Python форматируется ruff, а не Prettier.

## Документация

[useSyncExternalStore](https://react.dev/reference/react/useSyncExternalStore),
[useEffect](https://react.dev/reference/react/useEffect),
[Vite build](https://vite.dev/config/build-options),
[Prettier CLI](https://prettier.io/docs/cli).

## Новая команда

Кнопка доступна с начала работы и блокируется только на время запроса. Нажатие очищает предыдущий диалог, произносит одно приглашение и автоматически запускает запись после озвучивания. При незавершённом диалоге отмена сначала сохраняется через API без отдельного голосового сообщения. Если ASR недоступен, открывается текстовый ввод.

## Браузерный исполнитель

Виджет связывает независимые features: после ready вызывает BrowserExecutor,
получает квитанцию и POST /execution. В UI показывается ответ сервера, флаги
успеха локально не подменяются. Реестр adapters.js позволяет добавить другое
действие без ветвления в React-компонентах. Неизвестный исполнителю intent
сохраняет обычное ожидание внешней системы.

Сроки будильников, фон и уже полученные квитанции сохраняются в sessionStorage
текущей вкладки. Новая команда их не сбрасывает. Квитанция сохраняется до POST:
сбой связи и последующий повтор не устанавливают второй будильник.
Звуковой AudioContext открывается по пользовательскому жесту; после перезагрузки
может потребоваться снова включить звук. Подробности: ../docs/browser-execution.md.
