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