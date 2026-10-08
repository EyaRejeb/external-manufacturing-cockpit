"""Générateur de données synthétiques — DermaLab Laboratoires (entreprise fictive).

Partie 1 : référentiels (façonniers, produits, calendrier).
Toutes les règles de l'univers simulé sont dans config.yaml.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_VERITE = RACINE / "data" / "reference" / "verite"

MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

CODES_GAMME = {
    "Soin visage": "SV",
    "Solaire": "SO",
    "Capillaire": "CA",
    "Hygiène": "HY",
    "Bébé": "BB",
    "Dermatologie": "DE",
}

# Noms de lignes de produits fictifs
NOMS_PRODUITS = {
    "Soin visage": ["Hydra Confort", "Éclat Pur", "Peau Sensible", "Anti-Rougeurs",
                    "Matifiant", "Nutrition Intense", "Anti-Âge", "Apaisant"],
    "Solaire": ["Haute Protection", "Peaux Sensibles", "Enfant", "Après-Soleil",
                "Invisible", "Sport"],
    "Capillaire": ["Fortifiant", "Antipelliculaire", "Cheveux Secs", "Volume",
                   "Cuir Chevelu Sensible", "Réparateur"],
    "Hygiène": ["Surgras", "Peaux Atopiques", "Fraîcheur", "Douceur", "Protection 48h"],
    "Bébé": ["Change", "Hydratant Bébé", "Lavant Doux", "Croûtes de Lait"],
    "Dermatologie": ["Réparateur Cutané", "Anti-Démangeaisons", "Cicatrisant",
                     "Émollient", "Kératolytique"],
}

GAMMES_COMPLEXES = {"Solaire", "Dermatologie"}  # formulations plus exigeantes
CONTENANCES_ML = [30, 50, 100, 200, 400]


def charger_config(chemin: Path = RACINE / "config.yaml") -> dict:
    with open(chemin, encoding="utf-8") as fichier:
        return yaml.safe_load(fichier)


def repartir(total: int, parts: list[float]) -> list[int]:
    """Répartit un total entier selon des proportions (méthode du plus fort reste)."""
    brut = np.array(parts) / sum(parts) * total
    entiers = np.floor(brut).astype(int)
    reste = total - entiers.sum()
    ordre = np.argsort(-(brut - entiers))
    entiers[ordre[:reste]] += 1
    return entiers.tolist()


def generer_dim_facconnier(cfg: dict) -> pd.DataFrame:
    lignes = [
        {
            "id_facconnier": f["id"],
            "nom": f["nom"],
            "pays": f["pays"],
            "criticite": f["criticite"],
            "certification_iso": f["certification_iso"],
            "date_debut_contrat": f["date_debut_contrat"],
            "delai_contractuel_jours": f["delai_promis_jours"],
        }
        for f in cfg["facconniers"]
    ]
    return pd.DataFrame(lignes)


def generer_produits(cfg: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Crée le référentiel produits et l'affectation SKU → façonnier(s)."""
    gammes = cfg["gammes"]
    effectifs = repartir(cfg["volumes"]["nb_produits"], [g["part_produits"] for g in gammes])
    ids_facconniers = [f["id"] for f in cfg["facconniers"]]

    produits, affectations = [], []
    for gamme, nombre in zip(gammes, effectifs):
        nom_gamme = gamme["nom"]
        noms = NOMS_PRODUITS[nom_gamme]
        p_complexite = [0.30, 0.40, 0.30] if nom_gamme in GAMMES_COMPLEXES else [0.45, 0.40, 0.15]

        for i in range(1, nombre + 1):
            sku = f"DL-{CODES_GAMME[nom_gamme]}-{i:03d}"
            forme = str(rng.choice(gamme["formes"]))
            contenance = int(rng.choice(CONTENANCES_ML))
            complexite = int(rng.choice([1, 2, 3], p=p_complexite))
            prix = round(1.2 * complexite + rng.uniform(0.3, 2.0), 2)

            produits.append({
                "sku": sku,
                "libelle": f"{forme.capitalize()} {noms[(i - 1) % len(noms)]} {contenance} ml",
                "gamme": nom_gamme,
                "forme": forme,
                "contenance_ml": contenance,
                "complexite": complexite,
                "prix_standard_eur": prix,
            })

            principal = str(rng.choice(ids_facconniers))
            affectations.append({"sku": sku, "id_facconnier": principal, "role": "principal"})
            if rng.random() < 0.35:  # environ 1 SKU sur 3 a un second façonnier
                autres = [f for f in ids_facconniers if f != principal]
                affectations.append({"sku": sku, "id_facconnier": str(rng.choice(autres)),
                                     "role": "secondaire"})

    return pd.DataFrame(produits), pd.DataFrame(affectations)


def generer_dim_date(cfg: dict) -> pd.DataFrame:
    """Calendrier étendu de 120 jours après la fin de période,
    pour couvrir les livraisons des dernières commandes."""
    fin = pd.Timestamp(cfg["projet"]["date_fin"]) + pd.Timedelta(days=120)
    df = pd.DataFrame({"date": pd.date_range(cfg["projet"]["date_debut"], fin, freq="D")})
    df["annee"] = df["date"].dt.year
    df["trimestre"] = df["date"].dt.quarter
    df["mois"] = df["date"].dt.month
    df["libelle_mois"] = df["mois"].map(lambda m: MOIS_FR[m - 1])
    df["annee_mois"] = df["date"].dt.strftime("%Y-%m")
    df["semaine_iso"] = df["date"].dt.isocalendar().week.astype(int)
    df["jour_semaine"] = df["date"].dt.dayofweek + 1  # 1 = lundi
    df["jour_ouvre"] = df["jour_semaine"] <= 5
    return df


def sauvegarder(df: pd.DataFrame, nom: str) -> None:
    DOSSIER_VERITE.mkdir(parents=True, exist_ok=True)
    df.to_csv(DOSSIER_VERITE / f"{nom}.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    cfg = charger_config()
    rng = np.random.default_rng(cfg["projet"]["seed"])

    dim_facconnier = generer_dim_facconnier(cfg)
    dim_produit, ref_sku_facconnier = generer_produits(cfg, rng)
    dim_date = generer_dim_date(cfg)

    sauvegarder(dim_facconnier, "dim_facconnier")
    sauvegarder(dim_produit, "dim_produit")
    sauvegarder(ref_sku_facconnier, "ref_sku_facconnier")
    sauvegarder(dim_date, "dim_date")

    print(f"Façonniers : {len(dim_facconnier)}")
    print(f"Produits   : {len(dim_produit)}")
    print(dim_produit["gamme"].value_counts().to_string(), "\n")
    print("Complexité :", dim_produit["complexite"].value_counts().sort_index().to_dict())
    print("SKU par façonnier :",
          ref_sku_facconnier["id_facconnier"].value_counts().sort_index().to_dict())
    print(f"Calendrier : {dim_date['date'].min().date()} → {dim_date['date'].max().date()}")


if __name__ == "__main__":
    main()