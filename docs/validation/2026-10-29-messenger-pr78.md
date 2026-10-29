# Messenger PR78: парное GTK-сравнение BASE и HEAD

**Итог: 8/8 PASS; прежняя неопределённость четырёх GTK failures закрыта этим контролируемым прогоном.**

Дата завершения UTC: 2026-10-29T13:28:31.551477+00:00.

В одном и том же новом контейнере последовательно исполнены BASE `8cbd317ead6bf5b9f57ce57d5e9fa25556836f58` и PR-head `c3207188242a93d33c854f95a19ec7e1f5451f3e`: для каждой suite сначала BASE, затем HEAD. Образ закреплён: `ubuntu@sha256:c098726dd9b9733f3e885f8de0ef375206a311b0a317eadc40d347b1115fb944`. Проверено совпадение всех 430 dependency versions с прежним окружением, включая libgtk-3-bin; differences=0. Одна и та же копия latest kit `8386d13da8acca4e43ba8f3b85e590f5433c4810` использована обоими исходниками.

| Suite | BASE | PR-head |
|---|---|---|
| test_window.py | PASS, exit0 | PASS, exit0 |
| test_login.py | PASS, exit0 | PASS, exit0 |
| test_call_window.py | PASS, exit0 | PASS, exit0 |
| test_call_shutdown.py | PASS, exit0 | PASS, exit0 |

Все четыре файла тестов побайтно одинаковы в BASE и HEAD; их sha256 сохранены в paired-preflight.json. Для каждого запуска отдельные fixture profile prefixes и session D-Bus; общий runtime каталог создан до всех запусков. Broadway :50 перезапускается последовательно с завершением и wait перед следующим тестом, поэтому одновременных HTTP/socket-сессий нет. Исходная Python-команда из tests/run.sh вызвана без grep-фильтра. Все восемь raw logs непусты, содержат завершённые ok-маркеры, не содержат traceback; хэши журналов и количества маркеров проверены в paired-log-audit.json.

## Вывод и пределы

Четыре ранее наблюдавшихся head GTK failures в этих одинаковых контролируемых условиях не воспроизводятся. В пределах данного сравнения GTK-регрессии PR78 не обнаружено; прежние failures относятся к предыдущим условиям harness/environment. Единственная конкретная причина старых сбоев не установлена, старые FAIL и их журналы не удалялись и не заменялись.

Выполнены только запрошенные четыре suites для двух снимков. Другие уже успешные suites, integrated tree и synthetic peer-media не повторялись. Их прежние результаты сохраняются: integrated 10/12, media failure также воспроизведён на untouched main; этот прогон не подтверждает WebRTC media connection или настоящие звонки.

Оба снимка запускают полный исходный haltia-messenger; создаваемый install.sh compiled-module launcher не считается изменением исходного layout и не подменял исходники теста. Это source-suite validation с установленными зависимостями, не сборка/установка новой версии Messenger.

Сеть контейнера отключена; используются FakeLink/FakeKeyring и синтетические события. Аккаунты, настоящие звонки, камера/микрофон, пользовательские профили и host D-Bus не использовались. Контейнер удалён, cleanup exit0. Existing sibling worktrees, продуктовые исходники и GitHub не менялись.

Доказательства в приватном каталоге messenger-pr78: paired-gtk.results.json, paired-dependency-comparison.json, paired-preflight.json, paired-log-audit.json, paired.<snapshot>.<suite>.raw.log и paired.<snapshot>.<suite>.broadway.log. Скрипт выполненного прогона — run-paired-gtk.py. Этот отчёт снимает только прежнюю GTK validation неопределённость; независимое review и решение о merge остаются отдельными.

## Независимое ревью и интеграция

Claude проверил head `c3207188242a93d33c854f95a19ec7e1f5451f3e` без блокирующих замечаний.
Три оставшихся замечания учтены в [messenger#88](https://github.com/haltia-de/messenger/issues/88).
[PR #78](https://github.com/haltia-de/messenger/pull/78) слит без выпуска;
merge commit `9cdb42195947977580fbd9febbc81694393a7ac9`.
Реальные звонки, аккаунты и устройство этим результатом не проверены.
