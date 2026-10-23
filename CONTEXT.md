# Context

The words the Haltia repositories use for how the project is split. The
decisions behind them: ADR 0001 and ADR 0004 (`docs/adr/`).

- **Haltia** — the calm touch desktop (DE): the shell, the programs and the
  kit. In inflected Russian text it is «Халтия».
- **Pertin Haltia** — the line of ready images of Haltia for tablets, one
  profile per device.
- **Устройство** (device; a repository `device-<vendor>-<model>` each): the
  kernel and its patches, the DTS, the drivers, the installer, the image build
  and the device profile. It pins the versions of the shell and the programs
  its image installs (`packages.lock`).
- **Профиль устройства** (device profile): the device's own helpers and
  numbers that plug into the DE's hook points — reboot, display tuning,
  suspend hook, USB role, Wi-Fi watchdog, zram, GPU stack, `device.conf`.
- **Точки подключения** (hook points): how a device plugs into the DE
  without the DE knowing it — backlight, `/usr/lib/haltia/hooks/suspend`,
  the compositor in `device.conf`, touch thresholds as fractions of the axis
  range, doas rules (ADR 0004).
- **Оболочка** (shell; `haltia-de/shell`): what runs programs on a touch
  device — panel, home screen, the close button «✕», the touch filter and its
  buzz, the keyboard, rotation, settings, the updater with rollback, the GTK
  theme. It knows programs only through freedesktop standards.
- **Программа** (program; a repository each): Файлы/Галерея, Текст,
  Календарь, Новости, Погода, Видео, Музыка, Сообщения (MAX), Раскраска,
  Firefox, Камера, Почта. «Документы» (просмотр PDF) — вторая программа
  в репозитории `files`, пакет `haltia-documents`. Installs and works on
  its own, in GNOME or KDE as in the shell. Почта на планшете скрыта с
  домашнего экрана: через неё уходят отчёты помощнику.
- **Библиотека программ** (kit; `haltia-de/kit`, module `haltia_kit`): code
  the programs share — in-window questions and menus, settings, sound,
  photos. It knows nothing of the shell.
- **Id программы** (program id): `io.github.haltia_de.<Program>`, one name for
  the `.desktop` file, the window `app_id`, D-Bus, icon, metainfo and MPRIS.
- **Стандарты связи** (integration standards): `.desktop`, LauncherEntry for
  counts on buttons, MPRIS, logind inhibit, XDG autostart.
- **Метапакеты** (meta packages): `haltia-desktop` (shell, kit and the general
  programs), `haltia-desktop-ru` (programs for Russian services),
  `postmarketos-ui-haltia`.
- **Архитектор** (architect): the agent started in this repository. It
  designs, analyses and hands out work; it does not write product code
  (ADR 0005).
- **Исполнитель** (executor): an agent that works on one issue in one
  repository — a Claude Code session, Codex CLI or Grok Build.
- **Диспетчер** (dispatcher): the script in `orchestrator/` that starts
  executors for issues labelled `agent:ready`.
