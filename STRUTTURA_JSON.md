# Struttura JSON Output Articoli

## Formato Standard

Ogni articolo generato dal sistema segue questa struttura JSON:

```json
{
  "tipo": "Spotlight | Apertura | In Evidenza",
  "categoria": "Scuola | Sanità | Economia | Attualità | Cultura | Ambiente | Moda | Sociale | Sport | Territorio",
  "data_invio": "2025-12-28",
  "titolo": "Titolo principale dell'articolo",
  "sottotitolo": "Sottotitolo esplicativo",
  "occhiello": "Breve frase introduttiva (max 10 parole)",
  "contenuto": [
    "Primo paragrafo - Lead giornalistico (chi, cosa, quando, dove, perché)",
    "Secondo paragrafo - Sviluppo della notizia con dettagli",
    "Terzo paragrafo - Conclusione e informazioni finali"
  ],
  "immagine": "",
  "metadata": {
    "email_id": "123",
    "original_subject": "Oggetto email originale",
    "original_sender": "mittente@example.it",
    "original_date": "Fri, 27 Dec 2024 10:30:00 +0100",
    "generated_at": "2025-12-28T15:30:00.123456",
    "llm_provider": "openai"
  }
}
```

## Descrizione Campi

### Campi Principali

- **tipo**: Rilevanza dell'articolo
  - `Spotlight`: Massima rilevanza (notizia di grande importanza)
  - `Apertura`: Alta rilevanza (notizia importante)
  - `In Evidenza`: Media rilevanza (notizia interessante)

- **categoria**: Tema dell'articolo
  - `Scuola`: Istruzione, formazione, università
  - `Sanità`: Salute, medicina, ospedali, ASL
  - `Economia`: Business, lavoro, finanza, sviluppo economico
  - `Attualità`: Cronaca, eventi, politica locale
  - `Cultura`: Arte, spettacoli, musei, eventi culturali
  - `Ambiente`: Ecologia, sostenibilità, natura
  - `Moda`: Fashion, design, tendenze
  - `Sociale`: Welfare, volontariato, terzo settore
  - `Sport`: Attività sportive, competizioni, società sportive
  - `Territorio`: Urbanistica, trasporti, infrastrutture

- **data_invio**: Data corrente in formato `YYYY-MM-DD`

- **titolo**: Titolo principale accattivante dell'articolo

- **sottotitolo**: Sottotitolo che amplia e completa il titolo

- **occhiello**: Breve frase introduttiva che anticipa il tema (massimo 10 parole)

- **contenuto**: Array con **da 1 a 3 paragrafi** (adattivo alla lunghezza email):
  - Email breve: 1 paragrafo denso (150-200 parole)
  - Email media: 2 paragrafi ben strutturati (100-150 parole ciascuno)
  - Email ricca: 3 paragrafi completi (120-180 parole ciascuno)
  - Paragrafo 1: Lead giornalistico con le 5W (chi, cosa, quando, dove, perché)
  - Paragrafo 2: Sviluppo della notizia con dettagli (opzionale)
  - Paragrafo 3: Conclusione e informazioni finali (opzionale)
  - I paragrafi servono come punti di interruzione per banner pubblicitari

- **immagine**: Path al file immagine (può essere vuoto)

### Metadata (informazioni tecniche)

- **email_id**: ID univoco dell'email sorgente
- **original_subject**: Oggetto dell'email originale
- **original_sender**: Mittente dell'email
- **original_date**: Data ricezione email
- **generated_at**: Timestamp generazione articolo
- **llm_provider**: Provider LLM utilizzato (openai, anthropic, ollama)

## Note Importanti

1. **Tipo vs Categoria**:
   - Il `tipo` indica la rilevanza/priorità dell'articolo
   - La `categoria` indica l'argomento/tema dell'articolo

2. Il campo `contenuto` contiene **da 1 a 3 paragrafi** (adattivo al contenuto email)

3. L'`occhiello` è una frase breve (max 10 parole) che introduce il tema

4. La `categoria` viene scelta automaticamente dall'LLM in base al contenuto tra le 10 opzioni disponibili

5. Il `tipo` viene scelto dall'LLM in base all'importanza della notizia

6. Il campo `immagine` può rimanere vuoto se non disponibile

7. I `metadata` contengono info tecniche per tracciabilità

## Esempi per Categoria

- **Scuola**: "Nuove aule digitali", "Progetto educativo", "Borse di studio"
- **Sanità**: "Campagna vaccinale", "Nuovo reparto ospedaliero", "Servizi sanitari"
- **Economia**: "Bando imprese", "Sviluppo commerciale", "Occupazione"
- **Attualità**: "Evento cittadino", "Decisione amministrativa", "Cronaca locale"
- **Cultura**: "Mostra d'arte", "Festival", "Teatro"
- **Ambiente**: "Energia rinnovabile", "Parchi", "Mobilità sostenibile"
- **Sociale**: "Iniziativa solidale", "Assistenza anziani", "Integrazione"
- **Sport**: "Gara sportiva", "Nuovo impianto", "Squadra locale"
- **Territorio**: "Lavori stradali", "Piano urbanistico", "Trasporti pubblici"

## Utilizzo

Gli articoli vengono salvati automaticamente in `articles_generated.json` dopo la generazione.

Per visualizzare un'anteprima in modalità dry-run:
```bash
python main.py --dry-run
```

## Esempio Completo

Vedi il file `esempio_output.json` per 4 esempi concreti di articoli generati con diverse combinazioni di tipo e categoria.
