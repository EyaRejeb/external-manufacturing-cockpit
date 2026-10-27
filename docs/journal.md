# Journal de bord

## Phase 1 — Données synthétiques
- Générateur Python reproductible (seed 42, paramétré par `config.yaml`) : 8 façonniers, 60 produits, 6 000 commandes, 11 735 lots, 1 223 déviations.
- 5 signaux métier et 415 anomalies (6 types) injectés volontairement, avec tables de vérité dans `data/reference/verite/` pour valider le pipeline.
- Contrôle visuel : `notebooks/00_controle_generation.ipynb`.  

## Phase 2 — Pipeline Alteryx (ingestion, nettoyage, qualité)

### Objectif
Transformer 8 exports façonniers hétérogènes (5 formats de colonnes, 3 formats de date, 2 séparateurs décimaux, un fichier découpé en 36 onglets) en tables propres et traçables, sans perdre une seule ligne en silence.

### Ce qui a été construit
| Élément | Rôle | Résultat |
|---|---|---|
| `macro_normalisation.yxmc` | Macro batch : renomme les colonnes de chaque fichier/onglet via `mapping_colonnes.xlsx` | 1 macro pour tous les formats |
| `01_ingestion_facconniers` | Lit tous les fichiers et tous les onglets dynamiquement | 6 090 lignes brutes |
| `02_nettoyage_standardisation` | Types, doublons, contrôle du référentiel produits, 6 types d'anomalies, unification des noms | 6 000 commandes, 415 anomalies, 32 variantes de noms |
| `03_qualite_lots` | Lots et déviations rattachés aux commandes | 11 735 lots, 1 223 déviations |
| `04_rapport_qualite_donnees` | Rapport PDF : injecté vs détecté | `docs/rapport_qualite_donnees.pdf` |

### Résultats de validation
- **Détection : 415/415 anomalies retrouvées, 0 manquée, 0 fausse alerte** (comparaison ligne à ligne par `src/verifier_detection.py`).
- Aucune valeur nulle inattendue dans `fact_lot` ; 22 déviations ouvertes, délai moyen de clôture 23,9 jours.

### Décisions clés
- **Paramétrage plutôt que code** : formats de date, séparateurs et noms de colonnes sont dans `mapping_colonnes.xlsx`. Ajouter un façonnier = ajouter des lignes, pas modifier le workflow.
- **Rien n'est supprimé sans trace** : doublons, anomalies corrigées ou invalidées et lignes exclues sont toutes écrites dans `dq_anomalies` avec la valeur d'origine et l'action appliquée.
- **Correspondance approximative + table d'alias** : le fuzzy match (seuil 70 %) rattache 30 variantes de noms sur 32 ; les 2 cas trop éloignés (« Pyrénées Fab. », « LAB GARONNE ») sont gérés par une table d'alias explicite plutôt qu'en baissant le seuil.

### Problèmes rencontrés et solutions
- **Dates F04 toutes vides** : la valeur `serie_excel ` du mapping contenait un espace final. Correction à la source + `Trim()` systématique dans les formules.
- **Jointure d'alias vide** : en-tête `fournisseur ` avec espace. Leçon : toujours nettoyer les en-têtes des fichiers saisis à la main.
- **Variantes manquantes** : 30/32 trouvées par fuzzy match → ajout de la table d'alias.

### Tests de robustesse
1. **Ajout d'un 9e façonnier** (branche `test-9e-facconnier`) : fichier allemand (en-têtes, dates `dd/MM/yyyy`, virgule décimale). Intégré avec **12 lignes de paramétrage et aucune modification de workflow** : 6 020 commandes, 35 variantes cohérentes.
2. **Ce test a révélé 2 faiblesses**, corrigées sur `main` :
   - un façonnier absent du référentiel était exclu **sans trace** → ajout du contrôle `facconnier_non_reference` ;
   - espaces parasites dans le référentiel → `Trim()` à la lecture.
3. **Vérification du correctif** : F08 retiré du référentiel → **513 commandes tracées** dans `dq_anomalies`, 5 487 conservées, total = 6 000. Preuve : `docs/test_9e_facconnier/test_facconnier_non_reference.png`.

### Ce que je retiens
Un pipeline de données se juge autant sur ce qu'il signale que sur ce qu'il produit. Les tests volontairement « cassants » (nouveau fournisseur, fournisseur retiré) ont révélé des défauts invisibles sur les données nominales.


## Phase 3 — Analyses métier (Python)

### Démarche
Analyse menée uniquement sur les sorties Alteryx et le référentiel ERP, sans connaître les signaux à l'avance. Les tables de vérité ne sont ouvertes qu'à la fin, pour valider. Notebook : `notebooks/01_analyses_metier.ipynb`.

### Constats
| Question | Constat | Preuve |
|---|---|---|
| Quel façonnier se dégrade ? | F06 : OTIF de 88 % à 73 % depuis début 2025 | test de proportions, p < 0,001 |
| Saisonnalité ? | Solaire : 85 % à l'heure en mars-mai contre 96 % | présent en 2023, 2024 et 2025 |
| Causes des rejets ? | Complexité 3 : rejets ×1,9 (4,6 % contre 2,4 %) | effet présent chez 7 façonniers sur 8 |
| Causes des déviations ? | F03 : 50 % de descriptions liées à la matière | repérage par mots-clés, à confirmer en phase 4 |

### Décisions de méthode
- **Périmètre de l'OTIF documenté** : commandes en cours, livraisons sans date et mois incomplet exclus (5 657 commandes retenues sur 6 000).
- **Rupture détectée automatiquement** (mois qui sépare le mieux l'avant et l'après) : 02/2025 pour un signal injecté en 03/2025. Écart d'un mois expliqué par le faible volume (≈ 12 commandes par mois).
- **Effets séparés** : F06 exclu de l'analyse de saisonnalité, et effet complexité contrôlé à l'intérieur de chaque façonnier, pour ne pas confondre deux causes.

### Validation
OTIF par façonnier à **0,5 point maximum** de la vérité, taux de rejet par complexité à 0,1 point : le nettoyage Alteryx ne biaise pas les analyses.

### Ce que je retiens
Un indicateur global masque l'essentiel : il faut découper par fournisseur et dans le temps, puis contrôler les facteurs cachés avant de conclure.


## Phase 4 — Classification IA des déviations (LLM)

### Problème
Les 1 223 déviations ne sont décrites qu'en texte libre : impossible d'en analyser les causes sans catégorie.

### Solution
- `src/classifier_deviations.py` : Google Gemini (`gemini-flash-latest`, offre gratuite) classe chaque description selon les 6M (Matière, Méthode, Machine, Main-d'œuvre, Milieu, Mesure), en JSON structuré (catégorie, confiance, justification), par paquets de 100.
- Clé API dans `.env` (ignoré par Git), résultats sauvegardés en CSV : évaluation reproductible sans rappeler l'API.
- Gestion du quota gratuit : reprise automatique, nouvelles tentatives sur les erreurs 503, classification étalée sur 3 jours.
- Deux modes comparés : zero-shot (définitions seules) et few-shot (12 exemples annotés, exclus de l'évaluation).

### Résultats (`notebooks/02_evaluation_ia.ipynb`)
| | Zero-shot | Few-shot | Référence naïve |
|---|---|---|---|
| Exactitude | 99,8 % | 99,9 % | 33,7 % |
| F1 macro | 99,7 % | 99,9 % | — |

- Repérage des causes Matière : F1 de 100 % contre 79 % par mots-clés, 0 fausse alerte contre 109.
- Seule erreur : « port des équipements de protection non conforme », Main-d'œuvre classée Méthode. Cas réellement ambigu, signalé en confiance moyenne.

### Réponses métier (5e signal retrouvé)
- F03 : 54 % de déviations Matière, contre 18 à 28 % ailleurs → audit des matières premières.
- Lots > 50 000 unités : 35 % de déviations Méthode, contre 21 % (p < 0,001) → revoir les instructions pour les grands volumes.
- Les conclusions obtenues avec les catégories IA sont identiques à celles obtenues avec les vraies catégories.

### Limites
- Les descriptions synthétiques viennent de 48 modèles de phrases : bien plus régulières que des déviations réelles. Le score serait plus bas sur des données réelles.
- Le modèle s'annonce presque toujours en confiance haute : l'intérêt de la confiance pour trier les cas à relire n'a pas pu être vraiment testé.
- Avec de vraies données de santé : offre d'API sans réutilisation des données ou modèle hébergé en interne (RGPD).

### Ce que je retiens
Un LLM s'évalue comme n'importe quel modèle, et le few-shot n'est utile que s'il reste une marge de progression : ici, le zero-shot suffisait.


## Phase 5 — Tableau de bord Power BI

### Objectif
Mettre les résultats des phases 2 à 4 entre les mains des équipes achats et qualité : un tableau de bord qui se lit sans Python, et dont les chiffres sont identiques à ceux des notebooks.

### Ce qui a été construit
| Élément | Contenu |
|---|---|
| Modèle en étoile | 4 tables de faits (commandes, lots, déviations, anomalies) et 3 dimensions (façonnier, produit, date) |
| `dim_date` | Table calendrier en DAX (2023 à mars 2026), marquée comme table de dates, mois triés dans l'ordre du calendrier |
| Mesures | 17 mesures DAX regroupées dans une table `_Mesures` (OTIF, à l'heure, complète, taux de rejet, déviations pour 100 lots, clôture en 30 jours, coût de non-qualité, anomalies…) |
| Pages | 1. Vue d'ensemble · 2. Livraisons · 3. Qualité · 4. Qualité des données |
| Exports | [`powerbi/external_manufacturing_cockpit.pdf`](../powerbi/external_manufacturing_cockpit.pdf) et 4 captures dans `powerbi/captures/` |

### Décisions
- **La date promise sert de date de référence** pour l'OTIF : une commande est jugée sur le mois où elle devait arriver, comme dans le notebook 01.
- **F06 est suivi par trimestre** : avec une douzaine de commandes par mois, la courbe mensuelle est trop bruitée ; le trimestre montre la chute de 2025 sans faux signal.
- **Contrôle croisé avec Python** : l'OTIF global affiché (84,6 %) est identique à celui du notebook 01 (5 657 commandes dans le périmètre). Le tableau de bord ne recalcule rien de différent.
- **Chaque visuel a un titre qui donne la conclusion** (« F06 : l'OTIF chute nettement en 2025 ») plutôt qu'une description (« OTIF par trimestre »).

### Problèmes rencontrés et solutions
- **Nombres mal lus** : Power BI lisait les CSV avec la culture française, le point décimal était ignoré (25500.0 devenait 255000). Correction : types appliqués avec la culture `en-US` dans Power Query.
- **Table des anomalies sans en-têtes** : en-têtes promus manuellement, colonne `fichier_source` (chemin local) retirée, lecture avec `QuoteStyle.Csv` pour les virgules dans les valeurs.
- **Relations créées automatiquement** (lots → commandes, déviations → commandes, déviations ↔ lots) : elles créaient des chemins ambigus. Supprimées, puis détection automatique des relations et date/heure automatique désactivées.

### Ce que je retiens
Un tableau de bord n'est crédible que si ses chiffres sont recoupés avec une autre source : le contrôle OTIF = 84,6 % des deux côtés a validé à la fois le modèle et les mesures.


## Bilan du projet
- **Résultat** : un pipeline complet, des fichiers Excel hétérogènes au tableau de bord, validé à chaque étape contre des tables de vérité (415/415 anomalies, OTIF à 0,5 point, 99,9 % d'exactitude IA).
- **Valeur métier** : 5 problèmes retrouvés sans les connaître à l'avance, chacun avec une recommandation actionnable.
- **Ce qui a le plus servi** : tracer chaque ligne exclue et tester le pipeline avec des cas volontairement cassants.
- **Limite principale** : des données synthétiques, plus régulières que la réalité, surtout pour les descriptions de déviations.
- **Suite possible** : rejouer le pipeline sur des données réelles et automatiser son exécution (planification, alertes sur l'OTIF).
