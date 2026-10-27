# Как ещё ускорить программы на Python и GTK 3

Исследование от 26 октября 2026 года. Это записка с предложениями для
последующей проверки на планшете, а не ADR и не разрешение менять программы.
Изменения кода, задачи и выпуски в рамках исследования не создавались;
планшет не использовался.

## Вывод

Самые дешёвые и, вероятно, самые заметные выигрыши лежат не в отрисовке,
а в запуске и в том, что программа делает в первые секунды:

1. **Байт-код.** Образ B8000-H не ставит подпакеты `-pyc` программ Haltia
   и kit, а основной код многих программ лежит в исполняемом файле в
   `/usr/bin`, который Python не кэширует никогда. Каждый запуск заново
   компилирует сотни килобайт исходника (у «Сообщений» — 363 КБ в одном
   файле). Это проверяемый факт об упаковке; цена на Cortex-A7 — оценка,
   которую надо замерить.
2. **Один долгоживущий процесс вместо холодного старта.** Импорт `Gtk` в
   PyGObject уже включает `Gtk.init` (соединение с композитором, настройки,
   разбор темы Adwaita ~172 КБ CSS). Это постоянная цена каждого процесса;
   её не убрать оптимизацией кода, только не платить повторно
   (`Gtk.Application` с удержанием процесса, как уже сделано у «Сообщений»
   и у выбора файлов).
3. **Анимации GTK включены.** Ни тема, ни переопределение схем Haltia не
   выключают `org.gnome.desktop.interface enable-animations`, а GTK 3 на
   Wayland берёт `gtk-enable-animations` именно оттуда. В Adwaita для GTK 3
   46 переходов CSS; каждый — несколько кадров программной отрисовки.
4. **Главный поток.** Синхронные сеть, файлы и подпроцессы в обработчиках
   GTK и построение сотен строк списка за один проход дают «замирание»,
   которое человек воспринимает как медлительность; конкретные места —
   в разделе «Что найдено в коде».

GTK 4 на этом устройстве исключён (нет GLES 3.0), поэтому всё ниже — о GTK 3
3.24 с программной отрисовкой cairo/pixman в `wl_shm`.

## Метод и границы достоверности

- **Оценки доказательности:**
  - **[A] проверено по первоисточнику** — исходник или документация
    upstream, APKBUILD Alpine, файлы Haltia;
  - **[B] следует из первоисточника** — вывод из проверенного поведения,
    но эффект на B8000-H не измерен;
  - **[C] гипотеза** — правдоподобно, нужен замер до любых изменений;
  - **[—] первичного источника не найдено** — упомянуто только чтобы
    сказать, что опоры нет.
- Исходники закреплены: GTK `gtk-3-24` на
  `0f3aa454a2a14b68e2753f63bedb2c74bd45b54b`, PyGObject тег `3.56.3`
  (`fce190c5adc78a54dc9d05165ce879a1d9894eb3`), aports `3.24-stable` на
  `b02712468d0921412896c3c355582785339feaed`, at-spi2-core `main` на
  `98a724896fc75f1299dcaea8aab8f2cd8f121b4c`, gdk-pixbuf тег `2.44.7`.
  Документация CPython — ветка 3.14 (в Alpine 3.24 Python 3.14.8).
- Локальные снимки Haltia: shell `c8166ff`, kit `e6e7d66` (ветка
  `front-camera-turn`, не `main`), messenger `34ce0ed`
  (`feature/video-calls`), video `d415b7c` (`feat/shared-core-web`),
  mail `0f75b61`, music `525405b`, news `2775080`, weather `205764b`,
  text `290bc1d`, calendar `1d2c4b6`, camera `b36f6ce`, files `96e4673`,
  paint `9cc3202`. Ветки разработки не доказывают состояние выпуска.
- Единственные числа, измеренные в этом исследовании, получены на рабочей
  машине (Intel i5-4570, Python 3.12) и показывают порядок величин, а не
  время на планшете. Известные числа планшета взяты из документов проекта:
  выбор файлов — холодный старт ~3,5 с, тёплый ~1 с; Python-версия
  `haltia-ask` — 2,3 с против 0,3 с у fuzzel; помощники после панели —
  1–3 с каждый после загрузки; Firefox с одной страницей ~550 МБ.
- Профилировщики, удобные на x86-64, на этом устройстве частично
  недоступны: perf-трамплин CPython собирается только для
  `x86_64-linux-gnu` и `aarch64-linux-gnu`
  ([configure.ac](https://github.com/python/cpython/blob/v3.14.0/configure.ac#L3699-L3701)),
  а `py-spy` в Alpine 3.24 собран только для aarch64, x86_64 и ppc64le
  ([APKBUILD](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/community/py-spy/APKBUILD)).
  Остаются `-X importtime`, `cProfile`, `perf` (пакет `linux-tools`, все
  архитектуры) для нативной части, `strace` и `sysprof` (оба `arch="all"`).
- `GDK_DEBUG` и почти все ключи `GTK_DEBUG` на Alpine не работают: GTK
  собран `abuild-meson` с `--buildtype=plain`, где `debug=false`, а без
  `G_ENABLE_DEBUG` GTK оставляет только `GTK_DEBUG=interactive`
  (инспектор) и пишет предупреждение об остальном
  ([abuild-meson](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/main/meson/abuild-meson#L60),
  [meson.build GTK](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/meson.build#L62-L71),
  [gtkmain.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/gtkmain.c#L658-L669),
  [gdk.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gdk/gdk.c#L304-L316)). [A]

## От чего отталкивается Haltia

Платформа: Cortex-A7 (4 ядра), ~995 МБ RAM, ~180 МБ занято в покое, zram
512 МБ lz4 с `swappiness` 100 и `page-cluster` 0, earlyoom (меньше 10 %
доступной памяти и меньше 20 % свободного swap). GPU есть только у phoc
через libhybris; программы рисуют cairo/pixman на CPU в `wl_shm`
([AGENTS.md устройства](https://github.com/haltia-de/device-lenovo-b8000h/blob/main/AGENTS.md),
[b8k-zram](https://github.com/haltia-de/device-lenovo-b8000h/blob/main/linux-port/rootfs/b8k-zram)).

Сборки Alpine 3.24, от которых зависит скорость:

| Пакет | Версия | Что важно | Источник |
|---|---|---|---|
| python3 | 3.14.8 | `--enable-optimizations` (PGO) и `--with-lto`, `-O2`, computed gotos; `.pyc` стандартной библиотеки — в подпакете `python3-pyc`, ставится по `install_if` | [APKBUILD](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/main/python3/APKBUILD#L139-L182) [A] |
| py3-gobject3 | 3.56.3 | подпакет `-pyc`; импорт `Gtk` вызывает `Gtk.init_check` | [APKBUILD](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/community/py3-gobject3/APKBUILD), [Gtk.py](https://gitlab.gnome.org/GNOME/pygobject/-/blob/3.56.3/gi/overrides/Gtk.py#L1887-L1893) [A] |
| gtk+3.0 | 3.24.52 | `-O2`, LTO, без `G_ENABLE_DEBUG`; триггер `gtk-update-icon-cache` на `/usr/share/icons/*` | [APKBUILD](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/main/gtk+3.0/APKBUILD) [A] |
| gdk-pixbuf | 2.44.7 | встроенные загрузчики PNG, JPEG, GIF, TIFF выключены, включён glycin: декодирование идёт в отдельных процессах-загрузчиках (в bwrap, если он доступен) | [APKBUILD](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/main/gdk-pixbuf/APKBUILD#L42-L55), [meson.build](https://gitlab.gnome.org/GNOME/gdk-pixbuf/-/blob/2.44.7/gdk-pixbuf/meson.build#L217-L240) [A] |

Python в Alpine уже собран с PGO и LTO, и это 3.14, а не 3.10: выигрыш
«Faster CPython» 3.11+ уже получен, и пересборка интерпретатора ничего
очевидного не обещает. [A]

Проект уже сделал важные шаги: `haltia-ask` заменён на fuzzel, kit
декодирует картинки Pillow в отдельном процессе с ограничением памяти и
масштабированием JPEG при декодировании (`draft`), обход glycin
описан в Видео, Настройки строят страницы лениво и не блокируют поток GTK
(`background()`), «Сообщения» держат процесс в фоне
([pictures.py](https://github.com/haltia-de/kit/blob/e6e7d66f490100b9e27aff1cc68954c68a8bc191/haltia_kit/pictures.py#L1-L22),
[AGENTS.md Видео](https://github.com/haltia-de/video/blob/d415b7c/AGENTS.md),
[AGENTS.md оболочки](https://github.com/haltia-de/shell/blob/c8166ff/AGENTS.md)).

## 1. Запуск

### 1.1. Байт-код: что компилируется при каждом запуске

Документация CPython: модуль, запущенный прямо из командной строки,
«всегда перекомпилируется, и результат не сохраняется»; `.pyc` ускоряет
только загрузку, не выполнение. `-O` убирает `assert`, `-OO` ещё и
docstring'и; это уменьшает `.pyc`, а не ускоряет код
([Compiled Python files](https://docs.python.org/3.14/tutorial/modules.html#compiled-python-files)). [A]

Что из этого следует для Haltia:

- `update-lock.sh` устройства сознательно не берёт подпакеты `-pyc`
  («they only save the first start»)
  ([update-lock.sh](https://github.com/haltia-de/device-lenovo-b8000h/blob/main/linux-port/apps/update-lock.sh#L10-L11),
  [строка 42](https://github.com/haltia-de/device-lenovo-b8000h/blob/main/linux-port/apps/update-lock.sh#L42)).
  Это верно только если процесс может записать `__pycache__`. Код
  программ и kit ставится root'ом в `/usr/lib/...`, а запускает их
  пользователь сеанса, который туда писать не может; тогда кэш не
  создаётся никогда, и компиляция повторяется при каждом запуске.
  Нужно проверить на планшете (`ls /usr/lib/python3.14/site-packages/haltia_kit/__pycache__`,
  `ls /usr/lib/haltia-files/*/__pycache__`). [B]
- Основной код многих программ лежит в исполняемом файле без `.py`,
  который Python не кэширует в любом случае: `haltia-messenger` — 8075
  строк (363 КБ), `haltia-settings` — 2850 строк (121 КБ), `haltia-mail`
  — 42 КБ, `haltia-files` — 21 КБ. На рабочей машине одна компиляция
  занимает соответственно ~91, ~31, ~11 и ~6 мс. Cortex-A7 медленнее в
  разы (порядок 10×, не замерено), то есть для «Сообщений» это может быть
  порядка секунды на каждый холодный запуск. [A] факт, [C] величина.
- Колесо PyMax «Сообщений» распаковывается в `/usr/lib/haltia-messenger`
  `unzip`'ом без компиляции
  ([install.sh](https://github.com/haltia-de/messenger/blob/34ce0ed/install.sh#L38-L41)). [A]

**Что сделать.** (а) Перенести тело программ в модуль пакета, оставив в
`/usr/bin` три строки (`from haltia_x.app import main; main()`);
(б) компилировать при сборке пакета (`python3 -m compileall -q -j0` по
каталогу программы в `package()` либо `default_pyc`, как у kit) и
**не** выбрасывать `-pyc` в `update-lock.sh`. `-OO` не нужен: выигрыш —
только размер, а docstring'и бывают нужны. `PYTHONDONTWRITEBYTECODE`
трогать незачем: при нехватке прав записи Python и так молча работает
без кэша.
**Эффект:** минус время компиляции на каждый старт; для крупных
программ, вероятно, сотни миллисекунд. **Цена:** небольшая правка
упаковки и одноразовый перенос кода в модуль. **Замер:**
`python3 -X importtime /usr/bin/haltia-messenger --help 2>&1 | tail`,
и до/после — `time python3 -c 'compile(open("/usr/bin/haltia-messenger").read(), "m", "exec")'`.

### 1.2. Импорт и ленивые импорты

`python3 -X importtime` печатает собственное и накопленное время каждого
импорта; в 3.14 `-X importtime=2` показывает и уже загруженные модули
([What's New 3.14](https://docs.python.org/3.14/whatsnew/3.14.html)). [A]
Синтаксис `lazy import` (PEP 810) принят в 3.15, в 3.14 его нет
([PEP 810](https://peps.python.org/pep-0810/)); до тех пор ленивость —
это импорт внутри функции или `importlib.util.LazyLoader`. [A]

На рабочей машине импорт `gi` + `Gtk 3` занимает ~96 мс, из них ~71 мс —
собственное время `gi.repository.Gtk`, а первое окно с кнопкой — ещё ~82
мс. Собственное время `Gtk` так велико потому, что override PyGObject при
импорте вызывает `Gtk.init_check(sys.argv)` (соединение с дисплеем,
`GtkSettings`, тема); это поведение по умолчанию (`legacy_autoinit`)
([Gtk.py](https://gitlab.gnome.org/GNOME/pygobject/-/blob/3.56.3/gi/overrides/Gtk.py#L1887-L1893),
[gi/__init__.py](https://gitlab.gnome.org/GNOME/pygobject/-/blob/3.56.3/gi/__init__.py#L62-L65)).
Сам `gi` тянет `pkgutil`, `typing`, `re`, `socket` (~26 мс). [A] факт,
[C] перенос на планшет.

**Что сделать.** Импортировать тяжёлое (aiohttp, pydantic, PIL, Gst,
NM, Secret, mpv, Telethon, PyMax) не на верхнем уровне, а в функции,
которая впервые нужна, и после показа первого окна. Окно показывать с
заглушкой содержимого и наполнять через `GLib.idle_add`. **Эффект:** время
до первого кадра падает на сумму отложенных импортов. **Цена:** низкая,
но требует дисциплины (тесты должны импортировать модули явно).
**Замер:** `python3 -X importtime -c 'import haltia_x.app' 2>&1 | sort -t'|' -k2 -n | tail -20`.

### 1.3. Тёплый старт вместо холодного

`GApplication` с идентификатором — единственный экземпляр в сеансе;
второй запуск становится «удалённым» и передаёт `activate` первому;
счётчик `hold()`/`release()` держит процесс без окон; свойство
`inactivity-timeout` задаёт, сколько жить после простоя
([GApplication](https://docs.gtk.org/gio/class.Application.html)). [A]
Это единственный способ не платить повторно за `Gtk.init`, разбор темы,
импорты и прогрев кэшей. Проект уже это использует: «Сообщения» с
`--background`, бэкенд выбора файлов живёт 5 минут (холодный старт ~3,5 с
против ~1 с тёплого — та же разница).

**Что сделать.** Для часто открываемых программ (Настройки, Файлы,
Почта, Погода) — `hold()` после закрытия окна с
`inactivity-timeout` порядка минут, окно не уничтожать, а прятать и
сбрасывать в начальное состояние. **Эффект:** повторное открытие ~1 с
вместо нескольких. **Цена:** память: каждый живой процесс PyGObject+GTK 3
— десятки МБ PSS (оценка проекта: стоянка выбора файлов ~40 МБ, заглушка
портала ~20 МБ), а у устройства ~800 МБ на всё. Держать в фоне стоит
одну-две программы, которые открывают чаще всего, с таймаутом и
уходом при нехватке памяти. **Замер:** время от касания до кадра
(`haltia-launch` уже знает момент появления окна), PSS через
`grep Pss /proc/PID/smaps_rollup`.

### 1.4. Окружение и системные кэши

| Что | Факт | Оценка | Что проверить на планшете |
|---|---|---|---|
| Мост доступности | at-spi2-core не загружает мост, если `NO_AT_BRIDGE=1` ([bridge.c](https://gitlab.gnome.org/GNOME/at-spi2-core/-/blob/98a724896fc75f1299dcaea8aab8f2cd8f121b4c/atk-adaptor/bridge.c#L1017-L1028)); `haltia-launcher` экспортирует его и передаёт D-Bus-активации ([haltia-launcher](https://github.com/haltia-de/shell/blob/c8166ff/bin/haltia-launcher#L28)) | [A] уже сделано | процессы, запущенные не из сеанса (SSH, службы), его не имеют |
| Кэш иконок | GTK отображает `icon-theme.cache` через `mmap`, но игнорирует его, если он старше каталога темы, и тогда сканирует каталоги ([gtkiconcache.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/gtkiconcache.c#L82-L135)); apk обновляет кэш триггером, `install.sh` — нет | [A] | `stat -c %Y /usr/share/icons/hicolor /usr/share/icons/hicolor/icon-theme.cache` |
| Тема | Haltia — 5 КБ своего CSS поверх `@import` Adwaita из ресурса libgtk: 2055 строк, ~172 КБ, разбирается в каждом процессе при `Gtk.init` ([gtk-contained.css](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/theme/Adwaita/gtk-contained.css)) | [A] размер, [C] доля во времени | сравнить время `Gtk.init` с `GTK_THEME=Haltia` и с минимальной темой |
| GIO-модули | `GIO_USE_VFS=local` убирает лишний D-Bus у `GFile` ([GIO overview](https://docs.gtk.org/gio/overview.html)) | [B] эффект только при наличии gvfs | `ls /usr/lib/gio/modules` |
| Отладочные переменные | `G_MESSAGES_DEBUG=all` и обработчики логов стоят времени; в рабочем сеансе их быть не должно | [B] | `tr '\0' '\n' </proc/PID/environ` |

## 2. Отрисовка и главный цикл

### 2.1. Как GTK 3 рисует на Wayland без GPU

GTK 3 рисует только испорченную область окна в «staging»-буфер
`wl_shm` и сообщает композитору повреждённые прямоугольники
`wl_surface_damage`. Пока композитор держит предыдущий буфер, GTK
заводит новый и **дорисовывает в него неизменённые части копией прошлого
кадра**
([gdkwindow-wayland.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gdk/wayland/gdkwindow-wayland.c#L1085-L1127),
[там же](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gdk/wayland/gdkwindow-wayland.c#L755-L767)). [A]
Отсюда: стоимость кадра пропорциональна площади, которую программа
испортила, плюс копия остального. Мигающий курсор, спиннер, часы с
секундами или переход CSS на крупном виджете рисуют снова и снова.

`GtkWindow` сам выставляет непрозрачную область
(`gdk_window_set_opaque_region`), если фон окна в CSS непрозрачен, окно
не `app_paintable` и его `opacity` равна 1
([gtkwindow.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/gtkwindow.c#L7336-L7380)). [A]
Полупрозрачный фон окна или `set_opacity` лишают композитор этой
подсказки. Прозрачность виджета (`set_opacity`, CSS `opacity`)
заставляет GTK рисовать его через промежуточную группу
([gtkwidget.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/gtkwidget.c#L16098-L16102)). [A]

### 2.2. Анимации

`gtk-enable-animations` отключает: переходы и анимации CSS
([gtkcsswidgetnode.c:264](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/gtkcsswidgetnode.c#L264)),
переходы `GtkStack` и `GtkRevealer`, анимацию `GtkSwitch`, `GtkPopover`,
плавную прокрутку `GtkScrolledWindow` и анимации `GtkTreeView`
([gtkstack.c:1017](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/gtkstack.c#L1017),
[gtkrevealer.c:613](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/gtkrevealer.c#L613),
[gtkscrolledwindow.c:4230](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/gtkscrolledwindow.c#L4230-L4237)). [A]
На Wayland GTK 3 берёт это значение из GSettings
`org.gnome.desktop.interface enable-animations` (по умолчанию `true`),
как и `cursor-blink` и `overlay-scrolling`
([gdkscreen-wayland.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gdk/wayland/gdkscreen-wayland.c#L526-L538)). [A]
В Adwaita для GTK 3: 46 `transition`, 283 `box-shadow`, 144
`text-shadow`, 142 `-gtk-icon-shadow`, 113 `border-radius`. [A] подсчёт.
Переопределение схем Haltia задаёт `gtk-theme`, но не `enable-animations`
([haltia-shell.gschema.override](https://github.com/haltia-de/shell/blob/c8166ff/share/haltia-shell.gschema.override)). [A]

**Что сделать.** Добавить в `91-haltia-shell.gschema.override`
`enable-animations=false` (и, возможно, `cursor-blink-timeout` короче) в
`[org.gnome.desktop.interface]`; переходы `Gtk.Stack` программ ставить
`NONE` или полагаться на эту настройку. **Эффект:** нажатие кнопки, смена
страницы, раскрытие — один кадр вместо 8–15 за ~200 мс; меньше нагрузки
CPU во время касаний. **Цена:** почти нулевая; меньше «мягкости».
Перед тем как выключать, проверить, не завязан ли какой-то сигнал программ
на окончание перехода (`notify::transition-running`). У postmarketOS было
такое же предложение для PinePhone с Phosh — MR закрыт без слияния, то
есть это не общепринятая норма
([pmaports!2092](https://gitlab.postmarketos.org/postmarketOS/pmaports/-/merge_requests/2092)). [B]
**Замер:** `top -d 0.5` или `perf stat -e task-clock -p PID` во время
серии касаний по кнопкам и переключению страниц, до и после
(`gsettings set org.gnome.desktop.interface enable-animations false` в
окружении сеанса).

### 2.3. Дорогой CSS

Тени, размытие теней и скругления в cairo считаются на CPU при каждой
перерисовке затронутой области; GTK 3 кэширует пиксели только у
прокручиваемых областей (`GtkPixelCache`). [B] Конкретной первичной
таблицы стоимостей в документации GTK 3 нет. [—] Практический путь — в
своей теме гасить `box-shadow`, `text-shadow` и `-gtk-icon-shadow` у
больших и часто перерисовываемых элементов (строки списков, карточки,
кнопки панели заголовка) и не делать окна полупрозрачными.
**Замер:** время кадра нельзя взять из `GDK_DEBUG=frames` (не собрано),
поэтому — `perf record -g -p PID` во время прокрутки и доля
`pixman_*`/`_cairo_*` в `perf report`.

### 2.4. Списки

`GtkListBox.bind_model` в GTK 3 создаёт виджет для **каждого**
элемента модели сразу; виртуализации нет
([gtklistbox.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/gtklistbox.c#L3998-L4020)). [A]
Виртуализацию в GTK 3 даёт только `GtkTreeView` (ячейки рисуются, а не
создаются виджетами); `GtkFlowBox` тоже держит виджет на элемент. [A]
Для длинных списков (чаты, письма, треки, файлы, лог): первая страница
сразу, остальное порциями в `GLib.idle_add` с низким приоритетом, и не
перестраивать весь список при обновлении — менять строки в модели
(`Gio.ListStore.splice`). **Замер:** время от `set_model`/цикла
`add` до первого кадра; `cProfile` вокруг наполнения.

### 2.5. Картинки

Встроенные загрузчики gdk-pixbuf в Alpine 3.24 выключены: PNG, JPEG,
GIF, TIFF, SVG и прочие идут через glycin, то есть через пул
процессов-загрузчиков на каждый процесс программы (в bwrap, если он
работает)
([APKBUILD](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/main/gdk-pixbuf/APKBUILD#L42-L55),
[NEWS glycin](https://gitlab.gnome.org/GNOME/glycin/-/blob/2.1.5/NEWS)). [A]
Первый `GdkPixbuf` в процессе стоит запуска загрузчика; иконки темы в
PNG тоже идут этим путём. [B] Проект уже обходит это в kit и Видео
(Pillow, `draft` для JPEG, отдельный процесс). В остальных программах
каждое `Pixbuf.new_from_file` полного размера — декодирование всего
снимка с последующим масштабированием. **Что сделать:** все картинки — через
`haltia_kit.pictures` с размером цели; иконки программ — SVG/символьные
(librsvg), не крупные PNG. **Замер:** `ps -o pid,rss,args | grep glycin`
после открытия программы; `strace -f -e trace=execve -p PID`.

### 2.6. Главный поток

PyGObject: GTK вызывается только из главного потока; долгую работу
выносить в `threading.Thread`, результат возвращать через
`GLib.idle_add`; вызовы PyGObject отпускают GIL
([Threading](https://pygobject.gnome.org/guide/threading.html)). [A]
С PyGObject 3.50 есть интеграция asyncio (`gi.events.GLibEventLoopPolicy`),
асинхронные функции Gio без callback'а возвращают awaitable; API
помечено экспериментальным
([Asynchronous](https://pygobject.gnome.org/guide/asynchronous.html)). [A]
Настройки уже следуют этому правилу (`background(fetch, apply)`). Для
программ правило то же; нарушения — ниже. **Замер:** `strace -f -tt -T
-e trace=network,read,openat,wait4 -p PID`: системный вызов в главном
потоке (TID = PID) дольше ~50 мс — кандидат на вынос.

## 3. Память

| Тема | Факт | Оценка | Что делать |
|---|---|---|---|
| pymalloc | Объекты ≤ 512 байт — в аренах по 256 КиБ на 32-битных системах; крупнее — `PyMem_RawMalloc`, то есть musl `malloc` ([Memory Management](https://docs.python.org/3.14/c-api/memory.html)) | [A] | ничего; арены возвращаются ОС только целиком |
| mimalloc в CPython | В обычной сборке встроен, но не по умолчанию; включается `PYTHONMALLOC=mimalloc` (там же) | [A] наличие, [C] выигрыш | попробовать на одной программе, сравнить PSS и время прокрутки |
| musl mallocng | С musl 1.2.1: «возвращает освобождённую память гораздо мельче» и избегает многих катастрофических случаев фрагментации ([релизы musl](https://musl.libc.org/releases.html)) | [A] | на устройстве с 1 ГБ это скорее плюс; цена — скорость частых аллокаций |
| jemalloc/mimalloc через `LD_PRELOAD` | `mimalloc2` и `jemalloc` в Alpine 3.24 для всех архитектур ([mimalloc2](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/community/mimalloc2/APKBUILD), [jemalloc](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/main/jemalloc/APKBUILD)) | [C] | только по замеру; рост RSS из-за собственных кэшей аллокатора вероятен |
| GC | В 3.14.5+ возвращён поколенческий GC 3.13 (инкрементальный откатили из-за давления на память) ([What's New 3.14](https://docs.python.org/3.14/whatsnew/3.14.html)) | [A] | ничего |
| zram | Документация ядра допускает `swappiness` выше 100 для zram; `page-cluster` 0 отключает упреждающее чтение swap ([vm.rst](https://docs.kernel.org/admin-guide/sysctl/vm.html)) | [A] | уже 100 и 0; 150–180 — эксперимент устройства, не оболочки |

Разделение памяти между процессами: страницы кода `libgtk`, `libpython`
и т. п. общие, а куча Python, разобранная тема, кэши стилей и иконок —
свои у каждого процесса. Поэтому N коротких программ стоят N копий этой
базы, а одна долгоживущая — одну. [B] Измерять PSS, не RSS:
`grep -E 'Pss|Swap' /proc/PID/smaps_rollup`; для сравнения — `python3 -c
'import gi; gi.require_version("Gtk","3.0"); from gi.repository import Gtk; Gtk.Window().show(); input()'`
как «пустая» база.

## 4. CPU и система

- **Частота CPU.** `schedutil` берёт загрузку прямо из планировщика
  ([cpufreq.rst](https://docs.kernel.org/admin-guide/pm/cpufreq.html));
  `uclamp` позволяет поднять минимальную «загрузку» задачи
  (`sched_setattr`) или группы (`cpu.uclamp.min`), что schedutil
  превращает в частоту
  ([sched-util-clamp](https://docs.kernel.org/scheduler/sched-util-clamp.html)). [A]
  Есть ли у MT6589 в mainline-порте cpufreq вообще, в документах проекта
  не записано: в плане GPU стоит лишь «ускорять программную отрисовку
  (llvmpipe/pixman, cpufreq)». Сначала проверить
  `ls /sys/devices/system/cpu/cpu0/cpufreq/` и
  `cat .../scaling_governor .../scaling_cur_freq`. Если частота
  фиксирована максимальной — тут выигрывать нечего. [—] для устройства.
- **Фоновая работа.** Обновления уже идут под `nice -n 10 ionice -c 2
  -n 7`. То же стоит делать с фоновыми потоками программ, которые
  декодируют, индексируют или синхронизируют (`os.nice` в
  рабочем процессе kit; `SCHED_IDLE` для чисто фоновой работы, см.
  [sched(7)](https://man7.org/linux/man-pages/man7/sched.7.html)). [B]
- **Горячие места в C.** Проект уже это делает (домашний экран,
  «✕», заставка, фильтр касаний на C; fuzzel вместо Python-диалога
  дал 2,3 с → 0,3 с). Для программ: Cython 3.2.4 есть в Alpine для всех
  архитектур ([cython](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/main/cython/APKBUILD)),
  но имеет смысл только для доказанного профилем горячего цикла на
  чистом Python (разбор, расчёт); вызовы GTK от этого не ускоряются. [B]
  mypyc в Alpine 3.24 не найден. [—]
- **Версия Python.** 3.14 уже здесь; новый интерпретатор с хвостовыми
  вызовами работает только с Clang 19+ на x86-64 и AArch64
  ([What's New 3.14](https://docs.python.org/3.14/whatsnew/3.14.html)),
  к armv7 не относится. [A]

## 5. Что делали похожие проекты

| Проект | Что сделано | Первоисточник | Применимость |
|---|---|---|---|
| postmarketOS | zram по умолчанию: 75 % RAM на устройствах ≤ 2 ГБ, zstd («lz4 быстрее, zstd плотнее»), переопределение в deviceinfo | [коммит pmaports](https://gitlab.postmarketos.org/postmarketOS/pmaports/-/commit/bca632d4f61331d4a5c27d78ea8751542be88cd0) [A] | у B8000-H 512 МБ lz4 (~51 %); размер и алгоритм — решение устройства |
| postmarketOS / Phosh | предложение выключить `enable-animations` на PinePhone ради отзывчивости — закрыто без слияния | [pmaports!2092](https://gitlab.postmarketos.org/postmarketOS/pmaports/-/merge_requests/2092) [A] | идея та же, что в 2.2; не общая норма |
| Raspberry Pi OS | ушли с Wayfire на labwc, потому что Wayfire «не работал достаточно хорошо на старых Pi»; labwc «так же быстр, как X», ценой пары анимаций | [новость Raspberry Pi, окт. 2024](https://www.raspberrypi.com/news/a-new-release-of-raspberry-pi-os/) [A] | про композитор, не про программы; подтверждает отказ от эффектов на слабом железе |
| Sxmo | меню на лёгком оконном менеджере, звонки и сообщения — через shell-скрипты | [sxmo.org](https://sxmo.org/) [A] | тот же ход, что fuzzel вместо GTK-диалога |
| Purism / Librem 5 | первичного руководства по скорости программ не найдено, только обсуждения на форуме | [—] | — |
| Maemo Leste, Ubuntu Touch, Mobian | первичных рекомендаций по скорости GTK-программ не найдено | [—] | — |

## Что найдено в коде

Только чтение локальных клонов на снимках, перечисленных в «Методе».
Пути — `репозиторий/файл:строка`. Ни один факт ниже не измерен на
планшете; комментарии самого кода с замерами на планшете приведены как
есть. Оценка «вероятно» — [C]. Ни одна программа не использует
`Gtk.Builder`, `.ui` или gresource: всё строится кодом, так что выигрыша
от перехода на `.ui` ждать не стоит (скорее наоборот: разбор XML).
Ни одна не использует `bind_model`, `Gio.ListStore` или `GtkTreeView`.

### Подтверждения из самого кода

- `paint/haltia-paint:1997-1999`: «concurrent.futures took a third of a
  second to import on the tablet» — поэтому свой `Workers`.
- `weather/haltia-weather:210-212`: «urllib … took 0.3 s of the start,
  before the window was drawn» — импорт перенесён в поток загрузки.
- `paint/haltia-paint:519`: `urllib.parse` — «a fifth of a second at start».

То есть один лишний модуль стандартной библиотеки на верхнем уровне стоит
на планшете 0,2–0,3 с. [A] (замеры проекта)

### Запуск

| Место | Что | Почему важно |
|---|---|---|
| все программы, кроме kit | нет `.pyc`: исполняемый файл без расширения (messenger 8075 строк, paint 3869, settings 2850, video 2132) и модули в root-каталогах `/usr/lib/haltia-*` | компиляция при каждом старте (раздел 1.1) |
| `messenger/install.sh:38-41`, `music/install.sh:32` | колёса PyMax и yandex-music, ya-passport-auth, aiosendspin, mashumaro, cpace, noiseprotocol распаковываются `unzip` без компиляции | то же для зависимостей |
| `shell/bin/haltia-settings:828-829`, `1843-1844` | `SourceFileLoader` грузит `/usr/bin/haltia-brightness` и `haltia-touch-settings` | компилируются при каждом открытии страницы |
| `music/haltia-music:294` → `music/sources/music_assistant/__init__.py:33-38` | `sources.load()` в `__init__` импортирует все источники (aiohttp, `aiosendspin.client`) до окна | вероятно, самый дорогой старт в наборе |
| `music/haltia-music:45,48` | `urllib.request`, `concurrent.futures` на верхнем уровне | по замеру paint — ~0,3 с только второй |
| `messenger/haltia-messenger:95-117` | `asyncio` (тянет `ssl`), `concurrent.futures`, `urllib.request` на верхнем уровне | запуск; смягчено фоновым режимом |
| `mail/haltia-mail:44-46` | `smtplib`, `ssl`, `email.*`, `imaplib` до окна, хотя нужны только рабочему потоку | запуск |
| `video/haltia-video:36`, `video/pictures.py:32` | `concurrent.futures` и PIL на верхнем уровне | запуск |
| `video/haltia-video:568` | сразу после окна поток импортирует `yt_dlp` с экстракторами | борется с GTK за GIL в первые секунды; память |
| `kit/haltia_kit/camera.py:70-82` | PIL, Gst, GstVideo на верхнем уровне модуля; Камера импортирует его при старте | запуск |
| `shell/bin/haltia-settings:27,42-44` | `tarfile` и typelib `NM-1.0` при старте, даже если сеть не открывают | запуск Настроек |
| `paint/haltia-paint:2120`, `697-720` | `load_pictures()` в потоке GTK до окна: gzip и разбор начала всех 96 `.svgz` и фото | запуск |
| `messenger/haltia-messenger:960`, `1826-1834` | `calls_supported()` делает `Gst.init` и пробует элементы WebRTC; в каком потоке впервые — не установлено | загрузка реестра GStreamer |

### Главный поток

| Место | Что | Почему важно |
|---|---|---|
| `files/haltia-files:129-151`, `271-306` | каждое касание папки: пять подпроцессов `xdg-user-dir`, `stat` до 2000 элементов и `os.listdir` каждой подпапки — в потоке GTK | замирание, вероятно сотни мс на A7 |
| `files/chooser.py:364` | выбор файлов портала тоже перечисляет подпапки в потоке GTK | замирание диалога «Открыть/Сохранить» |
| `camera/haltia-camera:310-318` | после снимка `Pixbuf.new_from_file` полного кадра, поворот и `scale_simple` в потоке GTK | замирание и полный кадр в памяти |
| `shell/bin/haltia-touch-settings:214-221`, `464-476` | `doas -n haltia-touchguard-conf` синхронно на каждое применение (и внутри Настроек) | замирание |
| `shell/bin/haltia-brightness:129-145`, `214`, `267-274` | `pactl` до окна; на каждое изменение громкости три `subprocess.call` каждые 120 мс при перетаскивании | запуск и рывки ползунка |
| `messenger/haltia-messenger:6868-6875` | `scale_simple` снимка до 2048 px в потоке GTK при каждой подгонке | замирание просмотрщика |
| `messenger/haltia-messenger:8006` | `new_from_file_at_scale(96)` для вложений в потоке GTK (и через glycin) | замирание на каждое фото |
| `text/haltia-text:90-97` | `xdg-user-dir` при выборе места сохранения | малое замирание |

Хороший образец уже есть — `background(fetch, apply, latest=, serial=)`
в `shell/bin/haltia-settings:136-193`, — но программы им не пользуются:
каждая пишет свой `Thread` + `idle_add`. Общий помощник в kit сделал бы
правило дешёвым.

### Картинки, списки, отрисовка, CSS, память

| Место | Что | Почему важно |
|---|---|---|
| `news/haltia-news:484-497`, `paint/haltia-paint:643-648` | `PixbufLoader` без `set_size` и без предела пикселей, потом `scale_simple` | пик памяти — полный снимок; путь glycin |
| `music/haltia-music:934-985` | `fill()` очищает и строит все строки сразу; в плейлистах сотни треков | замирание и память |
| `mail/haltia-mail:686-700` | 50 строк из кэша, затем при обновлении удаляются и строятся заново | двойная постройка |
| `calendar/haltia-calendar:150-157`, `300-330` | вид года пересоздаёт 12 сеток × ~42 метки при каждом переключении | замирание |
| `kit/haltia_kit/sound.py:56-63` → `music/haltia-music:1143-1148` | наблюдатель mpv `time-pos` ставит `idle_add` на каждое изменение без прореживания; ползунок и метка перерисовываются много раз в секунду | постоянная нагрузка CPU во время музыки |
| `kit/haltia_kit/camera.py:614-615`, `754-785` | кадр видоискателя до 1280×1280 RGBA копируется в новый pixbuf и масштабируется cairo в `draw` каждый кадр, размер не подогнан к виджету | главная стоимость Камеры |
| `messenger/haltia-messenger:1959-1990` | видео звонка: новая `cairo.ImageSurface` на кадр, возможно построчное копирование в Python, масштаб в `draw` | CPU на звонке |
| `paint/haltia-paint:2417-2437` | миниатюры галереи масштабируются в каждом `draw` с `FILTER_GOOD` | CPU при прокрутке |
| `mail/haltia-mail:438` | `Gtk.Stack(transition_type=CROSSFADE)` | смешивание двух поверхностей на CPU при каждой смене страницы |
| `paint/haltia-paint:3203-3208` | новый `Gtk.CssProvider` на каждый образец палитры (20–40) при открытии картинки | разбор CSS и пересчёт стилей |
| `messenger/haltia-messenger:481`, `paint/haltia-paint:312`, `camera/haltia-camera:66` | тени с размытием 6–12 px (у Камеры `text-shadow` 12 px на 160 px тексте отсчёта, перерисовка раз в секунду) | размытие на CPU при каждой перерисовке |
| `shell/bin/haltia-brightness:232-234` | RGBA-визуал ради скруглённых углов | нет непрозрачной области у окна |
| `shell/themes/Haltia/gtk-3.0/gtk.css:26-39` | тема гасит тени и градиенты только у кнопок заголовка; кнопки в теле и диалогах сохраняют `transition: all 200ms`, градиенты и тени Adwaita | каждая кнопка анимирует 200 мс |
| `music/haltia-music:79`, `280-285` | 400 обложек в памяти по числу, не по байтам; дисковый кэш обложек без очистки | рост памяти и диска |
| `paint/haltia-paint:215-216` | кэш 40 плиток по 512² × 4 Б ≈ 40 МБ | ограничен, но велик для 1 ГБ |

Сделано хорошо и стоит тиражировать: «Сообщения» откладывают PyMax и
вход до первого кадра и подгружают пузыри по 3 за низкоприоритетный idle
(`messenger/haltia-messenger:166-183`, `5292-5330`, `6254-6264`); Новости
и Погода начинают загрузку по первому `draw`; Файлы — сетка медиа порциями
по 60 (`files/media.py:21`, `176-201`); Видео — LRU картинок по байтам
(`video/pictures.py:43-60`); kit — `gallery.Thumbs` с одним потоком и
`photos.Worker` в отдельном процессе с лимитом памяти.

## Приоритетный список

Порядок — по отношению «ожидаемый эффект / цена». Каждый пункт сначала
замерить «до» на планшете тем способом, что указан в разделе.

1. **Байт-код.** Код программ — в модули пакета, в `/usr/bin` — короткий
   запуск; `compileall` при сборке (или `default_pyc`) для программ и
   распакованных колёс; перестать выбрасывать `-pyc` в
   `update-lock.sh`. Проверить права на `__pycache__` на планшете. (1.1)
2. **Выключить анимации GTK** одной строкой `enable-animations=false` в
   `91-haltia-shell.gschema.override`; в теме Haltia — `transition: none`
   и сброс теней у кнопок тела и строк. (2.2, 2.3)
3. **Убрать блокировки главного потока** в Файлах (`go`, `places`,
   подсчёт подпапок), выборе файлов портала, Камере, Яркости и
   «Касаниях». Общий `background(fetch, apply)` перенести из Настроек в
   kit. (2.6, «Главный поток»)
4. **Ленивые импорты** в Музыке (`sources.load()` после окна,
   `urllib`/`concurrent.futures`), Почте (`smtplib`/`imaplib`/`ssl` в
   поток), «Сообщениях», Видео, `kit.camera`, Настройках (`NM`,
   `tarfile`). Проверка — `-X importtime`. (1.2)
5. **Тёплый старт** для одной-двух самых частых программ
   (`hold()` + `inactivity-timeout`, окно прятать), с учётом PSS и
   earlyoom. (1.3)
6. **Прореживать `time-pos`** в `kit/sound.py` до 1–2 обновлений в
   секунду. (Отрисовка)
7. **Списки порциями**: Музыка, Календарь (вид года не пересоздавать),
   Почта (не строить дважды), первый вход «Сообщений». (2.4)
8. **Картинки только через `haltia_kit.pictures` с размером цели**:
   Новости, Рисование, Камера, вложения «Сообщений»; ограничить обложки
   Музыки байтами и чистить их дисковый кэш. (2.5)
9. **Видоискатель и видео звонка**: просить у GStreamer кадр размера
   виджета (caps), а не масштабировать в `draw`; одна поверхность
   вместо новой на кадр. (Отрисовка)
10. **Проверить систему, а не только программы**: есть ли cpufreq и какой
    governor; не устарел ли `icon-theme.cache`; сколько процессов glycin
    живёт рядом с программами; попробовать `PYTHONMALLOC=mimalloc` на
    одной программе по PSS. Только по результатам замера. (1.4, 3, 4)

## Источники

- **GTK 3.24**, ветка `gtk-3-24` на `0f3aa454a2a14b68e2753f63bedb2c74bd45b54b`:
  [gdkwindow-wayland.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gdk/wayland/gdkwindow-wayland.c),
  [gdkscreen-wayland.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gdk/wayland/gdkscreen-wayland.c),
  [gtkwindow.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/gtkwindow.c),
  [gtklistbox.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/gtklistbox.c),
  [gtkcsswidgetnode.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/gtkcsswidgetnode.c),
  [gtkiconcache.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/gtkiconcache.c),
  [gtkmain.c](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/gtkmain.c),
  [meson.build](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/meson.build),
  [Adwaita gtk-contained.css](https://gitlab.gnome.org/GNOME/gtk/-/blob/0f3aa454a2a14b68e2753f63bedb2c74bd45b54b/gtk/theme/Adwaita/gtk-contained.css).
- **PyGObject 3.56.3**:
  [gi/overrides/Gtk.py](https://gitlab.gnome.org/GNOME/pygobject/-/blob/3.56.3/gi/overrides/Gtk.py),
  [gi/__init__.py](https://gitlab.gnome.org/GNOME/pygobject/-/blob/3.56.3/gi/__init__.py),
  [Threading](https://pygobject.gnome.org/guide/threading.html),
  [Asynchronous](https://pygobject.gnome.org/guide/asynchronous.html).
- **GLib/GIO**: [GApplication](https://docs.gtk.org/gio/class.Application.html),
  [GIO overview](https://docs.gtk.org/gio/overview.html).
- **at-spi2-core** `98a724896fc75f1299dcaea8aab8f2cd8f121b4c`:
  [atk-adaptor/bridge.c](https://gitlab.gnome.org/GNOME/at-spi2-core/-/blob/98a724896fc75f1299dcaea8aab8f2cd8f121b4c/atk-adaptor/bridge.c).
- **gdk-pixbuf 2.44.7 и glycin 2.1.5**:
  [meson.build](https://gitlab.gnome.org/GNOME/gdk-pixbuf/-/blob/2.44.7/gdk-pixbuf/meson.build),
  [io-jpeg.c](https://gitlab.gnome.org/GNOME/gdk-pixbuf/-/blob/ff4acb5b5c9a8ac29667235ec1626c996dec84de/gdk-pixbuf/io-jpeg.c)
  (масштаб при декодировании `scale_denom`, когда встроенный загрузчик
  JPEG включён — в Alpine 3.24 он выключен),
  [glycin NEWS](https://gitlab.gnome.org/GNOME/glycin/-/blob/2.1.5/NEWS).
- **CPython 3.14**:
  [Compiled Python files](https://docs.python.org/3.14/tutorial/modules.html#compiled-python-files),
  [What's New 3.14](https://docs.python.org/3.14/whatsnew/3.14.html),
  [Memory Management](https://docs.python.org/3.14/c-api/memory.html),
  [perf profiling](https://docs.python.org/3.14/howto/perf_profiling.html),
  [configure.ac](https://github.com/python/cpython/blob/v3.14.0/configure.ac),
  [PEP 810](https://peps.python.org/pep-0810/).
- **Alpine aports** `3.24-stable` на `b02712468d0921412896c3c355582785339feaed`:
  [python3](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/main/python3/APKBUILD),
  [py3-gobject3](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/community/py3-gobject3/APKBUILD),
  [gtk+3.0](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/main/gtk+3.0/APKBUILD),
  [gdk-pixbuf](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/main/gdk-pixbuf/APKBUILD),
  [glycin](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/community/glycin/APKBUILD),
  [abuild-meson](https://gitlab.alpinelinux.org/alpine/aports/-/blob/b02712468d0921412896c3c355582785339feaed/main/meson/abuild-meson).
- **musl**: [releases](https://musl.libc.org/releases.html) (1.2.1, mallocng).
- **Ядро Linux**: [sysctl/vm](https://docs.kernel.org/admin-guide/sysctl/vm.html),
  [cpufreq](https://docs.kernel.org/admin-guide/pm/cpufreq.html),
  [sched-util-clamp](https://docs.kernel.org/scheduler/sched-util-clamp.html),
  [sched(7)](https://man7.org/linux/man-pages/man7/sched.7.html).
- **Похожие проекты**: [pmaports, zram по умолчанию](https://gitlab.postmarketos.org/postmarketOS/pmaports/-/commit/bca632d4f61331d4a5c27d78ea8751542be88cd0),
  [pmaports!2092](https://gitlab.postmarketos.org/postmarketOS/pmaports/-/merge_requests/2092)
  (состояние «closed» получено через GitLab API 26 октября 2026),
  [Raspberry Pi OS, октябрь 2024](https://www.raspberrypi.com/news/a-new-release-of-raspberry-pi-os/),
  [Sxmo](https://sxmo.org/).
