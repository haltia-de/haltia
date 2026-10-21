# Камера: один стек для звонков, фотоаппарата и «снять фото» из программ (21 октября 2026)

Исследование к плану [Микрофон, камера и звонки MAX](../plans/calls.md),
шаг 6 (этап 3 — libcamera с программным ISP) и шаг 8 (видеозвонок).
Факты собраны по исходникам, индексам пакетов и документации; на планшете
ничего не запускалось. Оценки нагрузки на процессор — расчётные, их надо
мерить (см. «Что проверить на планшете»).

## Исходное состояние

- Фронтальный OV9760 даёт кадры через наш V4L2-драйвер `mt6589-seninf`:
  `/dev/video0` (`V4L2_CAP_IO_MC`, медиаграф `/dev/media0`, датчик
  `/dev/v4l-subdev0`), 1280×720 и 640×480, ~30 к/с
  (device-lenovo-b8000h PR #22, `docs/camera-front.md`).
- Формат — упакованный RAW10 MediaTek: 4 пикселя в 5 байтах **сплошным
  потоком битов, младшими вперёд**, fourcc `MBBA`, порядок BGGR. Это не
  CSI-2 packed (`SBGGR10P`/`pBAA`, где 4 старших байта и пятый с младшими
  битами), не IPU3 (25 пикселей в 32 байтах). В uapi ядра его нет —
  определён в драйвере.
- GPU: PowerVR SGX544, GLES **2.0** только через остров Debian (glibc,
  libhybris) и только у композитора (`docs/g4-hybris.md` в device). Для
  musl-программ Alpine аппаратного EGL/GLES нет; Mesa для SGX нет.
- Звук в образе — PulseAudio; PipeWire в образе нет.
- Программы — Python, GTK 3, `haltia_kit`; выпускаются apk, deb и Flatpak и
  должны работать вне планшета (ADR 0004).
- В мессенджере `webrtcbin` уже звонит голосом; исходящий держит
  видеосекцию `inactive` (messenger `docs/calls-protocol.md`).

## 1. Готовые программы камеры

Версии — из `APKINDEX` Alpine v3.24 armv7 (`main`, `community`) и edge
`testing`, скачанных 21 октября 2026
([dl-cdn v3.24 community armv7](https://dl-cdn.alpinelinux.org/alpine/v3.24/community/armv7/)).

| Программа | Набор | Чем берёт кадры | armv7 в 3.24 | Наш `MBBA` | GPU | «Сними и верни файл» |
|---|---|---|---|---|---|---|
| Megapixels 2.1.0 (+ `libmegapixels` 0.2.3, `libdng` 0.2.2) | GTK 4, C | свой стек V4L2 + media-ctl по конфигу устройства, без libcamera | есть | нет | обязателен (OpenGL-дебайер) | нет; после снимка зовёт скрипт `postprocess.sh` |
| Millipixels 0.24.0 (Purism) | GTK 3, C | libcamera 0.7 (`libcamera.so.0.7` в зависимостях) | есть | через libcamera — нет | зависит от `libEGL`/`libGLESv2` | нет |
| Snapshot 50.0 (GNOME Camera, `aperture`) | GTK 4 + libadwaita, Rust | только PipeWire (`pipewiresrc`), в песочнице — портал Camera | есть | через PipeWire/libcamera — нет | GTK 4 без GL падает на программный рендер | нет |
| Kamoso 26.04.2 (KDE) | Qt 6, Kirigami, KF6 | GStreamer | есть | нет | Qt Quick | нет (Purpose — «поделиться», не запрос) |
| Cheese | GTK 3 / GTK 4 | GStreamer | **нет в 3.24** (ни armv7, ни x86_64) | — | — | был `CheeseAvatarWidget` для аватара |
| qcam / `cam` (libcamera 0.7.1) | Qt 6 / CLI | libcamera | есть (`qcam`, `libcamera-tools`) | после доработки libcamera | нет | `cam -C1 -F файл` — инструмент отладки |
| Pinhole и прочие | — | — | в индексе 3.24 нет | — | — | — |

Подробности:

- **Megapixels 2.x.** Устройство описывается конфигом `libmegapixels`
  (libconfig, имя по `compatible`, ищется в `./config`, `/etc/megapixels/config`,
  `/usr/share/megapixels/config`): `BridgeDriver`, `SensorDriver`, режимы с
  командами `Link`/`Mode`/`Rate`/`Crop` над медиаграфом
  ([формат конфига](https://libmegapixels-12f3eb.pages.debian.net/config.html)).
  Таблица форматов `libmegapixels` (`src/mode.c`) знает только Bayer 8,
  `…10P` (CSI-2), 10/12 и 16 бит без упаковки и YUV — **MediaTek-упаковки
  нет** ([mode.c](https://gitlab.com/megapixels-org/libmegapixels/-/blob/master/src/mode.c)).
  Дебайер — шейдеры OpenGL; с GTK 4.17 приложение без GL-контекста не
  работает, 2.1.0 (17 февраля 2026) добавила лишь принудительный
  программный рендер как обход
  ([блог автора](https://blog.brixit.nl/megapixels-2-0-progress/),
  [теги](https://gitlab.com/megapixels-org/Megapixels/-/tags)). На Cortex-A7
  без GPU это llvmpipe/softpipe: и видоискатель, и дебайер на процессоре
  через эмуляцию GL. Вывод: без libcamera Megapixels наш датчик может
  поддержать, только если драйвер отдаст стандартный формат
  (`SBGGR10`/`SBGGR8`/`SBGGR10P`) и мы смиримся с программным GL — **не
  подходит**. Интерфейс тоже не для пожилого.
- **Millipixels** — форк Megapixels под Librem 5 на GTK 3 и libcamera.
  GTK 3 — плюс, но код под одно устройство и тянет EGL/GLES; запускать ли
  его без GPU — не проверено. Как основа своего фотоаппарата — нет; как
  образец кода «libcamera → GTK 3» — да
  ([репозиторий](https://source.puri.sm/Librem5/millipixels)).
- **Snapshot** — эталон «современного» пути: PipeWire + libcamera +
  портал. Вне песочницы ходит в PipeWire напрямую (сокет
  `pipewire-0` обходит разрешения портала,
  [snapshot#17](https://gitlab.gnome.org/GNOME/snapshot/-/issues/17)).
  GTK 4 + libadwaita + Rust на 1 ГБ и без GL — тяжело; годится как проверка
  PipeWire-пути на ПК, не как программа Haltia.
- **Kamoso** — KF6/Kirigami целиком, для планшета слишком тяжёл.
- **postmarketOS**: по умолчанию Megapixels/Millipixels; стек
  libcamera + soft ISP + PipeWire работает на Librem 5 и PinePhone, Snapshot
  ставится поверх; качество и скорость soft ISP там признаны «не там, где
  хотелось бы», нужны файлы настройки датчиков
  ([pmOS: камеры](https://postmarketos.org/edge/2023/03/01/default-camera/),
  [пост Robert Mader](https://fosstodon.org/tags/Megapixels)).

Итог по п. 1: **готовой программы, которая подошла бы пожилому на нашем
железе, нет.** Все живые варианты либо требуют GL, либо GTK 4/Qt, либо не
знают формат. Фотоаппарат пишем сами (GTK 3, Python), опираясь на
libcamera.

## 2. Нижние слои

### libcamera и программный ISP

- В Alpine 3.24 armv7 — **libcamera 0.7.1**: `libcamera`, `libcamera-ipa`,
  `libcamera-gstreamer` (`libcamerasrc`), `libcamera-v4l2` (v4l2-compat,
  `libcamerify`), `libcamera-tools` (`cam`), `qcam`. Пакет `libcamera`
  слинкован с `libEGL`/`libGLESv2`, то есть собран с GPU ISP.
- **GPU ISP** (`DebayerEGL`) — GLES **2.0**, шейдеры `#version 100`, но
  дисплей берётся через `EGL_PLATFORM_SURFACELESS_MESA`, буферы — через
  `eglCreateImageKHR` из dmabuf
  ([серия патчей GPUISP](https://patchwork.libcamera.org/cover/25124/),
  `src/libcamera/egl.cpp`). С 0.6/0.7 это **режим по умолчанию**
  ([патч](https://patchwork.libcamera.org/patch/25677/)). У нас Mesa на
  musl без аппаратного драйвера: surfaceless-дисплей в лучшем случае
  поднимется на программном рендере, в худшем — не поднимется. Android-EGL
  острова не умеет ни surfaceless Mesa, ни импорт dmabuf и живёт в glibc.
  **GPU-путь для нас закрыт; режим надо явно ставить `cpu`**:
  `software_isp: mode: cpu` в `configuration.yaml` (`/etc/libcamera`,
  `/usr/share/libcamera`, `~/.config/libcamera`) или
  `LIBCAMERA_SOFTISP_MODE=cpu` (`src/libcamera/global_configuration.cpp`,
  `software_isp/software_isp.cpp` v0.7.1).
- **CPU ISP** (`DebayerCpu`) умеет на входе только Bayer 8/10/12 **без
  упаковки** и 10-бит **CSI-2 packed**; на выходе RGB888/BGR888/XRGB8888 и
  родню. Внутри: статистика, AGC/AEC, AWB, чёрный уровень, CCM и
  насыщенность (с 0.5), многопоточность (`software_isp: threads`) и копия
  входного буфера в обычную память (`copy_input_buffer`, по умолчанию
  `true` — чтение некэшируемых dma-contig буферов на ARM очень медленное)
  (`software_isp/debayer_cpu.cpp` v0.7.1,
  [libcamera 0.5.0](https://lists.libcamera.org/pipermail/libcamera-devel/2025-April/049672.html)).
- **Simple pipeline handler** ищет медиаустройство по имени драйвера из
  жёсткой таблицы `supportedDevices[]`; файл настройки лишь
  включает/выключает soft ISP для драйверов, уже стоящих в таблице. Нашего
  `mt6589-seninf` там нет. Есть `mtk-seninf` — с конвертером `mtk-mdp` и
  выключенным soft ISP (`pipeline/simple/simple.cpp` v0.7.1).
- **Неизвестный fourcc** simple-обработчик в `PixelFormat` не переведёт —
  камеры просто не будет.
- **Датчик:** для OV9760 нет `CameraSensorHelper` (усиление ↔ код, чёрный
  уровень) — без него soft IPA работает с «сырыми» кодами усиления и
  предупреждением; нет и файла настройки IPA (`ov9760.yaml`) —
  берётся `uncalibrated.yaml`.

**Что нужно, чтобы libcamera увидела камеру** (по нарастанию работы):

| Путь | Где | Объём | Минусы |
|---|---|---|---|
| А. Драйвер отдаёт **неупакованный** `SBGGR10` (2 байта на пиксель) или `SBGGR8`, если pass 1 MT6589 это умеет (выключить `PAK`/`PAK2`, иной режим IMGO) | ядро | дни, если регистр найдётся | вдвое больше трафика DMA (1280×720×2×30 = 55 МБ/с — терпимо); возможность не проверена |
| Б. Своя «упаковка» в libcamera: `Packing::MTISP` в `bayer_format.cpp`, `formats.yaml`, `debayer10M_*` и разбор в `swstats_cpu.cpp` | libcamera (заплата в нашем apk) | 3–5 дней | заплата живёт у нас: `MBBA` нет в uapi, вверх её не примут, пока нет драйвера в основном ядре |
| В. Драйвер переименовать в `mtk-seninf`, чтобы попасть в таблицу без заплаты, и включить soft ISP через `configuration.yaml` | ядро | час | обман: так зовётся другой драйвер с конвертером `mtk-mdp`; хрупко |
| Г. Строка `{ "mt6589-seninf", {}, true }` в `supportedDevices[]` | libcamera | час | заплата; вверх — вместе с драйвером |

Рекомендация: **А + Г** (или Б + Г, если А невозможно), плюс
`CameraSensorHelperOv9760` и `ov9760.yaml` — всё одной заплатой в своём
пакете libcamera для Alpine (как уже сделано для `libnice` и
`gst-webrtc`).

**Нагрузка на Cortex-A7 (оценка, мерить встроенным бенчмарком
`DebayerCpu`, [документ](https://git.nekocwd.duckdns.org/Mirror/libcamera/src/branch/master/Documentation/software-isp-benchmarking.rst)).**
Дебайер с CCM — порядка 10–20 тактов на пиксель на A7 1,2 ГГц без NEON:
640×480 × 15 к/с ≈ 4,6 Мпикс/с ≈ 50–90 МГц — **5–8% одного ядра**;
1280×720 × 30 к/с ≈ 28 Мпикс/с ≈ 300–550 МГц — **четверть–половина ядра**.
Плюс копия входного буфера. Видеозвонок цели плана (640×480, 15 к/с)
укладывается; основная цена звонка — VP8 (~80% всех ядер по плану), а не
ISP. Для фото хватит одного кадра 1280×720.

### PipeWire

- В Alpine 3.24 armv7 — **PipeWire 1.6.8**, `wireplumber` 0.5.15,
  `gst-plugin-pipewire` (`pipewiresrc`). `pipewire-libs` слинкован с
  `libcamera.so.0.7` — SPA-модуль libcamera внутри.
- PipeWire можно поднять **только для видео**, оставив PulseAudio звуку
  (в WirePlumber выключить ALSA/bluez-мониторы). Цена — два постоянных
  процесса (оценка: 10–20 МБ RSS вместе, WirePlumber с Lua).
- Плюсы: **несколько потребителей одной камеры** (видоискатель звонка и
  запись одновременно), камера в Firefox через PipeWire, портал для
  Flatpak, простой значок «камера включена» (узел в состоянии `running`).
  Без PipeWire libcamera отдаёт камеру одному процессу (`Camera::acquire`
  исключителен).

### Портал Camera (`org.freedesktop.portal.Camera`)

- Реализован **во фронтенде** `xdg-desktop-portal` (1.21.2 в 3.24), не в
  бэкенде: `AccessCamera()` → `OpenPipeWireRemote()` даёт fd PipeWire, где
  видны только узлы камер
  ([документация](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Camera.html)).
- Диалог разрешения — через бэкенд `Access` (`impl.portal.Access`): его
  дают `xdg-desktop-portal-gtk` (GTK 3, есть в 3.24), `-gnome`, `-kde`,
  `-phosh`. GNOME не нужен.
- **Программам без песочницы доступ даётся автоматически**
  (`app_id_from_app_info()` → `""` для host-приложений,
  [camera.c](https://github.com/flatpak/xdg-desktop-portal/blob/1.20.0/src/camera.c)).
  Портал нужен только Flatpak-сборкам; ему нужен PipeWire.
- Клиенты: libportal `xdp_portal_open_pipewire_remote_for_camera`, далее
  `pipewiresrc fd=…` ([libportal](https://valadoc.org/libportal/Xdp.Portal.open_pipewire_remote_for_camera.html),
  [MR pipewire#1475](https://gitlab.freedesktop.org/pipewire/pipewire/-/merge_requests/1475));
  так делают WebRTC/Chromium и Firefox
  ([camera_portal.cc](https://webrtc.googlesource.com/src/+/main/modules/video_capture/linux/camera_portal.cc)).

### Как кадры попадут в GStreamer мессенджера

| Источник | Пакет | Когда | Замечания |
|---|---|---|---|
| `libcamerasrc` | `libcamera-gstreamer` | планшет без PipeWire | один процесс на камеру; простейший путь |
| `pipewiresrc` | `gst-plugin-pipewire` | планшет с PipeWire; Flatpak и ПК с GNOME/KDE (через портал) | делится между процессами |
| `v4l2src` | `gst-plugins-good` | веб-камеры USB на ПК | наш `/dev/video0` напрямую не годится: `MBBA` GStreamer не знает, нужен `media-ctl`, нет AWB/AE |
| `v4l2src` под `libcamerify` | `libcamera-v4l2` | старые программы, знающие только V4L2 | LD_PRELOAD; запасной путь |
| `v4l2src ! bayer2rgb` | `gst-plugins-bad` | обход libcamera | `bayer2rgb` понимает Bayer 8–16 бит LE/BE ([документация](https://gstreamer.freedesktop.org/documentation/bayer/bayer2rgb.html)), но не `MBBA` и без AWB/AE |

Дальше в мессенджере: `… ! videoconvert ! videoscale !
video/x-raw,width=640,height=480,framerate=15/1 ! tee`, ветка в
`vp8enc deadline=1 cpu-used=…` → `webrtcbin`, ветка в своё окошко.
Выбор источника — по порядку: `pipewiresrc` (через портал в песочнице),
`libcamerasrc`, `v4l2src`/`autovideosrc`.

## 3. «Сними фото и верни файл» между программами

**Стандарта в Linux нет.** Аналога Android `ACTION_IMAGE_CAPTURE` нет ни
во freedesktop, ни среди порталов: портал Camera даёт поток, а не снимок;
похожий по смыслу портал `Screenshot` возвращает URI файла, но для экрана.
Поиск по трекеру и рассылкам предложения «Camera.TakePhoto» не нашёл (не
исключено, что обсуждение есть, но решения нет).

Как делают другие:
- GNOME Settings («Взять фото» для аватара) — встроенный виджет; раньше
  `CheeseAvatarWidget` из libcheese ([API](https://developer-old.gnome.org/cheese/stable/CheeseAvatarWidget.html)),
  т.е. **виджет в процессе**, не межпрограммный вызов.
- KDE — Kamoso «делится» снимками через Purpose; запроса снимка из другой
  программы нет.
- Phosh/Megapixels — только скрипт-постобработчик после снимка.

Варианты для Haltia:

| Вариант | Как | Плюсы | Минусы |
|---|---|---|---|
| **К. Виджет в `haltia_kit`** (`haltia_kit.camera`: `Viewfinder` и диалог `take_photo(parent, on_done)`) | GStreamer в процессе программы, источник по порядку выше, `gdkpixbufsink`/`appsink` в `Gtk.Image`/`DrawingArea` GTK 3, снимок → JPEG в XDG Pictures | без IPC; работает в apk, deb и Flatpak (через портал); один интерфейс для всех программ; тот же виджет — в фотоаппарате и в окне звонка | каждая программа тащит GStreamer+libcamera (оценка: +15–25 МБ на время съёмки); без PipeWire — один владелец камеры за раз |
| **D. Служба D-Bus** `org.haltia.Camera1.Capture(parent_window, options) → (fd, mime)` у программы «Камера», активируемая D-Bus | одно окно фотоаппарата, программа получает файл | лёгкие клиенты; единое окно; возврат через **fd** проходит и в песочницу Flatpak (`--talk-name=org.haltia.Camera1`) | своя спецификация, своя служба; путь к файлу в песочнице не виден — только fd или document portal; вне Haltia службы нет — нужен запасной путь |
| **C. Режим CLI** `haltia-camera --capture-for <app>` печатает путь | `subprocess` | проще всего | не работает из Flatpak (`flatpak-spawn --host` — это побег из песочницы); выход через stdout хрупок |

## 4. Рекомендуемая архитектура

```
 устройство: ov9760 + mt6589-seninf (/dev/media0, /dev/video0)
     │  формат: неупакованный SBGGR10 (или MBBA + заплата libcamera)
     ▼
 libcamera 0.7 (наш apk: таблица simple, Ov9760 helper, ov9760.yaml,
                configuration.yaml: software_isp mode=cpu)
     │
     ├── этап 1: libcamerasrc прямо в программе
     └── этап 2: PipeWire + WirePlumber только для видео
                 (общий доступ, портал для Flatpak, Firefox, значок)
     ▼
 haltia_kit.camera (GTK 3): Viewfinder, take_photo(), выбор источника
     │                         pipewiresrc → libcamerasrc → v4l2src
     ├── Камера (новая программа, haltia-de/camera): большая кнопка,
     │   снимок в «Изображения/Камера», показ через photos.Viewer
     ├── Сообщения: своё видео в окне звонка, ветка tee → vp8enc → webrtcbin
     └── Раскраска и другие: take_photo() → путь к JPEG → своя обработка
```

Шаги:

1. **Устройство (живой сеанс, планшет).** Выяснить, отдаёт ли pass 1
   MT6589 неупакованный RAW10 или RAW8; если да — сменить формат драйвера
   на `SBGGR10`/`SBGGR8`. Иначе — оставить `MBBA`.
2. **Пакет libcamera** (новый репозиторий упаковки, как `libnice`):
   заплаты — строка `mt6589-seninf` в таблице simple; при `MBBA` —
   упаковка MTISP в дебайере и статистике; `CameraSensorHelperOv9760`;
   `ov9760.yaml`; `configuration.yaml` с `mode: cpu`. Проверка — `cam -l`,
   `cam -c1 -C30 -F` и встроенный бенчмарк.
3. **`haltia_kit.camera`**: `Viewfinder`, `take_photo()`, выбор источника,
   тесты на `videotestsrc`. Работает и на ПК (веб-камера через PipeWire или
   V4L2).
4. **Программа «Камера»**: одна большая кнопка, переключения нет (камера
   одна), снимок сразу виден, «Сохранить/Ещё раз»; файлы — в XDG Pictures.
5. **Мессенджер, шаг 8 плана**: источник из `haltia_kit.camera` или своя
   функция с тем же порядком выбора; своё видео на экране звонка.
6. **PipeWire (позже, по нужде)**: видео-только конфигурация WirePlumber в
   образе, значок камеры в оболочке по состоянию узла. До него значок
   можно брать из `runtime_status` датчика в sysfs — это и есть настоящее
   питание камеры (решение плана «вне звонка питание камеры выключено»).
7. **Служба `org.haltia.Camera1` (позже, по нужде)** — если окажется, что
   Flatpak-программам или памяти мешает вариант К; `take_photo()` в kit тогда
   сначала пробует службу, потом — свой диалог.

### Альтернативы

- **Сразу PipeWire.** Один путь для планшета, Flatpak и ПК, общий доступ;
  но +2 службы на 1 ГБ и настройка WirePlumber рядом с PulseAudio. Разумно,
  если в ближайшее время нужен Firefox с камерой или одновременная работа
  двух программ.
- **Без libcamera:** `v4l2src` + `bayer2rgb` + своя AE/AWB в Python или
  маленьком C-элементе. Меньше зависимостей, но свой ISP, нет поддержки
  портала и PipeWire, никакие сторонние программы камеру не увидят.
  Не рекомендуется (противоречит ADR 0004: камера — общая возможность).
- **Megapixels/Millipixels как фотоаппарат** — отвергнуто (п. 1).

### Оценка работ (один исполнитель)

| Работа | Дней |
|---|---|
| 1. Формат в драйвере (разведка регистра + правка) | 1–3 |
| 2. Пакет libcamera с заплатами (+3–5, если `MBBA`) | 2–4 |
| 2а. Настройка `ov9760.yaml` (чёрный уровень, CCM) | 2–4 |
| 3. `haltia_kit.camera` с тестами | 4–6 |
| 4. Программа «Камера» с упаковкой apk/deb/Flatpak | 3–5 |
| 5. Видео в мессенджере (часть шага 8) | 3–5 |
| 6. PipeWire только для видео + значок | 3–5 |
| 7. Служба D-Bus | 2–3 |

Без 6 и 7 — **3–4 недели**; со всем — 5–6 недель. Работы 1, 2, 2а —
`needs:tablet`.

## Что проверить на планшете

- Умеет ли IMGO писать неупакованный RAW10/RAW8 (регистры `PAK`/`PAK2`,
  формат IMGO в pass 1).
- Время `DebayerCpu` на кадр при 640×480 и 1280×720, 1–4 потока, с
  копией входа и без.
- Кэшируемы ли буферы `vb2-dma-contig` в пространстве пользователя
  (от этого зависит `copy_input_buffer`).
- Память процесса с `libcamerasrc` + `vp8enc` при звонке.
- Не поднимает ли `DebayerEGL` программный рендер Mesa без `mode: cpu`.

## Открытые решения для автора

1. Формат драйвера: неупакованный RAW (если железо умеет) против заплаты
   `MBBA` в libcamera.
2. PipeWire для видео: сразу или только когда понадобится общий доступ,
   Firefox или Flatpak.
3. «Снять фото» из программ: виджет в `haltia_kit` (рекомендуется для
   начала) или служба D-Bus у программы «Камера».
4. Новый репозиторий `camera` (программа) и репозиторий упаковки
   `libcamera` — завести ли.
5. Задняя камера A5142 — в этом стеке позже или не нужна.

## Источники

- device-lenovo-b8000h: `docs/camera-front.md`, PR #22, `docs/g4-hybris.md`.
- Alpine v3.24 armv7 `APKINDEX` (main, community), edge testing:
  <https://dl-cdn.alpinelinux.org/alpine/v3.24/>.
- libcamera v0.7.1:
  [`debayer_cpu.cpp`](https://github.com/libcamera-org/libcamera/blob/v0.7.1/src/libcamera/software_isp/debayer_cpu.cpp),
  [`software_isp.cpp`](https://github.com/libcamera-org/libcamera/blob/v0.7.1/src/libcamera/software_isp/software_isp.cpp),
  [`simple.cpp`](https://github.com/libcamera-org/libcamera/blob/v0.7.1/src/libcamera/pipeline/simple/simple.cpp),
  [`bayer_format.cpp`](https://github.com/libcamera-org/libcamera/blob/v0.7.1/src/libcamera/bayer_format.cpp),
  [`global_configuration.cpp`](https://github.com/libcamera-org/libcamera/blob/v0.7.1/src/libcamera/global_configuration.cpp),
  [`egl.cpp`](https://github.com/libcamera-org/libcamera/blob/v0.7.1/src/libcamera/egl.cpp),
  [`camera_sensor_helper.cpp`](https://github.com/libcamera-org/libcamera/blob/v0.7.1/src/ipa/libipa/camera_sensor_helper.cpp);
  [GPUISP GLES 2.0](https://patchwork.libcamera.org/cover/25124/),
  [GPU по умолчанию](https://patchwork.libcamera.org/patch/25677/),
  [бенчмарк soft ISP](https://git.nekocwd.duckdns.org/Mirror/libcamera/src/branch/master/Documentation/software-isp-benchmarking.rst).
- Megapixels: [libmegapixels config](https://libmegapixels-12f3eb.pages.debian.net/config.html),
  [mode.c](https://gitlab.com/megapixels-org/libmegapixels/-/blob/master/src/mode.c),
  [Megapixels 2.0 progress](https://blog.brixit.nl/megapixels-2-0-progress/),
  [теги](https://gitlab.com/megapixels-org/Megapixels/-/tags).
- [Millipixels](https://source.puri.sm/Librem5/millipixels);
  [Snapshot #17](https://gitlab.gnome.org/GNOME/snapshot/-/issues/17);
  [postmarketOS: камеры по умолчанию](https://postmarketos.org/edge/2023/03/01/default-camera/).
- xdg-desktop-portal:
  [Camera](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Camera.html),
  [`camera.c` 1.20.0](https://github.com/flatpak/xdg-desktop-portal/blob/1.20.0/src/camera.c),
  [Access-портал](https://whynothugo.nl/journal/2023/06/20/understanding-the-xdg-access-portal/),
  [libportal](https://valadoc.org/libportal/Xdp.Portal.open_pipewire_remote_for_camera.html),
  [WebRTC camera_portal.cc](https://webrtc.googlesource.com/src/+/main/modules/video_capture/linux/camera_portal.cc).
- GStreamer: [`bayer2rgb`](https://gstreamer.freedesktop.org/documentation/bayer/bayer2rgb.html).
- [CheeseAvatarWidget](https://developer-old.gnome.org/cheese/stable/CheeseAvatarWidget.html).
