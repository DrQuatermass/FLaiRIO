# Note Cross-Platform per FLaiRIO

## Compatibilità

FLaiRIO è progettato per funzionare su:
- ✅ **Windows** 10/11 (testato)
- ✅ **macOS** 11+ (Big Sur e successivi)
- ✅ **Linux** (Ubuntu 20.04+, Fedora, Arch)

## Differenze tra piattaforme

### Installazione Chrome per Playwright

Il sistema di gestione browser è completamente cross-platform.

**Path di installazione:**
- Windows: `%USERPROFILE%\AppData\Local\ms-playwright\chrome-*`
- macOS: `~/Library/Caches/ms-playwright/chrome-*`
- Linux: `~/.cache/ms-playwright/chrome-*`

**Dimensione download:**
- Windows: ~120-150 MB
- macOS (Intel): ~130-160 MB
- macOS (Apple Silicon): ~140-170 MB
- Linux: ~120-150 MB

### Configurazione IMAP

**Nessuna differenza** - IMAP funziona ugualmente su tutte le piattaforme.

### Database SQLite

**Nessuna differenza** - SQLite è cross-platform.

### Interfaccia Grafica (PySide6)

**Nessuna differenza** - PySide6/Qt funziona nativamente su:
- Windows (stile Windows 11)
- macOS (stile macOS nativo)
- Linux (stile tema desktop)

### Encoding e caratteri speciali

**macOS/Linux**: Supporto UTF-8 nativo, nessun problema con caratteri italiani.

**Windows**: FLaiRIO forza UTF-8 all'avvio (`app_gui.py` righe 14-27) per gestire correttamente:
- Caratteri accentati italiani (à, è, é, ì, ò, ù)
- Emoji (✓, ✗, ⚠️)
- Simboli speciali

## Dipendenze specifiche per piattaforma

### Windows

**Nessuna dipendenza aggiuntiva** oltre ai package Python.

### macOS

**Nessuna dipendenza aggiuntiva**.

Nota: Su macOS potrebbe essere richiesto di autorizzare FLaiRIO per:
- Accesso a Internet (per IMAP/SMTP)
- Accesso alla cartella Downloads (se salva allegati)

### Linux

**Dipendenze di sistema per Qt/Playwright:**

```bash
# Ubuntu/Debian
sudo apt-get install libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 \
  libxcb-xfixes0 libegl1 libdbus-1-3 libfontconfig1

# Fedora
sudo dnf install qt6-qtbase libxkbcommon-x11 dbus-libs fontconfig

# Arch
sudo pacman -S qt6-base libxkbcommon-x11 dbus fontconfig
```

Playwright installerà automaticamente le dipendenze browser quando esegui `playwright install chrome`.

## Performance

### Headless mode

- **Windows**: Chrome headless funziona perfettamente
- **macOS**: Chrome headless funziona perfettamente
- **Linux**: Chrome headless potrebbe richiedere Xvfb in ambienti senza X11
  ```bash
  xvfb-run python main.py  # se necessario
  ```

### Velocità IMAP

**Nessuna differenza significativa** tra piattaforme.

## Limitazioni note per piattaforma

### Windows

- Path massimo 260 caratteri (risolto in Windows 10+)
- Emoji potrebbero non visualizzarsi correttamente in vecchie versioni console

### macOS

- **Gatekeeper**: Al primo avvio potrebbe chiedere autorizzazioni
- **Apple Silicon (M1/M2)**: Playwright scarica la versione ARM nativa
- **Sandbox**: Playwright richiede permessi per eseguire browser

### Linux

- **Wayland**: Funziona con XWayland
- **Headless server**: Potrebbe richiedere Xvfb
- **Snap/Flatpak**: Non testato, preferire installazione pip standard

## Build eseguibile

### PyInstaller (Windows/macOS/Linux)

```bash
# Windows
pyinstaller --onefile --windowed --name FLaiRIO main.py

# macOS (crea .app bundle)
pyinstaller --onefile --windowed --name FLaiRIO \
  --osx-bundle-identifier com.flairio.app main.py

# Linux (crea AppImage con pyinstaller + appimagetool)
pyinstaller --onefile --windowed --name FLaiRIO main.py
```

**Nota importante**: Playwright browser NON sono inclusi nell'eseguibile.
L'app deve scaricarli al primo avvio usando il pulsante "Installa Chrome".

### Dimensione eseguibile finale

- Windows .exe: ~50-80 MB (senza browser)
- macOS .app: ~60-90 MB (senza browser)
- Linux AppImage: ~50-80 MB (senza browser)

Con Chrome installato:
- Windows: ~180-230 MB totali
- macOS: ~200-260 MB totali
- Linux: ~180-230 MB totali

## Testing cross-platform

### Test headless login

```bash
# Funziona su tutte le piattaforme
python test_headless_login.py
```

### Test browser manager

```bash
# Test installazione Chrome
python browser_manager.py
```

## Problemi comuni per piattaforma

### Windows: "Accesso negato" durante installazione Chrome

Soluzione: Esegui l'app con permessi normali (NON come amministratore).
Chrome viene installato nella cartella utente, non richiede admin.

### macOS: "FLaiRIO.app non può essere aperto"

Soluzione:
1. System Preferences → Security & Privacy
2. Clicca "Open Anyway" per FLaiRIO
3. Oppure: `xattr -cr FLaiRIO.app` da terminale

### Linux: "Error: Could not find Chrome"

Soluzione:
```bash
# Installa dipendenze
sudo apt-get install libgbm1 libasound2

# Reinstalla Chrome per Playwright
python -m playwright install chrome --with-deps
```

## Raccomandazioni deployment

### Per utenti Windows
- Distribuire come .exe (PyInstaller)
- Includere `GUIDA_UTENTE_CHROME.md`
- Chrome verrà installato automaticamente dall'app

### Per utenti macOS
- Distribuire come .app bundle firmato
- Notarizzare l'app per evitare warning Gatekeeper
- Includere istruzioni per bypass manuale se non notarizzata

### Per utenti Linux
- Distribuire come AppImage o .deb/.rpm
- Includere script per installare dipendenze Qt/Playwright
- Documentare uso con Wayland vs X11

## Supporto

Per problemi specifici della piattaforma, includere nel report:
- Sistema operativo e versione
- Architettura (x64, ARM, Apple Silicon)
- Output del comando: `python -m playwright --version`
- Log dell'applicazione

---

Ultimo aggiornamento: 2025-01-08
