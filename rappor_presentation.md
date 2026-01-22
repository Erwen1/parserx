# Présentation – XTI Viewer (parserx)

## 0) Intro 

Bonjour tout le monde,

Aujourd’hui je vous présente **XTI Viewer**, un outil qui permet d’ouvrir et d’explorer des fichiers **.xti** (traces Universal Tracer) avec une interface plus moderne, et surtout avec des vues orientées **workflow** :

- comprendre rapidement *ce qui s’est passé* dans la trace (timeline)
- repérer *les anomalies / incohérences* (parsing log)
- reconstruire *le déroulé TLS* d’une session (TLS Flow)

Objectif: **gagner du temps** quand on débug du trafic RSP/SGP.32-like, des canaux BIP, ou des problèmes réseau/certifs.

---

## 1) Le “pourquoi” 

Quand on reçoit un XTI “brut”, on a souvent 3 douleurs:

1. **Trop d’items** (des centaines / milliers de traceitems)
2. **Difficile de relier les événements** (Open Channel, DNS, TLS handshake, data, close)
3. **Difficile d’isoler le signal** (warnings, erreurs, sévérités, incohérences)

XTI Viewer répond à ça avec:

- une navigation rapide (liste + filtre)
- un inspecteur détaillé (hiérarchie d’interprétation)
- un rendu hex lisible
- et surtout des vues “métiers”: **Flow Overview**, **Parsing Log**, **TLS Flow**

---

## 2) Tour rapide de l’UI (2–3 min)

### 2.1. Fenêtre principale: 3 zones

1) **Interpretation List** (en haut à gauche)
- 1 ligne = 1 `<traceitem>`
- résumé + colonnes (protocol/type/timestamp)
- recherche temps réel

2) **Inspector** (en bas à gauche)
- arborescence complète des `interpretedresult`
- permet de comprendre exactement ce qu’un item signifie

3) **Hex Viewer** (à droite)
- le `rawhex` formaté (offsets, groupes, ASCII)
- pratique pour copier/coller et corréler avec des outils externes

---

## 3) Les vues “workflow” (le cœur de l’outil) (5–7 min)

### 3.1 Flow Overview (timeline)

**But**: donner une vue “film” de la trace.

Ce qu’on voit:
- des **sessions** (channel groups) avec port/protocol/role/server/ips/opened/closed/duration
- + quelques **événements clés** (ex: refresh, cold reset, ICCID) pour ancrer le contexte

Interactions:
- **double-clic sur une session** → filtre la session dans la trace et bascule vers **TLS Flow**
- export possible (CSV)

Pourquoi c’est utile:
- on comprend en 10 secondes si on a 1 session, 10 sessions, si ça “loop”, si ça drop, etc.

### 3.2 Parsing Log

**But**: une liste de contrôles cohérents et actionnables, classés par sévérité.

Source:
- un validateur parcourt la trace et génère des issues (Info/Warning/Critical)

Exemples d’issues:
- problèmes de state machine (ex: CLOSE sans OPEN)
- channel status (link dropped/off)
- erreurs SW / erreurs BIP
- location status (normal/limited/no service)

Pourquoi c’est utile:
- on arrête de “chercher l’aiguille” : on va directement aux anomalies

### 3.3 TLS Flow

**But**: reconstruire une vue “réseau” d’une session: handshake, app-data, etc.

Sous-tabs typiques:
- **Messages**: liste des messages TLS regroupés par phases
- **Overview**: résumé (version, cipher, stats, flow)
- **Security**: info sécurité/certifs/metadata (selon build)

Important (scope):
- on fait du **décodage record/handshake**, pas du déchiffrement.
- donc l’ApplicationData reste opaque (on affiche taille/compte, pas le contenu).

Comportement récent:
- on **n’affiche plus** l’indicateur “SGP.32 cipher approved list” dans l’Overview.
- on **ne classe plus** les `Alert` dans la “Closure Phase” (on évite de donner l’impression qu’il y a toujours une vraie phase de fermeture TLS).

---

chaque trace item est parsé en APDU/TLV Ensuite on extrait le champ “payload” TLV qui contient les octets TLS 
Réassemble par **direction** (buffer par `ME->SIM` / `SIM->ME`) car les records TLS peuvent être coupés sur plusieurs segments.

Repère un header TLS (5 octets) + longueur, puis découpe chaque record complet.
    - Reconnaît les types de record: Handshake (22), ApplicationData (23), ChangeCipherSpec (20), Alert (21).


LS Flow (important en Q&A)

Q: Vous déchiffrez TLS ?
R: Non. On fait du décodage “best-effort” des records/handshakes et on extrait des métadonnées (version/cipher/ALPN/SNI quand disponible). L’ApplicationData reste opaque (tailles/compteurs).

Q: Pourquoi “best-effort” ?
R: Parce que la trace peut fragmenter les records TLS sur plusieurs segments, ou manquer des morceaux. On tente de réassembler mais on ne peut pas garantir 100% si les inputs sont incomplets.

Q: Comment vous identifiez ClientHello / ServerHello etc. ?
R: Par scan des TLS records (content-type 20/21/22/23) et parsing minimal du handshake pour reconnaître les types et extraire certaines extensions. Une partie de l’analyse est dans








## 6) Positionnement / limites / prochaines étapes (1–2 min)

### Ce que l’outil fait très bien
- accélérer l’analyse “operator-friendly”
- remettre du contexte (sessions + events)
- donner une lecture TLS de la session

### Limites actuelles (assumées)
- pas de déchiffrement TLS
- l’analyse TLS est “best-effort” (selon fragmentation, traces, etc.)

### Prochaines étapes possibles (si l’équipe veut)
- améliorer encore la robustesse TLS record reassembly
- enrichir la Security view (cert chain, versions supportées, ALPN) de façon cohérente
- ajouter 2–3 événements “business” supplémentaires dans Flow Overview (si besoin)

---

## 7) Conclusion (15s)

En résumé: **XTI Viewer** transforme une trace XTI difficile à lire en une analyse structurée avec:
- une timeline (Flow Overview)
- des anomalies actionnables (Parsing Log)
- une reconstruction session TLS (TLS Flow)

Je peux faire une mini-démo sur un fichier réel et on itère ensuite sur ce qui manque.
