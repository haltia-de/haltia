# Платформы и оболочки для агентов: веб-панель, CLI, работа без GitHub (21 октября 2026)

Исследование к плану [Панель управления агентами](../plans/control-panel.md).
Факты собраны по документации и репозиториям; сами инструменты не
запускались. Что не удалось проверить — отмечено.

## Что стоит на ПК

- `opencode` 1.18.34 (`~/.opencode/bin`), `herdr` 0.9.5, `tmux`.
- Нет: `pi`, `ttyd`, `zellij`, `gotty`. `/usr/bin/orca` — экранный диктор
  GNOME, не Orca для агентов.

## Подписки в сторонних оболочках

| Поставщик | Можно ли подписку в OpenCode или pi | Источник |
|---|---|---|
| Anthropic (Claude Pro/Max) | **Нет.** «Anthropic does not permit third-party developers to offer Claude.ai login into their own applications»; вход по подписке — для Claude Code и родных приложений Anthropic. OpenCode убрал встроенный вход с 1.3.0. | [Claude Code: legal and compliance](https://code.claude.com/docs/en/legal-and-compliance), [OpenCode providers](https://opencode.ai/docs/providers/) |
| OpenAI (ChatGPT Plus/Pro) | **Да**, официально («Sign in with ChatGPT»): запросы — из локальной среды пользователя, план — только для подключённого приложения. OpenCode и pi среди первых. | [условия Sign in with ChatGPT](https://openai.com/policies/sign-in-with-chatgpt-terms/) |
| xAI (SuperGrok) | **Да для OpenCode**, официально: «Use your SuperGrok or X Premium subscription inside OpenCode». Для pi не подтверждено. | [x.ai/news/grok-opencode](https://x.ai/news/grok-opencode) |

Не проверено: разрешён ли вход по подписке Claude через официальный адаптер
`@agentclientprotocol/claude-agent-acp` (Anthropic вместе с Zed). Это первый
шаг пилота.

## Оболочки исполнителей

- **OpenCode** ([anomalyco/opencode](https://github.com/anomalyco/opencode),
  MIT): `opencode serve` — HTTP API (OpenAPI, поток событий SSE, пароль через
  `OPENCODE_SERVER_PASSWORD`); `opencode web` — веб-интерфейс со многими
  сеансами; `opencode attach` — терминал к тому же серверу; `opencode run` —
  без интерфейса, `--format json`; `opencode acp` — протокол ACP. Права:
  allow/ask/deny по инструментам (`read`, `edit`, `shell`, `webfetch`,
  `external_directory`…), шаблоны для команд shell.
  [docs](https://opencode.ai/docs/server/)
- **pi** ([earendil-works/pi](https://github.com/earendil-works/pi), MIT,
  v1.3.0): RPC и SDK, вход OAuth для многих поставщиков, расширения на
  TypeScript (могут блокировать вызовы инструментов). Подтверждений нет по
  умолчанию, изоляция — на пользователе (Docker, микро-ВМ). Веб-интерфейса
  нет, ACP — сторонним адаптером.

## Готовые платформы

| Платформа | Что даёт | Чего не хватает нам | Вердикт |
|---|---|---|---|
| [OpenHands Agent Canvas](https://github.com/OpenHands/OpenHands) (MIT, v1.29.0, beta) | Самостоятельная веб-панель «центр управления агентами»: свой агент и Claude Code, Codex, Gemini, pi, OpenCode или любой ACP-агент; подписки Claude и Codex из их файлов входа ([acp-agents](https://docs.openhands.dev/openhands/usage/agent-canvas/acp-agents)); разговоры, терминал, файлы, автоматизации; несколько бэкендов Agent Server; отдельный CLI | Grok не заявлен (но «любой ACP»); песочница — нет или Docker; не найдено: статистика по ACP-агентам, локальный diff с одобрением, лимиты | **Пилот на день** |
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) `dsh` (MIT, v0.2.1-rc) | `dsh web` с журналом заданий и счётчиком токенов, CLI, режим JSON, ACP, Claude Code и Codex как подагенты, bwrap | Предварительная версия с ломкой совместимости; песочница — только файлы, «must not be treated as secure» | Вернуться через ~3 месяца |
| [CloudCLI](https://github.com/siteboon/claudecodeui) (AGPL-3.0) | Веб и мобильный интерфейс к сеансам Claude Code, Codex, Cursor, OpenCode; терминал; git; плагины | Нет очереди, параллельности, ревью | Возможный слой просмотра |
| [Goose](https://github.com/aaif-goose/goose) (Apache-2.0) | Подписки Claude и ChatGPT через ACP | Одиночный агент, без песочницы | Нет |
| Coder (AgentAPI, Tasks) | — | AgentAPI заброшен, Tasks удалён, Coder Agents — свой агент на ключах API | Нет |
| [Vibe Kanban](https://github.com/BloopAI/vibe-kanban) | Ревью diff с комментариями агенту | Закрыт создателями 10 апреля 2026, теперь сообщество | Нет |
| Stoneforge, Orchestrator.inc, opcode, Nimbalyst, Plandex, Roo, Cline, Kilo, Continue | — | Агенты пушат сами, настольные, заброшены или привязаны к IDE | Нет |

## Связующие части

- **ACP** ([реестр](https://github.com/agentclientprotocol/registry)):
  `claude-acp`, `codex-acp`, `grok-build` (`grok agent stdio`), `opencode
  acp`, `gemini --acp`, `pi-acp` и другие. Клиенты с веб-интерфейсом:
  Codeg, tlbx, VibeAround, Raven, Remote Agent Server — зрелость не
  проверялась.
- **Claude Code Remote Control** (`claude remote-control`): живые сеансы
  Claude из браузера (claude.ai/code) и телефона, по подписке, только
  исходящий HTTPS. [docs](https://code.claude.com/docs/en/remote-control)
- **Терминал в браузере:** `zellij web` (токены, в том числе только на
  чтение; HTTPS вне localhost), ttyd. У herdr веб-интерфейса нет, только SSH.
- **Без GitHub:** Forgejo Actions (свой сервер Git, свой CI, не совместим с
  GitHub Actions один к одному) — не выбран (решение Q3 плана).
