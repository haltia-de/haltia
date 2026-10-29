# Диспетчер

Запускает исполнителей для задач с меткой `agent:ready` (ADR 0005, 0006).
Только стандартная библиотека Python и `gh`.

## Как он работает

`haltia_dispatch.py tick` раз в 5 минут (таймер systemd пользователя):

1. Находит задачи `agent:ready` во всех репозиториях `haltia-de`, старые
   первыми.
2. Пропускает задачи без ровно одной метки `model:*`, с `needs:tablet`, с
   другой меткой `agent:*`, и репозитории, где исполнитель уже работает.
3. На свободные места (по max_running) ставит `agent:working` и запускает
   `haltia_dispatch.py run` в своём юните `haltia-exec-<repo>-<номер>`.

`run` переключает свой клон на ветку `agent/<номер>`, даёт исполнителю копию
дерева без `.git` и задание (`prompt.md` с текстом задачи), ждёт его выхода,
коммитит, пушит, открывает PR и ставит `agent:review`. Перед коммитом
он запускает тесты репозитория (`tests/run.sh` или `tests/`) на копии
результата в песочнице без сети, с kit в `PYTHONPATH`; если они падают, а
без правки проходили, ничего не пушится и задача уходит в `agent:blocked` с
концом вывода. Кончился лимит подписки, исполнитель написал
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
- `~/.cache/haltia-dispatch/` — клоны диспетчера и копии для исполнителей.

На рабочем ПК автор установил max_running=4; это переопределение в
локальном dispatch.ini, не новое значение по умолчанию. agent:planned и
agent:deferred диспетчером не выбираются. agent:ready означает, что выполнены
условия готовности из [ADR 0011](../docs/adr/0011-review-queue-and-release-approval.md).

release-check проверяет автора GitHub-события, но общий аккаунт человека
и агентов не позволяет доказать человеческое одобрение. Пока идентичности
не разделены, выпуск разрешает только слово человека в чате; метка служит
для учёта и не заменяет это решение.

## Установка

```sh
ln -s /mnt/data/Projects/haltia-de/haltia/orchestrator ~/.local/share/haltia-dispatch
systemctl --user link ~/.local/share/haltia-dispatch/systemd/haltia-dispatch.service
systemctl --user enable --now ~/.local/share/haltia-dispatch/systemd/haltia-dispatch.timer
```

Пробный прогон: `python3 haltia_dispatch.py tick`. Тесты:
`python3 -m unittest test_haltia_dispatch`.

## Не проверено

- `codex exec -s workspace-write` на настоящей задаче.
