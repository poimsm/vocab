#!/usr/bin/env python
"""
Script para ejecutar tests de creación de usuario
Ejecutar: python run_tests.py
"""
import sys
from pathlib import Path

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from tests.test_user_creation_simple import test_data_loading, test_manual_word_creation

if __name__ == "__main__":
    try:
        print("=" * 80)
        print("TEST 1: Data Loading")
        print("=" * 80)
        test_data_loading()
        print()

        print("=" * 80)
        print("TEST 2: Manual Word Creation")
        print("=" * 80)
        test_manual_word_creation()
        print()

        print("=" * 80)
        print("✓ ALL TESTS PASSED!")
        print("=" * 80)
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
