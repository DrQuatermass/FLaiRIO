# FLaiRIO - Workflow Completo

## Panoramica Sistema
FLaiRIO è un sistema automatizzato per convertire email in articoli e pubblicarli sul CMS.

## Entry Point
- **Principale**: `run.py` - Launcher che avvia la GUI
- **GUI**: `app_gui.py` - Interfaccia grafica principale
- **CLI**: `main.py` - Workflow da riga di comando

## Flusso Operativo

### 1. Monitoraggio Email
**Modulo**: `email_processor.py`
- Connessione alle caselle email configurate
- Filtra email non lette
- Estrae: titolo, corpo, allegati (solo con Content-Disposition: attachment)
- Salva nel database locale

### 2. Generazione Articolo
**Modulo**: `llm_article_generator.py`
- Usa LLM (OpenAI/Anthropic) per generare articolo
- Input: contenuto email
- Output: articolo formattato con titolo, sommario, corpo

### 3. Pubblicazione CMS
**Modulo**: `cms_automation.py`
**Browser**: `browser_manager.py` (Playwright)

#### 3.1 Login CMS
- Accede a voce.it/admin
- Login automatico con credenziali

#### 3.2 Creazione Articolo
- Naviga a spotlight/create.php
- Compila form:
  - **Data**: formato DD-MM-YYYY (es. 14-01-2026)
  - **Ora**: formato HH:MM
  - **Template**: Template 2
  - **Tipo**: Notizia/Apertura/In Evidenza
  - **Categoria**: Selezionata dall'utente
  - **Titolo**: Da LLM
  - **Sommario**: Da LLM
  - **Testo**: Corpo articolo da LLM
  - **Fonte**: Email originale

#### 3.3 Approvazione Articolo
- Dopo submit, il sistema ritorna alla lista articoli
- **Struttura HTML**: `<div class="item" data-id="ARTICLE_ID">`
- Estrae article_id dal primo item (articolo appena creato)
- Clicca pulsante approvazione (icona gialla)
- Articolo rimane NON VISIBILE (da rendere visibile manualmente)

#### 3.4 Upload Foto Galleria
- Trova item articolo: `div.item[data-id="ARTICLE_ID"]`
- Clicca pulsante galleria: `<a href="../spotlight_gallery/index.php?id=ARTICLE_ID">`
- Carica tutte le foto allegate
- Ritorna alla lista articoli

### 4. Notifiche
**Modulo**: `notifier.py`
- Invia notifica email ai destinatari configurati
- Invia notifica Telegram (se configurato)

### 5. Database
**Modulo**: `database.py`
- Salva email processate
- Traccia articoli pubblicati
- Previene duplicati

## File Configurazione

### .env
Variabili d'ambiente richieste:
```
# Email
EMAIL_USER=
EMAIL_PASS=

# CMS
CMS_USERNAME=
CMS_PASSWORD=

# LLM
LLM_PROVIDER=openai
OPENAI_API_KEY=

# CRM (legacy, non usato)
CRM_TYPE=
CRM_USERNAME=
CRM_PASSWORD=
CRM_API_URL=
```

## Utility

### test_platform.py
Test di compatibilità cross-platform

### remove_duplicates.py
Pulizia email duplicate dal database

## Note Tecniche

### Date Format
- **IMPORTANTE**: Il CMS richiede formato `DD-MM-YYYY` con trattino `-`
- Non usare `/` altrimenti la data viene salvata come 01-01-1970

### Struttura HTML CMS
- Non è una tabella `<table>`, ma lista di `<div class="item">`
- Ogni item ha `data-id` con l'article_id
- Pulsanti: approvazione (yellow), visibilità (visibility), galleria (photo_camera)

### Foto
- Solo allegati con `Content-Disposition: attachment`
- Non include immagini inline
- Upload separato nella galleria dopo creazione articolo

### Browser
- Usa Playwright per automazione
- Browser: Chromium headless
- Context persistente per sessione

## Workflow Completo

```
Email → Database → LLM → CMS (Form) → Approvazione → Galleria Foto → Notifiche
```

1. Email scaricate e salvate in DB
2. Contenuto inviato a LLM per generazione articolo
3. Articolo pubblicato su CMS con data corretta
4. Articolo approvato automaticamente
5. Foto caricate nella galleria
6. Notifiche inviate
7. Email marcata come processata

## Deploy

### Requisiti
- Python 3.12+
- PySide6 (GUI)
- playwright (browser automation)
- openai/anthropic (LLM)
- python-dotenv

### Installazione
```bash
pip install -r requirements.txt
playwright install chromium
```

### Avvio
```bash
python run.py
```
