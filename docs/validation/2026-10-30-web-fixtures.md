# Локальная проверка web-Видео

Снимок 30 октября 2026, до исправления найденных дефектов. Источники Video
`c14a6d3210d0443e61fad1b29a110f094b727ebc` (2.15.0). Общий PASS не достигнут.
Это локальные desktop Chromium fixtures, не мобильная, YouTube или
пакетная приёмка.

## Условия

Python 3.12.3, aiohttp 3.13.5, Playwright 1.56.0, Chrome 156.0.8078.47,
FFmpeg 6.1.1. Отдельные XDG, непостоянные browser contexts, loopback HTTP
и fake source; пользовательские профили, аккаунты и vault не читались.
Media: 60 s H.264 160×90/10fps и synthetic AAC, combined и отдельные дорожки.
Все зависимости и артефакты размещались в отдельном локальном каталоге.
Продуктовые исходники и настройки не менялись.

Расширенная проверка не обходила CSP. Существующий UI baseline использует
bypass_csp=True, поэтому его результат CSP не подтверждает. Browser routing
допускал loopback/data/blob/about; неожиданных внешних запросов guard не
зарегистрировал. Guard различал hosts, но не ограничивал точные порты;
проверка не является сетевым аудитом всех фоновых соединений Chrome.

## Матрица первого этапа

| Сценарий | Результат и граница |
|---|---|
| Unit baseline | 20 PASS без skip |
| Existing UI baseline | 2 PASS, 1 FAIL: immediate count после history-click; отдельный case затем подтвердил transient 0 → rendered 1. Исходный FAIL сохранён |
| Pairing code/fragment/replay | PASS: 401 до pairing, replay 400, fragment очищен |
| SSE reconnect и overflow | PASS: собственный transport закрыт, новое соединение и snapshot; отдельная queue max16 после 33 publish содержит resync. Переполнение socket buffer не заявляется |
| Все 65 entries | PASS: страницы 30/30/5, 65 уникальных id, на последней нет Next; next/previous 30→31→30 |
| Combined MP4 | PASS: decoded frames и AAC bytes, seek 30s, Range 206; upstream UA сохранён, browser Cookie не передан |
| Split и seek | PASS: H.264+AAC decoded до/после, два FFmpeg с -c copy exit0; один seek, generation+1, старый URL 410, progress около 30.5s с учётом offset |
| Resolver replacement failure | PASS: различимая 503, предыдущая session и её progress сохранены |
| Segmented descriptor / нет FFmpeg | PASS: различимые ошибки 400, прежняя session сохранена |
| Upstream 403 | FAIL: proxy 502, но UI через 15s показывает «Нажмите ▶, чтобы начать просмотр.» вместо delivery error |
| Ранний abort | FAIL: после 128bytes MP4 с ложным Content-Length и закрытием transport UI через 15s остаётся «Подготавливаю видео…». Это не обрыв после нескольких секунд декодирования |
| Desktop viewports | PASS: 800×1280, 1280×800, 390×844 без горизонтального overflow; не Android/iPad acceptance |
| JS pageerrors | Не зарегистрированы; ожидаемые HTTP errors и SSE reconnect не означают пустую console |
| Continuation/natural-ended/recovery/browser revoke | Изначально NOT VERIFIED; последующее независимое завершение ниже дало PASS |
| Fullscreen/background/freeze, реальный звук, YouTube/mobile/package integration | NOT VERIFIED |

## Повторы и исправления стенда

Baseline не повторялся. Первый расширенный прогон дал 1 PASS/2 FAIL/5 ERROR;
второй — 4 PASS/2 FAIL/2 ERROR. Прежние raw результаты сохранены. Доказанные
ошибки стенда: CSP-несовместимый string wait, недостаточное моделирование
обрыва SSE, неверное ожидание 65 одновременных DOM nodes у пагинации,
null.dataset во время перерисовки, двойной seek от fill плюс dispatch.

Последний адресный прогон только pagination и single split-seek дал 2 PASS
за 13.130s. Исправлялись ожидания и действия стенда, не продукт, тайм-ауты
или критерии. Исходные FAIL/ERROR не заменены зелёным результатом. Полный
прогон после каждого исправления не повторялся.

Проверены source/media hashes; исходный checkout чист и остался на указанном
SHA. Собственных Chrome/Playwright/FFmpeg процессов после cleanup нет;
финальные целевые cases закрыли playback sessions. Пустые transfer/subscriber
maps и освобождение портов первым этапом отдельно не доказаны; последующее
завершение добавило такие проверки для пяти новых cases.
Raw logs, команды, fixture hashes и screenshots сохранены локально;
pairing secrets, cookies и внутренние media keys в публичный отчёт не входят.

## Независимое завершение матрицы

Пять ранее не выполненных cases запущены отдельно от известных FAIL,
чтобы один ранний assertion не скрывал остальные критерии. Все пять PASS
за 23.250s на прежнем exact SHA и в том же окружении:

| Кейс | Проверенный результат |
|---|---|
| Continuation | Штатный timeline 15s → pause → close → «Продолжить»; сохранено и восстановлено 15s с decoded video/audio |
| Natural-ended | Настоящие ended events после seek к 59s: A→C; после C следующий entry отсутствует, пауза на 60s. Отдельный двухэлементный плейлист, не все 65 роликов |
| Explicit recovery | Неправильное сообщение после upstream403 сначала сохранено; явные close и reopen с восстановленным fixture source дали новый upstream request и decoded media. Ошибка текста этим не исправлена |
| Browser revoke | Настоящий product Server.revoke в fixture: возврат к pairing, API401 и прежний media URL401; maps опустели, FFmpeg остановлен |
| History render | Immediate count после history-click снова 0, после ожидания реальной карточки 1; подтверждена ошибка синхронизации старого теста, не дефект сохранения layout |

Первоначально runner неверно импортировал WebController вместо Server;
пять import errors произошли до fixture/browser setup. Они сохранены;
исправлено только имя класса, затем каждый browser-case выполнен один раз.
Критерии, продукт и тайм-ауты не менялись, baseline не повторялся.

Для каждого нового case после зарегистрированных cleanup проверены
sessions/transfers/descriptors/preparing/subscribers=0, FFmpeg=0,
aiohttp client.closed=true. Три собственных fixture-порта больше не
принимали соединения. Maps не очищались вручную. Source/media hashes
совпали, собственных процессов после проверки нет. Это дополняет, но не
переписывает исходные raw результаты первого этапа.

## Остаток

Два повторённых отклонения UI принадлежат
[video#47](https://github.com/haltia-de/video/issues/47). Возможное перетирание
delivery error обработчиком autoplay — гипотеза по коду; механизм раннего
abort ещё требует диагностики.

Родительские [#21](https://github.com/haltia-de/video/issues/21) и
[#23](https://github.com/haltia-de/video/issues/23) остаются открытыми.
Fixtures не проверяют YouTube/CDN, авторизованные сервисы, Android/iPad,
слышимость физического выхода или состав установленного пакета.
