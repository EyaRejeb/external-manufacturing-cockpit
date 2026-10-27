"""Tests automatisés des sorties du pipeline (aucun appel à l'API Gemini).

Lancement depuis la racine du projet :
    pytest
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parents[1]
PROCESSED = RACINE / "data" / "processed"
REFERENCE = RACINE / "data" / "reference"
CATEGORIES_6M = {"Matière", "Méthode", "Machine", "Main-d'œuvre", "Milieu", "Mesure"}

sys.path.insert(0, str(RACINE / "src"))


def lire(chemin: Path) -> pd.DataFrame:
    # utf-8-sig : certaines sorties Alteryx commencent par un BOM
    return pd.read_csv(chemin, encoding="utf-8-sig")


@pytest.fixture(scope="module")
def commandes():
    return lire(PROCESSED / "fact_commande.csv")


@pytest.fixture(scope="module")
def lots():
    return lire(PROCESSED / "fact_lot.csv")


@pytest.fixture(scope="module")
def deviations():
    return lire(PROCESSED / "fact_deviation.csv")


@pytest.fixture(scope="module")
def anomalies():
    return lire(PROCESSED / "dq_anomalies.csv")


# --- Volumes -----------------------------------------------------------------
def test_volumes(commandes, lots, deviations, anomalies):
    assert len(commandes) == 6000
    assert len(lots) == 11735
    assert len(deviations) == 1223
    assert len(anomalies) == 415


# --- Unicité -----------------------------------------------------------------
@pytest.mark.parametrize("table, cle", [
    ("fact_commande.csv", "id_commande"),
    ("fact_lot.csv", "id_lot"),
    ("fact_deviation.csv", "id_deviation"),
])
def test_identifiants_uniques(table, cle):
    df = lire(PROCESSED / table)
    assert df[cle].notna().all(), f"identifiant vide dans {table}"
    doublons = df[df[cle].duplicated()][cle].tolist()
    assert not doublons, f"{len(doublons)} doublons dans {table} : {doublons[:5]}"


# --- Intégrité référentielle -------------------------------------------------
def test_tout_lot_pointe_vers_une_commande(commandes, lots):
    orphelins = set(lots["id_commande"]) - set(commandes["id_commande"])
    assert not orphelins, f"{len(orphelins)} lots sans commande"


def test_toute_deviation_pointe_vers_un_lot(lots, deviations):
    orphelines = set(deviations["id_lot"]) - set(lots["id_lot"])
    assert not orphelines, f"{len(orphelines)} déviations sans lot"


# --- Détection des anomalies (Alteryx vs anomalies injectées) ----------------
def test_les_415_anomalies_injectees_sont_retrouvees(anomalies):
    injectees = lire(REFERENCE / "anomalies_injectees.csv")
    cle = ["id_commande", "type_anomalie"]
    inj = injectees.groupby(cle).size()
    det = anomalies.groupby(cle).size()
    comparaison = pd.concat([inj.rename("injectees"), det.rename("detectees")], axis=1).fillna(0)

    manquees = comparaison[comparaison["detectees"] < comparaison["injectees"]]
    fausses_alertes = comparaison[comparaison["detectees"] > comparaison["injectees"]]
    assert len(injectees) == 415
    assert manquees.empty, f"{len(manquees)} anomalies manquées"
    assert fausses_alertes.empty, f"{len(fausses_alertes)} fausses alertes"


# --- Classification IA (résultats enregistrés) -------------------------------
@pytest.mark.parametrize("mode", ["zero_shot", "few_shot"])
def test_classification_complete_et_valide(mode, deviations):
    classees = lire(PROCESSED / f"deviations_classees_{mode}.csv")
    assert len(classees) == 1223
    assert classees["id_deviation"].is_unique
    assert set(classees["id_deviation"]) == set(deviations["id_deviation"])
    hors_liste = set(classees["categorie_ia"]) - CATEGORIES_6M
    assert not hors_liste, f"catégories hors 6M : {hors_liste}"


def test_exactitude_few_shot_au_moins_99_pct():
    verite = lire(REFERENCE / "verite" / "fact_deviation.csv")[["id_deviation", "categorie_6m_verite"]]
    exemples = lire(PROCESSED / "exemples_few_shot.csv")["id_deviation"]
    classees = lire(PROCESSED / "deviations_classees_few_shot.csv").merge(verite, on="id_deviation")
    evaluees = classees[~classees["id_deviation"].isin(exemples)]  # exemples exclus de l'évaluation
    exactitude = (evaluees["categorie_ia"] == evaluees["categorie_6m_verite"]).mean()
    assert len(evaluees) == 1211
    assert exactitude >= 0.99, f"exactitude {exactitude:.1%}"


# --- Reproductibilité du générateur ------------------------------------------
def generer_en_memoire():
    """Rejoue le générateur (sans rien écrire sur le disque) avec la graine de config.yaml."""
    import generation as g

    cfg = g.charger_config()
    rng = np.random.default_rng(cfg["projet"]["seed"])
    g.generer_dim_facconnier(cfg)
    dim_produit, ref_sku = g.generer_produits(cfg, rng)
    commandes = g.generer_commandes(cfg, rng, dim_produit, ref_sku)
    lots = g.generer_lots(cfg, rng, commandes, dim_produit)
    commandes = g.ajouter_qte_conforme(commandes, lots)
    deviations = g.generer_deviations(cfg, rng, lots, commandes)
    return {"fact_commande": commandes, "fact_lot": lots, "fact_deviation": deviations}


def test_meme_graine_memes_donnees(tmp_path):
    premiere, seconde = generer_en_memoire(), generer_en_memoire()
    for nom in premiere:
        pd.testing.assert_frame_equal(premiere[nom], seconde[nom], obj=nom)

    # Et les données régénérées sont identiques aux tables de vérité du dépôt
    for nom, df in premiere.items():
        chemin = tmp_path / f"{nom}.csv"
        df.to_csv(chemin, index=False, encoding="utf-8-sig")
        pd.testing.assert_frame_equal(lire(chemin), lire(REFERENCE / "verite" / f"{nom}.csv"),
                                      check_dtype=False, obj=nom)
