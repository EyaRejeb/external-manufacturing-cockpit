"""Crée un fichier pour un 9e façonnier fictif (test de robustesse du pipeline)."""
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
rng = np.random.default_rng(7)
skus = pd.read_csv(RACINE / "data" / "raw" / "erp" / "erp_produits.csv", sep=";")["sku"].tolist()

n = 20
dates = pd.Timestamp("2025-06-02") + pd.to_timedelta(rng.integers(0, 150, n), unit="D")
promises = dates + pd.Timedelta(days=30)
qte = (rng.integers(20, 100, n) * 500)
df = pd.DataFrame({
    "Bestellnummer": [f"CMD-2025-9{i:04d}" for i in range(1, n + 1)],
    "Artikelnummer": rng.choice(skus, n),
    "Lieferant": rng.choice(["Rhein Kosmetik GmbH", "RHEIN KOSMETIK", "Rhein Kosmetik"], n),
    "Bestelldatum": dates.strftime("%d/%m/%Y"),
    "Zugesagt": promises.strftime("%d/%m/%Y"),
    "Lieferdatum": (promises + pd.to_timedelta(rng.integers(-3, 6, n), unit="D")).strftime("%d/%m/%Y"),
    "Bestellmenge": qte,
    "Liefermenge": qte,
    "Akzeptiert": qte,
    "Stueckpreis": [f"{x:.3f}".replace(".", ",") for x in rng.uniform(2, 6, n)],
})
fichier = RACINE / "data" / "raw" / "facconniers" / "F09_rhein_kosmetik.xlsx"
df.to_excel(fichier, sheet_name="export", index=False)
print(f"{fichier.name} : {len(df)} lignes")