# Репозитории

Реестр репозиториев организации [haltia-de](https://github.com/haltia-de).
Слои — по ADR 0001 и 0004. Локальная папка — клон на ПК сборки в
`/mnt/data/Projects/`; с 21 октября 2026 года путь повторяет адрес на GitHub
(ADR 0005, шаг 6). На старых местах до 4 ноября лежат символьные ссылки.

| Репозиторий | Слой | Что это | Выпускает | Локальная папка | CLAUDE.md / AGENTS.md |
|---|---|---|---|---|---|
| [haltia](https://github.com/haltia-de/haltia) | проект | архитектура, ADR, планы, правила, ключи, диспетчер агентов | — | `haltia-de/haltia` | есть / есть |
| [.github](https://github.com/haltia-de/.github) | проект | профиль организации, знак и бренд (`brand/`) | — | `haltia-de/.github` | есть / есть |
| [shell](https://github.com/haltia-de/shell) | оболочка | панель, домашний экран, «✕», фильтр касаний, клавиатура, поворот, настройки, обновления, тема | apk | `haltia-de/shell` | есть / есть |
| [kit](https://github.com/haltia-de/kit) | библиотека | `haltia_kit`: вопросы, настройки, звук, фото (GTK 3) | apk, deb, Flatpak-модуль | `haltia-de/kit` | есть / есть |
| [files](https://github.com/haltia-de/files) | программа | Файлы и Галерея | apk | `haltia-de/files` | есть / есть |
| [text](https://github.com/haltia-de/text) | программа | блокнот | apk | `haltia-de/text` | есть / есть |
| [calendar](https://github.com/haltia-de/calendar) | программа | настенный календарь | apk | `haltia-de/calendar` | есть / есть |
| [news](https://github.com/haltia-de/news) | программа | новости RSS | apk, deb, Flatpak | `haltia-de/news` | есть / есть |
| [weather](https://github.com/haltia-de/weather) | программа | погода (Gismeteo) | apk, deb, Flatpak | `haltia-de/weather` | есть / есть |
| [video](https://github.com/haltia-de/video) | программа | видео: YouTube и другие источники | apk, deb, Flatpak | `haltia-de/video` | есть / есть |
| [music](https://github.com/haltia-de/music) | программа | музыка: Яндекс Музыка и другие | apk, deb, Flatpak | `haltia-de/music` | есть / есть |
| [messenger](https://github.com/haltia-de/messenger) | программа | мессенджер MAX без браузера | apk, deb, Flatpak | `haltia-de/messenger` | есть / есть |
| [paint](https://github.com/haltia-de/paint) | программа | раскраска по номерам | apk, deb, Flatpak | `haltia-de/paint` | есть / есть |
| [firefox](https://github.com/haltia-de/firefox) | программа | Firefox для сенсорного экрана и слабого железа | apk | `haltia-de/firefox` | есть / есть |
| [camera](https://github.com/haltia-de/camera) | программа | Камера: одна кнопка, снимки для человека и для других программ (`haltia_kit.camera`) | apk | `haltia-de/camera` | — |
| [ci](https://github.com/haltia-de/ci) | упаковка | общий выпуск по тегам: apk, deb, Flatpak (`@v1`) | — | `haltia-de/ci` | есть / есть |
| [packages](https://github.com/haltia-de/packages) | упаковка | репозитории apk, apt и Flatpak на GitHub Pages, метапакеты | репозитории | `haltia-de/packages` | есть / есть |
| [device-lenovo-b8000h](https://github.com/haltia-de/device-lenovo-b8000h) | устройство | Lenovo YOGA Tablet 10 B8000-H: ядро 7.1, драйверы, остров GPU, образы Pertin Haltia | образы, ядро, остров | `haltia-de/device-lenovo-b8000h` | есть / есть |
| [libnice](https://github.com/haltia-de/libnice) | упаковка | libnice 0.1.23 для Alpine armv7 под именем Alpine (в Alpine 0.1.22, а webrtcbin нужен ≥0.1.23); заплата уходит и в aports | apk | `haltia-de/libnice` | — |
| [gst-webrtc](https://github.com/haltia-de/gst-webrtc) | упаковка | `haltia-gst-webrtc`: webrtcbin и libgstwebrtcnice к gst-plugins-bad Alpine, для звонков | apk | `haltia-de/gst-webrtc` | — |
| [libcamera](https://github.com/haltia-de/libcamera) | упаковка | libcamera для Alpine armv7 с заплатами планшета: SENINF MT6589, OV9760, обработка на процессоре | apk | `haltia-de/libcamera` | — |
| paint-android (закрытый) | исследование | Раскраска для Android: исследование и план | — | `haltia-de/paint-android` | есть / нет |

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
