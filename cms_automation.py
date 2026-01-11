"""
Automazione pubblicazione articoli su CMS Voce
Usa Playwright per compilare e inviare il form automaticamente
"""

import asyncio
from playwright.async_api import async_playwright
from datetime import datetime
import json
import os

class CMSPublisher:
    """Classe per pubblicare articoli sul CMS Voce"""

    # Mapping categorie: nome → valore nel CMS
    CATEGORIA_MAP = {
        'Ambiente': '48',
        'Attualità': '7',
        'Cultura': '19',
        'Economia': '5',
        'Moda': '29',
        'Sanità': '3',
        'Scuola': '1',
        'Sociale': '28',
        'Sport': '8',
        'Territorio': '7'  # Territorio → Attualità
    }

    # Mapping tipi articolo → URL sezione CMS
    TIPO_URL_MAP = {
        'Spotlight': 'https://www.voce.it/admin/spotlight/',
        'Apertura': 'https://www.voce.it/admin/apertura/',
        'In Evidenza': 'https://www.voce.it/admin/in_evidenza/'
    }

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.logged_in = False

    async def start(self, headless: bool = False):
        """Avvia il browser e fa login"""
        self.playwright = await async_playwright().start()

        # Args ottimizzati per headless stealth mode
        launch_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-infobars',
            '--window-position=0,0',
            '--ignore-certificate-errors',
            '--ignore-certificate-errors-spki-list',
            '--disable-gpu'
        ]

        # Usa channel="chrome" per un browser più realistico
        # Chromium è più facile da rilevare rispetto a Chrome
        if headless:
            try:
                # Prova a usare Chrome invece di Chromium se disponibile
                # NOTA: Se Chrome si aggiorna e diventa incompatibile con Playwright,
                # eseguire: playwright install chrome
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    slow_mo=100,
                    args=launch_args,
                    channel="chrome"  # Usa Google Chrome se installato
                )
                print("[CMS] Usando Google Chrome in headless mode")
            except Exception as e:
                # Fallback a Chromium se Chrome non è disponibile o incompatibile
                print(f"[CMS] Warning: Chrome non disponibile ({e}), uso Chromium")
                print("[CMS] NOTA: Il CMS potrebbe rilevare Chromium come bot")
                print("[CMS] Per installare Chrome: playwright install chrome")
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    slow_mo=100,
                    args=launch_args
                )
                print("[CMS] Usando Chromium in headless mode")
        else:
            # Modalità visibile normale - prova prima Chrome, poi Chromium
            try:
                self.browser = await self.playwright.chromium.launch(
                    headless=False,
                    slow_mo=100,
                    args=launch_args,
                    channel="chrome"
                )
                print("[CMS] Usando Google Chrome visibile")
            except Exception as e:
                print(f"[CMS] Chrome non disponibile ({e}), uso Chromium")
                self.browser = await self.playwright.chromium.launch(
                    headless=False,
                    slow_mo=100,
                    args=launch_args
                )
                print("[CMS] Usando Chromium visibile")

        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            locale='it-IT',
            timezone_id='Europe/Rome',
            permissions=['geolocation'],
            geolocation={'longitude': 12.4964, 'latitude': 41.9028},  # Roma
            color_scheme='light',
            has_touch=False,
            is_mobile=False,
            device_scale_factor=1
        )

        # Script anti-detection avanzato
        await self.context.add_init_script("""
            // Override webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Override chrome property
            window.navigator.chrome = {
                runtime: {}
            };

            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Override plugins length
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['it-IT', 'it', 'en-US', 'en']
            });
        """)

        self.page = await self.context.new_page()

        # Esegui login
        await self._login()

    async def _login(self):
        """Effettua il login al CMS"""
        print("[CMS] Effettuando login...")

        # Naviga alla pagina di login
        await self.page.goto('http://www.voce.it/admin/', wait_until='networkidle')
        await asyncio.sleep(3)

        print(f"[CMS] URL pagina login: {self.page.url}")

        # Aspetta che il form sia completamente caricato
        await self.page.wait_for_selector('input#user', timeout=5000)
        await self.page.wait_for_selector('input#pwd', timeout=5000)
        await asyncio.sleep(1)

        # Compila form login con timing più umano
        await self.page.click('input#user')
        await asyncio.sleep(0.5)
        await self.page.keyboard.type(self.username, delay=150)
        await asyncio.sleep(0.8)

        await self.page.click('input#pwd')
        await asyncio.sleep(0.5)
        await self.page.keyboard.type(self.password, delay=150)
        await asyncio.sleep(0.8)

        print("[CMS] Inviando form login...")

        # Submit del form
        await self.page.click('input[type="submit"]')

        # Aspetta che la pagina cambi (attendi che l'URL non sia più la pagina di login)
        try:
            await self.page.wait_for_load_state('networkidle', timeout=15000)
            print("[CMS] Pagina caricata dopo submit")
        except Exception as e:
            print(f"[CMS] Warning durante attesa caricamento: {e}")

        await asyncio.sleep(4)

        # Verifica login - controllo più robusto
        current_url = self.page.url
        print(f"[CMS] URL dopo login: {current_url}")

        # Salva screenshot per debug
        await self.page.screenshot(path='cms_login_result.png', full_page=True)
        print("[CMS] Screenshot salvato: cms_login_result.png")

        # Verifica se login riuscito: controlla che il form di login NON sia più presente
        login_form = await self.page.query_selector('input#user')

        if login_form:
            # Form ancora presente = login fallito
            print("[CMS] [X] Form login ancora presente - login fallito")
            raise Exception("Login fallito: credenziali errate o pagina di login ancora visibile")
        else:
            # Form non presente = login riuscito
            print("[CMS] [OK] Form login non piu presente")

            # Verifica URL
            if 'index.php' in current_url or 'home' in current_url.lower() or 'admin' in current_url.lower():
                self.logged_in = True
                print("[CMS] [OK] Login riuscito!")
            else:
                print(f"[CMS] [!] URL inaspettato ma form sparito: {current_url}")
                # Considera comunque come successo se il form è sparito
                self.logged_in = True
                print("[CMS] [OK] Login probabilmente riuscito (form sparito)")

    async def publish_article(self, article_json: dict, fonte: str = "Ufficio Stampa") -> dict:
        """
        Pubblica un articolo sul CMS

        Args:
            article_json: Dizionario con struttura articolo (tipo, categoria, titolo, ecc.)
            fonte: Fonte dell'articolo (default: "Ufficio Stampa")

        Returns:
            Dizionario con risultato pubblicazione
        """
        if not self.logged_in:
            raise Exception("Non sei loggato al CMS")

        print(f"\n[CMS] Pubblicando articolo: {article_json.get('titolo', 'Senza titolo')}")

        # Estrai dati dall'articolo
        # SEMPRE Spotlight come default (implementazione futura per altre categorie)
        tipo = 'Spotlight'  # Forza sempre Spotlight, ignorando article_json.get('tipo')
        categoria = article_json.get('categoria', 'Attualità')
        titolo = article_json.get('titolo', '')
        sottotitolo = article_json.get('sottotitolo', '')
        occhiello = article_json.get('occhiello', '')
        contenuto = article_json.get('contenuto', [])

        # Naviga alla sezione Spotlight
        section_url = self.TIPO_URL_MAP['Spotlight']

        print(f"[CMS] Navigando a sezione '{tipo}'...")
        await self.page.goto(section_url, wait_until='networkidle')
        await asyncio.sleep(3)

        # Clicca bottone CREATE
        print("[CMS] Cliccando bottone CREATE...")
        create_btn = await self.page.query_selector('a:has-text("CREATE")')
        if not create_btn:
            raise Exception("Bottone CREATE non trovato")

        await create_btn.click()
        await asyncio.sleep(5)

        print(f"[CMS] Form aperto: {self.page.url}")

        # Screenshot del form vuoto per debug
        await self.page.screenshot(path='cms_form_empty.png', full_page=True)
        print("[CMS] Screenshot form vuoto: cms_form_empty.png")

        # Compila il form
        print("[CMS] Compilando form...")

        # Data e ora corrente
        now = datetime.now()
        data_str = now.strftime('%d/%m/%Y')
        ora_str = now.strftime('%H:%M')

        await self.page.fill('input[name="data"]', data_str)
        await self.page.fill('input[name="data_hour"]', ora_str)

        # Seleziona template (necessario per far apparire altri campi)
        # Usa JavaScript perché il select è nascosto (tabindex=-1)
        print("[CMS] Selezionando template...")
        try:
            await self.page.evaluate("""
                const select = document.querySelector('select[name="template"]');
                if (select) {
                    select.value = '1';
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """)
            await asyncio.sleep(1)
            print("[CMS] Template selezionato via JavaScript")
        except Exception as e:
            print(f"[CMS] Warning: Template non selezionato: {e}")

        # Campi principali
        await self.page.fill('input[name="titolo"]', titolo)
        await self.page.fill('input[name="sottotitolo"]', sottotitolo)
        await self.page.fill('input[name="occhiello"]', occhiello)

        # Scroll verso il basso per rendere visibili tutti i campi
        await self.page.evaluate('window.scrollTo(0, 500)')
        await asyncio.sleep(1)

        # Categoria - ora dovrebbe essere visibile dopo aver selezionato il template
        categoria_value = self.CATEGORIA_MAP.get(categoria, '7')  # Default: Attualità
        try:
            # Forza il click sul select anche se nascosto
            await self.page.evaluate(f"""
                const select = document.querySelector('select[name="categoria[]"]');
                if (select) {{
                    const option = select.querySelector('option[value="{categoria_value}"]');
                    if (option) {{
                        option.selected = true;
                        select.dispatchEvent(new Event('change'));
                    }}
                }}
            """)
            print(f"[CMS] Categoria selezionata: {categoria} (value: {categoria_value})")
        except Exception as e:
            print(f"[CMS] Warning: Impossibile selezionare categoria: {e}")

        # Contenuto - usa evaluate per CKEditor
        print("[CMS] Compilando contenuto (CKEditor)...")
        await self.page.evaluate('window.scrollTo(0, 1000)')
        await asyncio.sleep(2)

        # CKEditor richiede JavaScript per essere compilato
        if len(contenuto) >= 1 and contenuto[0]:
            try:
                await self.page.evaluate(f"""
                    if (typeof CKEDITOR !== 'undefined' && CKEDITOR.instances['testo']) {{
                        CKEDITOR.instances['testo'].setData({json.dumps(contenuto[0])});
                    }}
                """)
                print("[CMS] Paragrafo 1 inserito")
            except:
                print("[CMS] Warning: Impossibile inserire paragrafo 1 con CKEditor")

        if len(contenuto) >= 2 and contenuto[1]:
            try:
                await self.page.evaluate(f"""
                    if (typeof CKEDITOR !== 'undefined' && CKEDITOR.instances['testo2']) {{
                        CKEDITOR.instances['testo2'].setData({json.dumps(contenuto[1])});
                    }}
                """)
                print("[CMS] Paragrafo 2 inserito")
            except:
                print("[CMS] Warning: Impossibile inserire paragrafo 2 con CKEditor")

        if len(contenuto) >= 3 and contenuto[2]:
            try:
                await self.page.evaluate(f"""
                    if (typeof CKEDITOR !== 'undefined' && CKEDITOR.instances['testo3']) {{
                        CKEDITOR.instances['testo3'].setData({json.dumps(contenuto[2])});
                    }}
                """)
                print("[CMS] Paragrafo 3 inserito")
            except:
                print("[CMS] Warning: Impossibile inserire paragrafo 3 con CKEditor")

        # Fonte
        await self.page.fill('input[name="fonte"]', fonte)

        # Upload foto se presente nel JSON
        foto_path = article_json.get('foto_path')
        if foto_path:
            # Converti a path assoluto se è relativo
            if not os.path.isabs(foto_path):
                foto_path = os.path.abspath(foto_path)

            if os.path.exists(foto_path):
                print(f"[CMS] Caricando foto: {foto_path}")
                try:
                    file_input = await self.page.query_selector('input[name="img"]')
                    if file_input:
                        await file_input.set_input_files(foto_path)
                        print(f"[CMS] Foto caricata: {os.path.basename(foto_path)}")
                        await asyncio.sleep(2)  # Attendi caricamento
                except Exception as e:
                    print(f"[CMS] Warning: Impossibile caricare foto: {e}")
            else:
                print(f"[CMS] Warning: File foto non trovato: {foto_path}")

        # Screenshot del form compilato
        await self.page.screenshot(path='cms_form_filled.png', full_page=True)
        print("[CMS] Screenshot form compilato: cms_form_filled.png")

        # Submit del form
        print("[CMS] Inviando form...")
        submit_btn = await self.page.query_selector('input[type="submit"], button[type="submit"]')

        if submit_btn:
            await submit_btn.click()
            await asyncio.sleep(5)

            print(f"[CMS] URL dopo submit: {self.page.url}")
            await self.page.screenshot(path='cms_after_submit.png', full_page=True)

            # Verifica successo (se torna alla lista articoli, è andato bene)
            if 'spotlight' in self.page.url or 'apertura' in self.page.url or 'in_evidenza' in self.page.url:
                print("[CMS] Articolo salvato con successo!")

                # APPROVAZIONE AUTOMATICA - Trova e clicca il pulsante di approvazione
                print("[CMS] Approvando articolo...")
                await asyncio.sleep(3)

                try:
                    # Cerca il primo articolo nella lista (il più recente, appena creato)
                    # Il pulsante di approvazione ha classe yellow (non approvato) con data-action="confirm"
                    approve_btn = await self.page.query_selector('a.yellow[data-action="confirm"]')

                    if approve_btn:
                        # Clicca per approvare
                        await approve_btn.click()
                        await asyncio.sleep(2)
                        print("[CMS] Articolo approvato!")
                    else:
                        print("[CMS] Warning: Bottone approvazione non trovato (articolo già approvato?)")

                    # Rendi visibile l'articolo
                    visibility_btn = await self.page.query_selector('a.yellow[data-action="show"]')
                    if visibility_btn:
                        await visibility_btn.click()
                        await asyncio.sleep(2)
                        print("[CMS] Articolo reso visibile!")
                    else:
                        print("[CMS] Warning: Bottone visibilità non trovato (già visibile?)")

                except Exception as e:
                    print(f"[CMS] Warning: Errore durante approvazione/visibilità: {e}")

                await self.page.screenshot(path='cms_final.png', full_page=True)

                return {
                    'success': True,
                    'url': self.page.url,
                    'titolo': titolo,
                    'tipo': tipo
                }
            else:
                print("[CMS] Possibile errore nella pubblicazione")
                return {
                    'success': False,
                    'error': 'URL inaspettato dopo submit',
                    'url': self.page.url
                }
        else:
            raise Exception("Bottone submit non trovato")

    async def close(self):
        """Chiude il browser e Playwright"""
        try:
            if self.context:
                await self.context.close()
                print("[CMS] Context chiuso")
        except Exception as e:
            print(f"[CMS] Errore chiusura context: {e}")

        try:
            if self.browser:
                await self.browser.close()
                print("[CMS] Browser chiuso")
        except Exception as e:
            print(f"[CMS] Errore chiusura browser: {e}")

        try:
            if self.playwright:
                await self.playwright.stop()
                print("[CMS] Playwright chiuso")
        except Exception as e:
            print(f"[CMS] Errore chiusura playwright: {e}")


async def test_publish():
    """Funzione di test per pubblicare un articolo"""

    # Articolo di esempio
    test_article = {
        "tipo": "Spotlight",
        "categoria": "Sanità",
        "titolo": "Test articolo automatico da Playwright",
        "sottotitolo": "Questo è un test del sistema di pubblicazione automatica",
        "occhiello": "Sistema di pubblicazione automatica",
        "contenuto": [
            "Questo è il primo paragrafo del test. Il sistema sta funzionando correttamente e sta compilando automaticamente il form del CMS.",
            "Secondo paragrafo con ulteriori dettagli sul funzionamento del sistema automatico.",
            "Terzo e ultimo paragrafo che conclude l'articolo di test."
        ]
    }

    # Crea publisher e pubblica
    # NOTA: Inserisci le tue credenziali qui per testare
    publisher = CMSPublisher(username='your_username', password='your_password')

    try:
        await publisher.start(headless=False)
        result = await publisher.publish_article(test_article)

        print("\n" + "="*60)
        print("RISULTATO PUBBLICAZIONE:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("="*60)

        # Aspetta 10 secondi per vedere il risultato
        await asyncio.sleep(10)

    finally:
        await publisher.close()


if __name__ == '__main__':
    # Test diretto
    asyncio.run(test_publish())
