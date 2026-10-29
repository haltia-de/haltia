# Проверка переносимых runner и свежих исходников

29 октября 2026. Исторические GTK/container/source журналы не переписывались. Ни пользовательские установки, ни существующие sibling worktrees не изменялись.

## Изоляция и коды выхода переносимых runner

`run-functional.py` и `paint-candidate/run-candidate.py` используют уникальные UUID-имена, отслеживают успешное создание и удаляют только созданные своим запуском контейнеры. При отказе `docker run` cleanup не вызывается. Любой required FAIL приводит к ненулевому exit. `build.py` использует Docker `run --rm` без фиксированного имени; failed command и отсутствие deb возвращают ненулевой код. Новый `run-source-suites.py` использует те же правила владения и exit.

`test_runner_isolation.py`: **14/14 PASS**, 6.325 секунды, поддельный CLI Docker в отдельном временном PATH. Проверены creation collision, setup failure, required failure, уникальность имён, own cleanup, successful exits и build failure/no artifact. Реальный Docker этими тестами не вызывается.

После рефакторинга старые functional/candidate runner проверены только этой границей subprocess и синтаксически, без повторного E2E. Их ранее полученные реальные GTK/installed-deb результаты относятся к историческим исполненным версиям. Новый source-only runner отдельно выполнен E2E на свежих main-снимках ниже. Wrapper подготовки кандидата и API snapshot helper проверены синтаксически; эквивалентные команды подготовки/архивации выполнены отдельно.

## Свежие source suites

SHA main получены через GitHub API `repos/haltia-de/<repo>/commits/main`, затем скачан архив точного SHA; архивные SHA256 и commit dates записаны в `fresh-main/source-manifest.json`. Время снимка UTC: 2026-10-29T12:55:22.798450+00:00. Сеть контейнера отключена после установки зависимостей; GTK-проверки используют Xvfb. Все семь source snapshots получены заново, latest kit находится на PYTHONPATH. Это software-only проверка, не APK-install, не планшет и не сервисы.

| Репозиторий | Точный main commit | Результат |
|---|---|---|
| files | `2aeb0be7f688c644ebc65b9d5553d25686b912f1` | PASS: 8 script suites; 31 unittest checks плюс 2 script assertion suites |
| mail | `249e7cac2ae73513957a743e96762ef66cee3340` | PASS: 50 tests |
| firefox | `46eb9523e46505891bbd48d0c511f000f74b1404` | PASS: 12 tests |
| camera | `455483502856caf59977dd9bdece2d480b03e0c2` | PASS: 14 tests; synthetic videotestsrc, не физическая камера |
| text | `88377dbcd53410daffbdfb45fd1bb3093cb24d35` | PASS: 12 tests |
| calendar | `117190008f2da85f78f866760bf620cfe5d98475` | PASS: 17 tests, включая GTK checks на Xvfb |
| kit | `8386d13da8acca4e43ba8f3b85e590f5433c4810` | PASS: 25 tests, 20.130s; warnings сохранены |

Все 14 команд runner завершились PASS. На этом свежем main у Text и Calendar уже есть suites; прежний compile-only вывод относится только к старым локальным SHA. Ранние Files/Mail/Firefox/Camera/kit результаты также не выдаются за current main: старые snapshots отставали или расходились с main. Их точные SHA и сравнение с main сохранены отдельно в `source-freshness-20261029.json`.

Suite kit завершилась успешно, несмотря на многочисленные PyGI/asyncio deprecation и ResourceWarning; зависания/провала не подтверждено. Эти предупреждения не удалены из журнала. Все тесты software-only; физическая камера/микрофон, аккаунты, сообщения, звонки, звук, планшет и личные профили не использовались.

Исходные результаты свежего прогона: `fresh-main/source.results.json`, `fresh-main/*-0.log` и остальные Files logs. Результат исправленного Paint PR23 и опубликованные deb/Flatpak проверки приведены в отдельных исторических отчётах; этот прогон их не повторяет и не заменяет.
