#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
App Desktop per gestione Email -> Articoli -> CRM
Interfaccia grafica con PySide6
"""

import sys
import os
import json
from datetime import datetime
from typing import List, Dict, Optional

# Forza UTF-8 per Windows
if sys.platform == 'win32':
    import locale
    import codecs
    # Forza console UTF-8
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    # Imposta locale UTF-8
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except:
        pass

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QPushButton,
    QLabel, QLineEdit, QListWidget, QTextEdit, QMessageBox,
    QSplitter, QHeaderView, QProgressBar, QComboBox, QGroupBox,
    QGridLayout, QCheckBox, QDialog, QFormLayout
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QColor

# Import moduli esistenti
from email_processor import EmailProcessor
from llm_article_generator import ArticleGenerator
from cms_automation import CMSPublisher
from database import EmailDatabase
from browser_manager import PlaywrightBrowserManager

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class EmailCheckThread(QThread):
    """Thread per controllare nuove email in background senza bloccare la GUI"""
    finished = Signal(list, dict)  # Lista nuove email, dict last_uid
    error = Signal(str)
    progress = Signal(str, int, int)  # messaggio, current, total

    def __init__(self, email_processors, existing_ids, last_uids_dict=None):
        super().__init__()
        self.email_processors = email_processors
        self.existing_ids = existing_ids
        self.last_uids = last_uids_dict or {}

    def run(self):
        """Esegue il controllo email in background - NON tocca il database"""
        all_new_emails = []
        updated_last_uids = {}
        total_mailboxes = len(self.email_processors)
        current = 0

        try:
            for email_addr, processor in self.email_processors.items():
                current += 1
                self.progress.emit(f"Controllo {email_addr}...", current, total_mailboxes)

                try:
                    # Verifica connessione
                    if not processor.mail:
                        if not processor.connect():
                            continue

                    # OTTIMIZZAZIONE: Usa last_uid se disponibile
                    last_uid = self.last_uids.get(email_addr, 0)

                    # Prima controlla quante email ci sono (VELOCE)
                    mailbox_status = processor.get_mailbox_status()
                    uidnext = mailbox_status.get('UIDNEXT', 0)

                    # Fast path: se non ci sono nuove email, salta il download
                    # UIDNEXT punta al prossimo UID che sarà assegnato
                    # Se last_uid >= UIDNEXT - 1, abbiamo già tutte le email
                    if last_uid > 0 and uidnext > 0 and last_uid >= uidnext - 1:
                        # Nessuna nuova email
                        print(f"[FAST] {email_addr}: nessuna nuova email (last_uid={last_uid}, uidnext={uidnext})")
                        # NON aggiornare last_uid se skippiamo - è già corretto!
                        continue

                    # Controlla nuove email con last_uid
                    print(f"[DOWNLOAD] {email_addr}: scarico da UID {last_uid + 1}...")
                    new_emails = processor.check_for_new_emails(
                        existing_ids=self.existing_ids,
                        last_uid=last_uid
                    )

                    # Trova il massimo UID tra le email scaricate
                    max_uid_downloaded = last_uid
                    if new_emails:
                        print(f"[OK] {email_addr}: trovate {len(new_emails)} nuove email")
                        # Aggiungi mailbox_account e prepara per salvataggio
                        for email in new_emails:
                            email['mailbox_account'] = email_addr
                            all_new_emails.append(email)
                            # Aggiungi agli ID esistenti per evitare duplicati
                            self.existing_ids.add(email.get('id'))
                            # Traccia il massimo UID
                            try:
                                email_uid = int(email.get('imap_id', 0))
                                if email_uid > max_uid_downloaded:
                                    max_uid_downloaded = email_uid
                            except:
                                pass

                        # Aggiorna last_uid SOLO se abbiamo scaricato email
                        if max_uid_downloaded > last_uid:
                            updated_last_uids[email_addr] = max_uid_downloaded
                            print(f"[UID] {email_addr}: aggiornamento last_uid a {max_uid_downloaded}")
                    else:
                        # Nessuna email scaricata, ma aggiorna comunque a uidnext-1
                        # (potrebbero essere tutte duplicate o filtrate)
                        if uidnext > last_uid:
                            updated_last_uids[email_addr] = uidnext - 1
                            print(f"[UID] {email_addr}: aggiornamento last_uid a {uidnext - 1} (nessuna nuova email scaricata)")

                except Exception as e:
                    print(f"[X] Errore controllo {email_addr}: {e}")

            self.finished.emit(all_new_emails, updated_last_uids)

        except Exception as e:
            self.error.emit(f"Errore generale: {str(e)}")


class EmailFetchThread(QThread):
    """Thread per recuperare email in background"""
    finished = Signal(list)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, username, password, senders, fetch_all=False):
        super().__init__()
        self.username = username
        self.password = password
        self.senders = senders
        self.fetch_all = fetch_all

    def run(self):
        try:
            import imaplib
            import email as email_lib
            from email.header import decode_header

            self.progress.emit("Connessione al server...")
            processor = EmailProcessor(self.username, self.password)

            if not processor.connect():
                self.error.emit("Errore di connessione al server IMAP")
                return

            if self.fetch_all:
                # Recupera TUTTE le email dall'INBOX
                self.progress.emit("Recupero tutte le email...")
                try:
                    processor.mail.select("INBOX")
                    status, messages = processor.mail.search(None, "ALL")

                    if status != "OK":
                        self.error.emit("Errore nella ricerca email")
                        return

                    email_ids = messages[0].split()

                    # Limita alle ultime 100 email per performance
                    email_ids = email_ids[-100:] if len(email_ids) > 100 else email_ids

                    all_emails = []
                    for email_id in reversed(email_ids):  # Più recenti prima
                        try:
                            status, msg_data = processor.mail.fetch(email_id, "(RFC822)")
                            if status != "OK":
                                continue

                            for response_part in msg_data:
                                if isinstance(response_part, tuple):
                                    msg = email_lib.message_from_bytes(response_part[1])

                                    # Decodifica correttamente mittente e oggetto usando decode_header
                                    def decode_mime_header(header_value):
                                        if not header_value:
                                            return ""
                                        decoded_parts = []
                                        for part, encoding in decode_header(header_value):
                                            if isinstance(part, bytes):
                                                try:
                                                    decoded_parts.append(part.decode(encoding or 'utf-8', errors='replace'))
                                                except:
                                                    decoded_parts.append(part.decode('utf-8', errors='replace'))
                                            else:
                                                decoded_parts.append(str(part))
                                        return ''.join(decoded_parts)

                                    from_header = decode_mime_header(msg.get("From", ""))
                                    subject_header = decode_mime_header(msg.get("Subject", ""))
                                    to_header = decode_mime_header(msg.get("To", ""))

                                    email_info = {
                                        'id': email_id.decode(),
                                        'from': from_header,
                                        'subject': subject_header,
                                        'date': msg.get("Date", ""),
                                        'body': processor.get_email_body(msg),
                                        'to': to_header,
                                        'attachments': processor.get_attachments(msg),  # Estrai allegati
                                    }
                                    all_emails.append(email_info)
                        except:
                            continue

                    processor.disconnect()
                    self.finished.emit(all_emails)

                except Exception as e:
                    self.error.emit(str(e))
            else:
                # Recupera solo email da mittenti monitorati
                self.progress.emit("Recupero email da mittenti monitorati...")
                filtered = processor.filter_emails_by_multiple_senders(
                    self.senders,
                    only_unseen=False
                )

                # Converti in lista piatta
                all_emails = []
                for sender, emails_list in filtered.items():
                    all_emails.extend(emails_list)

                processor.disconnect()
                self.finished.emit(all_emails)

        except Exception as e:
            self.error.emit(str(e))


class ArticleGeneratorThread(QThread):
    """Thread per generare articolo in background"""
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, email_data, provider, format_mode=False):
        super().__init__()
        self.email_data = email_data
        self.provider = provider
        self.format_mode = format_mode

    def run(self):
        try:
            if self.format_mode:
                self.progress.emit("Impaginazione articolo con LLM...")
            else:
                self.progress.emit("Generazione articolo con LLM...")

            generator = ArticleGenerator(provider=self.provider)

            # Passa il flag format_mode al generator
            articles = generator.batch_generate_articles(
                [self.email_data],
                format_mode=self.format_mode
            )

            if articles:
                self.finished.emit(articles[0])
            else:
                self.error.emit("Nessun articolo generato")

        except Exception as e:
            self.error.emit(str(e))


class CMSPublishThread(QThread):
    """Thread per pubblicare articolo sul CMS in background"""
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, article, cms_username, cms_password, headless=False):
        super().__init__()
        self.article = article
        self.cms_username = cms_username
        self.cms_password = cms_password
        self.headless = headless

    def run(self):
        import asyncio
        loop = None
        try:
            mode = "nascosto" if self.headless else "visibile"
            self.progress.emit(f"Avvio browser ({mode}) per pubblicazione...")

            # Crea event loop per thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Esegui pubblicazione
            result = loop.run_until_complete(self._publish())

            self.finished.emit(result)

        except Exception as e:
            import traceback
            print(f"[CMSThread] Errore: {e}")
            traceback.print_exc()
            self.error.emit(f"Errore pubblicazione CMS: {str(e)}")

        finally:
            # Chiudi il loop in modo sicuro
            if loop:
                try:
                    # Aspetta che tutti i task pendenti completino
                    pending = asyncio.all_tasks(loop)
                    if pending:
                        print(f"[CMSThread] Attendo {len(pending)} task pendenti...")
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

                    # Chiudi loop
                    loop.close()
                    print(f"[CMSThread] Event loop chiuso correttamente")
                except Exception as e:
                    print(f"[CMSThread] Errore chiusura loop: {e}")

    async def _publish(self):
        """Metodo async per pubblicazione"""
        publisher = CMSPublisher(self.cms_username, self.cms_password)

        try:
            self.progress.emit("Login al CMS...")
            await publisher.start(headless=self.headless)

            self.progress.emit("Pubblicazione articolo in corso...")
            result = await publisher.publish_article(self.article)

            # Se pubblicazione riuscita E ci sono foto, caricale nella galleria
            if result.get('success') and result.get('article_id'):
                foto_path = self.article.get('foto_path')

                if foto_path:
                    # Supporto singola foto o lista
                    photo_paths = [foto_path] if isinstance(foto_path, str) else foto_path

                    # Converti a path assoluti
                    photo_paths = [os.path.abspath(p) if not os.path.isabs(p) else p for p in photo_paths]

                    # Filtra solo file esistenti
                    photo_paths = [p for p in photo_paths if os.path.exists(p)]

                    if photo_paths:
                        self.progress.emit(f"Caricamento {len(photo_paths)} foto nella galleria...")
                        print(f"[GUI] Avvio caricamento {len(photo_paths)} foto per article_id: {result['article_id']}")

                        try:
                            gallery_result = await publisher.upload_photos_to_gallery(
                                result['article_id'],
                                photo_paths
                            )

                            if gallery_result.get('success'):
                                print(f"[GUI] ✓ {gallery_result['uploaded_count']}/{gallery_result['total_photos']} foto caricate")
                                result['photos_uploaded'] = gallery_result['uploaded_count']
                            else:
                                error_msg = gallery_result.get('error', 'Errore sconosciuto')
                                print(f"[GUI] ✗ Errore caricamento foto: {error_msg}")
                                result['photos_uploaded'] = 0

                        except Exception as e:
                            print(f"[GUI] ✗ ERRORE durante caricamento foto: {e}")
                            import traceback
                            traceback.print_exc()
                            result['photos_uploaded'] = 0
                    else:
                        print(f"[GUI] Nessuna foto valida da caricare")
                        result['photos_uploaded'] = 0
                else:
                    print(f"[GUI] Articolo senza foto")
                    result['photos_uploaded'] = 0
            else:
                print(f"[GUI] Skip upload foto (success={result.get('success')}, article_id={result.get('article_id')})")
                result['photos_uploaded'] = 0

            self.progress.emit("Chiusura browser...")
            await publisher.close()
            return result

        except Exception as e:
            try:
                await publisher.close()
            except:
                pass  # Ignora errori durante chiusura in caso di eccezione
            raise e


class MainWindow(QMainWindow):
    """Finestra principale dell'applicazione"""

    def set_application_icon(self):
        """Carica icona FLaiRIO (SVG o PNG)"""
        try:
            from PySide6.QtGui import QIcon
            from PySide6.QtSvg import QSvgRenderer

            # Prova prima SVG, poi PNG come fallback
            svg_path = os.path.join(os.path.dirname(__file__), "Flairio-icon.svg")
            png_path = os.path.join(os.path.dirname(__file__), "Flairio-icon.png")

            if os.path.exists(svg_path):
                # Usa SVG (scalabile)
                icon = QIcon(svg_path)
                self.setWindowIcon(icon)
                QApplication.instance().setWindowIcon(icon)
                print(f"[OK] Icona SVG caricata: {svg_path}")
            elif os.path.exists(png_path):
                # Fallback a PNG
                icon = QIcon(png_path)
                self.setWindowIcon(icon)
                QApplication.instance().setWindowIcon(icon)
                print(f"[OK] Icona PNG caricata: {png_path}")
            else:
                print(f"[!] Icona non trovata (cercato: {svg_path} e {png_path})")
                # Fallback: icona generata
                self._create_fallback_icon()

        except Exception as e:
            print(f"[!] Errore caricamento icona: {e}")
            self._create_fallback_icon()

    def _create_fallback_icon(self):
        """Crea icona fallback se PNG non disponibile"""
        try:
            from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
            from PySide6.QtCore import Qt, QRectF

            icon = QIcon()
            for size in [16, 24, 32, 48, 64, 128, 256]:
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.GlobalColor.transparent)

                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                # Sfondo rosso
                painter.setBrush(QColor("#FF0000"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(0, 0, size, size)

                # Testo "F" bianco
                painter.setPen(QColor("white"))
                font = QFont("Arial", int(size * 0.6), QFont.Weight.Bold)
                painter.setFont(font)
                painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "F")

                painter.end()
                icon.addPixmap(pixmap)

            self.setWindowIcon(icon)
            QApplication.instance().setWindowIcon(icon)
            print("[OK] Icona fallback generata")
        except Exception as e:
            print(f"[!] Errore icona fallback: {e}")

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FLaiRIO - Email to Article Manager")
        self.setGeometry(100, 100, 1400, 900)

        # Dati
        self.config = self.load_config()
        self.emails = []
        self.selected_email = None
        self.generated_articles = {}  # email_id -> article

        # Mittenti monitorati per auto-elaborazione
        self.monitored_senders = self.config.get('email_filters', {}).get('mittenti_monitorati', [])
        print(f"[AUTO] Mittenti monitorati: {self.monitored_senders}")

        # Email processor (connessione persistente)
        self.email_processor = None

        # Database SQLite
        self.db = EmailDatabase()
        print(f"[DB] Statistiche: {self.db.get_stats()}")

        # Imposta icona applicazione
        self.set_application_icon()

        # Setup UI
        self.setup_ui()

        # Carica email dal database
        self.load_emails_from_db()

        # Carica mittenti salvati
        self.load_senders()

        # Avvia monitoraggio automatico
        self.start_auto_monitoring()

        # Verifica browser Chrome per headless mode
        self.check_chrome_installation()

    def load_config(self):
        """Carica configurazione"""
        try:
            with open("config.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {
                "email_filters": {"mittenti_monitorati": []},
                "llm_settings": {},
                "crm_settings": {}
            }

    def save_config(self):
        """Salva configurazione"""
        try:
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Errore", f"Errore salvataggio config: {e}")

    def on_headless_changed(self, index):
        """Callback quando cambia l'impostazione headless"""
        headless = (index == 1)  # 0=Visibile, 1=Nascosto

        # Assicura che 'cms' esista in config
        if 'cms' not in self.config:
            self.config['cms'] = {}

        # Salva in config
        self.config['cms']['headless'] = headless
        self.save_config()

        print(f"[CONFIG] Modalità browser salvata: {'Nascosto' if headless else 'Visibile'}")

    def on_auto_mode_changed(self, index):
        """Callback quando cambia la modalità di auto-elaborazione"""
        if 'auto_processing' not in self.config:
            self.config['auto_processing'] = {}

        mode = 'llm' if index == 0 else 'format_only'
        self.config['auto_processing']['mode'] = mode
        self.save_config()

        mode_name = "Elabora con LLM" if mode == 'llm' else "Solo impagina e pubblica"
        print(f"[CONFIG] Modalità auto-elaborazione: {mode_name}")

    def on_monitor_interval_changed(self, index):
        """Callback quando cambia l'intervallo di monitoraggio"""
        # Assicura che 'monitor' esista in config
        if 'monitor' not in self.config:
            self.config['monitor'] = {}

        # Salva in config
        self.config['monitor']['interval_index'] = index
        self.save_config()

        intervals = ["1 minuto", "2 minuti", "5 minuti", "10 minuti", "15 minuti", "30 minuti"]
        print(f"[CONFIG] Intervallo monitoraggio salvato: {intervals[index]}")

        # Riavvia il timer con il nuovo intervallo (se già attivo)
        if hasattr(self, 'email_timer') and self.email_timer:
            # Converti indice in minuti: [1, 2, 5, 10, 15, 30]
            interval_minutes = [1, 2, 5, 10, 15, 30][index]
            interval_ms = interval_minutes * 60 * 1000
            self.email_timer.setInterval(interval_ms)
            print(f"[CONFIG] Timer aggiornato: {interval_minutes} minuti ({interval_ms} ms)")

    def check_chrome_installation(self):
        """Verifica se Chrome è installato e avvisa l'utente se manca"""
        if not PlaywrightBrowserManager.is_chrome_installed():
            # Mostra avviso solo se headless è abilitato
            headless = self.config.get('cms', {}).get('headless', False)
            if headless:
                QMessageBox.information(
                    self,
                    'Chrome non installato',
                    'Chrome per Playwright non è installato.\n\n'
                    'Il sistema userà Chromium come fallback, ma potrebbe essere\n'
                    'rilevato come bot dal CMS in modalità headless.\n\n'
                    'Puoi installare Chrome dalla sezione Impostazioni → CMS.',
                    QMessageBox.StandardButton.Ok
                )

    def update_chrome_status(self):
        """Aggiorna la label con lo stato di Chrome"""
        if PlaywrightBrowserManager.is_chrome_installed():
            self.chrome_status_label.setText("✓ Chrome installato")
            self.chrome_status_label.setStyleSheet("color: green;")
        else:
            self.chrome_status_label.setText("✗ Chrome non installato (usando Chromium)")
            self.chrome_status_label.setStyleSheet("color: orange;")

    def install_chrome(self):
        """Installa Chrome per Playwright"""
        success = PlaywrightBrowserManager.install_chrome_with_ui(self)
        if success:
            self.update_chrome_status()

    def setup_ui(self):
        """Configura interfaccia utente"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Header con logo centrato
        header_layout = QHBoxLayout()
        header_layout.addStretch(1)  # Spazio elastico a sinistra

        # Logo - prova SVG, poi PNG, fallback a testo
        svg_path = os.path.join(os.path.dirname(__file__), "Flairio-logo.svg")
        png_path = os.path.join(os.path.dirname(__file__), "Flairio-logo.png")
        logo_loaded = False

        # Prova prima SVG
        if os.path.exists(svg_path):
            try:
                from PySide6.QtSvg import QSvgRenderer
                from PySide6.QtGui import QPixmap, QPainter
                from PySide6.QtCore import QSize

                # Renderizza SVG a QPixmap mantenendo aspect ratio
                renderer = QSvgRenderer(svg_path)

                # Ottieni dimensioni native SVG
                default_size = renderer.defaultSize()
                aspect_ratio = default_size.width() / default_size.height()

                # Calcola dimensioni mantenendo aspect ratio (larghezza fissa 200px)
                target_width = 200
                target_height = int(target_width / aspect_ratio)

                pixmap = QPixmap(QSize(target_width, target_height))
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()

                logo_label = QLabel()
                logo_label.setPixmap(pixmap)
                header_layout.addWidget(logo_label)
                logo_loaded = True
                print(f"[OK] Logo SVG caricato: {svg_path} ({target_width}x{target_height})")
            except Exception as e:
                print(f"[!] Errore caricamento logo SVG: {e}")

        # Fallback a PNG
        if not logo_loaded and os.path.exists(png_path):
            try:
                from PySide6.QtGui import QPixmap
                logo_pixmap = QPixmap(png_path)
                if not logo_pixmap.isNull():
                    # Scala mantenendo aspect ratio
                    scaled_logo = logo_pixmap.scaled(250, 60, Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation)
                    logo_label = QLabel()
                    logo_label.setPixmap(scaled_logo)
                    header_layout.addWidget(logo_label)
                    logo_loaded = True
                    print(f"[OK] Logo PNG caricato: {png_path}")
            except Exception as e:
                print(f"[!] Errore caricamento logo PNG: {e}")

        # Fallback a logo testuale
        if not logo_loaded:
            logo_label = QLabel("FLaiRIO")
            logo_font = QFont("Segoe UI", 32, QFont.Weight.Bold)
            logo_label.setFont(logo_font)
            logo_label.setStyleSheet("""
                QLabel {
                    color: #FF0000;
                    padding: 8px 15px;
                    background: white;
                    border: 3px solid #FF0000;
                }
            """)
            header_layout.addWidget(logo_label)
            print("[OK] Logo testuale fallback caricato")

        header_layout.addStretch(1)  # Spazio elastico a destra (uguale)
        layout.addLayout(header_layout)

        # Tab widget principale
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Tab 1: Gestione Email
        tab_emails = self.create_emails_tab()
        tabs.addTab(tab_emails, "Email & Articoli")

        # Tab 2: Caselle Email
        tab_mailboxes = self.create_mailboxes_tab()
        tabs.addTab(tab_mailboxes, "Caselle Email")

        # Tab 3: Configurazione Mittenti
        tab_senders = self.create_senders_tab()
        tabs.addTab(tab_senders, "Mittenti Monitorati")

        # Tab 4: Impostazioni
        tab_settings = self.create_settings_tab()
        tabs.addTab(tab_settings, "Impostazioni")

        # Status bar
        self.statusBar().showMessage("Pronto")

    def create_emails_tab(self):
        """Crea tab gestione email"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Pulsanti refresh
        btn_layout = QHBoxLayout()
        self.btn_refresh_all = QPushButton("🔄 Tutte le Email")
        self.btn_refresh_all.clicked.connect(lambda: self.refresh_emails(fetch_all=True))
        btn_layout.addWidget(self.btn_refresh_all)

        self.btn_refresh_monitored = QPushButton("🎯 Solo Mittenti Monitorati")
        self.btn_refresh_monitored.clicked.connect(lambda: self.refresh_emails(fetch_all=False))
        btn_layout.addWidget(self.btn_refresh_monitored)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Splitter verticale
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Tabella email (sopra)
        self.email_table = QTableWidget()
        self.email_table.setColumnCount(7)
        self.email_table.setHorizontalHeaderLabels([
            "Casella", "Mittente", "Oggetto", "Data", "Stato", "Azioni", "ID"
        ])

        # Imposta larghezze colonne per migliore leggibilità
        header = self.email_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)  # Casella
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)  # Mittente
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)       # Oggetto (stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Data
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Stato
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)         # Azioni

        # Larghezze iniziali
        self.email_table.setColumnWidth(0, 180)  # Casella
        self.email_table.setColumnWidth(1, 250)  # Mittente
        self.email_table.setColumnWidth(5, 150)  # Azioni fissa

        self.email_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.email_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.email_table.itemSelectionChanged.connect(self.on_email_selected)
        self.email_table.setColumnHidden(6, True)  # Nascondi colonna ID

        # Abilita word wrap per oggetto
        self.email_table.setWordWrap(True)

        splitter.addWidget(self.email_table)

        # Area preview articolo (sotto)
        preview_group = QGroupBox("Anteprima Articolo")
        preview_layout = QVBoxLayout(preview_group)

        self.article_preview = QTextEdit()
        self.article_preview.setReadOnly(True)
        preview_layout.addWidget(self.article_preview)

        # Pulsanti azioni articolo
        article_btn_layout = QHBoxLayout()

        # Pulsante "Impagina e Pubblica" - per pubblicazione diretta senza LLM
        self.btn_format_publish = QPushButton("📄 Impagina e Pubblica")
        self.btn_format_publish.clicked.connect(self.format_and_publish_email)
        self.btn_format_publish.setEnabled(False)
        self.btn_format_publish.setToolTip("Pubblica il contenuto della mail direttamente senza elaborazione LLM")
        article_btn_layout.addWidget(self.btn_format_publish)

        # Pulsante "Pubblica su CRM" - per articoli già generati
        self.btn_publish = QPushButton("📤 Pubblica su CRM")
        self.btn_publish.clicked.connect(self.publish_article)
        self.btn_publish.setEnabled(False)
        article_btn_layout.addWidget(self.btn_publish)

        article_btn_layout.addStretch()
        preview_layout.addLayout(article_btn_layout)

        splitter.addWidget(preview_group)
        splitter.setSizes([400, 300])

        layout.addWidget(splitter)

        return widget

    def create_mailboxes_tab(self):
        """Crea tab gestione caselle email multiple"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Titolo
        title = QLabel("Gestione Caselle Email")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Form per aggiungere casella
        form_group = QGroupBox("Aggiungi Nuova Casella")
        form_layout = QGridLayout(form_group)

        # Email
        form_layout.addWidget(QLabel("Email:"), 0, 0)
        self.mailbox_email_input = QLineEdit()
        self.mailbox_email_input.setPlaceholderText("casella@dominio.it")
        form_layout.addWidget(self.mailbox_email_input, 0, 1)

        # Password
        form_layout.addWidget(QLabel("Password:"), 1, 0)
        self.mailbox_password_input = QLineEdit()
        self.mailbox_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.mailbox_password_input.setPlaceholderText("Password email")
        form_layout.addWidget(self.mailbox_password_input, 1, 1)

        # Server IMAP
        form_layout.addWidget(QLabel("Server IMAP:"), 2, 0)
        self.mailbox_server_input = QLineEdit()
        self.mailbox_server_input.setText("imap.register.it")
        form_layout.addWidget(self.mailbox_server_input, 2, 1)

        # Porta
        form_layout.addWidget(QLabel("Porta:"), 3, 0)
        self.mailbox_port_input = QLineEdit()
        self.mailbox_port_input.setText("993")
        form_layout.addWidget(self.mailbox_port_input, 3, 1)

        # Pulsanti
        btn_layout = QHBoxLayout()
        btn_add_mailbox = QPushButton("➕ Aggiungi Casella")
        btn_add_mailbox.clicked.connect(self.add_mailbox)
        btn_layout.addWidget(btn_add_mailbox)

        btn_test_connection = QPushButton("🔌 Test Connessione")
        btn_test_connection.clicked.connect(self.test_mailbox_connection)
        btn_layout.addWidget(btn_test_connection)

        form_layout.addLayout(btn_layout, 4, 0, 1, 2)
        layout.addWidget(form_group)

        # Tabella caselle configurate
        self.mailbox_table = QTableWidget()
        self.mailbox_table.setColumnCount(5)
        self.mailbox_table.setHorizontalHeaderLabels(["Email", "Server IMAP", "Porta", "Attiva", "Azioni"])
        self.mailbox_table.horizontalHeader().setStretchLastSection(False)
        self.mailbox_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.mailbox_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.mailbox_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.mailbox_table)

        # Carica caselle dal database
        self.load_mailboxes()

        return widget

    def create_senders_tab(self):
        """Crea tab mittenti monitorati"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Titolo
        title = QLabel("Mittenti Email Monitorati")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Layout per aggiungere mittente
        add_layout = QHBoxLayout()
        self.sender_input = QLineEdit()
        self.sender_input.setPlaceholderText("Inserisci email mittente (es. ufficiostampa@comune.it)")
        add_layout.addWidget(self.sender_input)

        btn_add_sender = QPushButton("➕ Aggiungi")
        btn_add_sender.clicked.connect(self.add_sender)
        add_layout.addWidget(btn_add_sender)
        layout.addLayout(add_layout)

        # Lista mittenti
        self.sender_list = QListWidget()
        layout.addWidget(self.sender_list)

        # Pulsanti rimozione
        btn_layout = QHBoxLayout()

        btn_remove_sender = QPushButton("➖ Rimuovi Selezionato")
        btn_remove_sender.clicked.connect(self.remove_sender)
        btn_layout.addWidget(btn_remove_sender)

        btn_remove_all = QPushButton("🗑️ Elimina Tutti")
        btn_remove_all.clicked.connect(self.remove_all_senders)
        btn_layout.addWidget(btn_remove_all)

        layout.addLayout(btn_layout)

        return widget

    def create_settings_tab(self):
        """Crea tab impostazioni completo"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # === IMPOSTAZIONI LLM ===
        llm_group = QGroupBox("Impostazioni LLM")
        llm_layout = QVBoxLayout(llm_group)

        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["openai", "anthropic", "ollama"])
        self.provider_combo.setCurrentText(os.getenv("LLM_PROVIDER", "openai"))
        provider_layout.addWidget(self.provider_combo)
        provider_layout.addStretch()
        llm_layout.addLayout(provider_layout)

        # API Key OpenAI
        openai_layout = QHBoxLayout()
        openai_layout.addWidget(QLabel("OpenAI API Key:"))
        self.openai_key_input = QLineEdit()
        self.openai_key_input.setText(os.getenv("OPENAI_API_KEY", ""))
        self.openai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key_input.setPlaceholderText("sk-proj-...")
        openai_layout.addWidget(self.openai_key_input)
        llm_layout.addLayout(openai_layout)

        # API Key Anthropic
        anthropic_layout = QHBoxLayout()
        anthropic_layout.addWidget(QLabel("Anthropic API Key:"))
        self.anthropic_key_input = QLineEdit()
        self.anthropic_key_input.setText(os.getenv("ANTHROPIC_API_KEY", ""))
        self.anthropic_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_key_input.setPlaceholderText("sk-ant-...")
        anthropic_layout.addWidget(self.anthropic_key_input)
        llm_layout.addLayout(anthropic_layout)

        layout.addWidget(llm_group)

        # === CREDENZIALI CMS VOCE.IT ===
        cms_group = QGroupBox("Credenziali CMS Voce.it")
        cms_layout = QVBoxLayout(cms_group)

        cms_user_layout = QHBoxLayout()
        cms_user_layout.addWidget(QLabel("Username CMS:"))
        self.cms_user_input = QLineEdit()
        self.cms_user_input.setText(os.getenv("CMS_USERNAME", ""))
        self.cms_user_input.setPlaceholderText("SRinaldi")
        cms_user_layout.addWidget(self.cms_user_input)
        cms_layout.addLayout(cms_user_layout)

        cms_pass_layout = QHBoxLayout()
        cms_pass_layout.addWidget(QLabel("Password CMS:"))
        self.cms_pass_input = QLineEdit()
        self.cms_pass_input.setText(os.getenv("CMS_PASSWORD", ""))
        self.cms_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.cms_pass_input.setPlaceholderText("Password CMS")
        cms_pass_layout.addWidget(self.cms_pass_input)
        cms_layout.addLayout(cms_pass_layout)

        # Opzione Headless
        headless_layout = QHBoxLayout()
        headless_layout.addWidget(QLabel("Modalità Browser:"))
        self.headless_combo = QComboBox()
        self.headless_combo.addItems(["Visibile (headless=False)", "Nascosto (headless=True)"])
        # Carica da config
        headless_saved = self.config.get('cms', {}).get('headless', False)
        self.headless_combo.setCurrentIndex(1 if headless_saved else 0)
        # Salva quando cambia
        self.headless_combo.currentIndexChanged.connect(self.on_headless_changed)
        headless_layout.addWidget(self.headless_combo)
        headless_layout.addStretch()
        cms_layout.addLayout(headless_layout)

        # Modalità auto-elaborazione
        auto_mode_layout = QHBoxLayout()
        auto_mode_layout.addWidget(QLabel("Modalità auto-elaborazione:"))
        self.auto_mode_combo = QComboBox()
        self.auto_mode_combo.addItems([
            "Elabora con LLM (default)",
            "Solo impagina e pubblica"
        ])
        # Carica da config
        saved_mode = self.config.get('auto_processing', {}).get('mode', 'llm')
        self.auto_mode_combo.setCurrentIndex(0 if saved_mode == 'llm' else 1)
        self.auto_mode_combo.currentIndexChanged.connect(self.on_auto_mode_changed)
        self.auto_mode_combo.setToolTip(
            "LLM: Elabora le email con intelligenza artificiale prima della pubblicazione\n"
            "Impagina: Pubblica direttamente il contenuto della mail senza elaborazione"
        )
        auto_mode_layout.addWidget(self.auto_mode_combo)
        auto_mode_layout.addStretch()
        cms_layout.addLayout(auto_mode_layout)

        # Pulsante installazione Chrome
        chrome_layout = QHBoxLayout()
        self.chrome_status_label = QLabel()
        self.update_chrome_status()
        chrome_layout.addWidget(self.chrome_status_label)

        self.install_chrome_btn = QPushButton("Installa/Aggiorna Chrome")
        self.install_chrome_btn.setMaximumWidth(200)
        self.install_chrome_btn.clicked.connect(self.install_chrome)
        chrome_layout.addWidget(self.install_chrome_btn)
        chrome_layout.addStretch()
        cms_layout.addLayout(chrome_layout)

        layout.addWidget(cms_group)

        # === MONITORAGGIO AUTOMATICO ===
        monitor_group = QGroupBox("Monitoraggio Automatico Email")
        monitor_layout = QVBoxLayout(monitor_group)

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Controlla nuove email ogni:"))
        self.monitor_interval_combo = QComboBox()
        self.monitor_interval_combo.addItems([
            "1 minuto",
            "2 minuti",
            "5 minuti",
            "10 minuti",
            "15 minuti",
            "30 minuti"
        ])
        # Carica da config, default: 10 minuti (indice 3)
        saved_interval_index = self.config.get('monitor', {}).get('interval_index', 3)
        self.monitor_interval_combo.setCurrentIndex(saved_interval_index)
        # Salva quando cambia
        self.monitor_interval_combo.currentIndexChanged.connect(self.on_monitor_interval_changed)
        interval_layout.addWidget(self.monitor_interval_combo)
        interval_layout.addStretch()
        monitor_layout.addLayout(interval_layout)

        monitor_info = QLabel("Il monitoraggio si avvia automaticamente all'apertura dell'app.\nControllerà solo le email NON LETTE.")
        monitor_info.setStyleSheet("color: #666; font-size: 11px;")
        monitor_info.setWordWrap(True)
        monitor_layout.addWidget(monitor_info)

        layout.addWidget(monitor_group)

        # === NOTIFICHE ===
        notif_group = QGroupBox("Notifiche Pubblicazione Automatica")
        notif_layout = QVBoxLayout(notif_group)

        # Email Notifications
        email_notif_check = QCheckBox("Abilita notifiche Email")
        self.email_notif_enabled = email_notif_check
        email_notif_check.setChecked(self.config.get('notifications', {}).get('email', {}).get('enabled', False))
        notif_layout.addWidget(email_notif_check)

        # Email recipients
        email_recipients_layout = QHBoxLayout()
        email_recipients_layout.addWidget(QLabel("Email destinatari:"))
        self.email_notif_recipients = QLineEdit()
        saved_recipients = self.config.get('notifications', {}).get('email', {}).get('to_emails', [])
        self.email_notif_recipients.setText(', '.join(saved_recipients) if saved_recipients else '')
        self.email_notif_recipients.setPlaceholderText("email1@example.com, email2@example.com")
        self.email_notif_recipients.setToolTip("Inserisci uno o più indirizzi email separati da virgola")
        email_recipients_layout.addWidget(self.email_notif_recipients)
        notif_layout.addLayout(email_recipients_layout)

        # Test Email button
        test_email_layout = QHBoxLayout()
        test_email_btn = QPushButton("📧 Invia Email di Test")
        test_email_btn.setMaximumWidth(200)
        test_email_btn.clicked.connect(self.test_email_notification)
        test_email_layout.addWidget(test_email_btn)
        test_email_layout.addStretch()
        notif_layout.addLayout(test_email_layout)

        notif_layout.addSpacing(10)

        # Telegram Notifications
        telegram_notif_check = QCheckBox("Abilita notifiche Telegram")
        self.telegram_notif_enabled = telegram_notif_check
        telegram_notif_check.setChecked(self.config.get('notifications', {}).get('telegram', {}).get('enabled', False))
        notif_layout.addWidget(telegram_notif_check)

        # Telegram bot token
        telegram_token_layout = QHBoxLayout()
        telegram_token_layout.addWidget(QLabel("Bot Token:"))
        self.telegram_bot_token = QLineEdit()
        self.telegram_bot_token.setText(self.config.get('notifications', {}).get('telegram', {}).get('bot_token', ''))
        self.telegram_bot_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.telegram_bot_token.setPlaceholderText("123456:ABC-DEF...")
        telegram_token_layout.addWidget(self.telegram_bot_token)
        notif_layout.addLayout(telegram_token_layout)

        # Telegram chat IDs
        telegram_chat_layout = QHBoxLayout()
        telegram_chat_layout.addWidget(QLabel("Chat ID(s):"))
        self.telegram_chat_ids = QLineEdit()
        saved_chat_ids = self.config.get('notifications', {}).get('telegram', {}).get('chat_ids', [])
        self.telegram_chat_ids.setText(', '.join(saved_chat_ids) if saved_chat_ids else '')
        self.telegram_chat_ids.setPlaceholderText("123456789, 987654321")
        self.telegram_chat_ids.setToolTip("Inserisci uno o più Chat ID separati da virgola")
        telegram_chat_layout.addWidget(self.telegram_chat_ids)
        notif_layout.addLayout(telegram_chat_layout)

        # Test Telegram button
        test_telegram_layout = QHBoxLayout()
        test_telegram_btn = QPushButton("📱 Invia Test Telegram")
        test_telegram_btn.setMaximumWidth(200)
        test_telegram_btn.clicked.connect(self.test_telegram_notification)
        test_telegram_layout.addWidget(test_telegram_btn)
        test_telegram_layout.addStretch()
        notif_layout.addLayout(test_telegram_layout)

        # Info Telegram
        telegram_info = QLabel(
            "Come ottenere Bot Token e Chat ID:\n"
            "1. Cerca @BotFather su Telegram e crea un bot con /newbot\n"
            "2. Copia il token ricevuto\n"
            "3. Cerca @userinfobot su Telegram per ottenere il tuo Chat ID"
        )
        telegram_info.setStyleSheet("color: #666; font-size: 11px;")
        telegram_info.setWordWrap(True)
        notif_layout.addWidget(telegram_info)

        layout.addWidget(notif_group)

        # === BOTTONE SALVA ===
        save_button_layout = QHBoxLayout()
        save_button_layout.addStretch()
        self.save_settings_btn = QPushButton("💾 Salva Impostazioni")
        self.save_settings_btn.clicked.connect(self.save_settings)
        self.save_settings_btn.setMinimumWidth(200)
        save_button_layout.addWidget(self.save_settings_btn)
        save_button_layout.addStretch()
        layout.addLayout(save_button_layout)

        # Info
        info_label = QLabel(
            "[!] Le credenziali vengono salvate nel file .env\n"
            "Riavvia l'applicazione dopo aver modificato le impostazioni."
        )
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        return widget

    def save_settings(self):
        """Salva impostazioni nel file .env"""
        try:
            # Leggi .env esistente
            env_path = '.env'
            env_lines = []

            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    env_lines = f.readlines()

            # Aggiorna valori (le credenziali email sono gestite in "Caselle Email")
            settings = {
                'LLM_PROVIDER': self.provider_combo.currentText(),
                'OPENAI_API_KEY': self.openai_key_input.text().strip(),
                'ANTHROPIC_API_KEY': self.anthropic_key_input.text().strip(),
                'CMS_USERNAME': self.cms_user_input.text().strip(),
                'CMS_PASSWORD': self.cms_pass_input.text().strip(),
            }

            # Crea nuovo contenuto .env
            new_env = []
            updated_keys = set()

            for line in env_lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    new_env.append(line)
                    continue

                key = line.split('=')[0]
                if key in settings:
                    new_env.append(f"{key}={settings[key]}")
                    updated_keys.add(key)
                else:
                    new_env.append(line)

            # Aggiungi chiavi mancanti
            for key, value in settings.items():
                if key not in updated_keys and value:
                    new_env.append(f"{key}={value}")

            # Scrivi .env
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_env) + '\n')

            # Aggiorna variabili ambiente in memoria
            for key, value in settings.items():
                if value:
                    os.environ[key] = value

            # Salva configurazioni notifiche in config.json
            self._save_notification_config()

            QMessageBox.information(
                self, "Successo",
                "Impostazioni salvate correttamente!\n\n"
                "Alcune modifiche potrebbero richiedere il riavvio dell'applicazione."
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Errore",
                f"Errore durante il salvataggio:\n{str(e)}"
            )

    def _save_notification_config(self):
        """Salva configurazioni notifiche nel config.json"""
        try:
            # Parse email recipients
            email_recipients_text = self.email_notif_recipients.text().strip()
            email_recipients = [e.strip() for e in email_recipients_text.split(',') if e.strip()] if email_recipients_text else []

            # Parse telegram chat IDs
            telegram_chat_ids_text = self.telegram_chat_ids.text().strip()
            telegram_chat_ids = [c.strip() for c in telegram_chat_ids_text.split(',') if c.strip()] if telegram_chat_ids_text else []

            # Ottieni credenziali SMTP dalla prima casella disponibile (per test email)
            smtp_config = {}
            mailboxes = self.db.get_all_mailboxes(only_enabled=True)

            print(f"[DEBUG] Mailboxes recuperate dal DB: {len(mailboxes) if mailboxes else 0}")
            if mailboxes:
                first_mailbox = mailboxes[0]
                print(f"[DEBUG] Prima mailbox keys: {list(first_mailbox.keys())}")
                print(f"[DEBUG] Prima mailbox values (password nascosta): {dict((k, v if k != 'password' else '***') for k, v in first_mailbox.items())}")

                # Determina SMTP server e porta in base al provider
                imap_server = first_mailbox.get('imap_server', 'imap.gmail.com')
                email_address = first_mailbox.get('email_address', '')
                password = first_mailbox.get('password', '')

                # Mappatura speciale per provider conosciuti
                if 'register.it' in imap_server:
                    # Register.it usa server dedicato authsmtp.securemail.pro
                    smtp_server = 'authsmtp.securemail.pro'
                    smtp_port = 465  # Porta SSL Register.it
                    print(f"[DEBUG] Provider Register.it rilevato - usando authsmtp.securemail.pro:465")
                elif 'gmail.com' in imap_server:
                    smtp_server = 'smtp.gmail.com'
                    smtp_port = 587
                    print(f"[DEBUG] Provider Gmail rilevato - usando smtp.gmail.com:587")
                else:
                    # Default: sostituisci imap. con smtp.
                    smtp_server = imap_server.replace('imap.', 'smtp.')
                    smtp_port = 587
                    print(f"[DEBUG] Provider generico - usando {smtp_server}:587")

                print(f"[DEBUG] IMAP: {imap_server} → SMTP: {smtp_server}:{smtp_port}")
                print(f"[DEBUG] Email: {email_address}, Password presente: {bool(password)}")

                smtp_config = {
                    'smtp_server': smtp_server,
                    'smtp_port': smtp_port,
                    'smtp_username': email_address,
                    'smtp_password': password,
                    'from_email': email_address
                }
                print(f"[CONFIG] SMTP notifiche: {email_address}")
                print(f"[DEBUG] smtp_config: smtp_server={smtp_config['smtp_server']}, username={smtp_config['smtp_username']}, has_password={bool(smtp_config['smtp_password'])}")
            else:
                print(f"[CONFIG] Warning: Nessuna casella email configurata")

            # Prepara configurazione notifiche
            notifications_config = {
                'email': {
                    'enabled': self.email_notif_enabled.isChecked(),
                    'to_emails': email_recipients,
                    **smtp_config
                },
                'telegram': {
                    'enabled': self.telegram_notif_enabled.isChecked(),
                    'bot_token': self.telegram_bot_token.text().strip(),
                    'chat_ids': telegram_chat_ids
                }
            }

            # Aggiorna config
            self.config['notifications'] = notifications_config

            # Salva in config.json
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)

            print("[CONFIG] Configurazioni notifiche salvate")

        except Exception as e:
            print(f"[CONFIG] Errore salvataggio notifiche: {e}")

    def test_email_notification(self):
        """Invia email di test"""
        try:
            # Valida configurazione email
            email_recipients_text = self.email_notif_recipients.text().strip()
            if not email_recipients_text:
                QMessageBox.warning(
                    self, "Configurazione Incompleta",
                    "❌ Inserisci almeno un indirizzo email destinatario."
                )
                return

            # Salva prima la configurazione
            self._save_notification_config()

            # Crea notifier SOLO per email (ignora telegram per questo test)
            from notifier import Notifier
            notifier = Notifier(self.config.get('notifications', {}))

            # Testa solo email
            result = notifier.test_email()

            if result['success']:
                QMessageBox.information(
                    self, "Successo",
                    "✅ Email di test inviata con successo!\n\n"
                    f"Controlla la casella di posta dei destinatari."
                )
            else:
                QMessageBox.warning(
                    self, "Errore",
                    f"❌ Impossibile inviare email di test.\n\n"
                    f"Errore: {result.get('error', 'Sconosciuto')}\n\n"
                    f"Verifica:\n"
                    f"- Che esista almeno una casella configurata in 'Caselle Email'\n"
                    f"- Le credenziali SMTP della casella\n"
                    f"- Gli indirizzi destinatari"
                )

        except Exception as e:
            QMessageBox.critical(
                self, "Errore",
                f"Errore durante test email:\n{str(e)}"
            )

    def test_telegram_notification(self):
        """Invia messaggio Telegram di test"""
        try:
            # Valida configurazione Telegram
            bot_token = self.telegram_bot_token.text().strip()
            chat_ids_text = self.telegram_chat_ids.text().strip()

            if not bot_token:
                QMessageBox.warning(
                    self, "Configurazione Incompleta",
                    "❌ Inserisci il Bot Token di Telegram.\n\n"
                    "Come ottenerlo:\n"
                    "1. Cerca @BotFather su Telegram\n"
                    "2. Scrivi /newbot e segui le istruzioni\n"
                    "3. Copia il token ricevuto"
                )
                return

            if not chat_ids_text:
                QMessageBox.warning(
                    self, "Configurazione Incompleta",
                    "❌ Inserisci almeno un Chat ID.\n\n"
                    "Come ottenerlo:\n"
                    "1. Cerca @userinfobot su Telegram\n"
                    "2. Scrivi /start\n"
                    "3. Copia il tuo Chat ID"
                )
                return

            # Salva prima la configurazione
            self._save_notification_config()

            # Crea notifier SOLO per telegram (ignora email per questo test)
            from notifier import Notifier
            notifier = Notifier(self.config.get('notifications', {}))

            # Testa solo telegram
            result = notifier.test_telegram()

            if result['success']:
                QMessageBox.information(
                    self, "Successo",
                    f"✅ Messaggio Telegram inviato con successo!\n\n"
                    f"Messaggi inviati: {result.get('sent_count', 0)}"
                )
            else:
                QMessageBox.warning(
                    self, "Errore",
                    f"❌ Impossibile inviare messaggio Telegram.\n\n"
                    f"Errore: {result.get('error', 'Sconosciuto')}\n\n"
                    f"Verifica:\n"
                    f"- Bot Token corretto\n"
                    f"- Chat ID corretto\n"
                    f"- Di aver avviato una conversazione con il bot"
                )

        except Exception as e:
            QMessageBox.critical(
                self, "Errore",
                f"Errore durante test Telegram:\n{str(e)}"
            )

    def _send_publication_notification(self, email_id: str, result: dict):
        """Invia notifiche di pubblicazione (Email e/o Telegram)"""
        try:
            # Verifica se almeno una notifica è abilitata
            notifications_config = self.config.get('notifications', {})
            email_enabled = notifications_config.get('email', {}).get('enabled', False)
            telegram_enabled = notifications_config.get('telegram', {}).get('enabled', False)

            if not email_enabled and not telegram_enabled:
                print("[NOTIF] Nessuna notifica abilitata")
                return

            # Recupera informazioni email originale
            email_data = None
            for email in self.emails:
                if email.get('id') == email_id:
                    email_data = email
                    break

            if not email_data:
                print(f"[NOTIF] Email {email_id} non trovata in memoria")
                return

            # Recupera articolo generato per ottenere titolo e categoria
            article = self.generated_articles.get(email_id, {})

            # Prepara informazioni articolo per notifica
            article_info = {
                'titolo': result.get('titolo') or article.get('titolo', 'N/A'),
                'categoria': article.get('categoria', 'N/A'),
                'url': result.get('url', 'N/A'),
                'article_id': result.get('article_id', 'N/A'),
                'photos_uploaded': result.get('photos_uploaded', 0),
                'email_subject': email_data.get('subject', 'N/A'),
                'email_sender': email_data.get('from', 'N/A')
            }

            # Estrai casella che ha ricevuto l'email originale
            # email_id format: "mailbox_account:message_id"
            # esempio: "posta@voce.it:CANt6mx0sz2hq6ZR_us0ZmguSZAmDz..."
            mailbox_account = email_id.split(':', 1)[0] if ':' in email_id else None

            if mailbox_account and email_enabled:
                # Carica casella dal database
                mailboxes = self.db.get_all_mailboxes(only_enabled=True)
                sender_mailbox = None

                for mb in mailboxes:
                    if mb.get('email_address') == mailbox_account:
                        sender_mailbox = mb
                        break

                if sender_mailbox:
                    # Determina SMTP server e porta in base al provider
                    imap_server = sender_mailbox.get('imap_server', 'imap.gmail.com')

                    # Mappatura speciale per provider conosciuti
                    if 'register.it' in imap_server:
                        # Register.it usa server dedicato authsmtp.securemail.pro
                        smtp_server = 'authsmtp.securemail.pro'
                        smtp_port = 465  # Porta SSL Register.it
                    elif 'gmail.com' in imap_server:
                        smtp_server = 'smtp.gmail.com'
                        smtp_port = 587
                    else:
                        # Default: sostituisci imap. con smtp.
                        smtp_server = imap_server.replace('imap.', 'smtp.')
                        smtp_port = 587

                    # Sovrascrivi configurazione SMTP con quella della casella originale
                    notifications_config['email'].update({
                        'smtp_server': smtp_server,
                        'smtp_port': smtp_port,
                        'smtp_username': sender_mailbox.get('email_address', ''),
                        'smtp_password': sender_mailbox.get('password', ''),
                        'from_email': sender_mailbox.get('email_address', '')
                    })
                    print(f"[NOTIF] Invio notifica da casella originale: {mailbox_account} ({smtp_server}:{smtp_port})")
                else:
                    print(f"[NOTIF] Warning: Casella {mailbox_account} non trovata, uso config default")

            print(f"[NOTIF] Invio notifiche per articolo: {article_info['titolo']}")

            # Crea notifier e invia
            from notifier import Notifier
            notifier = Notifier(notifications_config)
            notification_results = notifier.send_publication_notification(article_info)

            # Log risultati
            if notification_results.get('email'):
                print(f"[NOTIF] ✓ Email inviata")
            if notification_results.get('telegram'):
                print(f"[NOTIF] ✓ Telegram inviato")

        except Exception as e:
            print(f"[NOTIF] ❌ Errore invio notifiche: {e}")
            import traceback
            traceback.print_exc()

    def load_senders(self):
        """Carica lista mittenti dalla config"""
        self.sender_list.clear()
        senders = self.config.get("email_filters", {}).get("mittenti_monitorati", [])
        for sender in senders:
            self.sender_list.addItem(sender)

    def add_sender(self):
        """Aggiungi mittente alla lista"""
        email = self.sender_input.text().strip()
        if not email:
            return

        if "@" not in email:
            QMessageBox.warning(self, "Errore", "Inserisci un indirizzo email valido")
            return

        # Aggiungi alla config
        if "email_filters" not in self.config:
            self.config["email_filters"] = {}
        if "mittenti_monitorati" not in self.config["email_filters"]:
            self.config["email_filters"]["mittenti_monitorati"] = []

        if email not in self.config["email_filters"]["mittenti_monitorati"]:
            self.config["email_filters"]["mittenti_monitorati"].append(email)
            self.save_config()
            self.load_senders()
            self.sender_input.clear()
            QMessageBox.information(self, "Successo", f"Mittente {email} aggiunto")

    def remove_sender(self):
        """Rimuovi mittente selezionato"""
        current_item = self.sender_list.currentItem()
        if not current_item:
            return

        email = current_item.text()
        reply = QMessageBox.question(
            self, "Conferma",
            f"Rimuovere {email} dalla lista?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.config["email_filters"]["mittenti_monitorati"].remove(email)
            self.save_config()
            self.load_senders()

    def remove_all_senders(self):
        """Elimina tutti i mittenti monitorati"""
        if "email_filters" not in self.config:
            return

        if "mittenti_monitorati" not in self.config["email_filters"]:
            return

        count = len(self.config["email_filters"]["mittenti_monitorati"])

        if count == 0:
            QMessageBox.information(self, "Info", "Nessun mittente da eliminare")
            return

        reply = QMessageBox.question(
            self, "Conferma",
            f"Eliminare tutti i {count} mittenti monitorati?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.config["email_filters"]["mittenti_monitorati"] = []
            self.save_config()
            self.load_senders()
            QMessageBox.information(self, "Successo", f"{count} mittenti eliminati")

    def load_mailboxes(self):
        """Carica caselle email dal database nella tabella"""
        self.mailbox_table.setRowCount(0)
        mailboxes = self.db.get_all_mailboxes(only_enabled=False)

        for mailbox in mailboxes:
            row = self.mailbox_table.rowCount()
            self.mailbox_table.insertRow(row)

            # Email
            self.mailbox_table.setItem(row, 0, QTableWidgetItem(mailbox['email_address']))

            # Server
            self.mailbox_table.setItem(row, 1, QTableWidgetItem(mailbox['imap_server']))

            # Porta
            self.mailbox_table.setItem(row, 2, QTableWidgetItem(str(mailbox['imap_port'])))

            # Checkbox Attiva
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)

            checkbox = QCheckBox()
            checkbox.setChecked(bool(mailbox['enabled']))
            checkbox.stateChanged.connect(lambda state, email=mailbox['email_address']: self.toggle_mailbox(email, state))
            checkbox_layout.addWidget(checkbox)

            self.mailbox_table.setCellWidget(row, 3, checkbox_widget)

            # Pulsante Rimuovi
            btn_remove = QPushButton("🗑 Rimuovi")
            btn_remove.clicked.connect(lambda checked, email=mailbox['email_address']: self.remove_mailbox(email))
            self.mailbox_table.setCellWidget(row, 4, btn_remove)

    def add_mailbox(self):
        """Aggiungi nuova casella email"""
        email = self.mailbox_email_input.text().strip()
        password = self.mailbox_password_input.text().strip()
        server = self.mailbox_server_input.text().strip()
        port = self.mailbox_port_input.text().strip()

        if not email or not password or not server or not port:
            QMessageBox.warning(self, "Errore", "Compila tutti i campi")
            return

        if "@" not in email:
            QMessageBox.warning(self, "Errore", "Inserisci un indirizzo email valido")
            return

        try:
            port_int = int(port)
        except ValueError:
            QMessageBox.warning(self, "Errore", "Porta deve essere un numero")
            return

        # Salva nel database
        success = self.db.add_mailbox(email, password, server, port_int)

        if success:
            QMessageBox.information(self, "Successo", f"Casella {email} aggiunta")
            # Pulisci form
            self.mailbox_email_input.clear()
            self.mailbox_password_input.clear()
            self.mailbox_server_input.setText("imap.register.it")
            self.mailbox_port_input.setText("993")
            # Ricarica tabella
            self.load_mailboxes()
        else:
            QMessageBox.critical(self, "Errore", "Impossibile aggiungere la casella")

    def remove_mailbox(self, email):
        """Rimuovi casella email"""
        reply = QMessageBox.question(
            self, "Conferma",
            f"Rimuovere la casella {email}?\n\nLe email già scaricate rimarranno nel database.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success = self.db.remove_mailbox(email)
            if success:
                QMessageBox.information(self, "Successo", f"Casella {email} rimossa")
                self.load_mailboxes()
            else:
                QMessageBox.critical(self, "Errore", "Impossibile rimuovere la casella")

    def toggle_mailbox(self, email, state):
        """Attiva/disattiva monitoraggio casella"""
        enabled = (state == Qt.CheckState.Checked.value)
        success = self.db.toggle_mailbox(email, enabled)

        if success:
            status = "attivato" if enabled else "disattivato"
            self.statusBar().showMessage(f"Monitoraggio {status} per {email}", 3000)
        else:
            QMessageBox.critical(self, "Errore", "Impossibile modificare lo stato della casella")
            self.load_mailboxes()  # Ricarica per ripristinare stato corretto

    def test_mailbox_connection(self):
        """Testa connessione alla casella email"""
        email = self.mailbox_email_input.text().strip()
        password = self.mailbox_password_input.text().strip()
        server = self.mailbox_server_input.text().strip()
        port = self.mailbox_port_input.text().strip()

        if not email or not password or not server or not port:
            QMessageBox.warning(self, "Errore", "Compila tutti i campi")
            return

        try:
            port_int = int(port)
        except ValueError:
            QMessageBox.warning(self, "Errore", "Porta deve essere un numero")
            return

        # Test connessione
        try:
            from email_processor import EmailProcessor
            test_processor = EmailProcessor(email, password, server, port_int)
            test_processor.connect()
            test_processor.disconnect()
            QMessageBox.information(self, "Successo", f"Connessione a {server} riuscita!")
        except Exception as e:
            QMessageBox.critical(self, "Errore Connessione", f"Impossibile connettersi:\n{str(e)}")

    def refresh_emails(self, fetch_all=False):
        """Aggiorna lista email da tutte le caselle configurate"""
        # Carica caselle dal database
        mailboxes = self.db.get_all_mailboxes(only_enabled=True)

        if not mailboxes:
            QMessageBox.warning(
                self, "Attenzione",
                "Nessuna casella email configurata!\n\n"
                "Vai nella tab 'Caselle Email' per aggiungere le tue caselle."
            )
            return

        # Disabilita pulsanti e mostra progress
        self.btn_refresh_all.setEnabled(False)
        self.btn_refresh_monitored.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate

        self.statusBar().showMessage(f"Recupero email da {len(mailboxes)} caselle...")

        # Usa il sistema di monitoraggio esistente
        # Chiama check_new_emails che usa i processors già connessi
        if hasattr(self, 'email_processors') and self.email_processors:
            # Usa i processor già connessi
            self.check_new_emails()
            # Riabilita pulsanti
            self.btn_refresh_all.setEnabled(True)
            self.btn_refresh_monitored.setEnabled(True)
            self.progress_bar.setVisible(False)
        else:
            # Avvia monitoraggio se non ancora avviato
            self.start_auto_monitoring()
            # Riabilita pulsanti
            self.btn_refresh_all.setEnabled(True)
            self.btn_refresh_monitored.setEnabled(True)
            self.progress_bar.setVisible(False)

    @Slot(list)
    def on_emails_loaded(self, emails):
        """Callback quando email sono caricate"""
        # Salva tutte le email nel database
        for email in emails:
            self.save_email_to_db(email)

        self.emails = emails
        self.populate_email_table()

        # Sincronizza con IMAP (elimina email non più presenti)
        current_ids = [e.get('id') for e in self.emails]
        deleted_count = self.db.sync_with_imap(current_ids)

        if deleted_count > 0:
            # Ricarica dal DB per aggiornare
            self.load_emails_from_db()

        self.btn_refresh_all.setEnabled(True)
        self.btn_refresh_monitored.setEnabled(True)
        self.progress_bar.setVisible(False)

        status_msg = f"{len(emails)} email trovate"
        if deleted_count > 0:
            status_msg += f" ({deleted_count} eliminate)"
        self.statusBar().showMessage(status_msg)

    @Slot(str)
    def on_email_error(self, error_msg):
        """Callback errore caricamento email"""
        self.btn_refresh_all.setEnabled(True)
        self.btn_refresh_monitored.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("Errore")
        QMessageBox.critical(self, "Errore", f"Errore nel recupero email:\n{error_msg}")

    @staticmethod
    def decode_mime_header(header_value):
        """Decodifica header MIME-encoded (=?utf-8?q?...) per visualizzazione"""
        if not header_value or header_value == 'N/A':
            return header_value

        try:
            from email.header import decode_header
            decoded_parts = []
            for part, encoding in decode_header(header_value):
                if isinstance(part, bytes):
                    decoded_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
                else:
                    decoded_parts.append(str(part))
            result = ''.join(decoded_parts)
            return result.replace('\n', ' ').replace('\r', '').strip()
        except:
            return header_value

    def populate_email_table(self):
        """Popola tabella con email (OTTIMIZZATO - no query DB)"""
        self.email_table.setRowCount(len(self.emails))

        for row, email in enumerate(self.emails):
            email_id = email.get('id', '')

            # Casella (già in memoria - no query DB!)
            mailbox_account = email.get('mailbox_account', '')
            # Mostra messaggio più chiaro se non assegnata
            if not mailbox_account:
                mailbox_account = "⚠️ Non assegnata"
            self.email_table.setItem(row, 0, QTableWidgetItem(mailbox_account))

            # Mittente - decodifica MIME se necessario
            from_header = self.decode_mime_header(email.get('from', 'N/A'))
            self.email_table.setItem(row, 1, QTableWidgetItem(from_header))

            # Oggetto - decodifica MIME se necessario (con indicatore allegati)
            subject = self.decode_mime_header(email.get('subject', 'N/A'))
            attachments = email.get('attachments', [])
            if attachments:
                subject += f" 📎({len(attachments)})"
            self.email_table.setItem(row, 2, QTableWidgetItem(subject))

            # Data
            self.email_table.setItem(row, 3, QTableWidgetItem(email.get('date', 'N/A')))

            # Stato (già in memoria - no query DB!)
            status = email.get('status', 'NEW')
            if status == 'PUBLISHED':
                status_item = QTableWidgetItem("🌐 Pubblicato")
                status_item.setForeground(QColor("blue"))
            elif status == 'GENERATED':
                status_item = QTableWidgetItem("✅ Articolo generato")
                status_item.setForeground(QColor("green"))
            else:  # NEW
                status_item = QTableWidgetItem("⏳ Da processare")
                status_item.setForeground(QColor("orange"))

            self.email_table.setItem(row, 4, status_item)

            has_article = email_id in self.generated_articles

            # Pulsante azione
            btn_generate = QPushButton("📝 Genera Articolo" if not has_article else "👁️ Vedi Articolo")
            btn_generate.clicked.connect(lambda checked, r=row: self.generate_or_view_article(r))
            self.email_table.setCellWidget(row, 5, btn_generate)

            # ID (nascosto)
            self.email_table.setItem(row, 6, QTableWidgetItem(email_id))

    def generate_or_view_article(self, row):
        """Genera articolo o mostra se già generato"""
        email = self.emails[row]
        email_id = email.get('id', '')

        if email_id in self.generated_articles:
            # Mostra articolo esistente
            self.show_article_preview(self.generated_articles[email_id])
        else:
            # Genera nuovo articolo
            self.generate_article(row)

    def generate_article(self, row):
        """Genera articolo per email selezionata"""
        email = self.emails[row]
        provider = self.provider_combo.currentText()
        email_id = email.get('id', '')

        self.statusBar().showMessage("Preparazione per generazione articolo...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        # Controlla se l'email ha già allegati scaricati
        if not email.get('attachments') or len(email.get('attachments', [])) == 0:
            # Scarica allegati on-demand
            self.statusBar().showMessage("Scaricamento allegati...")

            # Trova il processor giusto per questa email e l'UID IMAP
            db_email = self.db.get_email_with_attachments(email_id)
            mailbox_account = db_email.get('mailbox_account') if db_email else None
            imap_id = db_email.get('imap_id') if db_email else None

            if mailbox_account and imap_id and hasattr(self, 'email_processors') and mailbox_account in self.email_processors:
                processor = self.email_processors[mailbox_account]
                print(f"[ATTACH] Scarico allegati per IMAP UID: {imap_id}")
                # Passa l'UID IMAP, non l'email_id!
                attachments = processor.fetch_attachments_for_email(imap_id)

                if attachments:
                    # Aggiorna email in memoria
                    email['attachments'] = attachments

                    # Salva allegati nel database
                    self.db.insert_attachments(email_id, attachments)
                    print(f"[OK] {len(attachments)} allegati scaricati e salvati per email {email_id}")
                else:
                    print(f"[!] Nessun allegato trovato per IMAP UID {imap_id}")
            else:
                if not imap_id:
                    print(f"[!] IMAP UID mancante per email {email_id}")
                else:
                    print(f"[!] Impossibile scaricare allegati: casella {mailbox_account} non connessa")

        self.statusBar().showMessage("Generazione articolo in corso...")

        # Controlla se è modalità impaginazione
        format_mode = getattr(self, '_format_mode', False)

        # Avvia thread
        self.article_thread = ArticleGeneratorThread(email, provider, format_mode=format_mode)
        # Passa email_id direttamente invece di row (che può cambiare se la tabella viene ricaricata)
        self.article_thread.finished.connect(lambda article: self.on_article_generated(email_id, article))
        self.article_thread.error.connect(self.on_article_error)
        self.article_thread.progress.connect(lambda msg: self.statusBar().showMessage(msg))
        self.article_thread.start()

    @Slot(dict)
    def on_article_generated(self, email_id, article):
        """Callback articolo generato"""
        try:
            print(f"[CALLBACK] on_article_generated chiamato")
            print(f"[CALLBACK] Email ID: {email_id}")

            # Controlla se siamo in modalità "Impagina e Pubblica"
            format_and_publish_mode = getattr(self, '_format_and_publish_mode', False)

            # Reset flag format_mode se era attivo
            if hasattr(self, '_format_mode') and self._format_mode:
                self._format_mode = False
                print(f"[CALLBACK] Modalità impaginazione completata")

            self.generated_articles[email_id] = article

            # Salva articolo nel database
            print(f"[CALLBACK] Salvataggio articolo nel database...")
            article_id = self.db.save_article(email_id, article)
            if article_id:
                print(f"[DB] Articolo salvato con ID {article_id}")
            else:
                print(f"[DB] ERRORE: Impossibile salvare articolo")

            # Se siamo in modalità "Impagina e Pubblica", NON cambiare lo stato
            # Pubbliceremo direttamente e lo stato andrà a PUBLISHED
            if format_and_publish_mode:
                print(f"[CALLBACK] Modalità Impagina e Pubblica: salto aggiornamento a GENERATED")

                # Mostra preview articolo senza aggiornare la tabella
                print(f"[GUI] Mostra preview articolo...")
                self.show_article_preview(article)

                # Avvia pubblicazione diretta
                print(f"[CALLBACK] Avvio pubblicazione diretta...")
                self.statusBar().showMessage("Pubblicazione su CMS in corso...")

                # Reset del flag
                self._format_and_publish_mode = False

                # Pubblica direttamente
                self.publish_article()

            else:
                # Workflow normale: aggiorna stato a GENERATED
                print(f"[DB] Aggiornamento stato email a GENERATED...")
                success = self.db.update_email_status(email_id, 'GENERATED')
                if success:
                    print(f"[DB] Stato aggiornato a GENERATED con successo")
                    # IMPORTANTE: Aggiorna anche lo status in memoria trovando l'email per ID!
                    for i, email in enumerate(self.emails):
                        if email.get('id') == email_id:
                            self.emails[i]['status'] = 'GENERATED'
                            print(f"[MEMORY] Stato aggiornato in memoria per email {email_id}")
                            break
                else:
                    print(f"[DB] ERRORE: Impossibile aggiornare stato a GENERATED")

                # Aggiorna tabella
                print(f"[GUI] Aggiornamento tabella email...")
                self.populate_email_table()

                # Mostra preview
                print(f"[GUI] Mostra preview articolo...")
                self.show_article_preview(article)

                self.progress_bar.setVisible(False)
                self.statusBar().showMessage("Articolo generato con successo!")

                # AUTO-PUBBLICAZIONE: se email è in coda, pubblica automaticamente
                if hasattr(self, 'auto_publish_queue') and email_id in self.auto_publish_queue:
                    print(f"[AUTO] Articolo generato, avvio pubblicazione automatica...")
                    self.auto_publish_queue.remove(email_id)
                    self.auto_publish_article(email_id, article)
                else:
                    print(f"[CALLBACK] Email non in coda auto-pubblicazione (queue: {getattr(self, 'auto_publish_queue', set())})")

            print(f"[CALLBACK] on_article_generated completato con successo")

        except Exception as e:
            import traceback
            print(f"[CALLBACK] ❌ ERRORE CRITICO in on_article_generated: {e}")
            traceback.print_exc()
            self.statusBar().showMessage(f"❌ Errore: {e}", 5000)

    @Slot(str)
    def on_article_error(self, error_msg):
        """Callback errore generazione"""
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("Errore")
        QMessageBox.critical(self, "Errore", f"Errore generazione articolo:\n{error_msg}")

    def on_email_selected(self):
        """Callback selezione email nella tabella - mostra SEMPRE la mail originale"""
        selected_rows = self.email_table.selectedIndexes()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        email = self.emails[row]
        email_id = email.get('id', '')
        status = email.get('status', 'NEW')

        # Mostra sempre il contenuto della mail originale
        self.show_email_content(email)

        # Gestione visibilità pulsanti in base allo stato
        if status == 'NEW':
            # Email non elaborata: mostra solo "Impagina e Pubblica"
            self.btn_format_publish.setEnabled(True)
            self.btn_publish.setEnabled(False)
        elif status == 'GENERATED':
            # Articolo generato: mostra solo "Pubblica su CMS"
            self.btn_format_publish.setEnabled(False)
            self.btn_publish.setEnabled(True)
        elif status == 'PUBLISHED':
            # Articolo già pubblicato: disabilita entrambi
            self.btn_format_publish.setEnabled(False)
            self.btn_publish.setEnabled(False)

    def show_article_preview(self, article):
        """Mostra preview articolo"""
        preview_html = f"""
        <h2>{article.get('titolo', 'N/A')}</h2>
        <p><strong>Tipo:</strong> {article.get('tipo', 'N/A')} |
           <strong>Categoria:</strong> {article.get('categoria', 'N/A')}</p>
        <p><em>{article.get('occhiello', '')}</em></p>
        <h3>{article.get('sottotitolo', '')}</h3>
        """

        # Mostra foto se presenti (singola o multiple)
        foto_path = article.get('foto_path')
        if foto_path:
            # Normalizza a lista per gestione uniforme
            foto_list = [foto_path] if isinstance(foto_path, str) else foto_path

            # Filtra solo foto esistenti
            foto_esistenti = [f for f in foto_list if os.path.exists(f)]

            if foto_esistenti:
                preview_html += f"""
                <div style="margin: 20px 0;">
                    <p><strong>Foto allegate ({len(foto_esistenti)}):</strong></p>
                """

                for foto in foto_esistenti:
                    # Converti a path assoluto per QTextBrowser
                    abs_path = os.path.abspath(foto)
                    # Usa file:// URL per caricare l'immagine locale
                    preview_html += f"""
                    <div style="text-align: center; margin: 10px 0;">
                        <img src="file:///{abs_path.replace(chr(92), '/')}"
                             style="max-width: 100%; max-height: 300px; border: 2px solid #ccc; border-radius: 5px;">
                        <p><small>{os.path.basename(foto)}</small></p>
                    </div>
                    """

                preview_html += "</div>"

        preview_html += "<hr>"

        for i, para in enumerate(article.get('contenuto', []), 1):
            if para:
                preview_html += f"<p><strong>[Paragrafo {i}]</strong><br>{para}</p>"

        preview_html += f"""
        <hr>
        <p><small>Data: {article.get('data_invio', 'N/A')}</small></p>
        """

        self.article_preview.setHtml(preview_html)
        self.btn_publish.setEnabled(True)

    def show_email_content(self, email):
        """Mostra il contenuto della mail originale"""
        # Decodifica MIME header se necessario
        from_header = self.decode_mime_header(email.get('from', 'N/A'))
        to_header = self.decode_mime_header(email.get('to', 'N/A'))
        subject = self.decode_mime_header(email.get('subject', 'N/A'))

        # Estrai il corpo del messaggio
        body = email.get('body', 'Nessun contenuto')

        # Converti eventuali newline in <br> per HTML
        body_html = body.replace('\n', '<br>')

        # Informazioni sugli allegati
        attachments = email.get('attachments', [])
        attachments_html = ""
        if attachments:
            attachments_html = "<h3 style='color: #3498db;'>Allegati:</h3><ul style='color: #ecf0f1;'>"
            for att in attachments:
                filename = att.get('filename', 'N/A')
                size_kb = att.get('size', 0) / 1024
                attachments_html += f"<li>{filename} ({size_kb:.1f} KB)</li>"
            attachments_html += "</ul>"

        # Mappa stato a colore
        status = email.get('status', 'NEW')
        status_map = {
            'NEW': ('Da processare', '#f39c12'),
            'GENERATED': ('Articolo generato', '#27ae60'),
            'PUBLISHED': ('Pubblicato', '#3498db')
        }
        status_text, status_color = status_map.get(status, (status, '#95a5a6'))

        # Crea HTML preview con colori adatti a tema scuro
        email_html = f"""
        <div style="font-family: Arial, sans-serif; padding: 10px; background: #2c3e50; color: #ecf0f1;">
            <h2 style="color: #3498db; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                Email Originale
            </h2>

            <div style="background: #34495e; padding: 15px; margin: 10px 0; border-radius: 5px; color: #ecf0f1;">
                <p><strong style="color: #3498db;">Da:</strong> {from_header}</p>
                <p><strong style="color: #3498db;">A:</strong> {to_header}</p>
                <p><strong style="color: #3498db;">Oggetto:</strong> {subject}</p>
                <p><strong style="color: #3498db;">Data:</strong> {email.get('date', 'N/A')}</p>
                <p><strong style="color: #3498db;">Stato:</strong> <span style="color: {status_color};">{status_text}</span></p>
            </div>

            {attachments_html}

            <h3 style="color: #3498db; margin-top: 20px;">Contenuto:</h3>
            <div style="background: #34495e; padding: 15px; border: 1px solid #3498db; border-radius: 5px; color: #ecf0f1;">
                {body_html}
            </div>

            <p style="margin-top: 20px; color: #95a5a6; font-size: 12px;">
                💡 Clicca su "Genera Articolo" o "Vedi Articolo" per visualizzare l'articolo generato
            </p>
        </div>
        """

        self.article_preview.setHtml(email_html)

    def publish_article(self):
        """Pubblica articolo su CMS usando Playwright"""
        selected_rows = self.email_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "Attenzione", "Seleziona un articolo da pubblicare")
            return

        row = selected_rows[0].row()
        email_id = self.emails[row].get('id', '')

        if email_id not in self.generated_articles:
            QMessageBox.warning(self, "Attenzione", "Genera prima l'articolo")
            return

        article = self.generated_articles[email_id]

        reply = QMessageBox.question(
            self, "Conferma Pubblicazione",
            f"Pubblicare l'articolo '{article.get('titolo', '')}' sul CMS Voce.it?\n\n"
            f"Tipo: Spotlight (default)\n"
            f"Categoria: {article.get('categoria', 'N/A')}\n\n"
            "Il browser si aprirà per la pubblicazione automatica.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Salva email_id per uso nel callback
            self.publishing_email_id = email_id

            # Avvia thread pubblicazione CMS
            cms_username = self.cms_user_input.text().strip() or os.getenv("CMS_USERNAME", "")
            cms_password = self.cms_pass_input.text().strip() or os.getenv("CMS_PASSWORD", "")

            # Determina headless mode
            headless = self.headless_combo.currentIndex() == 1  # 0=Visibile, 1=Nascosto

            self.cms_thread = CMSPublishThread(article, cms_username, cms_password, headless)
            self.cms_thread.progress.connect(self.on_cms_progress)
            self.cms_thread.finished.connect(self.on_cms_finished)
            self.cms_thread.error.connect(self.on_cms_error)

            self.btn_publish.setEnabled(False)
            self.statusBar().showMessage("Pubblicazione in corso...")
            self.cms_thread.start()

    def on_cms_progress(self, message):
        """Aggiorna stato pubblicazione CMS"""
        self.statusBar().showMessage(message)

    def on_cms_finished(self, result):
        """Callback quando pubblicazione CMS termina"""
        # Nascondi barra di progresso
        self.progress_bar.setVisible(False)

        if result.get('success'):
            # Marca articolo come pubblicato nel database
            if hasattr(self, 'publishing_email_id'):
                email_id = self.publishing_email_id
                self.db.mark_article_published(
                    email_id,
                    cms_url=result.get('url')
                )
                print(f"[DB] Articolo marcato come pubblicato per email {email_id}")

                # Aggiorna status email a PUBLISHED
                self.db.update_email_status(email_id, 'PUBLISHED')

                # IMPORTANTE: Aggiorna anche lo status in memoria!
                for i, email in enumerate(self.emails):
                    if email.get('id') == email_id:
                        self.emails[i]['status'] = 'PUBLISHED'
                        print(f"[MEMORY] Stato aggiornato in memoria per email {email_id}")
                        break

                # Aggiorna tabella per mostrare nuovo stato
                self.populate_email_table()

                # NON riabilitare il pulsante - l'articolo è ora pubblicato
                self.btn_publish.setEnabled(False)

            # Prepara messaggio con info foto se presenti
            photo_info = ""
            if 'photos_uploaded' in result:
                photos_count = result.get('photos_uploaded', 0)
                if photos_count > 0:
                    photo_info = f"\nFoto caricate: {photos_count}"
                else:
                    photo_info = "\nNessuna foto caricata"

            QMessageBox.information(
                self, "Successo!",
                f"Articolo pubblicato con successo sul CMS!\n\n"
                f"Titolo: {result.get('titolo', 'N/A')}\n"
                f"Tipo: {result.get('tipo', 'N/A')}\n"
                f"URL: {result.get('url', 'N/A')}"
                f"{photo_info}"
            )
            self.statusBar().showMessage("Articolo pubblicato con successo!", 5000)
        else:
            # Solo in caso di errore, riabilita il pulsante
            self.btn_publish.setEnabled(True)
            QMessageBox.warning(
                self, "Errore",
                f"Errore durante la pubblicazione:\n{result.get('error', 'Unknown')}"
            )
            self.statusBar().showMessage("Errore pubblicazione", 5000)

    def on_cms_error(self, error_msg):
        """Callback quando pubblicazione CMS ha errore"""
        # Nascondi barra di progresso
        self.progress_bar.setVisible(False)

        self.btn_publish.setEnabled(True)
        QMessageBox.critical(
            self, "Errore Pubblicazione CMS",
            f"Si è verificato un errore durante la pubblicazione:\n\n{error_msg}"
        )
        self.statusBar().showMessage("Errore pubblicazione", 5000)

    def format_and_publish_email(self):
        """Formatta il contenuto email con LLM (prompt specifico per impaginazione) e pubblica su CMS"""
        # 1. Recupera email selezionata
        selected_rows = self.email_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "Attenzione", "Seleziona un'email")
            return

        row = selected_rows[0].row()
        email = self.emails[row]
        email_id = email.get('id', '')

        # 2. Imposta flag per usare prompt di impaginazione E pubblicazione diretta
        self._format_mode = True
        self._format_and_publish_mode = True  # Flag per pubblicazione diretta
        self._format_publish_email_id = email_id  # Salva l'email_id per la pubblicazione

        # 3. Mostra messaggio utente
        self.statusBar().showMessage("Impaginazione e pubblicazione email con LLM...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        # 4. Riutilizza il workflow esistente generate_article
        # Il flag _format_mode cambierà il prompt usato
        self.generate_article(row)

    def _format_email_to_article(self, email: dict, metadata: dict) -> dict:
        """
        Formatta il contenuto email in struttura articolo CMS

        Args:
            email: Dati email (id, subject, body, from, date, ...)
            metadata: Dati dal dialog (titolo, sottotitolo, occhiello, categoria)

        Returns:
            dict: Articolo in formato CMS
        """
        body = email.get('body', '')

        # Split paragrafi su doppio newline
        paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]

        # Se non ci sono doppie newline, split su singola newline
        if len(paragraphs) < 2:
            paragraphs = [p.strip() for p in body.split('\n') if p.strip()]

        # Limita a 3 paragrafi (testo, testo2, testo3)
        paragraphs = paragraphs[:3]

        # Se c'è un solo paragrafo molto lungo, prova a dividerlo
        if len(paragraphs) == 1 and len(paragraphs[0]) > 500:
            # Cerca di dividere su punti seguiti da spazio maiuscola
            import re
            sentences = re.split(r'\.(\s+[A-Z])', paragraphs[0])
            if len(sentences) > 3:
                # Ricostruisci i paragrafi
                para1 = sentences[0] + '.'
                para2 = sentences[2] + '.' if len(sentences) > 2 else ''
                para3 = sentences[4] + '.' if len(sentences) > 4 else ''
                paragraphs = [p for p in [para1, para2, para3] if p and p != '.']

        # Costruisci articolo
        article = {
            'tipo': 'Spotlight',
            'categoria': metadata['categoria'],
            'titolo': metadata['titolo'],
            'sottotitolo': metadata['sottotitolo'],
            'occhiello': metadata['occhiello'],
            'contenuto': paragraphs,
            'immagine': '',
            'data_invio': email.get('date', ''),
            'metadata': {
                'original_sender': email.get('from', ''),
                'original_subject': email.get('subject', ''),
                'email_date': email.get('date', ''),
                'processing_mode': 'format_only'  # Flag per distinguere da LLM
            }
        }

        return article

    def _auto_publish_article(self, email_id: str, article: dict, message_id: str):
        """Pubblica articolo automaticamente (usato da auto_process_email in modalità format_only)"""
        try:
            print(f"[AUTO] Avvio pubblicazione automatica...")

            # Credenziali CMS
            cms_username = self.cms_user_input.text().strip() or os.getenv("CMS_USERNAME", "")
            cms_password = self.cms_pass_input.text().strip() or os.getenv("CMS_PASSWORD", "")

            if not cms_username or not cms_password:
                print("[AUTO] ⚠️ Credenziali CMS mancanti, skip pubblicazione automatica")
                # Rimuovi Message-ID dal set
                if hasattr(self, 'processing_message_ids') and message_id:
                    self.processing_message_ids.discard(message_id)
                return

            # Headless mode
            headless = self.headless_combo.currentIndex() == 1  # 0=Visibile, 1=Nascosto

            # Avvia thread pubblicazione
            self.cms_thread = CMSPublishThread(
                article=article,
                cms_username=cms_username,
                cms_password=cms_password,
                headless=headless
            )

            self.cms_thread.progress.connect(lambda msg: print(f"[AUTO] {msg}"))
            self.cms_thread.finished.connect(
                lambda result: self._on_auto_publish_finished(email_id, message_id, result)
            )
            self.cms_thread.error.connect(
                lambda err: self._on_auto_publish_error(email_id, message_id, err)
            )

            self.cms_thread.start()
            print("[AUTO] Thread pubblicazione avviato")

        except Exception as e:
            import traceback
            print(f"[AUTO] ❌ Errore avvio pubblicazione: {e}")
            traceback.print_exc()
            # Rimuovi Message-ID dal set in caso di errore
            if hasattr(self, 'processing_message_ids') and message_id:
                self.processing_message_ids.discard(message_id)

    def _on_auto_publish_finished(self, email_id: str, message_id: str, result: dict):
        """Callback dopo pubblicazione automatica completata"""
        try:
            if result.get('success'):
                print(f"[AUTO] ✅ Pubblicazione completata con successo")
                print(f"[AUTO] URL: {result.get('url', 'N/A')}")

                # Aggiorna status a PUBLISHED nel database
                self.db.update_email_status(email_id, 'PUBLISHED')
                self.db.mark_article_published(
                    email_id,
                    cms_url=result.get('url')
                )

                # Aggiorna status in memoria
                for i, email in enumerate(self.emails):
                    if email.get('id') == email_id:
                        self.emails[i]['status'] = 'PUBLISHED'
                        print(f"[AUTO] Stato aggiornato in memoria: PUBLISHED")
                        break

                # Aggiorna tabella GUI
                self.refresh_email_table()

                # Mostra messaggio nella status bar
                self.statusBar().showMessage(
                    f"✅ Articolo pubblicato automaticamente: {result.get('titolo', 'N/A')}",
                    5000
                )

                print(f"[AUTO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print(f"[AUTO] ELABORAZIONE AUTOMATICA COMPLETATA")
                print(f"[AUTO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            else:
                print(f"[AUTO] ❌ Pubblicazione fallita: {result.get('error')}")
                self.statusBar().showMessage(
                    f"❌ Errore pubblicazione automatica: {result.get('error', 'Unknown')}",
                    5000
                )

        except Exception as e:
            import traceback
            print(f"[AUTO] ❌ Errore in callback pubblicazione: {e}")
            traceback.print_exc()

        finally:
            # Rimuovi Message-ID dal set di elaborazione
            if hasattr(self, 'processing_message_ids') and message_id:
                self.processing_message_ids.discard(message_id)
                print(f"[AUTO] Message-ID rimosso da processing_message_ids")

    def _on_auto_publish_error(self, email_id: str, message_id: str, error_msg: str):
        """Callback quando pubblicazione automatica ha errore"""
        print(f"[AUTO] ❌ Errore pubblicazione: {error_msg}")
        self.statusBar().showMessage(f"❌ Errore pubblicazione automatica: {error_msg}", 5000)

        # Rimuovi Message-ID dal set
        if hasattr(self, 'processing_message_ids') and message_id:
            self.processing_message_ids.discard(message_id)
            print(f"[AUTO] Message-ID rimosso da processing_message_ids (errore)")

    def sort_emails_by_date(self):
        """Ordina le email per data (più recenti prima)"""
        from email.utils import parsedate_to_datetime

        def get_email_datetime(email):
            """Estrae datetime da email, gestendo formati diversi"""
            date_str = email.get('date', '')
            if not date_str:
                return datetime.min.replace(tzinfo=None)  # Email senza data vanno in fondo

            try:
                # Prova a parsare con parsedate_to_datetime (formato RFC 2822)
                dt = parsedate_to_datetime(date_str)
                # Rimuovi timezone info per permettere confronto
                return dt.replace(tzinfo=None) if dt.tzinfo else dt
            except:
                try:
                    # Prova formati comuni
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y']:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except:
                            continue
                    return datetime.min.replace(tzinfo=None)
                except:
                    return datetime.min.replace(tzinfo=None)

        # Ordina email per data decrescente (più recenti prima)
        try:
            self.emails.sort(key=get_email_datetime, reverse=True)
        except Exception as e:
            print(f"[!] Errore ordinamento email: {e}")

    def load_emails_from_db(self):
        """Carica email dal database all'avvio (LAZY LOADING - solo recenti)"""
        try:
            # LAZY LOADING: Carica solo ultime 100 email invece di tutte
            db_emails = self.db.get_recent_emails(limit=100)

            # Inizializza cache ID per check futuri
            if not hasattr(self, 'email_ids_cache'):
                self.email_ids_cache = set()

            # Deduplicazione: usa set per tracciare ID già visti
            seen_ids = set()

            # Converti formato DB a formato applicazione
            self.emails = []
            duplicates_skipped = 0

            for db_email in db_emails:
                email_id = db_email['email_id']

                # Salta duplicati
                if email_id in seen_ids:
                    print(f"[DB] Email duplicata ignorata al caricamento: {email_id}")
                    duplicates_skipped += 1
                    continue

                seen_ids.add(email_id)

                email_data = {
                    'id': email_id,
                    'from': db_email['sender'],
                    'subject': db_email['subject'],
                    'date': db_email['date'],
                    'body': db_email['body'],
                    'to': db_email['recipient'],
                    'attachments': [],
                    'mailbox_account': db_email.get('mailbox_account', ''),  # Evita query DB
                    'status': db_email.get('status', 'NEW')  # Evita query DB
                }

                # Popola cache ID
                self.email_ids_cache.add(email_id)

                # Converti allegati (lazy - già vuoti da get_recent_emails)
                for att in db_email.get('attachments', []):
                    email_data['attachments'].append({
                        'filename': att['filename'],
                        'path': att['filepath'],
                        'content_type': att['content_type']
                    })

                self.emails.append(email_data)

                # Carica articolo se esiste
                article = self.db.get_article_by_email(db_email['email_id'])
                if article:
                    self.generated_articles[db_email['email_id']] = article['data']

            # Ordina email per data (più recenti prima)
            self.sort_emails_by_date()

            self.populate_email_table()
            if duplicates_skipped > 0:
                print(f"[LAZY] Caricate {len(self.emails)} email uniche (ignorate {duplicates_skipped} duplicati, limite: 100)")
            else:
                print(f"[LAZY] Caricate {len(self.emails)} email recenti (limite: 100)")

        except Exception as e:
            print(f"[DB] Errore caricamento email: {e}")

    def save_email_to_db(self, email_data, mailbox_account=None):
        """Salva una nuova email nel database"""
        try:
            # Aggiungi mailbox_account se fornito
            if mailbox_account:
                email_data['mailbox_account'] = mailbox_account

            # Salva email
            self.db.insert_or_update_email(email_data)

            # Salva allegati
            if email_data.get('attachments'):
                self.db.insert_attachments(email_data['id'], email_data['attachments'])

            return True
        except Exception as e:
            print(f"[DB] Errore salvataggio email: {e}")
            return False

    def start_auto_monitoring(self):
        """Avvia monitoraggio automatico di tutte le caselle email abilitate"""
        # Carica tutte le caselle abilitate dal database
        mailboxes = self.db.get_all_mailboxes(only_enabled=True)

        if not mailboxes:
            print("[!] Nessuna casella email configurata, monitoraggio automatico disabilitato")
            print("[!] Aggiungi caselle nella tab 'Caselle Email'")
            return

        # Dizionario per mantenere i processor di ogni casella
        self.email_processors = {}

        # Connetti a ogni casella
        for mailbox in mailboxes:
            email_addr = mailbox['email_address']
            try:
                processor = EmailProcessor(
                    mailbox['email_address'],
                    mailbox['password'],
                    mailbox['imap_server'],
                    mailbox['imap_port']
                )

                if processor.connect():
                    self.email_processors[email_addr] = processor
                    print(f"[OK] Connesso a {email_addr}")
                else:
                    print(f"[X] Impossibile connettersi a {email_addr}")

            except Exception as e:
                print(f"[X] Errore connessione a {email_addr}: {e}")

        if self.email_processors:
            print(f"[OK] {len(self.email_processors)} caselle connesse per monitoraggio automatico")

            # NON scaricare email all'avvio per non bloccare la GUI
            # L'utente può cliccare "Refresh" o aspettare il timer
            # self.check_new_emails()

            # Timer per controllo periodico
            interval_text = self.monitor_interval_combo.currentText()
            interval_minutes = int(interval_text.split()[0])  # Estrai numero
            interval_ms = interval_minutes * 60 * 1000  # Converti a millisecondi

            self.email_timer = QTimer()
            self.email_timer.timeout.connect(self.check_new_emails)
            self.email_timer.start(interval_ms)

            self.statusBar().showMessage(
                f"Monitoraggio automatico attivo per {len(self.email_processors)} caselle (controllo ogni {interval_minutes} min)",
                10000
            )
        else:
            print("[X] Nessuna casella connessa")

    def check_new_emails(self):
        """Controlla nuove email da tutte le caselle abilitate e sincronizza con DB (in background)"""
        if not hasattr(self, 'email_processors') or not self.email_processors:
            print("[!] Nessun email processor attivo")
            return

        # Evita check multipli simultanei
        if hasattr(self, 'email_check_thread') and self.email_check_thread.isRunning():
            print("[!] Controllo email già in corso, attendere...")
            return

        print(f"\n[CHECK] Avvio controllo veloce da {len(self.email_processors)} caselle...")

        # Usa cache degli ID email (nessuna query DB pesante)
        # La cache viene aggiornata incrementalmente quando aggiungiamo email
        if not hasattr(self, 'email_ids_cache'):
            self.email_ids_cache = set()

        # Ottieni last_uid per ogni casella
        last_uids = {}
        for email_addr in self.email_processors.keys():
            last_uid = self.db.get_mailbox_last_uid(email_addr)
            last_uids[email_addr] = last_uid
            if last_uid > 0:
                print(f"[OPT] {email_addr}: ultimo UID controllato = {last_uid}")

        # Disabilita pulsanti durante il check
        if hasattr(self, 'btn_refresh_all'):
            self.btn_refresh_all.setEnabled(False)
        if hasattr(self, 'btn_refresh_monitored'):
            self.btn_refresh_monitored.setEnabled(False)

        # Mostra progress bar
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(len(self.email_processors))
            self.progress_bar.setValue(0)

        # Crea e avvia thread
        self.email_check_thread = EmailCheckThread(self.email_processors, self.email_ids_cache, last_uids)
        self.email_check_thread.progress.connect(self.on_email_check_progress)
        self.email_check_thread.finished.connect(self.on_email_check_finished)
        self.email_check_thread.error.connect(self.on_email_check_error)
        self.email_check_thread.start()

    def on_email_check_progress(self, message, current, total):
        """Aggiorna progress bar durante il controllo email"""
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(current)
        self.statusBar().showMessage(f"{message} ({current}/{total})")
        print(f"[PROGRESS] {message}")

    def on_email_check_error(self, error_msg):
        """Gestisce errori durante il controllo email"""
        print(f"[ERROR] {error_msg}")
        self.statusBar().showMessage(f"Errore: {error_msg}", 5000)
        # Riabilita pulsanti
        if hasattr(self, 'btn_refresh_all'):
            self.btn_refresh_all.setEnabled(True)
        if hasattr(self, 'btn_refresh_monitored'):
            self.btn_refresh_monitored.setEnabled(True)
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setVisible(False)

    def add_new_emails_to_gui(self, new_emails):
        """Aggiunge nuove email alla GUI senza ricaricare tutto (UPDATE INCREMENTALE)"""
        if not new_emails:
            return

        # Crea set degli email_id già presenti in memoria per deduplicazione
        existing_ids = {email.get('id') for email in self.emails}

        added_count = 0
        # Converti formato email e aggiungi a self.emails
        for email in new_emails:
            email_id = email.get('id', '')

            # CONTROLLO DUPLICATI: salta se già presente
            if email_id in existing_ids:
                print(f"[GUI] Email duplicata ignorata: {email_id}")
                continue

            email_data = {
                'id': email_id,
                'from': email.get('from'),
                'subject': email.get('subject'),
                'date': email.get('date'),
                'body': email.get('body'),
                'to': email.get('to'),
                'attachments': email.get('attachments', []),
                'mailbox_account': email.get('mailbox_account', ''),  # Evita query DB
                'status': 'NEW'  # Email nuove sono sempre NEW
            }
            # Aggiungi in cima alla lista (più recenti prima)
            self.emails.insert(0, email_data)
            existing_ids.add(email_id)  # Aggiorna il set
            added_count += 1

        # MEMORY MANAGEMENT: Limita email in memoria per evitare memory leak
        MAX_EMAILS_IN_MEMORY = 200
        if len(self.emails) > MAX_EMAILS_IN_MEMORY:
            removed_count = len(self.emails) - MAX_EMAILS_IN_MEMORY
            # Rimuovi le email più vecchie dalla memoria (rimangono nel DB)
            removed_emails = self.emails[MAX_EMAILS_IN_MEMORY:]
            self.emails = self.emails[:MAX_EMAILS_IN_MEMORY]

            # Pulisci anche articoli generati per email rimosse
            for old_email in removed_emails:
                old_id = old_email.get('id')
                if old_id in self.generated_articles:
                    del self.generated_articles[old_id]

            print(f"[MEMORY] Rimosse {removed_count} email più vecchie dalla memoria (limite: {MAX_EMAILS_IN_MEMORY})")

        # Ri-ordina tutte le email per data
        self.sort_emails_by_date()

        # Aggiorna solo la tabella (senza ricaricare dal DB)
        self.populate_email_table()
        print(f"[GUI] {added_count} email aggiunte alla tabella (ignorate {len(new_emails) - added_count} duplicati)")

    def cleanup_memory_sets(self):
        """Pulizia periodica dei set in memoria per evitare entry orfane"""
        # Pulisci processing_message_ids: mantieni solo Message-ID di email ancora in memoria
        if hasattr(self, 'processing_message_ids') and self.processing_message_ids:
            current_message_ids = set()
            for email in self.emails:
                email_id = email.get('id', '')
                if ':' in email_id:
                    message_id = email_id.split(':', 1)[1]
                    current_message_ids.add(message_id)

            orphaned = self.processing_message_ids - current_message_ids
            if orphaned:
                self.processing_message_ids = self.processing_message_ids & current_message_ids
                print(f"[MEMORY] Rimossi {len(orphaned)} Message-ID orfani da processing_message_ids")

        # Pulisci auto_publish_queue: mantieni solo email_id ancora in memoria
        if hasattr(self, 'auto_publish_queue') and self.auto_publish_queue:
            current_email_ids = {e.get('id') for e in self.emails}
            orphaned = self.auto_publish_queue - current_email_ids
            if orphaned:
                self.auto_publish_queue = self.auto_publish_queue & current_email_ids
                print(f"[MEMORY] Rimossi {len(orphaned)} email_id orfani da auto_publish_queue")

    def on_email_check_finished(self, all_new_emails, updated_last_uids):
        """Chiamato quando il controllo email termina - SALVA nel database (thread principale)"""
        print(f"\n[FINISHED] Controllo completato, {len(all_new_emails)} nuove email trovate")

        # MEMORY MANAGEMENT: Pulizia periodica dei set in memoria
        self.cleanup_memory_sets()

        # Salva nuove email nel database (thread-safe: siamo nel thread principale)
        if all_new_emails:
            print(f"[DB] Salvataggio {len(all_new_emails)} email nel database...")
            for email in all_new_emails:
                try:
                    self.save_email_to_db(email, mailbox_account=email.get('mailbox_account'))
                    # Aggiorna cache ID
                    if hasattr(self, 'email_ids_cache'):
                        self.email_ids_cache.add(email.get('id'))
                except Exception as e:
                    print(f"[X] Errore salvataggio email: {e}")

        # Salva last_uid aggiornati
        for email_addr, last_uid in updated_last_uids.items():
            self.db.update_mailbox_last_uid(email_addr, last_uid)
            print(f"[OPT] Aggiornato last_uid per {email_addr}: {last_uid}")

        # Riabilita pulsanti
        if hasattr(self, 'btn_refresh_all'):
            self.btn_refresh_all.setEnabled(True)
        if hasattr(self, 'btn_refresh_monitored'):
            self.btn_refresh_monitored.setEnabled(True)
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setVisible(False)

        # UPDATE INCREMENTALE: aggiungi solo nuove email alla GUI (non ricaricare tutto!)
        if all_new_emails:
            print(f"[GUI] Update incrementale: aggiungo {len(all_new_emails)} email alla tabella")
            self.add_new_emails_to_gui(all_new_emails)

        # AUTO-ELABORAZIONE: controlla se ci sono email da mittenti monitorati
        if all_new_emails and hasattr(self, 'monitored_senders'):
            print(f"[AUTO] Controllo {len(all_new_emails)} nuove email per mittenti monitorati...")
            print(f"[AUTO] Mittenti configurati: {self.monitored_senders}")

            for email in all_new_emails:
                sender = email.get('from', '')
                print(f"[AUTO] Mittente email: '{sender}'")

                # Estrai l'indirizzo email dal formato "Nome <email@domain.com>"
                import re
                email_match = re.search(r'<([^>]+)>', sender)
                sender_email = email_match.group(1) if email_match else sender.strip()
                print(f"[AUTO] Email estratta: '{sender_email}'")

                if sender_email.lower() in [m.lower() for m in self.monitored_senders]:
                    print(f"[AUTO] ✅ Email da mittente monitorato: {sender_email}")
                    print(f"[AUTO] Avvio elaborazione automatica per: {email.get('subject')}")
                    # Avvia elaborazione automatica in background
                    self.auto_process_email(email)
                else:
                    print(f"[AUTO] ❌ Mittente non monitorato: {sender_email}")

        # Notifica utente
        if all_new_emails:
            self.statusBar().showMessage(f"✅ {len(all_new_emails)} nuove email scaricate", 10000)
            QApplication.beep()
        else:
            self.statusBar().showMessage("Nessuna nuova email", 3000)

    def auto_process_email(self, email):
        """Elabora automaticamente email da mittente monitorato: riusa metodi manuali"""
        try:
            email_id = email.get('id')
            print(f"[AUTO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"[AUTO] INIZIO ELABORAZIONE AUTOMATICA")
            print(f"[AUTO] Email ID: {email_id}")
            print(f"[AUTO] Oggetto: {email.get('subject')}")
            print(f"[AUTO] Mittente: {email.get('from')}")
            print(f"[AUTO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            # Estrai Message-ID puro dall'email_id (formato: "casella:message-id")
            if ':' in email_id:
                message_id = email_id.split(':', 1)[1]
            else:
                message_id = email_id

            print(f"[AUTO] Message-ID: {message_id}")

            # LOCK IN MEMORIA: Previeni elaborazioni duplicate dello stesso Message-ID
            if not hasattr(self, 'processing_message_ids'):
                self.processing_message_ids = set()

            if message_id in self.processing_message_ids:
                print(f"[AUTO] ⚠️ SKIP: Message-ID già in elaborazione in questo momento")
                print(f"[AUTO]     (stessa email ricevuta su caselle multiple)")
                print(f"[AUTO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                return

            # Verifica se questo Message-ID è già stato elaborato nel database
            already_processed = self.db.is_message_id_processed(message_id)
            if already_processed:
                print(f"[AUTO] ⚠️ SKIP: Message-ID già elaborato in precedenza")
                print(f"[AUTO]     Casella originale: {already_processed['mailbox_account']}")
                print(f"[AUTO]     Stato: {already_processed['status']}")
                print(f"[AUTO]     Oggetto: {already_processed['subject']}")
                print(f"[AUTO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                self.statusBar().showMessage(
                    f"⚠️ Email già elaborata su {already_processed['mailbox_account']}",
                    5000
                )
                return

            # Trova l'indice dell'email nella lista
            row = None
            for i, e in enumerate(self.emails):
                if e.get('id') == email_id:
                    row = i
                    break

            if row is None:
                print(f"[AUTO] ❌ Email non trovata nella lista")
                return

            # Aggiungi Message-ID al set di elaborazione in corso
            self.processing_message_ids.add(message_id)
            print(f"[AUTO] Message-ID aggiunto a processing_message_ids: {message_id[:30]}...")

            # Controlla configurazione modalità di elaborazione
            auto_mode = self.config.get('auto_processing', {}).get('mode', 'llm')
            print(f"[AUTO] Modalità: {auto_mode}")

            # Marca questa email per auto-pubblicazione dopo generazione
            if not hasattr(self, 'auto_publish_queue'):
                self.auto_publish_queue = set()
            self.auto_publish_queue.add(email_id)

            if auto_mode == 'format_only':
                # Modalità "Solo impagina e pubblica" - usa LLM con prompt di impaginazione
                print(f"[AUTO] Modalità: impaginazione con LLM")

                # Imposta flag per usare prompt di impaginazione
                self._format_mode = True

                # Genera articolo (con prompt di impaginazione)
                print(f"[AUTO] Chiamata a generate_article(row={row}) con modalità impaginazione")
                self.generate_article(row)

            else:
                # Modalità "Elabora con LLM" (default - prompt completo)
                print(f"[AUTO] Modalità: elaborazione LLM completa")

                # 1. Genera articolo usando il metodo manuale (include download allegati!)
                print(f"[AUTO] Chiamata a generate_article(row={row}) - include download allegati")
                self.generate_article(row)

        except Exception as e:
            import traceback
            print(f"[AUTO] ❌ ERRORE ELABORAZIONE AUTOMATICA: {e}")
            traceback.print_exc()
            self.statusBar().showMessage(f"❌ Errore elaborazione automatica: {e}", 5000)

            # Rimuovi Message-ID dal set in caso di errore
            if hasattr(self, 'processing_message_ids') and 'message_id' in locals():
                self.processing_message_ids.discard(message_id)

    def auto_publish_article(self, email_id, article):
        """Pubblica automaticamente l'articolo usando il metodo manuale"""
        try:
            print(f"[AUTO] Pubblicazione automatica dell'articolo...")

            # Ottieni credenziali CMS (usa gli stessi della GUI)
            cms_username = self.cms_user_input.text().strip() or os.getenv("CMS_USERNAME", "")
            cms_password = self.cms_pass_input.text().strip() or os.getenv("CMS_PASSWORD", "")

            if not cms_username or not cms_password:
                print(f"[AUTO] ❌ Credenziali CMS mancanti")
                self.statusBar().showMessage(f"⚠️ Articolo generato ma non pubblicato (credenziali mancanti)", 5000)
                return

            # Usa STESSA impostazione headless della GUI
            headless = self.headless_combo.currentIndex() == 1  # 0=Visibile, 1=Nascosto
            print(f"[AUTO] Modalità browser dalla GUI: {'Nascosto' if headless else 'Visibile'}")

            print(f"[AUTO] Avvio CMSPublishThread (headless={headless})...")
            self.cms_thread = CMSPublishThread(article, cms_username, cms_password, headless)
            self.cms_thread.progress.connect(lambda msg: print(f"[AUTO] {msg}"))
            self.cms_thread.finished.connect(lambda result: self.on_auto_cms_published(email_id, result))
            self.cms_thread.error.connect(lambda err: self.on_auto_error(email_id, f"Pubblicazione: {err}"))
            self.cms_thread.start()

        except Exception as e:
            import traceback
            print(f"[AUTO] ❌ Errore avvio pubblicazione: {e}")
            traceback.print_exc()

    def on_auto_cms_published(self, email_id, result):
        """Callback quando articolo è pubblicato automaticamente"""
        try:
            print(f"[AUTO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"[AUTO] ✅ ARTICOLO PUBBLICATO CON SUCCESSO!")
            print(f"[AUTO] URL: {result.get('url', 'N/A')}")
            print(f"[AUTO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            # Aggiorna stato email a PUBLISHED
            self.db.update_email_status(email_id, 'PUBLISHED')

            # IMPORTANTE: Aggiorna anche lo status in memoria!
            for email in self.emails:
                if email.get('id') == email_id:
                    email['status'] = 'PUBLISHED'
                    print(f"[MEMORY] Stato aggiornato in memoria per email {email_id}")
                    break

            # Rimuovi Message-ID dal set di elaborazione in corso
            if ':' in email_id:
                message_id = email_id.split(':', 1)[1]
                if hasattr(self, 'processing_message_ids'):
                    self.processing_message_ids.discard(message_id)
                    print(f"[AUTO] Message-ID rimosso da processing_message_ids: {message_id[:30]}...")

            # Aggiorna GUI
            self.populate_email_table()

            # Notifica utente
            self.statusBar().showMessage(f"✅ Articolo pubblicato automaticamente!", 10000)
            QApplication.beep()

            # Invia notifiche (Email/Telegram) se configurate
            self._send_publication_notification(email_id, result)

        except Exception as e:
            print(f"[AUTO] ❌ Errore aggiornamento stato: {e}")

    def on_auto_article_generated(self, email_id, article):
        """Callback quando articolo è stato generato automaticamente - procede con pubblicazione"""
        try:
            print(f"[AUTO] Articolo generato, salvataggio nel DB...")

            # Salva articolo nel database
            self.db.save_article(email_id, article)
            self.generated_articles[email_id] = article

            # Aggiorna stato email a GENERATED
            self.db.update_email_status(email_id, 'GENERATED')

            # IMPORTANTE: Aggiorna anche lo status in memoria!
            for email in self.emails:
                if email.get('id') == email_id:
                    email['status'] = 'GENERATED'
                    print(f"[MEMORY] Stato aggiornato in memoria per email {email_id}")
                    break

            print(f"[AUTO] Articolo salvato, avvio pubblicazione automatica...")

            # 2. Pubblica automaticamente sul CRM
            cms_username = self.config.get('cms', {}).get('username', '')
            cms_password = self.config.get('cms', {}).get('password', '')

            if not cms_username or not cms_password:
                print(f"[AUTO] Credenziali CMS mancanti, pubblicazione annullata")
                self.statusBar().showMessage(f"⚠️ Articolo generato ma non pubblicato (credenziali CMS mancanti)", 5000)
                return

            # Avvia pubblicazione in background (headless)
            self.publish_thread = PublishThread(article, cms_username, cms_password, headless=True)
            self.publish_thread.finished.connect(lambda result: self.on_auto_published(email_id, result))
            self.publish_thread.error.connect(lambda err: self.on_auto_error(email_id, f"Errore pubblicazione: {err}"))
            self.publish_thread.start()

        except Exception as e:
            print(f"[AUTO] Errore salvataggio articolo: {e}")
            self.on_auto_error(email_id, str(e))

    def on_auto_published(self, email_id, result):
        """Callback quando articolo è stato pubblicato automaticamente"""
        try:
            print(f"[AUTO] ✅ Articolo pubblicato con successo!")
            print(f"[AUTO] URL: {result.get('url', 'N/A')}")

            # Aggiorna stato email a PUBLISHED
            self.db.update_email_status(email_id, 'PUBLISHED')

            # IMPORTANTE: Aggiorna anche lo status in memoria!
            for email in self.emails:
                if email.get('id') == email_id:
                    email['status'] = 'PUBLISHED'
                    print(f"[MEMORY] Stato aggiornato in memoria per email {email_id}")
                    break

            # Notifica utente
            self.statusBar().showMessage(f"✅ Articolo pubblicato automaticamente!", 10000)
            QApplication.beep()

            # Ricarica GUI per mostrare nuovo stato
            self.populate_email_table()

        except Exception as e:
            print(f"[AUTO] Errore aggiornamento stato: {e}")

    def on_auto_error(self, email_id, error_msg):
        """Callback per errori durante elaborazione automatica"""
        print(f"[AUTO] ❌ Errore: {error_msg}")
        self.statusBar().showMessage(f"❌ Elaborazione automatica fallita: {error_msg}", 10000)

        # Rimuovi Message-ID dal set di elaborazione in corso
        if ':' in email_id:
            message_id = email_id.split(':', 1)[1]
            if hasattr(self, 'processing_message_ids'):
                self.processing_message_ids.discard(message_id)
                print(f"[AUTO] Message-ID rimosso da processing_message_ids dopo errore: {message_id[:30]}...")

    def closeEvent(self, event):
        """Gestisce chiusura applicazione"""
        # Controlla se ci sono thread di elaborazione/pubblicazione attivi
        active_threads = []
        if hasattr(self, 'article_thread') and self.article_thread and self.article_thread.isRunning():
            active_threads.append('generazione articolo')
        if hasattr(self, 'cms_thread') and self.cms_thread and self.cms_thread.isRunning():
            active_threads.append('pubblicazione CMS')

        # Se ci sono elaborazioni in corso, chiedi conferma
        if active_threads:
            reply = QMessageBox.question(
                self,
                'Elaborazione in corso',
                f'Sono in corso le seguenti operazioni:\n'
                f'- {", ".join(active_threads)}\n\n'
                f'Chiudendo ora, queste operazioni verranno interrotte e i dati potrebbero non essere salvati.\n\n'
                f'Vuoi davvero chiudere?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            else:
                print("[APP] ⚠️ Chiusura forzata durante elaborazione - potrebbero esserci dati non salvati")

        # Aspetta che il thread di controllo email termini
        if hasattr(self, 'email_check_thread') and self.email_check_thread and self.email_check_thread.isRunning():
            print("[APP] Attendo termine controllo email...")
            self.email_check_thread.wait(5000)  # Aspetta max 5 secondi

        # Aspetta thread attivi (max 5 secondi ciascuno)
        if hasattr(self, 'article_thread') and self.article_thread and self.article_thread.isRunning():
            print("[APP] Attendo termine generazione articolo...")
            self.article_thread.wait(5000)

        if hasattr(self, 'cms_thread') and self.cms_thread and self.cms_thread.isRunning():
            print("[APP] Attendo termine pubblicazione CMS...")
            self.cms_thread.wait(5000)

        # Disconnetti tutti gli email processors
        if hasattr(self, 'email_processors'):
            for email_addr, processor in self.email_processors.items():
                try:
                    processor.disconnect()
                    print(f"[OK] Disconnesso da {email_addr}")
                except:
                    pass

        # Chiudi database
        if hasattr(self, 'db') and self.db:
            self.db.close()
            print("[DB] Database chiuso")

        event.accept()


def main():
    """Entry point applicazione"""
    # Imposta encoding UTF-8 per Qt su Windows
    if sys.platform == 'win32':
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        os.environ['PYTHONUTF8'] = '1'

        # Forza codepage UTF-8 su Windows (console)
        import subprocess
        import ctypes
        try:
            # Imposta console UTF-8
            subprocess.run(['chcp', '65001'], shell=True, capture_output=True, check=False)
            # Imposta codepage UTF-8 per il processo corrente
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception as e:
            print(f"[!] Warning UTF-8 setup: {e}")

    app = QApplication(sys.argv)

    # Stile
    app.setStyle("Fusion")

    # Font con supporto completo UTF-8 e caratteri speciali italiani
    from PySide6.QtGui import QFont
    font = QFont("Segoe UI", 9)  # Segoe UI ha ottimo supporto UTF-8
    app.setFont(font)

    # Imposta text codec per Qt (se disponibile)
    try:
        from PySide6.QtCore import QTextCodec
        codec = QTextCodec.codecForName(b"UTF-8")
        QTextCodec.setCodecForLocale(codec)
    except (ImportError, AttributeError):
        # Qt6 usa UTF-8 di default
        pass

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
