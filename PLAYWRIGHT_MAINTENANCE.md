# Manutenzione Playwright per FLaiRIO

## Problema: Chrome si aggiorna e Playwright smette di funzionare

### Sintomi
- Errore durante l'avvio del browser in modalità headless
- Messaggio: "Chrome non disponibile"
- Il sistema passa automaticamente a Chromium (che può essere rilevato come bot dal CMS)

### Causa
Quando Google Chrome installato sul sistema si aggiorna automaticamente, può diventare incompatibile con la versione di Playwright installata.

## Soluzioni

### Opzione 1: Aggiorna i browser di Playwright (CONSIGLIATO)
```bash
playwright install chrome
```

Questo comando scarica e installa la versione di Chrome gestita da Playwright, compatibile con la versione attuale.

### Opzione 2: Aggiorna Playwright completamente
```bash
pip install --upgrade playwright
playwright install chrome
```

Questo aggiorna sia Playwright che i browser.

### Opzione 3: Usa Chromium gestito da Playwright (non consigliato)
Se Chrome continua a dare problemi, puoi modificare `cms_automation.py` per usare solo Chromium:
- NOTA: Chromium è più facile da rilevare come bot dal CMS

## Verifica del funzionamento

Dopo aver aggiornato, testa con:
```bash
python test_headless_login.py
```

Dovresti vedere:
```
[CMS] Usando Google Chrome in headless mode
[CMS] [OK] Login riuscito!
[TEST] [OK] Bottone CREATE trovato!
```

## Manutenzione preventiva

### Controlla le versioni
```bash
playwright --version
```

### Aggiorna periodicamente (ogni 2-3 mesi)
```bash
pip install --upgrade playwright
playwright install chrome
```

## Troubleshooting

### Errore: "Executable doesn't exist"
```bash
playwright install chrome
```

### Errore: "Browser closed unexpectedly"
Verifica che Chrome non sia già in esecuzione, poi:
```bash
playwright install --force chrome
```

### Login fallisce in headless mode
1. Verifica che stai usando Chrome (non Chromium):
   - Cerca nel log: `[CMS] Usando Google Chrome in headless mode`
2. Se vedi "Usando Chromium", installa Chrome:
   ```bash
   playwright install chrome
   ```

## Note tecniche

- **channel="chrome"**: Usa Google Chrome installato da Playwright
- **Fallback automatico**: Se Chrome non funziona, passa a Chromium
- **Anti-detection**: Chrome è molto più difficile da rilevare come bot rispetto a Chromium
- **Versioni gestite**: Playwright gestisce i browser in `%USERPROFILE%\AppData\Local\ms-playwright`

## Frequenza aggiornamenti consigliata

- **Chrome di sistema**: Si aggiorna automaticamente ogni 4-6 settimane
- **Playwright**: Aggiornare ogni 2-3 mesi o quando Chrome smette di funzionare
- **Test**: Eseguire `test_headless_login.py` dopo ogni aggiornamento di Chrome

## Link utili

- [Playwright Browsers](https://playwright.dev/python/docs/browsers)
- [Playwright Releases](https://github.com/microsoft/playwright-python/releases)
