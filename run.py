#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher per FLaiRIO - Imposta UTF-8 prima di tutto
"""

import sys
import os

# FORZA UTF-8 su Windows PRIMA di importare qualsiasi cosa
if sys.platform == 'win32':
    # Variabili ambiente
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

    # Forza codepage console
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except:
        pass

# Ora importa e avvia l'app
if __name__ == "__main__":
    from app_gui import main
    main()
