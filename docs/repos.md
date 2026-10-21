# Репозитории

Реестр репозиториев организации [haltia-de](https://github.com/haltia-de).
Слои — по ADR 0001 и 0004. Локальная папка — клон на ПК сборки (до переезда
в `/mnt/data/Projects/haltia-de/<repo>`, ADR 0005, шаг 6).

| Репозиторий | Слой | Что это | Выпускает | Локальная папка | CLAUDE.md / AGENTS.md |
|---|---|---|---|---|---|
| [haltia](https://github.com/haltia-de/haltia) | проект | архитектура, ADR, планы, правила, ключи, диспетчер агентов | — | `haltia-de/haltia` | есть / есть |
| [.github](https://github.com/haltia-de/.github) | проект | профиль организации, знак и бренд (`brand/`) | — | `haltia-github` | нет / нет |
| [shell](https://github.com/haltia-de/shell) | оболочка | панель, домашний экран, «✕», фильтр касаний, клавиатура, поворот, настройки, обновления, тема | apk | `b8k-shell` | есть / есть |
| [kit](https://github.com/haltia-de/kit) | библиотека | `haltia_kit`: вопросы, настройки, звук, фото (GTK 3) | apk, deb, Flatpak-модуль | `b8k-compat` (лишний клон `kit`) | есть / есть |
| [files](https://github.com/haltia-de/files) | программа | Файлы и Галерея | apk | `haltia-files` | есть / есть |
| [text](https://github.com/haltia-de/text) | программа | блокнот | apk | `b8k-text` | нет / нет |
| [calendar](https://github.com/haltia-de/calendar) | программа | настенный календарь | apk | `b8k-calendar` | нет / нет |
| [news](https://github.com/haltia-de/news) | программа | новости RSS | apk, deb, Flatpak | `b8k-news` | есть / есть |
| [weather](https://github.com/haltia-de/weather) | программа | погода (Gismeteo) | apk, deb, Flatpak | `b8k-weather` | есть / есть |
| [video](https://github.com/haltia-de/video) | программа | видео: YouTube и другие источники | apk, deb, Flatpak | `b8k-video` | есть / есть |
| [music](https://github.com/haltia-de/music) | программа | музыка: Яндекс Музыка и другие | apk, deb, Flatpak | `b8k-music` | есть / есть |
| [messenger](https://github.com/haltia-de/messenger) | программа | мессенджер MAX без браузера | apk, deb, Flatpak | `b8k-max` | есть / есть |
| [paint](https://github.com/haltia-de/paint) | программа | раскраска по номерам | apk, deb, Flatpak | `b8k-paint` | есть / есть |
| [firefox](https://github.com/haltia-de/firefox) | программа | Firefox для сенсорного экрана и слабого железа | apk | `b8k-firefox` | есть / есть |
| [ci](https://github.com/haltia-de/ci) | упаковка | общий выпуск по тегам: apk, deb, Flatpak (`@v1`) | — | `b8k-ci` | есть / есть |
| [packages](https://github.com/haltia-de/packages) | упаковка | репозитории apk, apt и Flatpak на GitHub Pages, метапакеты | репозитории | `haltia-packages` | есть / есть |
| [device-lenovo-b8000h](https://github.com/haltia-de/device-lenovo-b8000h) | устройство | Lenovo YOGA Tablet 10 B8000-H: ядро 7.1, драйверы, остров GPU, образы Pertin Haltia | образы, ядро, остров | `lenovo-b8000h-linux` | есть / есть |
| paint-android (закрытый) | исследование | Раскраска для Android: исследование и план | — | `paint-android` | есть / нет |

## Кто работает в репозитории

Долгоживущие сеансы агентов (в herdr, ADR 0007) открыты в оболочке, сообщениях,
музыке, видео, раскраске и устройстве. Остальные репозитории берут
исполнители по задачам (ADR 0005). Имена сеансов и адреса планшетов в этот
публичный реестр не пишутся.

## Устройства

| Устройство | Репозиторий | Состояние |
|---|---|---|
| Lenovo YOGA Tablet 10 B8000-H (MT6589, armv7) | device-lenovo-b8000h | образы Pertin Haltia v2.x |
| Lenovo Tab P11 TB-J606L (SM6115, aarch64) | — | изыскания: основное ядро без касания, звука и зарядки; загрузчик разблокируется |
