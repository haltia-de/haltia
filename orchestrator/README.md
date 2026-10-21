# Диспетчер

Запускает исполнителей для задач с меткой `agent:ready` (ADR 0005, 0006).
Только стандартная библиотека Python и `gh`.

## Как он работает

`haltia_dispatch.py tick` раз в 5 минут (таймер systemd пользователя):

1. Находит задачи `agent:ready` во всех репозиториях `haltia-de`, старые
   первыми.
2. Пропускает задачи без ровно одной метки `model:*`, с `needs:tablet`, с
   другой меткой `agent:*`, и репозитории, где исполнитель уже работает.
3. На свободные места (всего два) ставит `agent:working` и запускает
   `haltia_dispatch.py run` в своём юните `haltia-exec-<repo>-<номер>`.

`run` готовит worktree на ветке `agent/<номер>`, передаёт исполнителю задание
(`prompt.md` с текстом задачи), ждёт его выхода, коммитит, пушит, открывает PR
и ставит `agent:review`. Кончился лимит подписки, исполнитель написал
`blocked` или ничего не изменил — `agent:blocked` с причиной в комментарии.
Модель задачи диспетчер не меняет.

Без `--live` `tick` только печатает, что сделал бы.

## Файлы на ПК

- `~/.config/haltia/dispatch.ini` — необязательный, секция `[dispatch]`:
  `max_running` (2), `memory_max` (4G), `timeout_minutes` (120), `approver`
  (логин человека для `release-check`), `claude_allowed_tools`.
- `~/.config/haltia/dispatch.env` — `PATH` с `claude`, `codex`, `grok` и `gh`
  для таймера.
- `~/.local/state/haltia-dispatch/jobs/` — задания и журналы исполнителей.
- `~/.cache/haltia-dispatch/` — клоны и worktree.

## Установка

```sh
ln -s /mnt/data/Projects/haltia-de/haltia/orchestrator ~/.local/share/haltia-dispatch
systemctl --user link ~/.local/share/haltia-dispatch/systemd/haltia-dispatch.service
systemctl --user enable --now ~/.local/share/haltia-dispatch/systemd/haltia-dispatch.timer
```

Пробный прогон: `python3 haltia_dispatch.py tick`. Тесты:
`python3 -m unittest test_haltia_dispatch`.

## Не проверено

- `grok -p` с правкой файлов: задачи `model:grok` до проверки не ставить в
  `agent:ready`.
- `codex exec -s workspace-write` на настоящей задаче.
