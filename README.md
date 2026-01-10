# FLaiRIO - Email to Article Automation System

Sistema automatizzato per convertire email in articoli giornalistici e pubblicarli su CMS.

![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![PySide6](https://img.shields.io/badge/PySide6-6.7-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## 🌟 Caratteristiche

- **Monitoraggio Multi-Casella**: Monitora automaticamente più caselle email IMAP
- **Generazione Articoli con LLM**: Usa OpenAI/Anthropic per generare articoli professionali
- **Pubblicazione Automatica**: Pubblica articoli sul CMS usando Playwright
- **Gestione Duplicati**: Rileva e salta automaticamente email duplicate
- **GUI Desktop**: Interfaccia grafica completa con PySide6
- **Database SQLite**: Storico completo di email e articoli
- **Memory Management**: Ottimizzato per funzionare 24/7 senza memory leak

## 📋 Requisiti

- Python 3.12+
- Account OpenAI o Anthropic (per generazione articoli)
- Accesso IMAP alle caselle email
- Credenziali CMS

## 🚀 Installazione

### 1. Clone del repository

```bash
git clone https://github.com/DrQuatermass/FLaiRIO.git
cd FLaiRIO
```

### 2. Ambiente virtuale

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 3. Installazione dipendenze

```bash
pip install -r requirements.txt
```

### 4. Installazione browser Playwright

```bash
# Installa Chromium (base)
playwright install chromium

# OPZIONALE: Installa Chrome (consigliato per headless mode)
playwright install chrome
```

### 5. Configurazione

Crea un file `.env` nella root del progetto:

```env
# LLM Provider (openai o anthropic)
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# CMS Credentials
CMS_USERNAME=your_cms_username
CMS_PASSWORD=your_cms_password
```

## 📖 Utilizzo

### Avvio GUI

```bash
python app_gui.py
```

### Configurazione Iniziale

1. **Caselle Email**: Vai alla tab "Caselle Email" e aggiungi le tue caselle IMAP
2. **Mittenti Monitorati**: Nella tab "Impostazioni", aggiungi gli indirizzi email da monitorare automaticamente
3. **LLM Provider**: Configura le API keys per OpenAI o Anthropic
4. **CMS**: Inserisci username e password del CMS

### Workflow Automatico

1. L'app monitora automaticamente le caselle email configurate
2. Quando arriva un'email da un mittente monitorato:
   - Scarica automaticamente gli allegati
   - Genera l'articolo usando il LLM
   - Pubblica l'articolo sul CMS
3. Tutto il processo è completamente automatico

### Workflow Manuale

1. Vai alla tab "Email"
2. Clicca "Aggiorna Email" per scaricare nuove email
3. Seleziona un'email dalla lista
4. Clicca "Genera Articolo"
5. Clicca "Pubblica su CMS"

## 🔧 Configurazione Avanzata

### Intervallo di Monitoraggio

Nella tab "Impostazioni" puoi configurare:
- Intervallo controllo email (1-30 minuti)
- Modalità browser (visibile/nascosto)
- Provider LLM

### Gestione Memoria

L'app è ottimizzata per girare 24/7:
- Massimo 200 email in RAM
- Pulizia automatica articoli vecchi
- Consumo RAM costante ~2-3 MB

### Duplicati

Il sistema rileva automaticamente email duplicate basandosi su:
- Message-ID (standard RFC 5322)
- Combinazione subject+data+mittente

## 🏗️ Architettura

```
FLaiRIO/
├── app_gui.py              # GUI principale (PySide6)
├── email_processor.py      # Gestione IMAP email
├── llm_article_generator.py # Generazione articoli con LLM
├── cms_automation.py       # Pubblicazione CMS (Playwright)
├── database.py             # Database SQLite
├── main.py                 # CLI (legacy, usa app_gui.py)
└── requirements.txt        # Dipendenze Python
```

## 🐛 Troubleshooting

### Chrome non installato

Se vedi l'avviso "Chrome non installato":

```bash
playwright install chrome
```

### Errori IMAP

Verifica che:
- IMAP sia abilitato sulla casella email
- Username/password siano corretti
- La porta IMAP (993) non sia bloccata dal firewall

### Errori LLM

Verifica che:
- Le API keys siano valide
- Hai credito sufficiente sull'account
- Il provider selezionato sia corretto

## 📊 Database

Il database SQLite (`flairio.db`) contiene:

- **emails**: Tutte le email scaricate
- **articles**: Articoli generati
- **attachments**: Allegati scaricati
- **mailboxes**: Configurazione caselle email

## 🔐 Sicurezza

- Le password sono salvate in `.env` (non committato su git)
- Le credenziali CMS sono salvate in `config.json` (non committato su git)
- Nessuna password viene loggata
- Comunicazioni IMAP criptate (SSL/TLS)

## 📝 License

MIT License - vedi [LICENSE](LICENSE) per dettagli

## 🤝 Contributi

I contributi sono benvenuti! Per favore:

1. Fai fork del progetto
2. Crea un branch per la tua feature (`git checkout -b feature/AmazingFeature`)
3. Commit delle modifiche (`git commit -m 'Add some AmazingFeature'`)
4. Push al branch (`git push origin feature/AmazingFeature`)
5. Apri una Pull Request

## 📧 Contatti

Progetto: [https://github.com/DrQuatermass/FLaiRIO](https://github.com/DrQuatermass/FLaiRIO)

## 🎯 Roadmap

- [ ] Supporto per più CMS
- [ ] Editor articoli integrato
- [ ] Statistiche e analytics
- [ ] Export articoli in vari formati
- [ ] API REST per integrazione esterna
- [ ] Notifiche push/email

---

Fatto con ❤️ usando Python, PySide6 e Playwright
