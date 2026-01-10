#!/usr/bin/env python3
"""
Sistema di database SQLite per tracciare email, allegati e articoli
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional
import os


class EmailDatabase:
    """Gestisce il database SQLite per email e articoli"""

    def __init__(self, db_path: str = "email_manager.db"):
        self.db_path = db_path
        self.conn = None
        self.init_database()

    def init_database(self):
        """Inizializza il database e crea le tabelle se non esistono"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Permette accesso per nome colonna
        cursor = self.conn.cursor()

        # Tabella EMAIL
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            email_id TEXT PRIMARY KEY,
            mailbox_account TEXT,
            subject TEXT,
            sender TEXT,
            recipient TEXT,
            date TEXT,
            body TEXT,
            status TEXT DEFAULT 'NEW',
            deleted_from_imap BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Tabella MAILBOXES (configurazione caselle email)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS mailboxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_address TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            imap_server TEXT DEFAULT 'imap.register.it',
            imap_port INTEGER DEFAULT 993,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Tabella ATTACHMENTS
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT NOT NULL,
            filename TEXT,
            filepath TEXT,
            content_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (email_id) REFERENCES emails(email_id)
        )
        """)

        # Tabella ARTICLES
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT UNIQUE NOT NULL,
            title TEXT,
            json_data TEXT,
            cms_published BOOLEAN DEFAULT 0,
            cms_url TEXT,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            published_at TIMESTAMP,
            FOREIGN KEY (email_id) REFERENCES emails(email_id)
        )
        """)

        # Indici per performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_status ON emails(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_deleted ON emails(deleted_from_imap)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_email ON attachments(email_id)")

        # Migrazione: aggiungi mailbox_account se non esiste
        cursor.execute("PRAGMA table_info(emails)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'mailbox_account' not in columns:
            print("[DB] Migrazione: aggiunta colonna mailbox_account")
            cursor.execute("ALTER TABLE emails ADD COLUMN mailbox_account TEXT")

            # Popola con valore di default per email esistenti
            cursor.execute("SELECT COUNT(*) FROM emails WHERE mailbox_account IS NULL")
            null_count = cursor.fetchone()[0]

        # Migrazione: aggiungi last_uid_checked a mailboxes per ottimizzazione
        cursor.execute("PRAGMA table_info(mailboxes)")
        mailbox_columns = [row[1] for row in cursor.fetchall()]
        if 'last_uid_checked' not in mailbox_columns:
            print("[DB] Migrazione: aggiunta colonna last_uid_checked per sync incrementale")
            cursor.execute("ALTER TABLE mailboxes ADD COLUMN last_uid_checked INTEGER DEFAULT 0")

        # Migrazione: aggiungi imap_id a emails per sync cancellazioni
        cursor.execute("PRAGMA table_info(emails)")
        email_columns = [row[1] for row in cursor.fetchall()]
        if 'imap_id' not in email_columns:
            print("[DB] Migrazione: aggiunta colonna imap_id per sync IMAP")
            cursor.execute("ALTER TABLE emails ADD COLUMN imap_id TEXT")

        # Assegna mailbox_account alle email esistenti se necessario
        if 'mailbox_account' in columns:
            cursor.execute("SELECT COUNT(*) FROM emails WHERE mailbox_account IS NULL")
            null_count = cursor.fetchone()[0]
            if null_count > 0:
                # Prova a trovare una casella esistente
                cursor.execute("SELECT email_address FROM mailboxes LIMIT 1")
                mailbox = cursor.fetchone()
                if mailbox:
                    default_mailbox = mailbox[0]
                    print(f"[DB] Assegnazione mailbox '{default_mailbox}' a {null_count} email esistenti")
                    cursor.execute("UPDATE emails SET mailbox_account = ? WHERE mailbox_account IS NULL", (default_mailbox,))
                else:
                    print(f"[DB] {null_count} email senza mailbox assegnata (nessuna casella configurata)")

        self.conn.commit()
        print("[DB] Database inizializzato")

    def insert_or_update_email(self, email_data: Dict) -> bool:
        """
        Inserisce o aggiorna un'email nel database

        Args:
            email_data: Dizionario con dati email (id, subject, sender, date, body, to)

        Returns:
            True se inserita/aggiornata, False se errore
        """
        try:
            cursor = self.conn.cursor()

            email_id = email_data.get('id')
            if not email_id:
                return False

            # Controlla se esiste già
            cursor.execute("SELECT email_id FROM emails WHERE email_id = ?", (email_id,))
            exists = cursor.fetchone()

            if exists:
                # Email duplicata - non inserire
                print(f"[DB] Email duplicata ignorata: {email_id}")
                print(f"     Oggetto: {email_data.get('subject', 'N/A')[:50]}")
                # Aggiorna timestamp
                cursor.execute("""
                    UPDATE emails
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE email_id = ?
                """, (email_id,))
            else:
                # Inserisci nuova email
                print(f"[DB] Inserimento nuova email: {email_id}")
                print(f"     Oggetto: {email_data.get('subject', 'N/A')[:50]}")
                cursor.execute("""
                    INSERT INTO emails (email_id, mailbox_account, subject, sender, recipient, date, body, imap_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    email_id,
                    email_data.get('mailbox_account', ''),
                    email_data.get('subject', ''),
                    email_data.get('from', ''),
                    email_data.get('to', ''),
                    email_data.get('date', ''),
                    email_data.get('body', ''),
                    email_data.get('imap_id', '')
                ))

            self.conn.commit()
            return True

        except Exception as e:
            print(f"[DB] Errore inserimento email: {e}")
            return False

    def delete_email(self, email_id: str) -> bool:
        """Elimina un'email dal database (sync cancellazioni IMAP)"""
        try:
            cursor = self.conn.cursor()
            # Elimina allegati associati
            cursor.execute("DELETE FROM attachments WHERE email_id = ?", (email_id,))
            # Elimina email
            cursor.execute("DELETE FROM emails WHERE email_id = ?", (email_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB] Errore eliminazione email: {e}")
            return False

    def insert_attachments(self, email_id: str, attachments: List[Dict]) -> bool:
        """
        Inserisce allegati per un'email

        Args:
            email_id: ID email
            attachments: Lista dizionari con filename, path, content_type

        Returns:
            True se successo
        """
        try:
            cursor = self.conn.cursor()

            for att in attachments:
                # Verifica se già esiste questo allegato
                cursor.execute("""
                    SELECT id FROM attachments
                    WHERE email_id = ? AND filename = ?
                """, (email_id, att.get('filename')))

                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO attachments (email_id, filename, filepath, content_type)
                        VALUES (?, ?, ?, ?)
                    """, (
                        email_id,
                        att.get('filename'),
                        att.get('path'),
                        att.get('content_type')
                    ))

            self.conn.commit()
            return True

        except Exception as e:
            print(f"[DB] Errore inserimento allegati: {e}")
            return False

    def save_article(self, email_id: str, article_data: Dict) -> Optional[int]:
        """
        Salva un articolo generato

        Args:
            email_id: ID email di origine
            article_data: Dizionario con dati articolo

        Returns:
            ID articolo o None se errore
        """
        try:
            cursor = self.conn.cursor()

            # Aggiorna stato email
            cursor.execute("""
                UPDATE emails
                SET status = 'GENERATED', updated_at = CURRENT_TIMESTAMP
                WHERE email_id = ?
            """, (email_id,))

            # Inserisci o aggiorna articolo
            cursor.execute("""
                INSERT OR REPLACE INTO articles (email_id, title, json_data)
                VALUES (?, ?, ?)
            """, (
                email_id,
                article_data.get('titolo', ''),
                json.dumps(article_data, ensure_ascii=False)
            ))

            self.conn.commit()

            # Restituisci ID articolo
            cursor.execute("SELECT id FROM articles WHERE email_id = ?", (email_id,))
            row = cursor.fetchone()
            return row[0] if row else None

        except Exception as e:
            print(f"[DB] Errore salvataggio articolo: {e}")
            return None

    def is_message_id_processed(self, message_id: str) -> Optional[Dict]:
        """
        Verifica se un Message-ID è già stato elaborato (GENERATED o PUBLISHED)
        indipendentemente dalla casella di arrivo

        Args:
            message_id: Message-ID puro (senza prefisso casella)

        Returns:
            Dict con info email se già elaborato, None altrimenti
        """
        try:
            cursor = self.conn.cursor()
            # Cerca email_id che contengono il message_id e hanno status diverso da NEW
            # Pattern: "%:message_id" per matchare qualsiasi casella
            cursor.execute("""
                SELECT email_id, status, mailbox_account, subject
                FROM emails
                WHERE email_id LIKE ? AND status IN ('GENERATED', 'PUBLISHED')
                LIMIT 1
            """, (f'%:{message_id}',))

            result = cursor.fetchone()
            if result:
                return {
                    'email_id': result[0],
                    'status': result[1],
                    'mailbox_account': result[2],
                    'subject': result[3]
                }
            return None
        except Exception as e:
            print(f"[DB] Errore verifica Message-ID: {e}")
            return None

    def update_email_status(self, email_id: str, status: str) -> bool:
        """
        Aggiorna lo stato di una email

        Args:
            email_id: ID email
            status: Nuovo stato (NEW, GENERATED, PUBLISHED)

        Returns:
            True se successo, False altrimenti
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE emails
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE email_id = ?
            """, (status, email_id))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"[DB] Errore aggiornamento stato email: {e}")
            return False

    def mark_article_published(self, email_id: str, cms_url: str = None) -> bool:
        """
        Marca un articolo come pubblicato su CMS

        Args:
            email_id: ID email
            cms_url: URL articolo su CMS (opzionale)

        Returns:
            True se successo
        """
        try:
            cursor = self.conn.cursor()

            # Aggiorna articolo
            cursor.execute("""
                UPDATE articles
                SET cms_published = 1, published_at = CURRENT_TIMESTAMP, cms_url = ?
                WHERE email_id = ?
            """, (cms_url, email_id))

            # Aggiorna stato email
            cursor.execute("""
                UPDATE emails
                SET status = 'PUBLISHED', updated_at = CURRENT_TIMESTAMP
                WHERE email_id = ?
            """, (email_id,))

            self.conn.commit()
            return True

        except Exception as e:
            print(f"[DB] Errore marcatura pubblicazione: {e}")
            return False

    def get_email_with_attachments(self, email_id: str) -> Optional[Dict]:
        """
        Recupera email completa con allegati

        Args:
            email_id: ID email

        Returns:
            Dizionario con email e lista attachments
        """
        try:
            cursor = self.conn.cursor()

            # Email
            cursor.execute("SELECT * FROM emails WHERE email_id = ?", (email_id,))
            email_row = cursor.fetchone()

            if not email_row:
                return None

            email_data = dict(email_row)

            # Allegati
            cursor.execute("SELECT * FROM attachments WHERE email_id = ?", (email_id,))
            attachments = [dict(row) for row in cursor.fetchall()]

            email_data['attachments'] = attachments

            return email_data

        except Exception as e:
            print(f"[DB] Errore recupero email: {e}")
            return None

    def get_recent_emails(self, limit: int = 200, status_filter: str = None) -> List[Dict]:
        """
        Recupera le email più recenti (LAZY LOADING - veloce!)

        Args:
            limit: Numero massimo di email da caricare
            status_filter: Filtra per stato (NEW, GENERATED, PUBLISHED)

        Returns:
            Lista dizionari email
        """
        try:
            cursor = self.conn.cursor()

            query = "SELECT * FROM emails WHERE 1=1"
            params = []

            if status_filter:
                query += " AND status = ?"
                params.append(status_filter)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            emails = [dict(row) for row in cursor.fetchall()]

            # NON caricare allegati qui (lazy load quando necessario)
            for email in emails:
                email['attachments'] = []  # Vuoto, caricato on-demand

            return emails

        except Exception as e:
            print(f"[DB] Errore recupero email recenti: {e}")
            return []

    def get_all_emails(self, include_deleted: bool = False, status_filter: str = None) -> List[Dict]:
        """
        Recupera tutte le email (LENTO - usa get_recent_emails quando possibile!)

        Args:
            include_deleted: Include email eliminate da IMAP
            status_filter: Filtra per stato (NEW, GENERATED, PUBLISHED)

        Returns:
            Lista dizionari email
        """
        try:
            cursor = self.conn.cursor()

            query = "SELECT * FROM emails WHERE 1=1"
            params = []

            if status_filter:
                query += " AND status = ?"
                params.append(status_filter)

            query += " ORDER BY date DESC"

            cursor.execute(query, params)
            emails = [dict(row) for row in cursor.fetchall()]

            # Aggiungi allegati per ogni email
            for email in emails:
                cursor.execute("SELECT * FROM attachments WHERE email_id = ?", (email['email_id'],))
                email['attachments'] = [dict(row) for row in cursor.fetchall()]

            return emails

        except Exception as e:
            print(f"[DB] Errore recupero email: {e}")
            return []

    def get_article_by_email(self, email_id: str) -> Optional[Dict]:
        """Recupera articolo generato per un'email"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM articles WHERE email_id = ?", (email_id,))
            row = cursor.fetchone()

            if row:
                article = dict(row)
                # Parse JSON data
                article['data'] = json.loads(article['json_data'])
                return article

            return None

        except Exception as e:
            print(f"[DB] Errore recupero articolo: {e}")
            return None

    def sync_with_imap(self, current_email_ids: List[str]) -> int:
        """
        Sincronizza database con stato IMAP (hard delete)
        Elimina fisicamente email, articoli e file allegati quando eliminati da IMAP

        Args:
            current_email_ids: Lista ID email attualmente su IMAP

        Returns:
            Numero email eliminate
        """
        try:
            cursor = self.conn.cursor()

            if not current_email_ids:
                # Nessuna email su IMAP, elimina tutto
                cursor.execute("SELECT email_id FROM emails")
                to_delete = [row[0] for row in cursor.fetchall()]
            else:
                # Trova email da eliminare (non più su IMAP)
                placeholders = ','.join('?' * len(current_email_ids))
                query = f"SELECT email_id FROM emails WHERE email_id NOT IN ({placeholders})"
                cursor.execute(query, current_email_ids)
                to_delete = [row[0] for row in cursor.fetchall()]

            deleted_count = 0

            for email_id in to_delete:
                # 1. Recupera allegati per eliminare i file fisici
                cursor.execute("SELECT filepath FROM attachments WHERE email_id = ?", (email_id,))
                attachments = cursor.fetchall()

                for (filepath,) in attachments:
                    if filepath and os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                            print(f"[DB] File eliminato: {filepath}")
                        except Exception as e:
                            print(f"[DB] Errore eliminazione file {filepath}: {e}")

                # 2. Elimina allegati dal database
                cursor.execute("DELETE FROM attachments WHERE email_id = ?", (email_id,))

                # 3. Elimina articolo
                cursor.execute("DELETE FROM articles WHERE email_id = ?", (email_id,))

                # 4. Elimina email
                cursor.execute("DELETE FROM emails WHERE email_id = ?", (email_id,))

                deleted_count += 1

            self.conn.commit()

            if deleted_count > 0:
                print(f"[DB] {deleted_count} email eliminate fisicamente (con allegati)")

            return deleted_count

        except Exception as e:
            print(f"[DB] Errore sincronizzazione: {e}")
            return 0

    def get_stats(self) -> Dict:
        """Statistiche database"""
        try:
            cursor = self.conn.cursor()

            stats = {}

            # Totale email
            cursor.execute("SELECT COUNT(*) FROM emails WHERE deleted_from_imap = 0")
            stats['total_emails'] = cursor.fetchone()[0]

            # Email per stato
            cursor.execute("""
                SELECT status, COUNT(*)
                FROM emails
                WHERE deleted_from_imap = 0
                GROUP BY status
            """)
            stats['by_status'] = {row[0]: row[1] for row in cursor.fetchall()}

            # Articoli pubblicati
            cursor.execute("SELECT COUNT(*) FROM articles WHERE cms_published = 1")
            stats['published_articles'] = cursor.fetchone()[0]

            # Totale allegati
            cursor.execute("SELECT COUNT(*) FROM attachments")
            stats['total_attachments'] = cursor.fetchone()[0]

            return stats

        except Exception as e:
            print(f"[DB] Errore statistiche: {e}")
            return {}

    # ===== GESTIONE MAILBOXES =====

    def add_mailbox(self, email_address: str, password: str,
                    imap_server: str = "imap.register.it", imap_port: int = 993) -> bool:
        """Aggiunge una casella email da monitorare"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO mailboxes (email_address, password, imap_server, imap_port)
                VALUES (?, ?, ?, ?)
            """, (email_address, password, imap_server, imap_port))
            self.conn.commit()
            print(f"[DB] Mailbox aggiunta: {email_address}")
            return True
        except Exception as e:
            print(f"[DB] Errore aggiunta mailbox: {e}")
            return False

    def get_all_mailboxes(self, only_enabled: bool = True) -> List[Dict]:
        """Recupera tutte le caselle email configurate"""
        try:
            cursor = self.conn.cursor()
            query = "SELECT * FROM mailboxes"
            if only_enabled:
                query += " WHERE enabled = 1"
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"[DB] Errore recupero mailboxes: {e}")
            return []

    def update_mailbox_last_uid(self, email_address: str, last_uid: int) -> bool:
        """Aggiorna l'ultimo UID controllato per una casella (ottimizzazione sync)"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE mailboxes
                SET last_uid_checked = ?
                WHERE email_address = ?
            """, (last_uid, email_address))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB] Errore aggiornamento last_uid: {e}")
            return False

    def get_mailbox_last_uid(self, email_address: str) -> int:
        """Recupera l'ultimo UID controllato per una casella"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT last_uid_checked FROM mailboxes
                WHERE email_address = ?
            """, (email_address,))
            result = cursor.fetchone()
            return result['last_uid_checked'] if result else 0
        except Exception as e:
            print(f"[DB] Errore recupero last_uid: {e}")
            return 0

    def get_emails_by_mailbox(self, mailbox_account: str) -> List[dict]:
        """Ottiene tutte le email di una casella specifica (per sync cancellazioni)"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT email_id, imap_id FROM emails
                WHERE mailbox_account = ? AND status != 'DELETED'
            """, (mailbox_account,))
            # IMPORTANTE: Converti esplicitamente in dizionari Python puri (thread-safe)
            results = []
            for row in cursor.fetchall():
                results.append({
                    'email_id': row['email_id'],
                    'imap_id': row['imap_id']
                })
            return results
        except Exception as e:
            print(f"[DB] Errore get_emails_by_mailbox: {e}")
            return []

    def remove_mailbox(self, email_address: str) -> bool:
        """Rimuove una casella email"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM mailboxes WHERE email_address = ?", (email_address,))
            self.conn.commit()
            print(f"[DB] Mailbox rimossa: {email_address}")
            return True
        except Exception as e:
            print(f"[DB] Errore rimozione mailbox: {e}")
            return False

    def toggle_mailbox(self, email_address: str, enabled: bool) -> bool:
        """Attiva/disattiva monitoraggio casella"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE mailboxes SET enabled = ? WHERE email_address = ?
            """, (1 if enabled else 0, email_address))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB] Errore toggle mailbox: {e}")
            return False

    def remove_duplicate_emails(self):
        """
        Rimuove email duplicate dal database.
        Mantiene solo l'email più recente per ogni combinazione di subject+date+sender.

        Returns:
            int: Numero di duplicati rimossi
        """
        try:
            cursor = self.conn.cursor()

            # Trova duplicati basati su subject + date + sender
            # (email identiche anche se con Message-ID diverso)
            cursor.execute("""
                SELECT subject, date, sender, COUNT(*) as count, GROUP_CONCAT(email_id) as ids
                FROM emails
                GROUP BY subject, date, sender
                HAVING count > 1
            """)

            duplicates = cursor.fetchall()
            total_removed = 0

            for dup in duplicates:
                subject, date, sender, count, ids_str = dup
                ids = ids_str.split(',')

                print(f"[DB] Trovati {count} duplicati per: {subject[:50]}...")

                # Mantieni solo il primo ID, elimina gli altri
                to_remove = ids[1:]

                for email_id in to_remove:
                    # Elimina allegati associati
                    cursor.execute("DELETE FROM attachments WHERE email_id = ?", (email_id,))
                    # Elimina articoli associati
                    cursor.execute("DELETE FROM articles WHERE email_id = ?", (email_id,))
                    # Elimina email
                    cursor.execute("DELETE FROM emails WHERE email_id = ?", (email_id,))
                    total_removed += 1
                    print(f"[DB] Rimosso duplicato: {email_id}")

            self.conn.commit()
            print(f"[DB] Totale duplicati rimossi: {total_removed}")
            return total_removed

        except Exception as e:
            print(f"[DB] Errore rimozione duplicati: {e}")
            return 0

    def close(self):
        """Chiude connessione database"""
        if self.conn:
            self.conn.close()
            print("[DB] Connessione chiusa")


# Funzioni di utilità
def migrate_existing_data():
    """Migra dati esistenti da JSON a SQLite (se necessario)"""
    pass


if __name__ == "__main__":
    # Test
    db = EmailDatabase()
    print(db.get_stats())
    db.close()
