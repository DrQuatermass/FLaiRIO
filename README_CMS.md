# Guida Pubblicazione Automatica CMS Voce.it

## Panoramica

Il sistema ora include la **pubblicazione automatica** degli articoli sul CMS di Voce.it usando Playwright per automatizzare il browser.

## Come Funziona

1. **Login Automatico**: Il sistema fa login al CMS con tecniche anti-detection
2. **Navigazione Intelligente**: Naviga automaticamente alla sezione corretta (Spotlight/Apertura/In Evidenza)
3. **Compilazione Form**: Compila tutti i campi del form CMS inclusi i CKEditor
4. **Verifica Successo**: Controlla che la pubblicazione sia andata a buon fine

## Uso dalla GUI

### 1. Genera l'articolo
- Click su "📝 Genera Articolo" per un'email
- L'articolo viene mostrato nell'anteprima

### 2. Pubblica sul CMS
- Click su "Pubblica su CMS"
- Conferma nella dialog
- Il browser si apre automaticamente e pubblicherà l'articolo
- Riceverai notifica di successo/errore

## Configurazione Credenziali

Nel file `.env`, aggiungi:

```env
CMS_USERNAME=TuoUsername
CMS_PASSWORD=TuaPassword
```

## Mapping Automatico

### Tipo Articolo → Sezione CMS
- `Spotlight` → `https://www.voce.it/admin/spotlight/`
- `Apertura` → `https://www.voce.it/admin/apertura/`
- `In Evidenza` → `https://www.voce.it/admin/in_evidenza/`

### Categoria → Valore CMS
| Categoria | Valore CMS |
|-----------|------------|
| Ambiente | 48 |
| Attualità | 7 |
| Cultura | 19 |
| Economia | 5 |
| Moda | 29 |
| Sanità | 3 |
| Scuola | 1 |
| Sociale | 28 |
| Sport | 9 |
| Territorio | 7 (→ Attualità) |

### Contenuto → CKEditor
- `contenuto[0]` → Primo paragrafo (CKEditor `testo`)
- `contenuto[1]` → Secondo paragrafo (CKEditor `testo2`)
- `contenuto[2]` → Terzo paragrafo (CKEditor `testo3`)

## Test Manuale

Per testare la pubblicazione:

```bash
python cms_automation.py
```

Questo pubblicherà un articolo di test sul CMS.

## Troubleshooting

### Browser si apre ma non fa login
- Verifica che le credenziali in `.env` siano corrette
- Il sistema usa tecniche stealth per bypassare protezioni anti-bot
- Se persiste, il problema potrebbe essere lato CMS

### Form non viene compilato
- Il sistema usa JavaScript per compilare campi nascosti e CKEditor
- Verifica negli screenshot salvati (`cms_form_filled.png`)

### Pubblicazione ritorna errore
- Controlla `cms_after_submit.png` per vedere eventuali messaggi di errore
- Il template deve essere selezionato (viene fatto automaticamente)
- La categoria deve essere valida

## Screenshots Generati

Durante la pubblicazione, il sistema salva:
- `cms_form_empty.png` - Form vuoto iniziale
- `cms_form_filled.png` - Form compilato prima del submit
- `cms_after_submit.png` - Pagina dopo la pubblicazione

Questi possono essere utili per il debug.

## Sicurezza

- Le credenziali sono memorizzate solo in `.env` (mai committato su Git)
- Il browser viene chiuso automaticamente dopo la pubblicazione
- La connessione avviene sempre su HTTPS dopo il redirect iniziale

## Performance

- Tempo medio pubblicazione: **30-40 secondi**
  - Login: ~7 secondi
  - Navigazione: ~5 secondi
  - Compilazione form: ~10 secondi
  - Submit: ~5 secondi

---

**Sistema sviluppato con Claude Code e Playwright**
