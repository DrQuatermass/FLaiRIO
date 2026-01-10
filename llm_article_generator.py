#!/usr/bin/env python3
"""
Modulo per generare articoli da email usando LLM
Supporta OpenAI, Anthropic Claude, e altri provider
"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime


class ArticleGenerator:
    """
    Genera articoli giornalistici da email usando LLM
    """

    def __init__(self, provider: str = "openai", api_key: Optional[str] = None):
        """
        Args:
            provider: 'openai', 'anthropic', o 'ollama' (locale)
            api_key: chiave API (non necessaria per ollama)
        """
        self.provider = provider.lower()
        self.api_key = api_key or self._get_api_key()

        # Inizializza il client appropriato
        self.client = None
        self._init_client()

    def _get_api_key(self) -> Optional[str]:
        """Recupera API key dalle variabili d'ambiente"""
        if self.provider == "openai":
            return os.getenv("OPENAI_API_KEY")
        elif self.provider == "anthropic":
            return os.getenv("ANTHROPIC_API_KEY")
        return None

    def _init_client(self):
        """Inizializza il client LLM"""
        try:
            if self.provider == "openai":
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                print(f"[OK] Client OpenAI inizializzato")

            elif self.provider == "anthropic":
                from anthropic import Anthropic
                self.client = Anthropic(api_key=self.api_key)
                print(f"[OK] Client Anthropic inizializzato")

            elif self.provider == "ollama":
                # Ollama locale non richiede API key
                try:
                    import requests
                    # Verifica che Ollama sia in esecuzione
                    response = requests.get("http://localhost:11434/api/tags")
                    if response.status_code == 200:
                        print(f"[OK] Ollama locale disponibile")
                    else:
                        print(f"[!] Ollama non risponde correttamente")
                except:
                    print(f"[!] Ollama non disponibile su localhost:11434")

        except ImportError as e:
            print(f"[X] Errore: {e}")
            print(f"   Installa il pacchetto necessario:")
            if self.provider == "openai":
                print(f"   pip install openai")
            elif self.provider == "anthropic":
                print(f"   pip install anthropic")

    def generate_article(self, email_content: str,
                        subject: str = "",
                        sender: str = "",
                        custom_instructions: str = "") -> str:
        """
        Genera un articolo giornalistico dal contenuto email

        Args:
            email_content: contenuto dell'email
            subject: oggetto dell'email
            sender: mittente dell'email
            custom_instructions: istruzioni aggiuntive per il LLM

        Returns:
            Articolo generato
        """

        # Crea il prompt
        prompt = self._create_article_prompt(
            email_content, subject, sender, custom_instructions
        )

        # Genera con il provider appropriato
        if self.provider == "openai":
            return self._generate_openai(prompt)
        elif self.provider == "anthropic":
            return self._generate_anthropic(prompt)
        elif self.provider == "ollama":
            return self._generate_ollama(prompt)
        else:
            return f"Provider '{self.provider}' non supportato"

    def _create_article_prompt(self, content: str, subject: str,
                               sender: str, custom_instructions: str) -> str:
        """Crea il prompt per il LLM"""

        base_prompt = f"""Sei un giornalista professionista. Il tuo compito è trasformare il contenuto di questa email in un articolo giornalistico ben strutturato.

INFORMAZIONI EMAIL:
- Mittente: {sender}
- Oggetto: {subject}

CONTENUTO EMAIL:
{content}

ISTRUZIONI:
1. Analizza il contenuto dell'email e identifica le informazioni chiave
2. Scrivi un articolo giornalistico professionale
3. Mantieni uno stile giornalistico oggettivo e professionale
4. Usa un linguaggio chiaro e accessibile
5. Dividi il contenuto in paragrafi ben strutturati
6. Scegli la categoria più appropriata tra: Scuola, Sanità, Economia, Attualità, Cultura, Ambiente, Moda, Sociale, Sport, Territorio
7. Genera keywords SEO rilevanti per l'articolo

{custom_instructions if custom_instructions else ''}

FORMATO OUTPUT - IMPORTANTE:
Restituisci SOLO un oggetto JSON valido con questa struttura (non aggiungere testo prima o dopo il JSON):

{{
  "tipo": "Spotlight",
  "categoria": "una tra: Scuola, Sanità, Economia, Attualità, Cultura, Ambiente, Moda, Sociale, Sport, Territorio",
  "titolo": "titolo principale accattivante",
  "sottotitolo": "sottotitolo che amplia il titolo",
  "occhiello": "breve frase introduttiva che anticipa il tema",
  "contenuto": [
    "prima parte con lead giornalistico (chi, cosa, quando, dove, perché)",
    "seconda parte con sviluppo della notizia (opzionale se email breve)",
    "terza parte con conclusione e dettagli finali (opzionale se email breve)"
  ],
  "immagine": ""
}}

IMPORTANTE - REGOLE OBBLIGATORIE:

1. CONTESTO LOCALE:
   - I lettori sono di Carpi (Modena)
   - Evita ridondanze tipo "L'Ospedale Ramazzini di Carpi, situato nella provincia di Modena"
   - I carpigiani conoscono i luoghi locali, non servono specificazioni ovvie

2. CLASSIFICAZIONE:
   - Campo "tipo": Spotlight di default (massima rilevanza)
   - Campo "categoria": Scuola | Sanità | Economia | Attualità | Cultura | Ambiente | Moda | Sociale | Sport | Territorio
   - Campo "occhiello": massimo 10 parole introduttive

3. LUNGHEZZA PARAGRAFI - VINCOLO CRITICO:
   ATTENZIONE: OGNI paragrafo DEVE contenere MINIMO 200 parole e MASSIMO 350 parole

   PRIMO paragrafo (MINIMO 200 parole - MASSIMO 350 parole):
   - Lead giornalistico con le 5W (chi, cosa, quando, dove, perché)
   - Introduzione completa della notizia
   - Contesto immediato e rilevanza

   SECONDO paragrafo (MINIMO 200 parole - MASSIMO 350 parole):
   - Sviluppo approfondito con TUTTI i dettagli dell'email
   - Citazioni dirette se presenti
   - Dati, numeri, informazioni specifiche
   - Espansione dei concetti chiave

   TERZO paragrafo (MINIMO 200 parole - MASSIMO 350 parole):
   - Conclusioni e implicazioni
   - Contesto più ampio
   - Chiusura professionale

4. QUALITÀ OBBLIGATORIA:
   - VIETATO scrivere paragrafi sotto le 200 parole
   - OBBLIGATORIO: testo denso, ricco, articolato
   - Usa TUTTE le informazioni dell'email senza tralasciare nulla
   - Espandi i concetti con stile giornalistico professionale
   - I paragrafi separano banner pubblicitari nel CMS

5. VALIDAZIONE PRIMA DI GENERARE:
   - Conta le parole di ogni paragrafo PRIMA di creare il JSON
   - Se un paragrafo ha meno di 200 parole, ESPANDILO aggiungendo:
     * Maggiori dettagli dal contenuto email
     * Contesto giornalistico e background
     * Frasi di collegamento elaborate
     * Sviluppo professionale dei concetti
   - NON generare il JSON finché TUTTI i paragrafi non hanno almeno 200 parole

Genera l'articolo in formato JSON:"""

        return base_prompt

    def _generate_openai(self, prompt: str, model: str = "gpt-4o") -> str:
        """Genera articolo usando OpenAI"""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Sei un giornalista professionista esperto nella scrittura di articoli."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=10000
            )
            return response.choices[0].message.content

        except Exception as e:
            return f"Errore OpenAI: {e}"

    def _generate_anthropic(self, prompt: str, model: str = "claude-3-5-sonnet-20241022") -> str:
        """Genera articolo usando Anthropic Claude"""
        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=10000,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            return response.content[0].text

        except Exception as e:
            return f"Errore Anthropic: {e}"

    def _generate_ollama(self, prompt: str, model: str = "llama3.1") -> str:
        """Genera articolo usando Ollama locale"""
        try:
            import requests

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                }
            )

            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                return f"Errore Ollama: {response.status_code}"

        except Exception as e:
            return f"Errore Ollama: {e}"

    def batch_generate_articles(self, emails: List[Dict],
                                custom_instructions: str = "") -> List[Dict]:
        """
        Genera articoli per una lista di email

        Args:
            emails: lista di dizionari email (da EmailProcessor)
            custom_instructions: istruzioni personalizzate

        Returns:
            Lista di articoli generati con metadata
        """
        articles = []

        total = len(emails)
        print(f"\n[AI] Generazione di {total} articoli con {self.provider.upper()}...\n")

        for i, email_data in enumerate(emails, 1):
            print(f"[>] Processando email {i}/{total}: {email_data.get('subject', 'N/A')}")

            article_raw = self.generate_article(
                email_content=email_data.get('body', ''),
                subject=email_data.get('subject', ''),
                sender=email_data.get('from', ''),
                custom_instructions=custom_instructions
            )

            # Parse e struttura il JSON
            article_structured = self._parse_and_structure_article(article_raw)

            # Aggiungi foto allegata (se presente)
            attachments = email_data.get('attachments', [])
            foto_path = None
            if attachments and len(attachments) > 0:
                # Usa la prima foto allegata
                foto_path = attachments[0].get('path')
                print(f"   [OK] Foto trovata: {attachments[0].get('filename')}")

            # Aggiungi metadata
            article_data = {
                **article_structured,  # Unpack del JSON strutturato
                'data_invio': datetime.now().strftime('%Y-%m-%d'),
                'foto_path': foto_path,  # Path alla foto allegata
                'metadata': {
                    'email_id': email_data.get('id', ''),
                    'original_subject': email_data.get('subject', ''),
                    'original_sender': email_data.get('from', ''),
                    'original_date': email_data.get('date', ''),
                    'generated_at': datetime.now().isoformat(),
                    'llm_provider': self.provider,
                    'attachments_count': len(attachments)
                }
            }

            articles.append(article_data)
            print(f"   [OK] Articolo generato\n")

        return articles

    def _parse_and_structure_article(self, article_raw: str) -> Dict:
        """
        Parse il JSON dell'articolo e aggiunge campi mancanti

        Args:
            article_raw: stringa JSON o testo dall'LLM

        Returns:
            Dizionario strutturato con tutti i campi
        """
        try:
            # DEBUG: Mostra risposta grezza dell'LLM
            print(f"   [DEBUG] Risposta LLM (primi 200 char): {article_raw[:200]}")

            # Prova a fare il parse del JSON
            # Rimuovi eventuali backtick markdown
            cleaned = article_raw.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            print(f"   [DEBUG] JSON cleaned (primi 200 char): {cleaned[:200]}")

            article_json = json.loads(cleaned)

            # Valida e completa i campi richiesti
            contenuto = article_json.get('contenuto', [])

            # Assicura che ci siano da 1 a 3 paragrafi (massimo 3)
            if len(contenuto) > 3:
                contenuto = contenuto[:3]
            elif len(contenuto) < 1:
                # Minimo 1 paragrafo richiesto
                contenuto = ["Contenuto non disponibile"]

            # Rimuovi eventuali paragrafi vuoti in coda
            contenuto = [p for p in contenuto if p.strip()]

            structured = {
                'tipo': article_json.get('tipo', 'Spotlight'),
                'categoria': article_json.get('categoria', 'Attualità'),
                'titolo': article_json.get('titolo', 'Articolo senza titolo'),
                'sottotitolo': article_json.get('sottotitolo', ''),
                'occhiello': article_json.get('occhiello', ''),
                'contenuto': contenuto,
                'immagine': article_json.get('immagine', '')
            }

            return structured

        except json.JSONDecodeError as e:
            print(f"   [!] Errore parsing JSON, uso formato fallback: {e}")
            # Fallback: crea struttura base dal testo
            return {
                'tipo': 'Spotlight',
                'categoria': 'Attualità',
                'titolo': 'Articolo generato',
                'sottotitolo': '',
                'occhiello': '',
                'contenuto': [article_raw, '', ''],
                'immagine': ''
            }

    def save_articles(self, articles: List[Dict], filename: str = "articles_generated.json"):
        """Salva gli articoli generati in JSON"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)
            print(f"[OK] {len(articles)} articoli salvati in {filename}")
        except Exception as e:
            print(f"[X] Errore nel salvare articoli: {e}")


def main():
    """Esempio di utilizzo"""

    # Carica email filtrate (dal email_processor.py)
    try:
        with open("emails_filtered.json", 'r', encoding='utf-8') as f:
            filtered_emails = json.load(f)
    except FileNotFoundError:
        print("[X] File emails_filtered.json non trovato")
        print("   Esegui prima email_processor.py per filtrare le email")
        return

    # Inizializza generatore
    # Opzioni: "openai", "anthropic", "ollama"
    provider = os.getenv("LLM_PROVIDER", "openai")
    generator = ArticleGenerator(provider=provider)

    # Istruzioni personalizzate opzionali
    custom_instructions = """
    - Focalizzati su notizie locali e territoriali
    - Mantieni un tono informale ma professionale
    - Evidenzia l'impatto sulla comunità locale
    """

    # Genera articoli per tutte le email
    all_articles = []

    for sender, emails in filtered_emails.items():
        print(f"\n{'='*80}")
        print(f"Processando email da: {sender}")
        print(f"{'='*80}")

        articles = generator.batch_generate_articles(emails, custom_instructions)
        all_articles.extend(articles)

    # Salva tutti gli articoli
    if all_articles:
        generator.save_articles(all_articles)
        print(f"\n[OK] Totale articoli generati: {len(all_articles)}")


if __name__ == "__main__":
    main()
