"""Affiche l'avancement de la classification IA des déviations (sans appeler l'API)."""
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
PROCESSED = RACINE / "data" / "processed"
total = len(pd.read_csv(PROCESSED / "fact_deviation.csv"))

print(f"Déviations à classer : {total}\n")
for mode in ["zero_shot", "few_shot"]:
    fichier = PROCESSED / f"deviations_classees_{mode}.csv"
    fait = pd.read_csv(fichier)["id_deviation"].nunique() if fichier.exists() else 0
    reste = total - fait
    barre = "█" * int(20 * fait / total) + "░" * (20 - int(20 * fait / total))
    etat = "TERMINÉ ✅" if reste == 0 else f"reste {reste} (≈ {-(-reste // 100)} requêtes en paquets de 100)"
    print(f"{mode:<10} {barre} {fait:>4}/{total}  {etat}")