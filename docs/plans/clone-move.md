# План: клоны в /mnt/data/Projects/haltia-de (ADR 0005, шаг 6)

Составлен 21 октября 2026. Цель — чтобы локальный путь каждого клона
повторял адрес на GitHub: `/mnt/data/Projects/haltia-de/<repo>`.

## Состояние на 21 октября

- Все клоны на `/mnt/data` (один раздел), поэтому перенос — переименование
  каталога, мгновенно даже для 21 ГБ устройства.
- Ни в одном клоне нет незакоммиченных изменений и неотправленных коммитов;
  в `b8k-max` и `b8k-music` лежит только служебный каталог
  `claude-security-guidance-1000/` вне git.
- Ни один процесс не работает в старых каталогах.
- У kit два клона одного репозитория: `b8k-compat` и `kit`.

## Что куда

| Сейчас | Станет |
|---|---|
| `b8k-shell` | `haltia-de/shell` |
| `b8k-compat` | `haltia-de/kit` |
| `kit` | удаляется (второй клон kit) |
| `haltia-files` | `haltia-de/files` |
| `b8k-text` | `haltia-de/text` |
| `b8k-calendar` | `haltia-de/calendar` |
| `b8k-news` | `haltia-de/news` |
| `b8k-weather` | `haltia-de/weather` |
| `b8k-video` | `haltia-de/video` |
| `b8k-music` | `haltia-de/music` |
| `b8k-max` | `haltia-de/messenger` |
| `b8k-paint` | `haltia-de/paint` |
| `b8k-firefox` | `haltia-de/firefox` |
| `b8k-ci` | `haltia-de/ci` |
| `haltia-packages` | `haltia-de/packages` |
| `haltia-github` | `haltia-de/.github` |
| `lenovo-b8000h-linux` | `haltia-de/device-lenovo-b8000h` |
| `paint-android` | `haltia-de/paint-android` |

## Память агентов

Claude Code хранит разговоры и память по пути проекта:
`~/.claude/projects/<путь, где «/» и «.» заменены на «-»>`. Каталог
переезжает вместе с клоном, например
`-mnt-data-Projects-b8k-shell` → `-mnt-data-Projects-haltia-de-shell`,
`haltia-github` → `-mnt-data-Projects-haltia-de--github`.

- Память kit — из двух каталогов (`-b8k-compat` и `-kit`) в один; файлы
  `memory/` сливаются, `MEMORY.md` — объединением строк.
- Старый каталог `-mnt-data-Projects-b8k-files` (имя Файлов до ADR 0004)
  сливается с памятью `files`.
- Пути внутри старых разговоров остаются прежними; на продолжение
  разговора это не влияет.
- Codex и Grok хранят сеансы по датам, не по пути; переносить нечего,
  только `codex resume --last` в новом каталоге не найдёт старый сеанс.

## Порядок

1. Проверить ещё раз: нет процессов в старых каталогах, нет изменений.
2. `git pull --ff-only` в каждом клоне: после слияний шага 4 все отстают.
3. Переименовать каталоги по таблице. Удалить второй клон kit после того,
   как его память слита.
4. Перенести каталоги памяти Claude.
5. На старых местах оставить символьные ссылки на новые на две недели, для
   скриптов и привычки. Сеансы запускать только из новых путей: иначе
   Claude заведёт память по старому пути.
6. Обновить `docs/repos.md` (столбец «Локальная папка»), `AGENTS.md` корня
   и локальную память архитектора.
7. Завести задачи на старые пути внутри репозиториев (`AGENTS.md` shell,
   music, paint, video, устройства; `docs/shell.md`;
   `docs/plan-music-assistant.md`). `benchmarks/` в firefox — датированная
   запись, не трогать.
8. Живые сеансы поднимать в herdr уже из новых путей (ADR 0007).

## Откат

Переименовать обратно и вернуть каталоги памяти: ничего не удаляется, кроме
второго клона kit, а он полностью есть на GitHub.
