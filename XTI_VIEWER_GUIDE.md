# XTI Viewer - Guide Utilisateur Simplifié

## ✅ Fonctionnalités Principales

### 🔥 Corrélations & Navigation Essentielles
- **Pairing FETCH ↔ TERMINAL RESPONSE** : Affichage de la ligne du FETCH associé au-dessus des réponses pour voir la conversation complète
- **Navigation dans la même session** : Raccourcis Alt+↑/↓ pour naviguer entre items de même protocole/canal
- **Corrélations visuelles** : Liens clairs entre commandes et réponses avec indicateurs de statut

## 🎮 Raccourcis Clavier Simplifiés

### Navigation par Paires
- **Ctrl+G** : Aller vers l'item pairé (FETCH ↔ TERMINAL RESPONSE)

### Navigation Contextuelle  
- **Alt+↑** : Item précédent dans la même session (protocole/canal)
- **Alt+↓** : Item suivant dans la même session (protocole/canal)

## 🎯 Fonctionnalités Avancées

### FETCH ↔ TERMINAL RESPONSE Pairing
- ✅ Détection automatique des paires commande-réponse
- ✅ Calcul de durée avec statut (Success/Error/Pending)
- ✅ Navigation bidirectionnelle entre paires
- ✅ Affichage des corrélations dans l'arbre (ligne FETCH au-dessus des réponses)

### Décodeurs Spécialisés
- ✅ SETUP_DESCRIPTOR avec analyse des capacités
- ✅ DEVICE_QUERY avec parsing des informations système
- ✅ Détection ASCII intelligente pour commandes texte
- ✅ Décodeur CONFIG_TLV avec types étendus

### Navigation Bidirectionnelle
- ✅ Clic sur hex → sélection TLV correspondant
- ✅ Clic sur TLV → sélection hex correspondant
- ✅ Synchronisation automatique hex-TLV

### Enrichissement des Résumés
- ✅ Résumés contextuels selon le type TLV
- ✅ Informations détaillées dans les tooltips
- ✅ Cartes de résumé enrichies avec métadonnées

## 💡 Guide d'Utilisation

### 1. Chargement de Fichier
- Ouvrir un fichier XTI via **File → Open**
- L'analyse automatique commence immédiatement
- Les paires FETCH↔RESPONSE sont détectées automatiquement

### 2. Navigation Efficace

#### Navigation par Paires (PRINCIPALE)
- Sélectionner une commande FETCH et appuyer **Ctrl+G** pour voir sa réponse
- Sélectionner une réponse TERMINAL et appuyer **Ctrl+G** pour voir la commande

#### Navigation Contextuelle (Même Session)
- **Alt+↓** : Item suivant dans le même contexte protocole/canal
- **Alt+↑** : Item précédent dans le même contexte protocole/canal

### 3. Interface Optimisée

#### Affichage des Corrélations
- Les réponses TERMINAL affichent la ligne FETCH correspondante au-dessus
- Format : "↳ Response to: [résumé de la commande FETCH]"
- Statut visible : ✅ Success, ❌ Error, ⏳ Pending

#### Informations de Pairing
- Panneau de statut montre les détails de pairing
- Durée calculée automatiquement entre commande et réponse
- Bouton "Go to Paired Item" pour navigation rapide

### 4. Décodage Intelligent

#### Décodeurs Automatiques
- **SETUP_DESCRIPTOR** : Analyse des capacités de canal
- **DEVICE_QUERY** : Informations système détaillées
- **CONFIG_TLV** : Types étendus avec descriptions
- **ASCII Detection** : Commandes texte automatiquement détectées

#### Navigation Hex-TLV
- Cliquer sur une ligne hex sélectionne le TLV correspondant
- Cliquer sur un élément TLV sélectionne la zone hex correspondante
- Synchronisation automatique entre les vues

## 🚀 Interface Simplifiée et Efficace

### Filtrage Intelligent
- Filtre par texte dans l'interprétation
- Filtres par protocole, type, canal
- Recherche dans les résumés enrichis

### Enrichissement Contextuel
- Tooltips détaillés sur tous les éléments
- Résumés adaptatifs selon le type de TLV
- Métadonnées complètes affichées

### Interface Professionnelle
- Layout optimisé pour l'analyse
- Animations visuelles pour les sauts de navigation
- Gestion des erreurs avec messages informatifs

## ✨ Exemples d'Utilisation

### Analyser une Session de Communication
1. Charger le fichier XTI
2. Utiliser **Alt+↑/↓** pour parcourir tous les échanges dans le contexte
3. Pour chaque FETCH, utiliser **Ctrl+G** pour voir la réponse
4. Observer les corrélations visuelles dans l'arbre

### Déboguer un Problème de Communication
1. Filtrer par type d'erreur dans le panneau de recherche
2. Sélectionner une réponse d'erreur
3. Utiliser **Ctrl+G** pour voir la commande qui a causé l'erreur
4. Analyser le contenu détaillé dans l'inspecteur

### Explorer une Nouvelle Trace
1. Parcourir avec **Alt+↑/↓** pour voir les séquences complètes
2. Examiner les décodeurs spécialisés pour comprendre les protocoles
3. Utiliser les tooltips pour comprendre les détails techniques
4. Observer les corrélations FETCH→RESPONSE automatiques

## 🎉 XTI Viewer - Interface Simplifiée et Puissante !

Le XTI Viewer offre maintenant :
- ✅ Navigation intuitive avec seulement 3 raccourcis essentiels
- ✅ Pairing automatique FETCH↔TERMINAL RESPONSE avec corrélations visuelles  
- ✅ Navigation contextuelle intelligente Alt+↑/↓
- ✅ Décodeurs spécialisés pour analyse approfondie
- ✅ Interface épurée et focalisée sur l'efficacité

**Interface simplifiée = Productivité maximisée !** 🚀