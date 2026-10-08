"""Télécharge des motifs de rappels réels depuis l'API openFDA (Drug Enforcement).

Ces données servent à calibrer le vocabulaire des déviations simulées.
"""
import json
import time
from pathlib import Path

import requests

URL = "https://api.fda.gov/drug/enforcement.json"
PAGES = 5
LIMIT = 1000  # maximum autorisé par appel
SORTIE = Path(__file__).resolve().parents[1] / "data" / "reference"
CHAMPS = [
    "recall_number",
    "report_date",
    "classification",
    "reason_for_recall",
    "product_description",
    "status",
]


def telecharger() -> list[dict]:
    resultats = []
    for page in range(PAGES):
        params = {"limit": LIMIT, "skip": page * LIMIT}
        reponse = requests.get(URL, params=params, timeout=30)
        reponse.raise_for_status()
        lot = reponse.json().get("results", [])
        resultats.extend(lot)
        print(f"Page {page + 1}/{PAGES} : {len(lot)} rappels")
        time.sleep(1)  # pause pour respecter les limites de l'API
    return resultats


def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    rappels = telecharger()
    propres = [{champ: r.get(champ) for champ in CHAMPS} for r in rappels]
    fichier = SORTIE / "openfda_recalls.json"
    fichier.write_text(json.dumps(propres, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(propres)} rappels enregistrés dans {fichier}")


if __name__ == "__main__":
    main()