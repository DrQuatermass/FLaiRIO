"""
Test compatibilità cross-platform per FLaiRIO
Verifica che tutti i componenti funzionino sul sistema corrente
"""
import sys
import platform
from pathlib import Path

def test_platform_info():
    """Mostra informazioni sulla piattaforma"""
    print("=" * 60)
    print("INFORMAZIONI PIATTAFORMA")
    print("=" * 60)
    print(f"Sistema operativo: {platform.system()}")
    print(f"Versione: {platform.version()}")
    print(f"Release: {platform.release()}")
    print(f"Architettura: {platform.machine()}")
    print(f"Python: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print()

def test_browser_manager():
    """Testa il browser manager"""
    print("=" * 60)
    print("TEST BROWSER MANAGER")
    print("=" * 60)

    try:
        from browser_manager import PlaywrightBrowserManager

        # Path Playwright
        if sys.platform == 'win32':
            playwright_dir = Path.home() / "AppData" / "Local" / "ms-playwright"
        elif sys.platform == 'darwin':
            playwright_dir = Path.home() / "Library" / "Caches" / "ms-playwright"
        else:
            playwright_dir = Path.home() / ".cache" / "ms-playwright"

        print(f"Directory Playwright: {playwright_dir}")
        print(f"Directory esiste: {playwright_dir.exists()}")

        # Chrome installato?
        chrome_installed = PlaywrightBrowserManager.is_chrome_installed()
        print(f"Chrome installato: {chrome_installed}")

        if chrome_installed:
            chrome_path = PlaywrightBrowserManager.get_chrome_path()
            print(f"Chrome path: {chrome_path}")
        else:
            print("Chrome non installato - usa il pulsante nelle impostazioni dell'app")

        print("OK Browser manager funziona")
        return True

    except Exception as e:
        print(f"X Errore: {e}")
        return False

def test_qt():
    """Testa Qt/PySide6"""
    print("\n" + "=" * 60)
    print("TEST QT/PYSIDE6")
    print("=" * 60)

    try:
        from PySide6 import QtCore
        # PySide6 usa __version__ invece di QT_VERSION_STR
        try:
            version = QtCore.__version__
        except:
            version = "installato (versione sconosciuta)"

        print(f"PySide6 version: {version}")
        print("OK PySide6 disponibile")
        return True

    except ImportError as e:
        print(f"X PySide6 non installato: {e}")
        print("Installa con: pip install PySide6")
        return False

def test_playwright():
    """Testa Playwright"""
    print("\n" + "=" * 60)
    print("TEST PLAYWRIGHT")
    print("=" * 60)

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"Playwright version: {version}")
            print("OK Playwright installato")
            return True
        else:
            print("X Playwright non risponde correttamente")
            return False

    except Exception as e:
        print(f"X Errore: {e}")
        print("Installa con: pip install playwright")
        return False

def test_database():
    """Testa SQLite"""
    print("\n" + "=" * 60)
    print("TEST DATABASE SQLITE")
    print("=" * 60)

    try:
        import sqlite3
        print(f"SQLite version: {sqlite3.sqlite_version}")
        print("OK SQLite disponibile")
        return True

    except Exception as e:
        print(f"X Errore: {e}")
        return False

def test_encoding():
    """Testa encoding UTF-8"""
    print("\n" + "=" * 60)
    print("TEST ENCODING UTF-8")
    print("=" * 60)

    try:
        # Test caratteri italiani (no emoji su Windows console)
        test_strings = [
            "Perche' l'ancora e' cosi'",
            "Caratteri accentati: à è é ì ò ù",
            "Euro: [EUR] Pound: [GBP]"
        ]

        for s in test_strings:
            try:
                print(f"  {s}")
            except UnicodeEncodeError:
                # Fallback per console che non supporta UTF-8
                print(f"  {s.encode('ascii', 'replace').decode('ascii')}")

        print("OK Encoding base funziona")
        return True

    except Exception as e:
        print(f"X Errore encoding: {e}")
        return False

def main():
    """Esegue tutti i test"""
    print("\n")
    print("=" * 60)
    print(" " * 15 + "TEST COMPATIBILITA' FLAIRIO")
    print("=" * 60)
    print()

    test_platform_info()

    results = {
        "Browser Manager": test_browser_manager(),
        "Qt/PySide6": test_qt(),
        "Playwright": test_playwright(),
        "SQLite": test_database(),
        "Encoding UTF-8": test_encoding()
    }

    # Riepilogo
    print("\n" + "=" * 60)
    print("RIEPILOGO")
    print("=" * 60)

    all_passed = True
    for name, passed in results.items():
        status = "OK" if passed else "X FALLITO"
        print(f"{name:20} {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\nTUTTI I TEST SUPERATI!")
        print("FLaiRIO è compatibile con questo sistema.")
    else:
        print("\nALCUNI TEST FALLITI")
        print("Installa le dipendenze mancanti prima di usare FLaiRIO.")

    print()
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
