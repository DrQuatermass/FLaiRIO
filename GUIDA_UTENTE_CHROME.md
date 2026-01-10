# Guida: Gestione Browser per Pubblicazione Automatica

## Cos'è Chrome per Playwright?

FLaiRIO usa **Playwright** per automatizzare la pubblicazione degli articoli sul CMS. Playwright può usare due browser:

- **Google Chrome** ✓ CONSIGLIATO - Difficile da rilevare come bot
- **Chromium** ⚠️ FALLBACK - Può essere rilevato come bot dal CMS

## Perché Chrome è importante?

Quando usi la **modalità headless** (browser nascosto), il CMS Voce potrebbe rilevare Chromium come un bot automatico e **bloccare il login**.

Chrome è più difficile da rilevare e garantisce che la pubblicazione automatica funzioni sempre.

## Come installare Chrome

### Dall'applicazione (FACILE)

1. Apri FLaiRIO
2. Vai alla scheda **Impostazioni**
3. Nella sezione **CMS Voce**, controlla lo stato del browser:
   - ✓ Chrome installato = tutto OK
   - ✗ Chrome non installato = da installare

4. Clicca sul pulsante **"Installa/Aggiorna Chrome"**
5. Attendi il download (~100-150 MB)
6. Fatto! Chrome è installato

### Primo avvio

All'avvio, se hai attivato la **modalità headless** ma Chrome non è installato, FLaiRIO ti mostrerà un avviso:

```
Chrome non installato

Il sistema userà Chromium come fallback, ma potrebbe essere
rilevato come bot dal CMS in modalità headless.

Puoi installare Chrome dalla sezione Impostazioni → CMS.
```

Basta andare nelle impostazioni e cliccare "Installa/Aggiorna Chrome".

## Quando aggiornare Chrome

Chrome si aggiorna automaticamente, ma Playwright potrebbe non supportare subito l'ultima versione. Se noti problemi:

1. Vai in **Impostazioni → CMS**
2. Clicca **"Installa/Aggiorna Chrome"**
3. FLaiRIO scaricherà la versione compatibile

### Come capire se Chrome ha bisogno di aggiornamento

Se la pubblicazione automatica in headless mode fallisce con errori come:
- "Login fallito"
- "Browser closed unexpectedly"
- "Chrome non disponibile"

Prova ad aggiornare Chrome dal pulsante nelle impostazioni.

## Modalità Browser

Nelle impostazioni CMS puoi scegliere:

- **Visibile (headless=False)**: Vedi il browser aprirsi e compilare il form
  - Più lento
  - Usa più risorse
  - Utile per debug
  - Funziona con Chrome e Chromium

- **Nascosto (headless=True)**: Browser invisibile in background
  - Più veloce
  - Usa meno risorse
  - ⚠️ RICHIEDE Chrome (Chromium può essere bloccato)

## Risoluzione problemi

### "Chrome non installato (usando Chromium)"

**Soluzione**: Installa Chrome dal pulsante nelle impostazioni

### Login fallisce in modalità headless

1. Controlla che Chrome sia installato (Impostazioni → CMS)
2. Se Chrome è installato ma fallisce, prova ad aggiornarlo (stesso pulsante)
3. Se continua a fallire, passa temporaneamente a modalità "Visibile"

### Download di Chrome non parte

- Verifica la connessione internet
- Riprova dopo qualche minuto
- Se persiste, contatta il supporto

### Chrome installato ma sistema usa Chromium

Riavvia l'applicazione dopo l'installazione di Chrome.

## Dove viene installato Chrome

Chrome per Playwright viene scaricato in:

**Windows:**
```
C:\Users\[TuoNome]\AppData\Local\ms-playwright\chrome-*
```

**macOS:**
```
~/Library/Caches/ms-playwright/chrome-*
```

**Linux:**
```
~/.cache/ms-playwright/chrome-*
```

**Non eliminare questa cartella!** È necessaria per il funzionamento di FLaiRIO.

## Dimensione occupata

- Chrome: ~120-150 MB
- Chromium: ~100-120 MB (installato automaticamente con Playwright)

## FAQ

**Q: Devo avere Google Chrome installato sul PC?**
A: No, FLaiRIO usa una versione separata di Chrome gestita da Playwright.

**Q: Chrome si aggiorna automaticamente?**
A: No, la versione di Chrome usata da FLaiRIO è gestita manualmente. Usa il pulsante "Installa/Aggiorna Chrome" quando necessario.

**Q: Posso usare solo Chromium?**
A: Sì, ma in modalità headless potresti avere problemi con il login al CMS.

**Q: Quanto spesso devo aggiornare Chrome?**
A: Solo se riscontri problemi. In generale ogni 2-3 mesi o quando l'app ti avvisa.

**Q: L'installazione di Chrome richiede permessi amministratore?**
A: No, viene installato nella tua cartella utente.

---

Per supporto: controlla il log dell'applicazione o contatta l'amministratore del sistema.
