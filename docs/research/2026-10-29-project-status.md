# Haltia: архитектура, правила и состояние разработки на 29 октября 2026

Снимок GitHub: 29 октября 2026, 08:11 UTC (11:11 МСК); запросы деталей
завершались позднее. Исследование по документации, Git и аутентифицированному
GitHub REST API всех 24 доступных репозиториев. Это анализ состояния,
не ревью продуктового кода и не приёмка на устройствах. Предложения ниже
не являются принятыми решениями или разрешением на выпуск.

## Оценка проекта

Haltia уже представляет собой работающую платформу: самостоятельная оболочка,
общая библиотека, набор программ и общий контур подписанной упаковки.
Сильная сторона — разделение устройства и пользовательской среды. Основной
риск следующего этапа — расхождение между ветками разработки, выпусками,
составом образов, фактически установленной системой и описанием статуса.
Количество программ растёт быстрее, чем появляется единая аппаратная приёмка.

На GitHub открыты 39 issues и 7 PR. Из 24 репозиториев API показывает
22 публичных и два приватных: haltia и paint-android. Это расходится с
описанием корневого репозитория как публичного в AGENTS.md и ADR 0005.
Публичные ссылки на общие правила и архитектуру при таком доступе могут
быть недоступны внешнему участнику. Изменять видимость без решения автора
не следует; сначала нужно определить, какое состояние задумано.

## Архитектура

Основание: [архитектура](../architecture.md), [словарь](../../CONTEXT.md),
[ADR 0004](../adr/0004-de-apart-from-device.md), [реестр](../repos.md).

| Слой | Ответственность | Граница |
|---|---|---|
| device-* | ядро, DTS, драйверы, прошивки, профиль, установщик и образ | аппаратные особенности не переходят в программы |
| shell | сеанс на phoc, домашний экран, панель, ввод, настройки, обновление и откат | программы обнаруживаются через стандарты freedesktop |
| программы | конкретная пользовательская задача | работают также вне Haltia; без знания модели планшета |
| kit | общие GTK-механизмы, фоновые операции, изображения, камера, звук, обмен файлами | не зависит от оболочки |
| ci / packages | сборка, подпись, выпуск, публикация индексов | сборка продукта отделяется от использования ключей |
| haltia / .github | архитектура, ADR, соглашения, координация, бренд | корневой агент не пишет продуктовый код |

Для связи используются .desktop, MPRIS, LauncherEntry, logind и XDG;
аппаратные особенности подключаются через device.conf и крюки устройства.
Это позволяет сохранять один пользовательский интерфейс для двух планшетов.

Второе устройство уже проверяет архитектурную границу на практике:
B8000-H использует armv7 и GPU-остров libhybris для композитора,
P11 — aarch64 и freedreno/MSM DRM. Различие должно оставаться в device-слое.
Ошибка [shell#88](https://github.com/haltia-de/shell/issues/88) показывает,
что конфигурация ввода и поведение установщика требуют проверки на обоих.

У Видео появилось ещё одно направление: общее ядро для GTK и встроенного
веб-клиента, передача видео через ПК, подключение браузеров и публикация
через прокси. Это документировано в
[video README](https://github.com/haltia-de/video/blob/c14a6d32/README.md)
и [embedded-web](https://github.com/haltia-de/video/blob/c14a6d32/docs/architecture/embedded-web.md),
но общая архитектура корня пока не отражает этот способ использования.
Пока достаточно обозначить его как режим одной программы; общего сетевого
слоя для всей DE из этого автоматически не следует.

Общую сборку образов pertin-haltia имеет смысл рассмотреть после фиксации
реального устройства P11 и его испытанной схемы. Первоначальное условие
«после загрузки второго устройства» уже требует пересмотра по новым данным,
но самостоятельная реорганизация упаковки сейчас не является приоритетом.

## Правила и управление

Соглашения задают SemVer, единые app_id, XDG-пути, русские документы,
английские код и коммиты, общий CI и выпуск только по решению человека.
Шесть программ имеют apk/deb/Flatpak; остальные преимущественно apk.
Важное исключение к общему SemVer уже есть в CI: теги vX.Y.Z_pN для
пересборок дистрибутивных библиотек, но общий текст соглашений его не объясняет.

Процесс задач определён последовательно: issue → один исполнитель →
изолированная копия → проверка → PR → независимое ревью → merge.
ADR 0008 ограничивает допустимого ревьюера: Codex не проверяет Claude;
статус этих PR здесь изучен без продуктового ревью. ADR 0009 разрешает
архитектору squash merge после надлежащего ревью, кроме слияний с публикацией.
Выпуски и перенос ci@v1 требуют отдельного решения человека.

Изоляция диспетчера отделяет рабочую копию без .git от GitHub, ключей и
других клонов. Сеть CLI и документальный поиск разрешены с ограничениями;
тесты результата идут без сети. Проверены 17 локальных unittest диспетчера:
все прошли. Это не сквозная проверка запуска исполнителя и не проверка
реальной стойкости песочницы.

Таймер haltia-dispatch.timer активен и ожидает запуска; последнее срабатывание
29 октября в 11:07:58 МСК. Служба после запуска inactive/dead с Result=success —
нормальный результат завершившегося oneshot. В локальном dispatch.ini задан
max_running=4; в коде и README остаётся значение по умолчанию 2. Само по себе
это допустимое переопределение; README нужно пояснение о конфигурации ПК.

На GitHub нет issues с agent:ready, agent:working или agent:review;
одна имеет agent:blocked. У 39 issues нет assignees; только восемь имеют
model:claude/codex. Поэтому очередь GitHub не описывает всю живую работу.
Это не доказывает простой сессий, но показывает отсутствие единого видимого
учёта владения и состояния. Поднимать max_running сейчас бессмысленно.

ADR 0006 отдельно предупреждает: метка release:approved от общего GitHub
аккаунта не отличает человека от агента. AGENTS.md допускает её при проверке
автора. Следует явно определить актуальный способ подтверждения; пока
идентичности общие, одна метка не доказывает человеческого решения.
Старые ADR сохраняются как история; новые решения оформляются новым ADR,
а актуальное правило — соглашениями и AGENTS.md.

## Состояние устройств и программ

### B8000-H

Последний опубликованный образ — v2.3.1 от 22 октября. Работают базовая
среда, экран, ввод, Wi-Fi, динамики, микрофон и фронтальная камера;
сам проект называет качество альфой. Главный блокер — kernel panic и
подозрение на повреждение памяти после сна/вокруг SDIO:
[#39](https://github.com/haltia-de/device-lenovo-b8000h/issues/39),
[#50](https://github.com/haltia-de/device-lenovo-b8000h/issues/50).
MT6628 — гипотеза, причина пока не установлена.

Подготовлен диагностический kernel 28 в PR #54, включающий #51 и #52.
Его сборка прошла; требуется аппаратная проверка. Диагностическое ядро
нельзя считать обычным релизным кандидатом. Сбор следов падения улучшен
через #56, но issue #38 сохраняет аппаратные пункты приёмки.

### Lenovo P11 / TB-J606L

Корневые docs/repos.md и plans/tab-p11.md отстают: там ещё нет Linux proof.
В действительности [PR #12](https://github.com/haltia-de/device-lenovo-tb-j606l/pull/12)
слит 27 октября; текущий main d89d30c описывает установленную Haltia.
[dual-boot.md](https://github.com/haltia-de/device-lenovo-tb-j606l/blob/d89d30c/docs/dual-boot.md)
фиксирует другую схему: Android остаётся B, Linux находится в recovery_b,
корень — в отдельном разделе haltia. Раздел userdata уменьшен и создан заново.
Переключение использует recovery-флаг в misc, а не постоянную смену слота A/B.

Документированы экран, касание, Wi-Fi, Bluetooth, динамики, микрофоны,
фронтальная камера, зарядка, поворот и s2idle. Остаются проблемы перезагрузки,
звука и модема на ветке mainline-7.3, редкие падения touch-драйвера и глубокий
сон. По комментарию #31 замена qrtr.ko с патчем 3768c60 дала 5/5 загрузок;
полный образ ещё требует пересборки и проверки. Это ограниченный результат
автора комментария, не повторённый данным исследованием.

Даже README устройства внутренне противоречив: новый раздел от 27 октября
описывает рабочую систему, а вступление и раздел резервов сохраняют старое
«прошивать нечего / копий нет». Нужна редакционная синхронизация.

### Программы и ускорение

28 октября вышла широкая серия обновлений: kit 2.4.0, shell 2.13.2,
Messenger 2.9.7, Music 3.0.4, Video 2.15.0 и небольшие программы.
В main уже попали фоновые операции kit, облегчённый запуск, ограничение
частоты обновлений плеера, перенос исполняемого Python-кода в модули,
предкомпиляция и отключение анимаций оболочки. Поэтому исследование
[GTK3 performance](2026-10-26-gtk3-performance.md) нельзя исполнять как
список ещё не сделанного: сначала нужна сверка пунктов с текущим main.

Измеримый следующий шаг — сравнить первый кадр, готовность к касанию,
память и восстановление после сна на обоих устройствах. Постоянное удержание
каждой программы в памяти следует оценивать отдельно: на B8000-H память
ограничена. Полная смена UI-стека не обоснована имеющимися данными.

У Видео новая функциональность быстрее прошла этап разработки, чем аппаратную
приёмку: issues #21–24 прямо оставляют мобильные браузеры, слабое устройство,
реальные сценарии YouTube и ARMv7 непроверенными. Windows/macOS (#25)
разумно отложить до закрытия этой матрицы.

## Выпуск, образ и установленная система

Нельзя смешивать четыре состояния: main, опубликованный пакет, содержимое
образа по lock и фактически установленную систему. Пример B8000-H:

| Компонент | Lock тега образа v2.3.1 | Lock локального origin/main | Последний release GitHub |
|---|---|---|---|
| shell | 2.12.2 | 2.13.0 | 2.13.2 |
| kit | 2.3.1 | 2.3.1 | 2.4.0 |
| Messenger | 2.9.4 | 2.9.5 | 2.9.7 |
| Video | 2.4.3 | 2.11.0 | 2.15.0 |
| Music | 3.0.2 | 3.0.2 | 3.0.4 |
| Mail | 0.1.1 | 0.1.1 | 0.2.1 |

Lock прочитан Git-командами из локального тега и origin/main устройства,
последний столбец — живой GitHub API. Установленные версии не проверялись.
Различие lock и свежего release само по себе не дефект: закрепление нужно
для воспроизводимости. Нужна отдельная запись, какой набор принят для образа.

ci@v1 сейчас указывает на c04f734cce4172c4c50656f11921fc9c55fe0907,
совпадая с изученным main: изменения подписи и компиляции Python уже активны,
а не просто ожидают переноса тега. Последние workflow release у shell,
messenger и video, а также publish у packages успешны. Подписи репозиториев,
наличие каждого артефакта в индексах и установка здесь отдельно не проверялись.

## Оценка открытых работ

- packages#17 — закрыть остаточный обход provides/replaces чужими именами
  Alpine. В текущем [fetch-apks.py](https://github.com/haltia-de/packages/blob/6847c96c2720ff67925718b098adfb26d141e642/fetch-apks.py)
  статически подтверждено: запрет проверяет имена других публикаторов,
  но неизвестные ему busybox/openrc не попадают в множество запрещённых.
  Это подтверждённый пробел проверки метаданных; практическая перезапись
  файлов и публикация вредного пакета не проверялись.
  Старую уже сделанную защиту от присвоения имён другого Haltia-публикатора
  нельзя считать решением неизвестных имён вроде busybox/openrc.
- B8000 #39/#50 — аппаратная проверка #54 и сохранение следов с точными
  хэшами ядра/образа, до обещаний стабильности.
- P11 #24/#29/#26/#31/#32/#33 — отделить установленный baseline от ветки 7.3,
  повторить результаты на полном образе, проверить загрузку и возврат Android.
- shell#88 — ограничение профиля устройства уже отражено в touchguard=no,
  но issue остаётся о включении фильтра установщиком и обработке этого ввода.
- Messenger #24/#29 — по комментариям многие пункты уже исправлены;
  переписать остаток и связать с #78, а не повторять исходный аудит.
- P11 PR #10 — ранний RAM diagnostic; решить судьбу ветки после сравнения
  с текущим main: закрыть как исторический либо выделить полезный остаток.
- B8000 #57 — upstream PR уже созданы; требуется завершить проверки и ответы
  владельцем аппаратной работы. Это не новая задача «начать отправку».

У всех семи PR mergeable=true, формальных reviews нет. Для пяти heads нет
GitHub check runs; это не доказывает отсутствие локальных тестов.
Наличие результата в другой ветке также не равно проверке текущего head.
Независимое ревью по ADR 0008 и аппаратная приёмка остаются отдельными
условиями, даже когда GitHub разрешает merge.

## Предлагаемый порядок следующих шагов

1. **Уточнить актуальную картину.** Исправить реестр, план P11 и его README;
   зафиксировать фактическую схему recovery_b; принять решение о видимости
   корневых правил. Обновить текущие соглашения по _pN, утверждению выпусков
   и конфигурации диспетчера. Старые ADR не переписывать.
2. **Подготовить конечную очередь.** Для issues указать владельца, реальный
   остаток, критерии приёмки и зависимости. Только готовым к автоматическому
   выполнению дать agent:ready и ровно одну model-метку; аппаратные оставить
   живым сессиям с needs:tablet. Один планшет — один держатель блокировки.
3. **Закрыть опасные и пользовательские сбои.** Проверить packages#17;
   выполнить ограниченный аппаратный план B8000 #54; стабилизировать P11
   restart/audio/modem/touch; довести Messenger #78 и сценарии busy/teardown.
   Требуемые ревью назначать по ADR 0008. Публикацию согласовывать отдельно.
4. **Принять единый набор пакетов для устройств.** Привязать отчёт приёмки
   к kernel SHA, rootfs SHA и packages.lock. Проверить обновление, отказ
   обновления/откат, холодную загрузку, сон/пробуждение, сеть, звук, камеру,
   звонки и возврат Android на P11. Состав конкретного прогона согласует
   владелец устройства; данный отчёт не разрешает эти действия.
5. **Измерить эффект уже сделанного ускорения.** Записать время до первого
   кадра и готового управления, RSS/PSS и затраты CPU на B8000-H/P11;
   сравнивать одинаковые сценарии и наборы пакетов. Следующие оптимизации
   выбирать по измерению, а не по старому списку гипотез.
6. **После устойчивой базы — расширение.** Мобильная приёмка веб-Видео,
   затем Windows/macOS; глубокий сон и дополнительные устройства ввода P11;
   пилот панели агентов. Удаление старых symlink — по существующей задаче
   4 ноября, а не в рамках текущего анализа.

## Границы проверки

Изменён только этот исследовательский документ. Код программ, ADR, issues,
PR, labels, релизы и настройки GitHub не менялись. Планшеты и установленные
программы не использовались. Результаты устройств выше — документальные
свидетельства и сообщения исполнителей с указанными источниками.
Локальные старые рабочие ветки не принимались за актуальные релизы.
Незакоммиченные материалы docs/drafts и исследование публикации 4PDA
сохранены без изменений.

Далее — полный снимок GitHub с прямыми ссылками, всеми 39 issues и семью PR.

## Приложение: полный снимок GitHub
Снимок: 2026-10-29T08:11:46.191613+00:00. Read-only GitHub REST API, все 24 доступных репозитория; списки репозиториев, issues, PR и комментариев пагинированы. Данные GitHub не доказывают текущее состояние установленной программы или устройства.

Всего: **39 issues и 7 PR**. 22 публичных репозитория, 2 приватных (haltia и paint-android).

### Репозитории и релизы

|Репозиторий|Issues|PR|Последний release|Дата UTC|
|---|---:|---:|---|---|
|[device-lenovo-b8000h](https://github.com/haltia-de/device-lenovo-b8000h)|8|4|v2.3.1|2026-10-22T13:59:14Z|
|[paint](https://github.com/haltia-de/paint)|0|0|v4.8.2|2026-10-28T10:49:51Z|
|[weather](https://github.com/haltia-de/weather)|0|0|v2.1.5|2026-10-28T10:49:34Z|
|[news](https://github.com/haltia-de/news)|0|0|v2.2.5|2026-10-28T10:49:50Z|
|[messenger](https://github.com/haltia-de/messenger)|5|1|v2.9.7|2026-10-28T10:48:48Z|
|[video](https://github.com/haltia-de/video)|5|0|v2.15.0|2026-10-28T16:29:14Z|
|[music](https://github.com/haltia-de/music)|1|0|v3.0.4|2026-10-28T10:49:10Z|
|[calendar](https://github.com/haltia-de/calendar)|0|0|v2.0.7|2026-10-28T10:50:08Z|
|[files](https://github.com/haltia-de/files)|0|0|v2.2.2|2026-10-28T10:49:29Z|
|[text](https://github.com/haltia-de/text)|0|0|v2.0.6|2026-10-28T10:50:04Z|
|[kit](https://github.com/haltia-de/kit)|0|0|v2.4.0|2026-10-28T06:13:06Z|
|[firefox](https://github.com/haltia-de/firefox)|0|0|v2.1.0|2026-10-21T21:36:53Z|
|[shell](https://github.com/haltia-de/shell)|2|1|v2.13.2|2026-10-28T10:53:18Z|
|[ci](https://github.com/haltia-de/ci)|0|0|—|—|
|[packages](https://github.com/haltia-de/packages)|1|0|—|—|
|[.github](https://github.com/haltia-de/.github)|0|0|—|—|
|[paint-android](https://github.com/haltia-de/paint-android)|0|0|—|—|
|[haltia](https://github.com/haltia-de/haltia)|3|0|—|—|
|[libnice](https://github.com/haltia-de/libnice)|0|0|v0.1.24_p2|2026-10-27T07:52:26Z|
|[gst-webrtc](https://github.com/haltia-de/gst-webrtc)|0|0|v1.28.3|2026-10-21T20:10:14Z|
|[camera](https://github.com/haltia-de/camera)|0|0|v0.1.2|2026-10-28T10:50:22Z|
|[libcamera](https://github.com/haltia-de/libcamera)|0|0|v0.7.1_p1|2026-10-22T06:07:01Z|
|[mail](https://github.com/haltia-de/mail)|0|0|v0.2.1|2026-10-28T10:49:20Z|
|[device-lenovo-tb-j606l](https://github.com/haltia-de/device-lenovo-tb-j606l)|14|1|—|—|

### Все открытые PR

Формальных GitHub reviews нет у всех семи PR; это не исключает внешнее review в herdr или комментариях. `mergeable=true` у всех семи означает отсутствие конфликта Git, а не разрешение на merge.

|PR|Draft|GitHub checks|Назначение|
|---|---|---|---|
|[device-lenovo-b8000h#54](https://github.com/haltia-de/device-lenovo-b8000h/pull/54)|True|release: skipped; rootfs: success; kernel: success|DEBUG kernel 28: #51 + #52 + memory checks, the test kernel for #39 and #50|
|[device-lenovo-b8000h#53](https://github.com/haltia-de/device-lenovo-b8000h/pull/53)|False|нет checks на head|Keep the bytecode subpackages of Python packages in the image|
|[device-lenovo-b8000h#52](https://github.com/haltia-de/device-lenovo-b8000h/pull/52)|True|нет checks на head|DEBUG: report an MMC claim frame that changes while its task sleeps (#39, test kernel)|
|[device-lenovo-b8000h#51](https://github.com/haltia-de/device-lenovo-b8000h/pull/51)|False|нет checks на head|Keep MT6628 RX copies and SDIO reads inside their buffers (needs tablet verification)|
|[messenger#78](https://github.com/haltia-de/messenger/pull/78)|False|нет checks на head|Keep a call through refused candidates and stray service errors, and tell its end before the hang-up goes.|
|[shell#87](https://github.com/haltia-de/shell/pull/87)|False|tests: success; headless: success|Turn the screen off and on with a folio cover's lid switch.|
|[device-lenovo-tb-j606l#10](https://github.com/haltia-de/device-lenovo-tb-j606l/pull/10)|True|нет checks на head|Add a reproducible RAM diagnostic image for the verified J606L.|

### Все открытые issues

|Issue|Задача|Метки|Обновлено UTC|Возраст, дней|
|---|---|---|---|---:|
|[device-lenovo-b8000h#57](https://github.com/haltia-de/device-lenovo-b8000h/issues/57)|Send the patches TeamYogaBlade2 asked for as PRs against blade/v7.1|model:claude, kind:mechanical, needs:tablet|2026-10-29T06:33:39Z|0|
|[device-lenovo-b8000h#50](https://github.com/haltia-de/device-lenovo-b8000h/issues/50)|Three unrelated processes segfault in the same second after a resume (possible MT6628 memory corruption, see #39).|agent:blocked, model:claude, kind:research, needs:tablet|2026-10-28T06:34:02Z|2|
|[device-lenovo-b8000h#39](https://github.com/haltia-de/device-lenovo-b8000h/issues/39)|Kernel panic: stack-protector in mmc_release_host from sdio_irq_work (k27c, after a video call)|—|2026-10-28T17:57:18Z|7|
|[device-lenovo-b8000h#38](https://github.com/haltia-de/device-lenovo-b8000h/issues/38)|Make crash evidence available after a reboot: pstore on the rootfs, OOM and watchdog traces for haltia-report.|model:claude, kind:feature, needs:tablet|2026-10-28T06:44:05Z|7|
|[device-lenovo-b8000h#4](https://github.com/haltia-de/device-lenovo-b8000h/issues/4)|Камеры (A5142, OV9726/OV9760)|enhancement|2026-10-19T05:31:56Z|10|
|[device-lenovo-b8000h#3](https://github.com/haltia-de/device-lenovo-b8000h/issues/3)|Модем 3G (MD1 MT6589, CCCI)|enhancement|2026-10-19T05:31:53Z|10|
|[device-lenovo-b8000h#2](https://github.com/haltia-de/device-lenovo-b8000h/issues/2)|GPS через MT6628 (канал STP и стоковый MNL)|enhancement|2026-10-19T05:31:51Z|10|
|[device-lenovo-b8000h#1](https://github.com/haltia-de/device-lenovo-b8000h/issues/1)|Звук: наушники, микрофон, дрожание тона, переход на ASoC|enhancement|2026-10-19T05:31:48Z|10|
|[messenger#29](https://github.com/haltia-de/messenger/issues/29)|Fix the full code review's findings: call teardown deadlock, per-frame cost, lost input on send, cache lock.|model:claude, kind:feature|2026-10-27T20:54:48Z|7|
|[messenger#24](https://github.com/haltia-de/messenger/issues/24)|Fix the second audit's findings: reconnect backoff, a call ended by the message socket, double connections, dead backend on a keyring error.|model:codex, kind:feature|2026-10-27T20:54:51Z|7|
|[messenger#20](https://github.com/haltia-de/messenger/issues/20)|Tell the person about a call that got a busy answer during another call.|model:codex, kind:feature|2026-10-21T20:53:58Z|7|
|[messenger#14](https://github.com/haltia-de/messenger/issues/14)|Close the dial confirmation when a call rings, and test the busy reply live.|model:codex, kind:feature|2026-10-21T17:46:21Z|7|
|[messenger#3](https://github.com/haltia-de/messenger/issues/3)|Bring the icon and the brand sketch in haltia-de/.github back in step.|kind:mechanical|2026-10-21T10:36:04Z|7|
|[video#25](https://github.com/haltia-de/video/issues/25)|Package Видео for Windows and macOS.|—|2026-10-27T05:22:12Z|2|
|[video#24](https://github.com/haltia-de/video/issues/24)|Re-check the B8000-H (ARMv7) after 2.6.0 and 2.7.0.|—|2026-10-27T05:22:10Z|2|
|[video#23](https://github.com/haltia-de/video/issues/23)|Check real YouTube scenarios in the web player.|—|2026-10-27T05:22:09Z|2|
|[video#22](https://github.com/haltia-de/video/issues/22)|Measure the web mode's resources on a weak device.|—|2026-10-27T05:22:07Z|2|
|[video#21](https://github.com/haltia-de/video/issues/21)|Check the web client in real mobile browsers.|—|2026-10-27T05:22:05Z|2|
|[music#3](https://github.com/haltia-de/music/issues/3)|Bring the icon and the brand sketch in haltia-de/.github back in step.|kind:mechanical|2026-10-21T10:36:02Z|7|
|[shell#88](https://github.com/haltia-de/shell/issues/88)|haltia-touchguard passes no touches on the TB-J606L|—|2026-10-28T07:46:07Z|1|
|[shell#80](https://github.com/haltia-de/shell/issues/80)|Turn the screen off and on with a folio cover (SW_LID).|—|2026-10-26T18:23:05Z|2|
|[packages#17](https://github.com/haltia-de/packages/issues/17)|Allow only own names and virtual names in .PKGINFO provides and replaces.|model:codex, kind:mechanical|2026-10-22T06:14:41Z|7|
|[haltia#3](https://github.com/haltia-de/haltia/issues/3)|Pilot Grok through OpenCode on SuperGrok inside the bwrap sandbox.|kind:research|2026-10-21T12:21:22Z|7|
|[haltia#2](https://github.com/haltia-de/haltia/issues/2)|Pilot OpenHands Agent Canvas for one day (docs/plans/control-panel.md).|kind:research|2026-10-21T12:21:19Z|7|
|[haltia#1](https://github.com/haltia-de/haltia/issues/1)|Remove the old clone symlinks in /mnt/data/Projects on 4 November 2026.|kind:mechanical|2026-10-21T11:13:42Z|7|
|[device-lenovo-tb-j606l#33](https://github.com/haltia-de/device-lenovo-tb-j606l/issues/33)|A reboot from Linux sometimes ends in Android|—|2026-10-28T19:03:10Z|0|
|[device-lenovo-tb-j606l#32](https://github.com/haltia-de/device-lenovo-tb-j606l/issues/32)|The sound card still fails on some 7.3 boots|—|2026-10-28T15:18:46Z|0|
|[device-lenovo-tb-j606l#31](https://github.com/haltia-de/device-lenovo-tb-j606l/issues/31)|With PSCI idle on, the modem stalls at boot on 7.3 and Wi-Fi comes up late|—|2026-10-28T19:03:08Z|0|
|[device-lenovo-tb-j606l#29](https://github.com/haltia-de/device-lenovo-tb-j606l/issues/29)|Unbinding the touch driver oopses in nvt_ts_suspend|—|2026-10-28T07:46:34Z|1|
|[device-lenovo-tb-j606l#28](https://github.com/haltia-de/device-lenovo-tb-j606l/issues/28)|Wired headphones through USB-C (no 3.5 mm jack)|—|2026-10-28T06:38:28Z|1|
|[device-lenovo-tb-j606l#26](https://github.com/haltia-de/device-lenovo-tb-j606l/issues/26)|Reboot hangs in msm_kms_shutdown while the screen is dark|—|2026-10-28T07:46:32Z|1|
|[device-lenovo-tb-j606l#25](https://github.com/haltia-de/device-lenovo-tb-j606l/issues/25)|Reach the SoC's deep sleep (RPM vlow/vmin) in s2idle|—|2026-10-27T18:55:14Z|1|
|[device-lenovo-tb-j606l#24](https://github.com/haltia-de/device-lenovo-tb-j606l/issues/24)|The touch driver oopses when the panel goes away under it|—|2026-10-27T18:55:12Z|1|
|[device-lenovo-tb-j606l#18](https://github.com/haltia-de/device-lenovo-tb-j606l/issues/18)|Find why starting both hexagonrpcd PDs early crashed the SoC.|—|2026-10-26T18:22:35Z|2|
|[device-lenovo-tb-j606l#17](https://github.com/haltia-de/device-lenovo-tb-j606l/issues/17)|Power USB-C devices from the tablet (OTG).|—|2026-10-28T10:35:15Z|2|
|[device-lenovo-tb-j606l#16](https://github.com/haltia-de/device-lenovo-tb-j606l/issues/16)|Support the pogo keyboard.|—|2026-10-26T18:22:29Z|2|
|[device-lenovo-tb-j606l#15](https://github.com/haltia-de/device-lenovo-tb-j606l/issues/15)|Bring up the rear camera.|—|2026-10-26T18:22:27Z|2|
|[device-lenovo-tb-j606l#14](https://github.com/haltia-de/device-lenovo-tb-j606l/issues/14)|Support the stylus on the NT36523W touch controller.|—|2026-10-26T18:22:25Z|2|
|[device-lenovo-tb-j606l#13](https://github.com/haltia-de/device-lenovo-tb-j606l/issues/13)|Bring up the LTE modem for mobile data and SMS.|—|2026-10-26T18:22:23Z|2|

Метки: {'model:claude': 4, 'kind:mechanical': 5, 'needs:tablet': 3, 'agent:blocked': 1, 'kind:research': 3, 'kind:feature': 5, 'enhancement': 4, 'model:codex': 4}. Issues с GitHub assignee: 0/39. Отсутствие assignee не доказывает отсутствия живого исполнителя.

### Уточнения по последним комментариям

- B8000 #39/#50: причина повреждения памяти не установлена. Последняя поправка 28 октября 17:57 UTC: собственный wlan_mt6628 остаётся подозреваемым; сначала испытать #54, включающий исправления #51, затем исследовать общие части с upstream. Не выдавать гипотезу MT6628 за доказанную причину.
- B8000 #38: klogd, panic=10 и документация уже в main через #56. Открыты аппаратная проверка pstore, forced panic, watchdog и очистка pstore после отправки отчёта.
- B8000 #57: upstream PR уже созданы; задача остаётся ради аппаратных проверок. По комментарию планшет недоступен до следующей недели. Есть дополнительные запросы upstream от 29 октября.
- Messenger #24/#29: старые заголовки перечисляют уже исправленные critical-дефекты. Комментарии от 27 октября показывают большинство исправлений в main; #78 закрывает часть оставшихся call defects, #79 (уже не открыт) касался backend. Остаток: layout/bubbles на планшете, блокирующий media set_state, cache eviction, _received/close race, thread per item, экспериментальное уведомление Telegram disconnect. Нужен пересмотр issue на актуальность, а не повторное исправление всей исходной простыни.
- TB #31: 28 октября 19:03 UTC на mainline-7.3 исправлено 0020/3768c60 (QRTR HELLO). Сменой только qrtr.ko получено 5/5 загрузок без stall; полный образ с 0020 ещё надо пересобрать. cpuidle.off=1 ранее опровергнуто и отменено.
- TB #24: патч cleanup panel уже поставлен, но редкий failure path после этого ещё не воспроизведён; issue остаётся для проверки.
- TB #17: OTG даёт 5.006 V на порту, но dock не enumerates из-за VBUSOK/TCPM; feature ещё не работает.
- TB main по API: d89d30c860b43b8f5d568c7b21b42db5a19e7383. Root docs/repos.md отстаёт от подтверждённой документации живого device repo. PR #10 draft — ранняя diagnostic image; описание no Linux launch устарело относительно current main и требует решения судьбы ветки.
- Shell #88: touchguard при включении блокирует все касания на J606L; пакетная установка его сама не включает, ошибку обнаружили после non-package install.sh. Приоритет выше косметических задач.
- Packages #17: allowlist APK provides/replaces пропускает чужие имена (пример busybox/openrc), что позволяет permitted repo заявить замену Alpine files. Следующая важная задача укрепления контура публикации.
- ci@v1 указывает на c04f734cce4172c4c50656f11921fc9c55fe0907: последняя main версия активна.

### Свежий CI

- shell: [release](https://github.com/haltia-de/shell/actions/runs/40674951648), success, 5d750b49, 2026-10-28T10:47:55Z.
- shell: [session](https://github.com/haltia-de/shell/actions/runs/40674943034), success, 5d750b49, 2026-10-28T10:47:51Z.
- shell: [session](https://github.com/haltia-de/shell/actions/runs/40674714471), success, 27f259a6, 2026-10-28T10:46:06Z.
- messenger: [release](https://github.com/haltia-de/messenger/actions/runs/40674970428), success, 5ab88bbb, 2026-10-28T10:48:04Z.
- messenger: [release](https://github.com/haltia-de/messenger/actions/runs/40642762378), success, 185ff7e8, 2026-10-28T06:15:33Z.
- messenger: [release](https://github.com/haltia-de/messenger/actions/runs/39939650157), success, 71ab79ac, 2026-10-23T10:30:56Z.
- video: [release](https://github.com/haltia-de/video/actions/runs/40725297357), success, c14a6d32, 2026-10-28T16:22:19Z.
- video: [Shared core](https://github.com/haltia-de/video/actions/runs/40725296562), success, c14a6d32, 2026-10-28T16:22:19Z.
- video: [Shared core](https://github.com/haltia-de/video/actions/runs/40725245800), success, c14a6d32, 2026-10-28T16:22:00Z.
- packages: [publish](https://github.com/haltia-de/packages/actions/runs/40808063267), success, 6847c96c, 2026-10-29T02:43:40Z.
- packages: [publish](https://github.com/haltia-de/packages/actions/runs/40787329696), success, 6847c96c, 2026-10-28T23:26:02Z.
- packages: [publish](https://github.com/haltia-de/packages/actions/runs/40750571822), success, 6847c96c, 2026-10-28T19:01:52Z.

Сырые ответы API сохранены локально; в Git не включены.

### Дополнения после завершения пагинации

- [TB PR #12](https://github.com/haltia-de/device-lenovo-tb-j606l/pull/12) «Run Haltia on the TB-J606L next to Android on slot B» merged 27 октября 20:34 UTC. Это явная точка, после которой root docs о no Linux proof устарели.
- [TB PR #30](https://github.com/haltia-de/device-lenovo-tb-j606l/pull/30) merged 28 октября 11:15 UTC: touchguard=no в device.conf; shell#88 остаётся для поведения самого фильтра и non-package install.
- [TB PR #27](https://github.com/haltia-de/device-lenovo-tb-j606l/pull/27) merged 28 октября 11:15 UTC: openrc-settingsd/time settings.
- Packages: [publish](https://github.com/haltia-de/packages/actions/runs/40808063267) success, 2026-10-29T02:43:40Z.
- Packages: [publish](https://github.com/haltia-de/packages/actions/runs/40787329696) success, 2026-10-28T23:26:02Z.
- Packages: [publish](https://github.com/haltia-de/packages/actions/runs/40750571822) success, 2026-10-28T19:01:52Z.

### Проверка актуального кода packages

`packages/main` по API: `6847c96c2720ff67925718b098adfb26d141e642`. Прочитаны [fetch-apks.py](https://github.com/haltia-de/packages/blob/6847c96c2720ff67925718b098adfb26d141e642/fetch-apks.py) и [publishers.conf](https://github.com/haltia-de/packages/blob/6847c96c2720ff67925718b098adfb26d141e642/publishers.conf). `pkgname` строго ограничен names издателя; claims отклоняются лишь если `claimed_name in all_names - names`. Busybox/openrc отсутствуют в общем списке, поэтому их provides/replaces не отклоняются этим guard. Статически подтверждён пробел проверки метаданных; публикация вредного APK и фактическая перезапись файлов не выполнялись.

`haltia/main` по API совпадает с локальным: `3c9b0a1e4d5ae611b899fa070d70da6186c5f4c0`.
