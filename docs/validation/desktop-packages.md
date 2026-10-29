# Приёмка настольных пакетов Haltia

Дата: 29 октября 2026. Архитектура: amd64/x86_64. Планшет, личные аккаунты и установленные пользователем приложения не использовались. Продуктовый код не менялся.

## Источник и точные версии

Официальные подписанные репозитории: `https://haltia-de.github.io/packages/apt` и `https://haltia-de.github.io/packages/flatpak/repo/`. Доверенный ключ взят из `haltia/keys/haltia-archive-keyring.gpg`; fingerprint `13461D3E807729260DD4A61461FCD08BBFE7462F`. Для apt проверена цепочка подпись InRelease → SHA256 Packages.gz → SHA256 каждого deb (21 файл). Для каждого Flatpak проверена подпись OSTree-коммита этим ключом.

| Пакет | Версия во всех трёх apt-ветках |
|---|---|
| haltia-messenger | 2.9.7 |
| haltia-music | 3.0.4 |
| haltia-news | 2.2.5 |
| haltia-paint | 4.8.2 |
| haltia-video | 2.15.0 |
| haltia-weather | 2.1.5 |
| python3-haltia-kit | 2.4.0 |

## Фактически выполненные проверки

| Формат / среда | Импорт установленных модулей | Два старта по 8 секунд | Хранение данных: четыре отдельных процесса |
|---|---|---|---|
| deb / noble | 7/7 pass | 10/12 pass | 24/24 pass |
| deb / resolute | 7/7 pass | 12/12 pass | 24/24 pass |
| deb / trixie | 7/7 pass | 10/12 pass | 24/24 pass |
| Flatpak / GNOME Platform 51 | 6/6 pass | 12/12 pass | 24/24 pass |

В deb применён Xvfb; после установки сеть контейнера отключена. Flatpak запущен через Broadway внутри отдельного сетевого namespace; удалённого доступа к Broadway нет. HOME, XDG-каталоги, каталог установки Flatpak и session D-Bus изолированы; имеющееся развёртывание runtime использовано для чтения. Контейнеры удаляются по окончании.

Данные fixture: город Погоды; локальная лента Новостей на `example.invalid`; прогресс искусственной картинки Раскраски; тестовое поле `kit.Settings` в профилях Музыки и Сообщений; вид списка в `Library` Видео. Для каждого: записать → прочитать новым процессом → изменить → прочитать новым процессом. Для Музыки/Сообщений это проверка слоя настроек, не плейлистов, чатов или сессий.

## Обнаруженный дефект

**FAIL: Раскраска 4.8.2, deb noble и trixie.** Оба старта в каждой из этих веток воспроизводят `AttributeError: gi.repository.GLibUnix has no attribute signal_add` при активации окна, `/usr/lib/haltia-paint/haltia_paint_main.py:2176`. Импорт модуля и хранение прогресса проходят; это не отменяет отказ активации интерфейса.

## Обновление установленного пакета

Погода deb noble 2.1.4 → 2.1.5: **PASS**. Город записан публичным методом старого установленного пакета и проверен новым процессом после установки нового deb. Оба deb сверены по подписанному индексу; операция внутри одноразового контейнера.

Обновление пакетов остальных программ и обновление Flatpak с предыдущей версии: **NOT RUN**.

## Пределы проверки

Успех smoke означает, что процесс пережил 8 секунд и в логе нет Python traceback; видимость и пригодность окна не проверялись визуально. Не проверялись реальная погода/RSS, аккаунты MAX/Яндекс/VK/YouTube, отправка сообщений/звонки, воспроизведение звука/видео, микрофон/камера, Bluetooth, порталы выбора файлов, Secret Service или desktop integration на настоящем сеансе. В изолированном Flatpak встречаются ожидаемые предупреждения отсутствующих portal/keyring/IBus/Pantheon backend; их нельзя трактовать как успешную проверку порталов.

Первые попытки pull Музыки и Видео дали HTTP503; один повтор завершился успешно. Первоначальные ошибки harness (launcher принудительно __main__, путь Музыки `/usr/share`, старый Weather без wrapper) исправлены и соответствующие проверки повторены.

## Артефакты и воспроизведение

Приватный каталог: `/mnt/data/haltia-desktop-validation-20261029` (0700). `run-deb.py [noble|resolute|trixie]`, `run-flatpak.py`, `flatpak-persistence.py`, `flatpak-smoke.py`, `weather-upgrade.py`, `verify-metadata.py`, `collect-flatpak.py`, `report.py`. Выполнять из обычного пользователя с Docker/Flatpak, сетевой установкой зависимостей и достаточным местом; host-пакеты не устанавливаются. `flatpak-persistence.py` и `flatpak-smoke.py` запускать после завершения `run-flatpak.py`.

`metadata.results.json` содержит точные deb-версии, имена и sha256. `flatpak.artifacts.json` содержит коммиты, исходные git-коммиты, подтверждение подписи и версии встроенного kit. `*.results.json` содержат результаты по проверкам; `*.install.log` — установку. Не публиковать сырые логи без повторной проверки приватности.

### Подписанные Flatpak-коммиты

| Программа | Версия | OSTree commit |
|---|---|---|
| Messenger | 2.9.7 | `9d9b0878521e2661acfb0e1fbe8f510809e976eddd954404b1d2697c828abaac` |
| Music | 3.0.4 | `d6ffaa4a415f23037c5561810668a97316f1a603c791acf8a5bfe1f5525bcc37` |
| News | 2.2.5 | `30845792d7736e00a382361e2edab8ea68779735058ee200f41160f332b9ef3c` |
| Paint | 4.8.2 | `c0066ef6a9f70d7a3d70b58b8bb7b300466b1b673741c92e31da71245c3e8558` |
| Video | 2.15.0 | `a03966f6b6e1af4a9690e5e0730c6276f552c3689e15249b0cc1d488cba81951` |
| Weather | 2.1.5 | `d2dab56f6f1b262fef5be021a57729a064f03fb9cc28c2f4a693194286946fb0` |

### SHA256 deb-артефактов

| Ветка | Пакет | SHA256 |
|---|---|---|
| noble | haltia-messenger | `3b566325dfb51275a66eb29a311bef0d824d07e4583067ec86df06765dc99c37` |
| noble | haltia-music | `c4c5ad4fc73f0b745f1e4c128f56bf13081e8ddf1f0c1cef6d6a250d0d1652e5` |
| noble | haltia-news | `f8831089ac5033c9c89ad5459cdcc69e9049338c40d5cbe900dbe5bf2da65469` |
| noble | haltia-paint | `c89ef8a0cbbad23147cd6be5a9e447257dcca016b9cdad0223e434e050719dba` |
| noble | haltia-video | `1cf8fee19281b9c11accb3ef2f5e33482e288255fd13e3070b0a8a7b26c73f8c` |
| noble | haltia-weather | `b35fc4867743acba2ebb7149b1ce2bb49b41d5eb2b883dedc30ab4f0b4e1ddb8` |
| noble | python3-haltia-kit | `32b71317b7180a72f8ce70e8e505b1f384be86ac51ea011331d4122fc0381a16` |
| resolute | haltia-messenger | `92da482ebedc9aebc09589288b5d4a7a669cce65fe5df72ef3b564aaedcab7f7` |
| resolute | haltia-music | `60d3b832a0601d6dfe62ace3ad7b77aab9e504170f14e25cb5f399b2cf635a76` |
| resolute | haltia-news | `44bf7a98e4c8831069f6e60e4376edc3cb60cb0659a2df8063b419ed102c7f19` |
| resolute | haltia-paint | `579c28f4929c59cfb481532e036c79963050eab6bdbefa61241e77697f51ea11` |
| resolute | haltia-video | `018e800b749aa69c71c3ed6d0282584535e9f82828269612758d3d043f8b2c8c` |
| resolute | haltia-weather | `a2032ffcafddeffe95b9d614ea29055ec22d4b6f08f08735c68ef725dad95cae` |
| resolute | python3-haltia-kit | `f34f4235d23c625801e42cdd27807c8f92546885191fe8befad3c9e25a8f600e` |
| trixie | haltia-messenger | `040dcf3e7e0e4ff857dad8bae14475158b37800b205e724b9865cfbcb327a4d8` |
| trixie | haltia-music | `18ee30f6507d0f49d3054f715f444734b49c2c7683957a1aeedc5fbc7c02e242` |
| trixie | haltia-news | `b0492d905b832de4b6721298ec4a8b7cb1ca15091c2b33d66e01dd6f2016094f` |
| trixie | haltia-paint | `703de15edd225d769b0f439f9c70162bed4f8cb52734064ef93c60ed97720c2c` |
| trixie | haltia-video | `9e74087c2f03279c6e808ab4372e7be2ee72820123dbca97cb7f606045373220` |
| trixie | haltia-weather | `8bad3b66cc040d93c6d8efb1819cbbeb60614132d8056de8100c42e63cebdbad` |
| trixie | python3-haltia-kit | `ced70d389b1003b1ca16c7d8203828c17a2b0dfcdfa093b6e0982bbab90c79d5` |

Отслеживание дефекта: [paint#22](https://github.com/haltia-de/paint/issues/22).
Неисполненные пункты общей функциональной приёмки остаются открытыми.
