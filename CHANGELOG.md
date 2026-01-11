# Changelog

Tutte le modifiche significative al progetto saranno documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.0.0/),
e questo progetto aderisce al [Semantic Versioning](https://semver.org/lang/it/).

## [1.0.0] - 2025-01-11

### 🎉 Rilascio Iniziale

#### Aggiunto
- GUI desktop completa con PySide6
- Monitoraggio automatico multi-casella email IMAP
- Generazione articoli con LLM (OpenAI/Anthropic)
- Pubblicazione automatica su CMS con Playwright
- Database SQLite per storico email/articoli
- Rilevamento automatico email duplicate
- Gestione memoria ottimizzata (limite 200 email in RAM)
- Supporto tema scuro
- Configurazione intervallo monitoraggio (1-30 minuti)
- Browser headless/visible selezionabile
- Scaricamento automatico allegati
- Visualizzazione email e articoli nell'interfaccia

#### Caratteristiche Tecniche
- Thread-safe Qt GUI
- Async Playwright per automazione browser
- Lazy loading email dal database
- Pulizia automatica memoria
- Gestione corretta chiusura Playwright
- Lock in memoria per prevenire elaborazioni duplicate
- Callback basati su email_id invece di row index

#### Documentazione
- README completo con guida installazione
- Note supporto cross-platform
- Guida configurazione Chrome/Chromium
- Documentazione struttura JSON articoli
- Report file cleanup
- Note manutenzione Playwright

#### Sicurezza
- Password in .env (non committato)
- Configurazione in config.json (non committata)
- Comunicazioni IMAP criptate SSL/TLS

---

## [Unreleased]

### Pianificato
- Editor articoli integrato
- Supporto per più CMS
- Statistiche e analytics
- Export articoli in vari formati
- API REST per integrazione esterna
- Notifiche push/email
- Sistema plugin per estensibilità

---

[1.0.0]: https://github.com/DrQuatermass/FLaiRIO/releases/tag/v1.0.0
