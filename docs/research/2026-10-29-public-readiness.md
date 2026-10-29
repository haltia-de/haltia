# Аудит готовности корня к публичности

Дата: 29 октября 2026. Проверка только чтением; visibility, refs, история и файлы корня не менялись.

## Зафиксированная область

- `main`: `3c9b0a1e4d5ae611b899fa070d70da6186c5f4c0`.
- 67 reachable commits из всех локальных refs (`--all`); репозиторий не shallow.
- 169 уникальных reachable blobs; 52 tracked paths в дереве main.
- Рабочие untracked документы и отдельная ветка будущих process docs в этот проход не включены; финальные docs проверяются отдельным проходом.

## Результаты без значений

- Gitleaks 8.30.1 `git --all --full-history`: 0 findings, exit 0.
- Gitleaks 8.30.1 `dir` по экспортированному tracked main: 0 findings, exit 0.
- Дополнительные шаблоны LAN IPv4, private/link-local IPv6, MAC, credential URL, private-key marker, service token, absolute user-home, явные hardware serial/IMEI/IMSI/ICCID, операционные agent-session commands: 0 подтверждённых кандидатов.
- 15 исторических совпадений local-hostname heuristic: все являются упоминанием имени gitignored local-инструкций, не сетевыми адресами. Ложные срабатывания; значения не приводятся.
- Намеренные public keys: 2 RSA public PEM и 1 OpenPGP keyring. Keyring содержит pub/fpr/uid, secret-key packets отсутствуют. Public-key UID — атрибуция ключа публикации; приватных ключей не выявлено.

## Ложные срабатывания: path + line

- `.gitignore`: 1. Категория: имя local-инструкций в документации/ignore; не operational leak.
- `AGENTS.md`: 85, 91, 92, 98, 101, 104, 111, 113, 115. Категория: имя local-инструкций в документации/ignore; не operational leak.
- `docs/adr/0005-root-repo-and-agents.md`: 135. Категория: имя local-инструкций в документации/ignore; не operational leak.

## Происхождение сканера

- Официальный release: https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1 .
- Архив и checksums manifest проверены по закреплённым SHA256 из GitHub release metadata, затем архив дополнительно сверен с manifest.
- Сканирование локальное: дерево/история не отправлялись внешнему сервису.

## Ограничения

- Нулевые автоматические findings не гарантируют отсутствия неизвестного формата секрета или неявно личных сведений в прозе.
- Проверены все объекты, достижимые из имеющихся локальных refs. Недостижимые объекты, reflogs, удалённые ветки, GitHub PR/comments/issues, LFS remote objects и backups вне Git не проверялись.
- Git author/committer attribution и intentional public-key UID не считаются автоматически приватными account credentials; авторство Git не переатрибутировалось.
- Вне tracked main могли находиться локальные приватные материалы: они не включены в экспорт и не публиковались.
- Перед изменением visibility требуется отдельное решение человека; это исследование его не выполняет.

Итог: автоматический аудит tracked main и всей достижимой локальной истории не выявил секретов или явных operational leaks. Для финальных process docs нужен повторный scan.

## Финальный проход process-ветки до commit

- Источник: `/tmp/haltia-process-20261029`; tracked и untracked intended-public files из `git ls-files --cached --others --exclude-standard`; `.git` и `.superpowers` исключены.
- Экспортировано **57 файлов**; точные SHA256 каждого файла сохранены в private `final-tree-manifest.json`. Финальный commit SHA пока отсутствует.
- Gitleaks: **2 кандидата**, оба проверены как ложные срабатывания `generic-api-key`: `docs/research/2026-10-29-project-status.md:358` и `:391`. Это ранее независимо проверенные публичные Git commit SHA, соседствующие со словом API; не credential/token. Исходный exit1 сканера сохранён, не подавлен.
- Подтверждённых секретов: **0**. Дополнительные private-marker patterns: **0 подтверждённых**; 3 совпадения hostname-шаблона в `.gitignore:1`, `AGENTS.md:130`, `docs/adr/0005-root-repo-and-agents.md:135` — имя local-инструкций, не hostname.
- Публичные ключи скопированы из ранее проверенного дерева; новых private-key markers не выявлено.
- Новые ADR0011, stabilization plan, desktop validation, public-readiness и project-status включены в этот проход.
- Этот результат относится к снимку файлов в manifest. Изменения после снимка требуют повторной проверки; visibility и commit/push не выполнялись.
