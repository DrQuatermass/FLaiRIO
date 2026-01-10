#!/usr/bin/env python3
"""
Sistema per processare email filtrate e generare articoli con LLM
"""

import imaplib
import email
from email.header import decode_header
import os
import json
from datetime import datetime
from typing import List, Dict, Optional

# Flag debug - impostare a True solo per debugging approfondito
DEBUG_MODE = False


class EmailProcessor:
    """
    Classe per processare email da webmail.register.it
    """

    def __init__(self, username: str, password: str,
                 imap_server: str = "imap.register.it",
                 imap_port: int = 993):
        self.username = username
        self.password = password
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.mail = None

    def connect(self) -> bool:
        """Connessione al server IMAP"""
        try:
            print(f"[IMAP] Connessione a {self.imap_server}:{self.imap_port} per {self.username}...")
            self.mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            print(f"[IMAP] SSL connesso, tentativo login...")
            self.mail.login(self.username, self.password)
            print(f"[OK] Connesso e autenticato come {self.username}")
            return True
        except imaplib.IMAP4.error as e:
            print(f"[X] Errore IMAP per {self.username}: {e}")
            print(f"    Server: {self.imap_server}:{self.imap_port}")
            return False
        except Exception as e:
            print(f"[X] Errore di connessione per {self.username}: {type(e).__name__}: {e}")
            print(f"    Server: {self.imap_server}:{self.imap_port}")
            import traceback
            traceback.print_exc()
            return False

    def disconnect(self):
        """Disconnessione dal server"""
        if self.mail:
            try:
                self.mail.logout()
                print("[OK] Disconnesso dal server")
            except:
                pass

    @staticmethod
    def decode_str(s) -> str:
        """Decodifica stringhe email (inclusi header MIME-encoded)"""
        if s is None:
            return ""

        if isinstance(s, bytes):
            return s.decode('utf-8', errors='ignore')

        # IMPORTANTE: Anche le str possono essere MIME-encoded (=?utf-8?q?...)
        # Usa sempre decode_header per decodificare correttamente
        try:
            decoded_parts = []
            for part, encoding in decode_header(s):
                if isinstance(part, bytes):
                    decoded_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
                else:
                    decoded_parts.append(str(part))

            result = ''.join(decoded_parts)
            # Rimuovi newline e spazi extra
            return result.replace('\n', ' ').replace('\r', '').strip()
        except:
            # Fallback: restituisci la stringa originale
            return str(s)

    @staticmethod
    def get_email_body(msg) -> str:
        """Estrae il corpo dell'email"""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if "attachment" not in content_disposition:
                    if content_type == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            break
                        except:
                            pass
                    elif content_type == "text/html" and not body:
                        try:
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        except:
                            pass
        else:
            try:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                body = str(msg.get_payload())

        return body

    @staticmethod
    def get_attachments(msg) -> List[Dict]:
        """
        Estrae gli allegati dall'email e li salva nella cartella attachments/

        Returns:
            Lista di dizionari con info sugli allegati (filename, path, content_type)
        """
        attachments = []

        if not msg.is_multipart():
            return attachments

        # Crea cartella attachments se non esiste
        attachments_dir = "attachments"
        if not os.path.exists(attachments_dir):
            os.makedirs(attachments_dir)
            print(f"[OK] Cartella {attachments_dir}/ creata")

        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            filename = part.get_filename()

            # Debug: mostra tutte le parti con immagini
            if content_type.startswith('image/'):
                print(f"[DEBUG] Trovata immagine: type={content_type}, filename={filename}, disposition={content_disposition[:50] if content_disposition else 'None'}")

            # Verifica se è un allegato (due metodi: disposition o filename con image)
            is_attachment = "attachment" in content_disposition.lower() or (filename and content_type.startswith('image/'))

            if is_attachment and filename:
                # Decodifica il nome file
                filename = EmailProcessor.decode_str(filename)

                # Filtra solo immagini
                if content_type.startswith('image/'):
                        # Salva l'allegato
                        filepath = os.path.join(attachments_dir, filename)

                        try:
                            with open(filepath, 'wb') as f:
                                f.write(part.get_payload(decode=True))

                            attachments.append({
                                'filename': filename,
                                'path': filepath,
                                'content_type': content_type
                            })

                            print(f"[OK] Allegato salvato: {filename}")
                        except Exception as e:
                            print(f"[X] Errore salvataggio allegato {filename}: {e}")

        return attachments

    def filter_emails_by_sender(self, sender_email: str,
                                 mailbox: str = "INBOX",
                                 only_unseen: bool = False) -> List[Dict]:
        """
        Filtra email per mittente specifico

        Args:
            sender_email: indirizzo email del mittente
            mailbox: casella di posta (default INBOX)
            only_unseen: se True, prende solo email non lette

        Returns:
            Lista di dizionari con info email
        """
        if not self.mail:
            print("[X] Non connesso al server")
            return []

        try:
            self.mail.select(mailbox)

            # Costruisci criteri di ricerca
            criteria = f'FROM "{sender_email}"'
            if only_unseen:
                criteria = f'({criteria} UNSEEN)'

            # Cerca email
            status, messages = self.mail.search(None, criteria)

            if status != "OK":
                print(f"[X] Errore nella ricerca")
                return []

            email_ids = messages[0].split()
            print(f"[OK] Trovate {len(email_ids)} email da {sender_email}")

            # Recupera dettagli email
            emails = []
            for email_id in email_ids:
                try:
                    status, msg_data = self.mail.fetch(email_id, "(RFC822)")

                    if status != "OK":
                        continue

                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])

                            email_info = {
                                'id': email_id.decode(),
                                'from': self.decode_str(msg.get("From", "")),
                                'subject': self.decode_str(msg.get("Subject", "")),
                                'date': msg.get("Date", ""),
                                'body': self.get_email_body(msg),
                                'to': self.decode_str(msg.get("To", "")),
                                'attachments': self.get_attachments(msg),  # Estrai allegati
                            }

                            emails.append(email_info)

                except Exception as e:
                    print(f"[X] Errore nel recupero email: {e}")
                    continue

            return emails

        except Exception as e:
            print(f"[X] Errore: {e}")
            return []

    def filter_emails_by_multiple_senders(self, sender_list: List[str],
                                          mailbox: str = "INBOX",
                                          only_unseen: bool = False) -> Dict[str, List[Dict]]:
        """
        Filtra email per una lista di mittenti

        Returns:
            Dizionario con mittente come chiave e lista email come valore
        """
        results = {}

        for sender in sender_list:
            print(f"\n[EMAIL] Cerco email da: {sender}")
            emails = self.filter_emails_by_sender(sender, mailbox, only_unseen)
            if emails:
                results[sender] = emails

        return results

    def mark_as_read(self, email_id: str):
        """Marca un'email come letta"""
        try:
            self.mail.store(email_id, '+FLAGS', '\\Seen')
        except Exception as e:
            print(f"[X] Errore nel marcare email come letta: {e}")

    def save_emails_to_json(self, emails: Dict[str, List[Dict]],
                           filename: str = "emails_filtered.json"):
        """Salva le email filtrate in un file JSON"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(emails, f, ensure_ascii=False, indent=2)
            print(f"[OK] Email salvate in {filename}")
        except Exception as e:
            print(f"[X] Errore nel salvare email: {e}")

    def get_mailbox_status(self, mailbox: str = "INBOX") -> dict:
        """
        Ottiene lo status della mailbox (UIDNEXT, MESSAGES, etc.) senza scaricare email
        MOLTO PIÙ VELOCE di search
        """
        try:
            # Prima seleziona la mailbox
            self.mail.select(mailbox)

            # Usa STATUS per ottenere info velocemente
            status, data = self.mail.status(mailbox, '(MESSAGES UNSEEN UIDNEXT)')
            if status == 'OK' and data and data[0]:
                # Parse result: b'INBOX (MESSAGES 1512 UNSEEN 5 UIDNEXT 1513)'
                result_str = data[0].decode() if isinstance(data[0], bytes) else data[0]
                info = {}
                import re
                matches = re.findall(r'(\w+)\s+(\d+)', result_str)
                for key, value in matches:
                    info[key] = int(value)
                print(f"[STATUS] {mailbox}: {info}")
                return info
        except Exception as e:
            print(f"[!] Errore get_mailbox_status: {e}")
        return {'MESSAGES': 0, 'UNSEEN': 0, 'UIDNEXT': 0}

    def get_all_imap_uids(self, mailbox: str = "INBOX") -> set:
        """
        Ottiene tutti gli UID presenti sul server IMAP (per sync cancellazioni)
        Restituisce un set di UID (come stringhe)
        """
        try:
            if not self.mail:
                if not self.connect():
                    return set()

            self.mail.select(mailbox)

            # Cerca tutti gli UID sul server
            status, messages = self.mail.uid('SEARCH', None, 'ALL')
            if status != 'OK':
                return set()

            # Restituisce set di UID (come stringhe)
            uid_list = messages[0].split()
            return {uid.decode() for uid in uid_list}
        except Exception as e:
            print(f"[!] Errore get_all_imap_uids: {e}")
            return set()

    def check_for_new_emails(self, mailbox: str = "INBOX", only_unseen: bool = False, existing_ids: set = None, download_attachments: bool = False, last_uid: int = 0) -> List[Dict]:
        """
        Controlla nuove email OTTIMIZZATO - usa UID per scaricare solo nuove

        Args:
            mailbox: casella di posta
            only_unseen: se True, prende solo email non lette (default: False = tutte)
            existing_ids: set di ID email già presenti nel database (per evitare duplicati)
            download_attachments: se True, scarica anche gli allegati (default: False)
            last_uid: ultimo UID controllato (ottimizzazione)

        Returns:
            Lista di nuove email trovate
        """
        if not self.mail:
            print("[X] Non connesso al server")
            return []

        if existing_ids is None:
            existing_ids = set()

        try:
            # Reconnect se necessario (gestisce errori SSL)
            try:
                self.mail.select(mailbox)
            except Exception as e:
                print(f"[!] Riconnessione necessaria: {e}")
                if self.connect():
                    self.mail.select(mailbox)
                else:
                    return []

            # OTTIMIZZAZIONE: Se abbiamo last_uid, cerca solo email successive
            # IMPORTANTE: Usa SEMPRE uid('SEARCH') per ottenere UID, non sequence numbers!
            if last_uid > 0:
                # Cerca solo email con UID maggiore dell'ultimo conosciuto
                if DEBUG_MODE:
                    print(f"[SEARCH] Criterio: UID {last_uid + 1}:*")
                if only_unseen:
                    # IMAP syntax: UID range AND UNSEEN
                    status, messages = self.mail.uid('SEARCH', f'{last_uid + 1}:*', 'UNSEEN')
                else:
                    # Cerca tutte le email con UID > last_uid
                    status, messages = self.mail.uid('SEARCH', None, f'UID {last_uid + 1}:*')
            else:
                # Fallback: cerca tutte le email (usa UID search, non search normale)
                if DEBUG_MODE:
                    criteria = 'UNSEEN' if only_unseen else 'ALL'
                    print(f"[SEARCH] Criterio: {criteria}")
                status, messages = self.mail.uid('SEARCH', None, criteria)

            if status != "OK":
                print(f"[X] SEARCH fallito: status={status}")
                return []

            email_ids = messages[0].split()

            if DEBUG_MODE and email_ids:
                print(f"[SEARCH] Risultati UID: {[uid.decode() for uid in email_ids[:5]]}... (totale: {len(email_ids)})")

            if not email_ids:
                return []

            # Log solo se troviamo email (importante)
            if email_ids:
                print(f"[OK] Trovate {len(email_ids)} email totali su IMAP")

            # Recupera dettagli email (solo quelle non già nel DB)
            emails = []
            for email_id in email_ids:
                email_id_str = email_id.decode()

                # NOTA: Se usiamo last_uid, non serve controllare existing_ids
                # perché sappiamo che tutte le email con UID > last_uid sono nuove!
                # Il controllo existing_ids serve solo quando last_uid = 0 (primo sync)

                try:
                    # Usa uid('FETCH') per essere consistente con uid('SEARCH')
                    status, msg_data = self.mail.uid('FETCH', email_id, "(RFC822)")

                    if status != "OK":
                        continue

                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])

                            # ID univoco = casella + Message-ID per evitare duplicati tra caselle
                            message_id = msg.get("Message-ID", "").strip()
                            if message_id:
                                # Rimuovi < > se presenti nel Message-ID
                                message_id = message_id.strip('<>')
                                unique_id = f"{self.username}:{message_id}"
                            else:
                                # Fallback: combina username con IMAP ID locale
                                unique_id = f"{self.username}:imap_{email_id_str}"

                            # Controlla duplicati solo se last_uid = 0 (primo sync)
                            # Con last_uid > 0, sappiamo che sono tutte email nuove
                            if last_uid == 0 and existing_ids and unique_id in existing_ids:
                                continue

                            email_info = {
                                'id': unique_id,
                                'imap_id': email_id_str,  # Mantieni anche ID IMAP locale
                                'from': self.decode_str(msg.get("From", "")),
                                'subject': self.decode_str(msg.get("Subject", "")),
                                'date': msg.get("Date", ""),
                                'body': self.get_email_body(msg),
                                'to': self.decode_str(msg.get("To", "")),
                                'attachments': self.get_attachments(msg) if download_attachments else [],
                            }

                            emails.append(email_info)

                except Exception as e:
                    print(f"[X] Errore nel recupero email: {e}")
                    continue

            if emails:
                print(f"[OK] {len(emails)} email NUOVE (non ancora nel DB)")

            return emails

        except Exception as e:
            print(f"[X] Errore check_for_new_emails: {e}")
            # Prova a riconnettersi per il prossimo check
            try:
                self.disconnect()
                self.connect()
            except:
                pass
            return []

    def fetch_attachments_for_email(self, email_id: str, mailbox: str = "INBOX") -> List[Dict]:
        """
        Scarica gli allegati per una email specifica (on-demand)

        Args:
            email_id: ID dell'email (stringa)
            mailbox: casella di posta

        Returns:
            Lista di allegati scaricati
        """
        if not self.mail:
            print("[X] Non connesso al server")
            return []

        try:
            # Reconnect se necessario
            try:
                self.mail.select(mailbox)
            except Exception as e:
                print(f"[!] Riconnessione necessaria: {e}")
                if self.connect():
                    self.mail.select(mailbox)
                else:
                    return []

            print(f"[OK] Scaricamento allegati per IMAP UID: {email_id}")

            # Usa UID FETCH invece di FETCH normale
            # email_id è l'UID numerico (es. "264846")
            status, msg_data = self.mail.uid('FETCH', email_id, "(RFC822)")

            if status != "OK":
                print(f"[X] Errore fetch email")
                return []

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    attachments = self.get_attachments(msg)
                    print(f"[OK] Scaricati {len(attachments)} allegati")
                    return attachments

            return []

        except Exception as e:
            print(f"[X] Errore scaricamento allegati: {e}")
            return []


def main():
    """Esempio di utilizzo"""

    # Credenziali
    username = os.getenv("EMAIL_USER", "posta@voce.it")
    password = os.getenv("EMAIL_PASS", "@voce_001")

    # Lista mittenti da filtrare (da configurare)
    mittenti_importanti = [
        "redazione@esempio.it",
        "comunicati@agenzia.it",
        # Aggiungi qui altri mittenti
    ]

    # Crea processor
    processor = EmailProcessor(username, password)

    try:
        # Connetti
        if not processor.connect():
            return

        # Filtra email per mittenti specifici
        # only_unseen=True per prendere solo non lette
        filtered_emails = processor.filter_emails_by_multiple_senders(
            mittenti_importanti,
            only_unseen=False  # Cambia a True per prendere solo non lette
        )

        # Mostra risultati
        print("\n" + "=" * 80)
        print("RIEPILOGO EMAIL FILTRATE")
        print("=" * 80)

        for sender, emails in filtered_emails.items():
            print(f"\n📨 Mittente: {sender}")
            print(f"   Numero email: {len(emails)}")

            for i, em in enumerate(emails, 1):
                print(f"\n   Email {i}:")
                print(f"   - Oggetto: {em['subject']}")
                print(f"   - Data: {em['date']}")
                print(f"   - Anteprima: {em['body'][:100]}...")

        # Salva in JSON per processamento successivo
        if filtered_emails:
            processor.save_emails_to_json(filtered_emails)

    finally:
        processor.disconnect()


if __name__ == "__main__":
    main()
