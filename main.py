#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script principale per automazione email -> articoli -> CRM
Orchestrazione completa del workflow
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List

# Carica variabili d'ambiente da .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Attenzione: python-dotenv non installato. Installa con: pip install python-dotenv")
    print("Le variabili d'ambiente devono essere configurate manualmente.\n")

from email_processor import EmailProcessor
from llm_article_generator import ArticleGenerator
# from crm_publisher import CRMPublisher  # Modulo rimosso - usa app_gui.py come entry point


class EmailToCRMWorkflow:
    """
    Workflow completo: Email -> LLM -> CRM
    """

    def __init__(self, config_file: str = "config.json"):
        """Inizializza workflow con configurazione"""
        self.config = self._load_config(config_file)
        self.stats = {
            'start_time': datetime.now(),
            'emails_found': 0,
            'articles_generated': 0,
            'articles_published': 0,
            'errors': []
        }

    def _load_config(self, config_file: str) -> Dict:
        """Carica configurazione da file JSON"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"OK - Configurazione caricata da {config_file}")
            return config
        except FileNotFoundError:
            print(f"Attenzione: File {config_file} non trovato, uso configurazione di default")
            return self._get_default_config()
        except Exception as e:
            print(f"Errore nel caricare configurazione: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Configurazione di default"""
        return {
            'email_filters': {
                'mittenti_monitorati': [],
                'solo_non_lette': True,
                'mailbox': 'INBOX'
            },
            'llm_settings': {
                'istruzioni_personalizzate': '',
                'temperatura': 0.7,
                'max_tokens': 2000
            },
            'crm_settings': {
                'categoria_default': 'news',
                'tags_default': ['email', 'automated'],
                'status_pubblicazione': 'draft'
            },
            'workflow': {
                'marca_email_come_lette': True,
                'salva_backup_json': True
            }
        }

    def run(self, dry_run: bool = False):
        """
        Esegue il workflow completo

        Args:
            dry_run: se True, non pubblica su CRM (solo test)
        """
        print("\n" + "="*80)
        print("AVVIO WORKFLOW: Email -> Articoli -> CRM")
        print("="*80 + "\n")

        # Step 1: Filtra email
        print("STEP 1: Recupero email filtrate")
        print("-" * 80)
        emails = self._fetch_emails()

        if not emails:
            print("\nAttenzione: Nessuna email trovata. Workflow terminato.")
            return

        # Step 2: Genera articoli con LLM
        print("\n\nSTEP 2: Generazione articoli con LLM")
        print("-" * 80)
        articles = self._generate_articles(emails)

        if not articles:
            print("\nErrore: Nessun articolo generato. Workflow terminato.")
            return

        # Step 3: Pubblica su CRM
        if not dry_run:
            print("\n\nSTEP 3: Pubblicazione su CRM")
            print("-" * 80)
            publish_results = self._publish_to_crm(articles)
        else:
            print("\n\nDRY RUN: Pubblicazione su CRM saltata")
            print("-" * 80)
            self._show_articles_preview(articles)
            publish_results = None

        # Report finale
        self._print_final_report(publish_results)

    def _fetch_emails(self) -> List[Dict]:
        """Step 1: Recupera email filtrate"""
        try:
            # Credenziali email
            username = os.getenv("EMAIL_USER")
            password = os.getenv("EMAIL_PASS")

            if not username or not password:
                print("Errore: Credenziali email non configurate in .env")
                return []

            # Configurazione filtri
            email_config = self.config.get('email_filters', {})
            mittenti = email_config.get('mittenti_monitorati', [])

            if not mittenti:
                print("Attenzione: Nessun mittente configurato in config.json")
                print("Aggiungi mittenti in 'email_filters.mittenti_monitorati'")
                return []

            # Crea processor
            processor = EmailProcessor(username, password)

            if not processor.connect():
                return []

            try:
                # Filtra email
                filtered = processor.filter_emails_by_multiple_senders(
                    mittenti,
                    mailbox=email_config.get('mailbox', 'INBOX'),
                    only_unseen=email_config.get('solo_non_lette', True)
                )

                # Converti in lista piatta
                all_emails = []
                for sender, emails_list in filtered.items():
                    all_emails.extend(emails_list)

                self.stats['emails_found'] = len(all_emails)

                # Salva backup
                if self.config.get('workflow', {}).get('salva_backup_json', True):
                    processor.save_emails_to_json(filtered, 'emails_filtered.json')

                # NON marcare più come lette - richiesta utente: le email devono rimanere non lette sul server
                # if self.config.get('workflow', {}).get('marca_email_come_lette', False):
                #     for email_data in all_emails:
                #         processor.mark_as_read(email_data['id'])

                return all_emails

            finally:
                processor.disconnect()

        except Exception as e:
            print(f"Errore nel recupero email: {e}")
            self.stats['errors'].append(f"Fetch emails: {e}")
            return []

    def _generate_articles(self, emails: List[Dict]) -> List[Dict]:
        """Step 2: Genera articoli con LLM"""
        try:
            # Configurazione LLM
            provider = os.getenv("LLM_PROVIDER", "openai")
            generator = ArticleGenerator(provider=provider)

            # Istruzioni personalizzate
            llm_config = self.config.get('llm_settings', {})
            custom_instructions = llm_config.get('istruzioni_personalizzate', '')

            # Genera articoli
            articles = generator.batch_generate_articles(
                emails,
                custom_instructions=custom_instructions
            )

            self.stats['articles_generated'] = len(articles)

            # Salva backup
            if self.config.get('workflow', {}).get('salva_backup_json', True):
                generator.save_articles(articles, 'articles_generated.json')

            return articles

        except Exception as e:
            print(f"Errore nella generazione articoli: {e}")
            self.stats['errors'].append(f"Generate articles: {e}")
            return []

    def _publish_to_crm(self, articles: List[Dict]) -> Dict:
        """Step 3: Pubblica articoli su CRM"""
        print("\n⚠️ ATTENZIONE: Funzionalità di pubblicazione non disponibile in main.py")
        print("Usa app_gui.py per pubblicare articoli sul CMS con Playwright\n")
        return {'success': 0, 'failed': len(articles), 'total': len(articles)}

    def _show_articles_preview(self, articles: List[Dict]):
        """Mostra preview degli articoli generati in dry-run mode"""
        print("\nARTICOLI GENERATI (preview):")
        print("="*80)

        for i, article in enumerate(articles, 1):
            # Nuova struttura JSON
            tipo = article.get('tipo', 'N/A')
            categoria = article.get('categoria', 'N/A')
            titolo = article.get('titolo', 'N/A')
            sottotitolo = article.get('sottotitolo', '')
            occhiello = article.get('occhiello', '')
            contenuto = article.get('contenuto', [])
            data_invio = article.get('data_invio', 'N/A')
            immagine = article.get('immagine', '')

            # Metadata
            metadata = article.get('metadata', {})
            fonte = metadata.get('original_sender', 'N/A')
            oggetto_email = metadata.get('original_subject', 'N/A')

            print(f"\n[{i}/{len(articles)}] {titolo}")
            print("-" * 80)
            print(f"Tipo: {tipo}")
            print(f"Categoria: {categoria}")
            print(f"Data invio: {data_invio}")
            print(f"Fonte: {fonte}")
            print(f"Oggetto email: {oggetto_email}")

            if occhiello:
                print(f"\nOcchiello: {occhiello}")

            if sottotitolo:
                print(f"Sottotitolo: {sottotitolo}")

            # Mostra i paragrafi
            if contenuto and len(contenuto) > 0:
                print(f"\nContenuto ({len(contenuto)} paragrafi):")
                for idx, para in enumerate(contenuto, 1):
                    if para:
                        preview = para[:150] + "..." if len(para) > 150 else para
                        print(f"  [{idx}] {preview}")

            if immagine:
                print(f"\nImmagine: {immagine}")

            print("-" * 80)

        print(f"\n\nTotale articoli: {len(articles)}")
        print("Gli articoli completi sono salvati in: articles_generated.json")
        print("="*80)

    def _print_final_report(self, publish_results: Dict = None):
        """Stampa report finale del workflow"""
        end_time = datetime.now()
        duration = end_time - self.stats['start_time']

        print("\n" + "="*80)
        print("REPORT FINALE WORKFLOW")
        print("="*80)
        print(f"\nDurata: {duration}")
        print(f"\nEmail trovate: {self.stats['emails_found']}")
        print(f"Articoli generati: {self.stats['articles_generated']}")

        if publish_results:
            print(f"Articoli pubblicati: {self.stats['articles_published']}/{publish_results.get('total', 0)}")
            if publish_results.get('failed', 0) > 0:
                print(f"  Falliti: {publish_results.get('failed', 0)}")

        if self.stats['errors']:
            print(f"\nErrori ({len(self.stats['errors'])}):")
            for error in self.stats['errors']:
                print(f"  - {error}")

        print("\n" + "="*80 + "\n")


def main():
    """Entry point principale"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Workflow automatico: Email -> LLM -> CRM"
    )
    parser.add_argument(
        '--config',
        default='config.json',
        help='File di configurazione (default: config.json)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Esegue senza pubblicare su CRM (solo test)'
    )

    args = parser.parse_args()

    # Verifica dipendenze
    required_packages = {
        'openai': 'pip install openai',
        'anthropic': 'pip install anthropic',
        'requests': 'pip install requests',
        'dotenv': 'pip install python-dotenv'
    }

    print("Verifica dipendenze...")
    missing = []
    for package, install_cmd in required_packages.items():
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            if package not in ['openai', 'anthropic']:
                missing.append(f"  {install_cmd}")

    if missing:
        print("\nPacchetti mancanti:")
        for cmd in missing:
            print(cmd)
        print()

    # Esegui workflow
    workflow = EmailToCRMWorkflow(config_file=args.config)
    workflow.run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
