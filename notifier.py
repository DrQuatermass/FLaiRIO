"""
Sistema di notifiche per pubblicazione automatica articoli
Supporta Email e Telegram
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import requests
import json


class Notifier:
    """Classe per inviare notifiche di pubblicazione articoli"""

    def __init__(self, config: dict):
        """
        Inizializza il notifier con la configurazione

        Args:
            config: Dizionario con configurazione notifiche
                {
                    'email': {
                        'enabled': bool,
                        'smtp_server': str,
                        'smtp_port': int,
                        'smtp_username': str,
                        'smtp_password': str,
                        'from_email': str,
                        'to_emails': list[str]
                    },
                    'telegram': {
                        'enabled': bool,
                        'bot_token': str,
                        'chat_ids': list[str]
                    }
                }
        """
        self.config = config

    def send_publication_notification(self, article_info: dict) -> dict:
        """
        Invia notifica di pubblicazione articolo

        Args:
            article_info: Informazioni articolo pubblicato
                {
                    'titolo': str,
                    'categoria': str,
                    'url': str,
                    'article_id': str,
                    'photos_uploaded': int,
                    'email_subject': str,
                    'email_sender': str
                }

        Returns:
            Dizionario con risultati invio {email: bool, telegram: bool}
        """
        results = {'email': False, 'telegram': False}

        # Invia notifica Email se abilitata
        if self.config.get('email', {}).get('enabled', False):
            try:
                email_sent = self._send_email_notification(article_info)
                results['email'] = email_sent
                if email_sent:
                    print(f"[NOTIF] ✓ Email inviata")
            except Exception as e:
                print(f"[NOTIF] ✗ Errore invio email: {e}")

        # Invia notifica Telegram se abilitata
        if self.config.get('telegram', {}).get('enabled', False):
            try:
                telegram_sent = self._send_telegram_notification(article_info)
                results['telegram'] = telegram_sent
                if telegram_sent:
                    print(f"[NOTIF] ✓ Telegram inviato")
            except Exception as e:
                print(f"[NOTIF] ✗ Errore invio telegram: {e}")

        return results

    def _send_email_notification(self, article_info: dict) -> bool:
        """Invia notifica via email"""
        email_config = self.config.get('email', {})

        smtp_server = email_config.get('smtp_server')
        smtp_port = email_config.get('smtp_port')
        smtp_username = email_config.get('smtp_username')
        smtp_password = email_config.get('smtp_password')
        from_email = email_config.get('from_email')
        to_emails = email_config.get('to_emails', [])

        if not all([smtp_server, smtp_port, smtp_username, smtp_password, from_email, to_emails]):
            print(f"[NOTIF] Configurazione email incompleta")
            return False

        # Crea messaggio
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"✅ Articolo pubblicato: {article_info['titolo']}"
        msg['From'] = from_email
        msg['To'] = ', '.join(to_emails)

        # Corpo del messaggio in HTML
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .info {{ background-color: #f9f9f9; padding: 15px; margin: 10px 0; border-left: 4px solid #4CAF50; }}
                .label {{ font-weight: bold; color: #555; }}
                .footer {{ color: #999; font-size: 12px; padding: 20px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>🎉 Articolo Pubblicato Automaticamente</h2>
            </div>
            <div class="content">
                <div class="info">
                    <p><span class="label">📰 Titolo:</span><br>{article_info['titolo']}</p>
                </div>
                <div class="info">
                    <p><span class="label">📁 Categoria:</span> {article_info.get('categoria', 'N/A')}</p>
                </div>
                <div class="info">
                    <p><span class="label">🔗 URL Articolo:</span><br>
                    <a href="{article_info.get('url', '#')}">{article_info.get('url', '#')}</a></p>
                </div>
                <div class="info">
                    <p><span class="label">🆔 Article ID:</span> {article_info.get('article_id', 'N/A')}</p>
                </div>
                <div class="info">
                    <p><span class="label">📸 Foto caricate:</span> {article_info.get('photos_uploaded', 0)}</p>
                </div>
                <div class="info">
                    <p><span class="label">📧 Email originale:</span><br>
                    <strong>Da:</strong> {article_info.get('email_sender', 'N/A')}<br>
                    <strong>Oggetto:</strong> {article_info.get('email_subject', 'N/A')}</p>
                </div>
                <div class="info">
                    <p><span class="label">🕐 Data pubblicazione:</span> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
                </div>
            </div>
            <div class="footer">
                <p>Notifica automatica da FLaiRIO - Email-to-Article Automation System</p>
            </div>
        </body>
        </html>
        """

        # Testo plain alternativo
        text_body = f"""
✅ ARTICOLO PUBBLICATO AUTOMATICAMENTE

📰 Titolo: {article_info['titolo']}
📁 Categoria: {article_info.get('categoria', 'N/A')}
🔗 URL: {article_info.get('url', '#')}
🆔 Article ID: {article_info.get('article_id', 'N/A')}
📸 Foto caricate: {article_info.get('photos_uploaded', 0)}

📧 Email originale:
   Da: {article_info.get('email_sender', 'N/A')}
   Oggetto: {article_info.get('email_subject', 'N/A')}

🕐 Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

---
Notifica automatica da FLaiRIO
        """

        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        # Invia email
        try:
            # Gestione diverse porte SMTP
            if smtp_port == 465:
                # SSL diretto su porta 465
                with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
                    server.login(smtp_username, smtp_password)
                    server.send_message(msg)
            elif smtp_port == 25:
                # Porta 25 standard (Register.it) - prova con e senza TLS
                try:
                    with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                        server.ehlo()
                        # Prova STARTTLS se disponibile
                        if server.has_extn('STARTTLS'):
                            server.starttls()
                            server.ehlo()
                        server.login(smtp_username, smtp_password)
                        server.send_message(msg)
                except Exception as e:
                    print(f"[NOTIF] Tentativo porta 25 fallito: {e}")
                    raise
            else:
                # Porta 587 con STARTTLS (Gmail, standard)
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls()
                    server.login(smtp_username, smtp_password)
                    server.send_message(msg)
            return True
        except Exception as e:
            print(f"[NOTIF] Errore SMTP: {e}")
            return False

    def _send_telegram_notification(self, article_info: dict) -> bool:
        """Invia notifica via Telegram"""
        telegram_config = self.config.get('telegram', {})

        bot_token = telegram_config.get('bot_token')
        chat_ids = telegram_config.get('chat_ids', [])

        if not bot_token or not chat_ids:
            print(f"[NOTIF] Configurazione Telegram incompleta")
            return False

        # Formatta messaggio
        message = f"""
🎉 *Articolo Pubblicato*

📰 *{article_info['titolo']}*

📁 Categoria: {article_info.get('categoria', 'N/A')}
🆔 ID: {article_info.get('article_id', 'N/A')}
📸 Foto: {article_info.get('photos_uploaded', 0)}

🔗 [Visualizza articolo]({article_info.get('url', '#')})

📧 Da: {article_info.get('email_sender', 'N/A')}

🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}
        """

        # Invia a tutte le chat configurate
        success_count = 0
        for chat_id in chat_ids:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'Markdown',
                    'disable_web_page_preview': False
                }
                response = requests.post(url, json=payload, timeout=10)

                if response.status_code == 200:
                    success_count += 1
                else:
                    print(f"[NOTIF] Telegram errore chat {chat_id}: {response.status_code}")
            except Exception as e:
                print(f"[NOTIF] Errore invio telegram a {chat_id}: {e}")

        return success_count > 0

    def test_email(self) -> dict:
        """Testa la configurazione email inviando un messaggio di prova"""
        test_article = {
            'titolo': 'Test Notifica Email',
            'categoria': 'Test',
            'url': 'https://example.com/test',
            'article_id': 'TEST-123',
            'photos_uploaded': 0,
            'email_sender': 'test@example.com',
            'email_subject': 'Test Email Subject'
        }

        try:
            result = self._send_email_notification(test_article)
            return {'success': result, 'error': None if result else 'Invio fallito'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def test_telegram(self) -> dict:
        """Testa la configurazione Telegram inviando un messaggio di prova"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_ids = telegram_config.get('chat_ids', [])

        if not bot_token or not chat_ids:
            return {'success': False, 'error': 'Configurazione incompleta'}

        test_message = f"""
🧪 *Test Notifica FLaiRIO*

Questo è un messaggio di test per verificare che le notifiche Telegram funzionino correttamente.

✅ Bot configurato correttamente
🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        """

        try:
            success_count = 0
            for chat_id in chat_ids:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    'chat_id': chat_id,
                    'text': test_message,
                    'parse_mode': 'Markdown'
                }
                response = requests.post(url, json=payload, timeout=10)

                if response.status_code == 200:
                    success_count += 1

            if success_count > 0:
                return {'success': True, 'error': None, 'sent_count': success_count}
            else:
                return {'success': False, 'error': 'Nessun messaggio inviato'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
