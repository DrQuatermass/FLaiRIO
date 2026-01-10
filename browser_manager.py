"""
Gestione automatica dei browser Playwright
Permette di installare/aggiornare Chrome senza comandi manuali
"""
import subprocess
import sys
import os
from pathlib import Path


class PlaywrightBrowserManager:
    """Gestisce l'installazione e aggiornamento dei browser Playwright"""

    @staticmethod
    def get_chrome_path():
        """
        Trova il path del browser Chrome

        Nota: FLaiRIO usa channel="chrome" che si riferisce a Google Chrome
        installato sul sistema, NON al browser in ms-playwright.

        Questo metodo verifica se Google Chrome è disponibile sul sistema.
        """
        # Verifica presenza Google Chrome sul sistema
        if sys.platform == 'win32':
            # Windows: controlla path standard di Chrome
            chrome_paths = [
                Path(os.environ.get('PROGRAMFILES', 'C:\\Program Files')) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
                Path(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
                Path.home() / 'AppData' / 'Local' / 'Google' / 'Chrome' / 'Application' / 'chrome.exe'
            ]
            for path in chrome_paths:
                if path.exists():
                    return path

        elif sys.platform == 'darwin':  # macOS
            chrome_path = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
            if chrome_path.exists():
                return chrome_path

        else:  # Linux
            # Prova a trovare chrome tramite which
            import shutil
            chrome_path = shutil.which('google-chrome') or shutil.which('chrome')
            if chrome_path:
                return Path(chrome_path)

        return None

    @staticmethod
    def is_chrome_installed():
        """Verifica se Chrome di Playwright è installato"""
        return PlaywrightBrowserManager.get_chrome_path() is not None

    @staticmethod
    def install_chrome(progress_callback=None):
        """
        Guida l'utente all'installazione di Google Chrome

        FLaiRIO usa Google Chrome di sistema (non il browser Playwright),
        quindi non possiamo installarlo automaticamente.

        Args:
            progress_callback: Funzione da chiamare con messaggi di progresso

        Returns:
            bool: True se Chrome è già installato, False se va installato manualmente
        """
        try:
            if progress_callback:
                progress_callback("Verifica presenza Google Chrome...")

            # Controlla se Chrome è già installato
            chrome_path = PlaywrightBrowserManager.get_chrome_path()

            if chrome_path:
                if progress_callback:
                    progress_callback(f"Chrome trovato: {chrome_path}")
                    progress_callback("Chrome già installato!")
                return True
            else:
                if progress_callback:
                    progress_callback("Chrome non trovato sul sistema.")
                    progress_callback("")
                    progress_callback("Per usare la modalità headless senza rilevamento,")
                    progress_callback("installa Google Chrome dal sito ufficiale:")
                    progress_callback("")
                    progress_callback("https://www.google.com/chrome/")
                    progress_callback("")
                    progress_callback("Dopo l'installazione, riavvia FLaiRIO.")
                return False

        except Exception as e:
            if progress_callback:
                progress_callback(f"Errore: {e}")
            return False

    @staticmethod
    def check_and_offer_install():
        """
        Verifica se Chrome è installato e offre di installarlo se manca

        Returns:
            bool: True se Chrome è disponibile, False altrimenti
        """
        if PlaywrightBrowserManager.is_chrome_installed():
            return True

        print("\n" + "="*60)
        print("ATTENZIONE: Chrome per Playwright non è installato")
        print("="*60)
        print("\nIl sistema usa Chromium come fallback, ma il CMS potrebbe")
        print("rilevarlo come bot e bloccare il login in modalità headless.")
        print("\nVuoi installare Chrome ora? (consigliato)")
        print("Dimensione download: ~100-150 MB")
        print("="*60)

        return False

    @staticmethod
    def install_chrome_with_ui(parent_widget=None):
        """
        Verifica Chrome e guida l'utente all'installazione se necessario

        Args:
            parent_widget: Widget Qt parent per dialog

        Returns:
            bool: True se Chrome è disponibile
        """
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        # Verifica se Chrome è già installato
        chrome_path = PlaywrightBrowserManager.get_chrome_path()

        if chrome_path:
            QMessageBox.information(
                parent_widget,
                'Chrome già installato',
                f'Google Chrome è già installato:\n\n{chrome_path}\n\n'
                'Il sistema userà Chrome per le pubblicazioni in modalità headless.'
            )
            return True

        # Chrome non trovato - chiedi all'utente di installarlo
        reply = QMessageBox.question(
            parent_widget,
            'Chrome non trovato',
            'Google Chrome non è installato sul sistema.\n\n'
            'Il sistema usa Chromium come fallback, ma potrebbe essere\n'
            'rilevato come bot dal CMS in modalità headless.\n\n'
            'Vuoi aprire il sito di Google Chrome per scaricarlo?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Apri browser con pagina download Chrome
            QDesktopServices.openUrl(QUrl('https://www.google.com/chrome/'))

            QMessageBox.information(
                parent_widget,
                'Installazione manuale richiesta',
                'Scarica e installa Google Chrome dalla pagina aperta.\n\n'
                'Dopo l\'installazione, riavvia FLaiRIO per usare Chrome.'
            )

        return False


# Test standalone
if __name__ == '__main__':
    print("=== Test Browser Manager ===\n")

    # Verifica installazione
    if PlaywrightBrowserManager.is_chrome_installed():
        print("[OK] Chrome e' gia' installato")
        print(f"  Path: {PlaywrightBrowserManager.get_chrome_path()}")
    else:
        print("[X] Chrome non e' installato")
        print("\nPer usare modalita' headless senza rilevamento bot,")
        print("installa Google Chrome da: https://www.google.com/chrome/")
        print("\nDopo l'installazione, riavvia FLaiRIO.")
