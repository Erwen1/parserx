#!/usr/bin/env python3
"""Test script pour valider que l'import XTI fonctionne."""

import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_xti_import():
    """Test simple de l'import et création des modèles."""
    
    # Test import des modules
    try:
        from xti_viewer.models import InterpretationTreeModel, CommandResponsePairingManager, SessionNavigator
        from xti_viewer.xti_parser import XTIParser, TraceItem
        print("✅ Import des modules réussi")
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        return False
    
    # Test création des managers
    try:
        pairing_manager = CommandResponsePairingManager()
        session_navigator = SessionNavigator()
        print("✅ Création des managers réussie")
    except Exception as e:
        print(f"❌ Erreur création managers: {e}")
        return False
    
    # Test création du modèle
    try:
        model = InterpretationTreeModel()
        print("✅ Création du modèle réussie")
    except Exception as e:
        print(f"❌ Erreur création modèle: {e}")
        return False
    
    # Test avec des trace items vides
    try:
        model.load_trace_items([])
        print("✅ Chargement trace items vides réussi")
    except Exception as e:
        print(f"❌ Erreur chargement trace items: {e}")
        return False
    
    print("🎉 Tous les tests passent ! L'import XTI devrait fonctionner.")
    return True

if __name__ == "__main__":
    success = test_xti_import()
    sys.exit(0 if success else 1)