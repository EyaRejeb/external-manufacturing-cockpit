"""Compare, ligne à ligne, les anomalies injectées par le générateur
et les anomalies détectées par le pipeline Alteryx (workflow 02)."""
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]

injectees = pd.read_csv(RACINE / "data" / "reference" / "anomalies_injectees.csv")
detectees = pd.read_csv(RACINE / "data" / "processed" / "dq_anomalies.csv")

cle = ["id_commande", "type_anomalie"]
inj = injectees.groupby(cle).size().rename("nb_injectees")
det = detectees.groupby(cle).size().rename("nb_detectees")
comparaison = pd.concat([inj, det], axis=1).fillna(0).astype(int).reset_index()

comparaison["statut"] = "détectée"
comparaison.loc[comparaison["nb_detectees"] < comparaison["nb_injectees"], "statut"] = "manquée"
comparaison.loc[comparaison["nb_detectees"] > comparaison["nb_injectees"], "statut"] = "fausse alerte"

synthese = comparaison.pivot_table(index="type_anomalie", columns="statut",
                                   values="id_commande", aggfunc="count", fill_value=0)
print(synthese, "\n")

n_ok = (comparaison["statut"] == "détectée").sum()
print(f"Anomalies retrouvées à la bonne commande : {n_ok} / {len(comparaison)}")
print(f"Manquées : {(comparaison['statut'] == 'manquée').sum()}")
print(f"Fausses alertes : {(comparaison['statut'] == 'fausse alerte').sum()}")

comparaison.to_csv(RACINE / "docs" / "verification_detection.csv", index=False, encoding="utf-8-sig")