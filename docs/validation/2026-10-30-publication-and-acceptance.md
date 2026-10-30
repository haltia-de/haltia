# Выполненная публикация и оставшаяся приёмка

Исторический снимок ранней проверки 30 октября 2026. Позднейшие исправления
и текущий остаток — в [продолжении от 31 октября](2026-10-31-stabilization-progress.md).

Снимок 30 октября 2026. Это продолжение
[согласованного плана](../plans/2026-10-29-project-stabilization.md),
а не замена исторического аудита 29 октября. Текущие состояния PR могут
измениться после этого снимка.

## Одобренная серия выполнена

Автор явно одобрил в чате три подготовленных действия с точными исходниками.

| Действие | Проверенный результат |
|---|---|
| Открыть корневой репозиторий | Public на `ca5863faf2bda6b42ce3bc672b565b84b807a67d`; анонимный API GET вернул HTTP 200. `protect-main` и `protect-release-tags` остались active |
| Слить [packages#22](https://github.com/haltia-de/packages/pull/22) | Head `0a6e8c5fb48f2fbfea8a3460d511c09bc7b2d6b3`, squash `0b43ea7e0e0c9d6a8162925b7ea11fd9b4e0342d`; [build и deploy успешны](https://github.com/haltia-de/packages/actions/runs/40933822152) |
| Слить [ci#14](https://github.com/haltia-de/ci/pull/14) и активировать v1 | Head `fcbf7a88de8753c0846665ecbfdf32f6afa67339`, squash `8216fd9db887c3eff6dc87be30aff8e7d9af06ad`; tree обоих `be877af339892ca260eb905f43cb07b490da1705`. v1 перемещён с `c04f734cce4172c4c50656f11921fc9c55fe0907` ровно на одобренный head |

Перед открытием сверены прежний полный аудит дерева/истории и актуальные
тексты корневых issues/PR: восемь текстовых файлов, Gitleaks exit 0,
кандидатов 0. Это дополнение к [полному аудиту](../research/2026-10-29-public-readiness.md),
а не новый вывод об отсутствии любых возможных секретов.

После deploy публичные APKINDEX, Flatpak summary/signature/config доступны
по HTTP 200. Для apt noble/resolute/trixie подписи InRelease проверены
публичным ключом корневого репозитория. Сам HTTP 200 не является новой
криптографической проверкой APK или Flatpak. До активации CI прошли 21
offline test и независимое ревью; реальный выпуск приложения новой CI
не запускался. Новых SemVer-тегов, выпусков Paint/Messenger, обновлений
установок автора и действий с планшетом не было.

[Корневой этап #4 закрыт](https://github.com/haltia-de/haltia/issues/4).
Это не закрытие оставшихся продуктовых критериев.

## Messenger

Частичное исправление [#89](https://github.com/haltia-de/messenger/pull/89)
слито как `9a1bab5a496c2c5b857a5dd72061d8afa2820d3b`. Независимые
проверки сравнивали BASE `9cdb42195947977580fbd9febbc81694393a7ac9`
с HEAD `f52850c3179b27d876536e10a6df3d64abd5aa7f`, а не с SHA squash-коммита.
Проверки задержанного pipeline NULL и позднего received-потока дали
BASE RED → HEAD GREEN; calls/shutdown прошли в обоих снимках. Synthetic
audio/video воспроизвели прежние ICE failures на базе и head. Подробности
прежней [проверки #78](2026-10-29-messenger-pr78.md) не заменяют эту проверку.

Продолжение [#90](https://github.com/haltia-de/messenger/pull/90) на
`f6879492f5f8582623206435288fabb27ab05473` **заблокировано**:

1. Тайм-аут shutdown отменяет asyncio-обёртку и исходный queued Future;
   MEDIA_WORKER затем пропускает необходимый NULL. После освобождения
   занятого worker и FIFO barrier база остановила pipeline, head оставил
   PLAYING. Это проверка реального CameraWorker и связи Future, со stand-in
   pipeline; не реального драйвера.
2. Одновременные remote/rebuild_sender оставили новый sender с payload 96
   вместо согласованного 102. База прошла тот же контроль. FIFO worker
   не сериализует чтение и применение состояния на loop между await.

При этом 12 независимых проверок исходных blocking/stale/failure сценариев
дали смысловые BASE RED → HEAD GREEN, calls/shutdown прошли, а synthetic
audio/video остановились на прежних ICE assertions без нового teardown
traceback. Эти положительные результаты не снимают два новых блокера.
Оба снимка проверены в одном pinned Ubuntu container; полный inventory 517
пакетов совпадает с сохранённым полным inventory проверки #89. Историческое
число 430 относилось к подмножеству install-log, не ко всему inventory.
Контейнер удалён, исходники не изменялись проверкой.

[#91](https://github.com/haltia-de/messenger/pull/91) на
`10e0ada11bd53e165427fa5a91672c416a2488ac` — только предложение политики
кэша и scratch fixture; production prune отсутствует. Committed cache test
прошёл, но независимое ревью обнаружило противоречие: входящие сообщения
обновляют mtime, поэтому предложенная политика по mtime не отражает
давность открытия чата. Документ и fixture требуют доработки;
[блокер и остальные замечания ревью приложены к PR](https://github.com/haltia-de/messenger/pull/91#issuecomment-6515840433).
Число 200 — предложение, не разрешение удалять данные.

Текущие владельцы остатка: [#84](https://github.com/haltia-de/messenger/issues/84),
[#85](https://github.com/haltia-de/messenger/issues/85),
[#86](https://github.com/haltia-de/messenger/issues/86),
[#88](https://github.com/haltia-de/messenger/issues/88). Переходы исполнителей
Claude → Codex → Grok после наблюдённых лимитов записаны в issues по
[ADR 0012](../adr/0012-model-availability-fallback.md); это не
основание менять модель из-за обычного дефекта теста или продукта.

## Video и GTK 3

[Локальная web-проверка](2026-10-30-web-fixtures.md) имеет частичный результат:
декодирование, перемотка, страницы плейлиста и SSE проверены; два дефекта
сообщений об ошибках переданы в [video#47](https://github.com/haltia-de/video/issues/47).
Реальные мобильные браузеры и YouTube не проверялись.

[Сверка оптимизаций GTK 3](../research/2026-10-30-gtk3-reconciliation.md)
отделяет присутствие механизмов в текущих исходниках от старых измерений
ПК. Численный выигрыш RAM/CPU текущего main этими материалами не установлен.
Панель агентов и аппаратная работа остаются вне текущего этапа.
