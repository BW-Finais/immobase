#!/usr/bin/env python3
"""
Hauptscript für die Rechnungs-Automatisierung
Verarbeitet PDF-Rechnungen und schreibt Daten in Excel (31 Spalten)
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import shutil

# Füge src-Ordner zum Python-Pfad hinzu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from pdf_parser import parse_invoice
from excel_handler import create_or_load_excel


def print_header(title: str):
    """Gibt einen formatierten Header aus"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def print_welcome():
    """Begrüßungsnachricht"""
    print_header("📄 RECHNUNGS-AUTOMATISIERUNG")
    print("  PDF → Excel Übertragung")
    print("="*60)
    print(f"  Datum: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print("="*60)


def ask_use_ocr() -> bool:
    """Fragt Benutzer ob OCR verwendet werden soll"""
    print("\nWillkommen zur Rechnungs-Automatisierung!")
    print("Möchtest du OCR verwenden? (für gescannte PDFs)")
    print("  [1] Nein - nur Text-PDFs (schneller)")
    print("  [2] Ja - verwende OCR für alle PDFs")
    
    while True:
        choice = input("Deine Wahl (1/2): ").strip()
        if choice == "1":
            return False
        elif choice == "2":
            return True
        else:
            print("Bitte wähle 1 oder 2")


def move_to_processed(pdf_path: Path):
    """Verschiebt verarbeitete PDF in processed-Ordner"""
    try:
        processed_path = config.PROCESSED_DIR / pdf_path.name
        shutil.move(str(pdf_path), str(processed_path))
        print(f"  ✓ PDF verschoben nach: processed/")
    except Exception as e:
        print(f"  ⚠ Konnte PDF nicht verschieben: {e}")


def process_all_invoices(use_ocr: bool = False):
    """Verarbeitet alle PDFs im invoices-Ordner"""
    
    # Stelle sicher dass Ordner existieren
    config.ensure_directories()
    
    # Hole alle PDF-Dateien
    pdf_files = config.get_pdf_files()
    
    if not pdf_files:
        print("\n⚠ Keine PDF-Dateien im invoices-Ordner gefunden!")
        print(f"   Bitte lege PDFs in: {config.INVOICES_DIR}")
        return
    
    print(f"\n✓ {len(pdf_files)} PDF-Datei(en) gefunden")
    
    # Lade oder erstelle Excel
    print_header("📊 EXCEL VORBEREITEN")
    excel_handler = create_or_load_excel()
    
    # Verarbeite jede PDF
    print_header("🔄 VERARBEITE PDFs")
    
    processed_count = 0
    failed_count = 0
    skipped_count = 0
    
    for pdf_file in pdf_files:
        try:
            # Parse PDF
            invoice_data = parse_invoice(pdf_file, use_ocr)
            
            if invoice_data:
                # Füge zur Excel hinzu
                if excel_handler.add_invoice(invoice_data):
                    processed_count += 1
                    
                    # Verschiebe PDF
                    if config.MOVE_PROCESSED_FILES:
                        move_to_processed(pdf_file)
                else:
                    skipped_count += 1
            else:
                failed_count += 1
                print(f"  ❌ Konnte {pdf_file.name} nicht verarbeiten")
                
        except Exception as e:
            failed_count += 1
            print(f"  ❌ Fehler bei {pdf_file.name}: {e}")
    
    # Speichere Excel
    if processed_count > 0:
        print_header("💾 SPEICHERE EXCEL")
        excel_handler.save_excel()
    
    # Zusammenfassung
    print_header("✅ FERTIG!")
    print(f"  Erfolgreich verarbeitet: {processed_count}")
    print(f"  Übersprungen (duplikat): {skipped_count}")
    print(f"  Fehlgeschlagen: {failed_count}")
    print(f"  Gesamt: {len(pdf_files)}")
    
    # Excel-Statistiken
    excel_handler.print_summary()
    
    print(f"\n📁 Excel-Datei: {config.EXCEL_FILE}")
    print("\n")


def main():
    """Hauptfunktion"""
    try:
        print_welcome()
        
        # Frage nach OCR
        use_ocr = ask_use_ocr()
        
        # Verarbeite alle Rechnungen
        process_all_invoices(use_ocr)
        
    except KeyboardInterrupt:
        print("\n\n⚠ Abbruch durch Benutzer")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unerwarteter Fehler: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
