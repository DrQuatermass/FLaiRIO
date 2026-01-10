"""
Script di utility per rimuovere email duplicate dal database FLaiRIO

Usa questo script per pulire il database da email duplicate
che potrebbero essere state scaricate per errore.
"""

from database import EmailDatabase

def main():
    print("=" * 60)
    print("RIMOZIONE EMAIL DUPLICATE")
    print("=" * 60)
    print()

    # Connetti al database
    db = EmailDatabase()

    print("Ricerca email duplicate in corso...")
    print("(Email duplicate = stesso oggetto, data e mittente)")
    print()

    # Rimuovi duplicati
    removed = db.remove_duplicate_emails()

    print()
    print("=" * 60)
    if removed > 0:
        print(f"[OK] Rimozione completata: {removed} email duplicate eliminate")
        print()
        print("Riavvia FLaiRIO per vedere le modifiche.")
    else:
        print("[OK] Nessun duplicato trovato - database pulito!")
    print("=" * 60)

    # Chiudi connessione
    db.close()

if __name__ == '__main__':
    main()
