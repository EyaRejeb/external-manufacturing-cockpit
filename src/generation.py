"""Générateur de données synthétiques — DermaLab Laboratoires (entreprise fictive).

Partie 1 : référentiels (façonniers, produits, calendrier).
Toutes les règles de l'univers simulé sont dans config.yaml.
"""

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from gabarits_deviations import generer_description

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
CATEGORIES_6M = ["Matière", "Méthode", "Machine", "Main-d'œuvre", "Milieu", "Mesure"]
POIDS_6M = [0.22, 0.25, 0.20, 0.15, 0.08, 0.10]

COLONNES_EXPORT = ["id_commande", "sku", "fournisseur", "date_commande", "date_promise",
                   "date_livraison", "qte_commandee", "qte_livree", "qte_conforme",
                   "cout_unitaire_eur"]

FORMATS_EXPORT = {
    "fr_standard": {
        "libelles": ["N° commande", "Réf. article", "Fournisseur", "Date cde", "Date promise",
                     "Date livr.", "Qté commandée", "Qté livrée", "Qté conforme", "Prix unitaire"],
        "format_date": "%d/%m/%Y", "decimale": ","},
    "fr_variante": {
        "libelles": ["Commande", "Article", "Fabricant", "Date de commande", "Date prévue",
                     "Date de livraison", "Quantité", "Quantité reçue", "Quantité acceptée", "PU (€)"],
        "format_date": "%d/%m/%Y", "decimale": ","},
    "fr_codes": {
        "libelles": ["num_cde", "ref_art", "fourn", "dt_cde", "dt_prom", "dt_liv",
                     "qte_cde", "qte_liv", "qte_conf", "pu"],
        "format_date": "serie_excel", "decimale": "."},
    "es": {
        "libelles": ["Nº pedido", "Referencia", "Proveedor", "Fecha pedido", "Fecha prometida",
                     "Fecha entrega", "Cantidad pedida", "Cantidad entregada", "Cantidad conforme",
                     "Precio unitario"],
        "format_date": "%Y-%m-%d", "decimale": ","},
    "en": {
        "libelles": ["Order_ID", "Item_Code", "Supplier", "Order_Date", "Promised_Date",
                     "Delivery_Date", "Ordered_Qty", "Delivered_Qty", "Accepted_Qty", "Unit_Price"],
        "format_date": "%Y-%m-%d", "decimale": "."},
}

FORMAT_PAR_FACCONNIER = {"F01": "fr_standard", "F02": "fr_variante", "F03": "fr_standard",
                         "F04": "fr_codes", "F05": "es", "F06": "en", "F07": "es", "F08": "en"}
FACCONNIERS_ONGLET_PAR_MOIS = {"F06"}

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

def generer_lots(cfg: dict, rng: np.random.Generator,
                 commandes: pd.DataFrame, dim_produit: pd.DataFrame) -> pd.DataFrame:
    """Découpe chaque commande livrée en 1 à 3 lots et tire leur statut qualité."""
    params = {f["id"]: f for f in cfg["facconniers"]}
    taille_min, taille_max = cfg["volumes"]["taille_lot"]
    _, lots_max = cfg["volumes"]["lots_par_commande"]
    s_cplx = cfg["signaux"]["effet_complexite"]

    livrees = commandes[commandes["statut_commande"] == "livrée"].merge(
        dim_produit[["sku", "complexite"]], on="sku", how="left")

    lignes = []
    for c in livrees.itertuples(index=False):
        qte = int(c.qte_livree)
        n_min = max(1, int(np.ceil(qte / taille_max)))
        n_max = max(n_min, min(lots_max, qte // taille_min))
        n_lots = int(rng.integers(n_min, n_max + 1))
        tailles = np.full(n_lots, qte // n_lots // 100 * 100)
        tailles[-1] = qte - tailles[:-1].sum()

        duree = (c.date_livraison - c.date_commande).days
        multiplicateur = s_cplx["multiplicateur_rejet"] if c.complexite == s_cplx["niveau"] else 1.0
        p_rejet = params[c.id_facconnier]["taux_rejet"] * multiplicateur

        for k, taille in enumerate(tailles, start=1):
            tirage = rng.random()
            if tirage < p_rejet:
                statut, cout = "rejeté", taille * c.cout_unitaire_eur              # lot détruit
            elif tirage < 2.2 * p_rejet:
                statut, cout = "retraité", taille * c.cout_unitaire_eur * 0.15     # coût de reprise
            else:
                statut, cout = "libéré", 0.0
            lignes.append({
                "id_lot": f"L{c.id_commande[4:]}-{k}",
                "id_commande": c.id_commande,
                "date_fabrication": c.date_commande + pd.Timedelta(days=int(rng.integers(5, max(6, duree - 3)))),
                "taille_lot": int(taille),
                "statut_lot": statut,
                "cout_non_qualite_eur": round(float(cout), 2),
            })
    return pd.DataFrame(lignes)


def ajouter_qte_conforme(commandes: pd.DataFrame, lots: pd.DataFrame) -> pd.DataFrame:
    """Quantité conforme = lots libérés + lots retraités (les rejetés sont perdus)."""
    conforme = lots[lots["statut_lot"] != "rejeté"].groupby("id_commande")["taille_lot"].sum()
    commandes = commandes.copy()
    commandes["qte_conforme"] = commandes["id_commande"].map(conforme)
    livree = commandes["statut_commande"] == "livrée"
    commandes.loc[livree, "qte_conforme"] = commandes.loc[livree, "qte_conforme"].fillna(0)
    commandes["qte_conforme"] = commandes["qte_conforme"].astype("Int64")
    colonnes = ["id_commande", "sku", "id_facconnier", "date_commande", "date_promise",
                "date_livraison", "qte_commandee", "qte_livree", "qte_conforme",
                "cout_unitaire_eur", "statut_commande"]
    return commandes[colonnes]


def generer_deviations(cfg: dict, rng: np.random.Generator,
                       lots: pd.DataFrame, commandes: pd.DataFrame) -> pd.DataFrame:
    """Crée les déviations : toujours pour les lots rejetés ou retraités,
    parfois pour les lots libérés."""
    p_libere = cfg["volumes"]["proba_deviation_lot_libere"]
    s_taille = cfg["signaux"]["effet_taille_lot"]
    s_f03 = cfg["signaux"]["matiere_f03"]
    date_extraction = pd.Timestamp(cfg["projet"]["date_fin"])
    duree_moyenne = {"mineure": 15, "majeure": 30, "critique": 45}  # jours avant clôture

    lots_f = lots.merge(commandes[["id_commande", "id_facconnier"]], on="id_commande", how="left")
    lignes = []
    for lot in lots_f.itertuples(index=False):
        gros_lot = lot.taille_lot > s_taille["seuil_unites"]

        # Y a-t-il une déviation, et de quelle gravité ?
        if lot.statut_lot == "libéré":
            if rng.random() >= p_libere * (1.3 if gros_lot else 1.0):
                continue
            gravite = "majeure" if rng.random() < 0.15 else "mineure"
        elif lot.statut_lot == "retraité":
            gravite = "majeure" if rng.random() < 0.60 else "mineure"
        else:
            gravite = "critique" if rng.random() < 0.30 else "majeure"

        # Catégorie 6M + signaux F03 (Matière) et gros lots (Méthode)
        poids = np.array(POIDS_6M, dtype=float)
        if lot.id_facconnier == s_f03["facconnier"]:
            i_mat = CATEGORIES_6M.index("Matière")
            autres = np.delete(poids, i_mat)
            poids = np.insert(autres / autres.sum() * (1 - s_f03["part_deviations_matiere"]),
                              i_mat, s_f03["part_deviations_matiere"])
        if gros_lot:
            poids[CATEGORIES_6M.index("Méthode")] *= s_taille["multiplicateur_deviation_methode"]
        categorie = str(rng.choice(CATEGORIES_6M, p=poids / poids.sum()))

        # Dates d'ouverture et de clôture
        ouverture = min(lot.date_fabrication + pd.Timedelta(days=int(rng.integers(0, 4))), date_extraction)
        cloture = ouverture + pd.Timedelta(days=int(np.ceil(rng.gamma(3.0, duree_moyenne[gravite] / 3))))
        ouverte = cloture > date_extraction

        lignes.append({
            "id_lot": lot.id_lot,
            "date_ouverture": ouverture,
            "date_cloture": pd.NaT if ouverte else cloture,
            "statut_deviation": "ouverte" if ouverte else "clôturée",
            "gravite": gravite,
            "description_libre": generer_description(categorie, rng),
            "categorie_6m_verite": categorie,  # vérité terrain, pour évaluer l'IA en phase 4
        })

    df = pd.DataFrame(lignes).sort_values("date_ouverture").reset_index(drop=True)
    numero = df.groupby(df["date_ouverture"].dt.year).cumcount() + 1
    df.insert(0, "id_deviation", "DEV-" + df["date_ouverture"].dt.year.astype(str)
              + "-" + numero.astype(str).str.zfill(4))
    return df


def controler_qualite(cfg: dict, commandes: pd.DataFrame, lots: pd.DataFrame,
                      deviations: pd.DataFrame, dim_produit: pd.DataFrame) -> None:
    """Vérifie que les signaux qualité sont bien présents."""
    print("\n--- Contrôle des lots et déviations ---")
    print(f"Lots : {len(lots)} | Déviations : {len(deviations)}")
    print("Statut des lots :", lots["statut_lot"].value_counts().to_dict())

    lc = lots.merge(commandes[["id_commande", "sku", "id_facconnier"]], on="id_commande") \
             .merge(dim_produit[["sku", "complexite"]], on="sku")
    print("\nTaux de rejet par complexité :")
    print(lc.groupby("complexite")["statut_lot"].apply(lambda s: (s == "rejeté").mean()).round(4).to_string())

    dv = deviations.merge(lc[["id_lot", "id_facconnier", "taille_lot"]], on="id_lot")
    part_matiere = dv.groupby("id_facconnier")["categorie_6m_verite"].apply(lambda s: (s == "Matière").mean())
    print("\nPart des déviations 'Matière' par façonnier :")
    print(part_matiere.round(2).to_string())

    gros = dv["taille_lot"] > cfg["signaux"]["effet_taille_lot"]["seuil_unites"]
    print(f"\nPart 'Méthode' gros lots   : {(dv.loc[gros, 'categorie_6m_verite'] == 'Méthode').mean():.1%}")
    print(f"Part 'Méthode' autres lots : {(dv.loc[~gros, 'categorie_6m_verite'] == 'Méthode').mean():.1%}")

    tolerance = cfg["regles_metier"]["tolerance_retard_jours"]
    seuil = cfg["regles_metier"]["seuil_in_full"]
    liv = commandes[commandes["statut_commande"] == "livrée"].copy()
    liv["otif"] = (((liv["date_livraison"] - liv["date_promise"]).dt.days <= tolerance)
                   & (liv["qte_conforme"] >= seuil * liv["qte_commandee"]))
    print("\nOTIF par façonnier :")
    print(liv.groupby("id_facconnier")["otif"].mean().round(3).to_string())

    print("\nExemples de descriptions :")
    for texte in deviations["description_libre"].head(5):
        print("-", texte)

def injecter_anomalies(cfg: dict, rng: np.random.Generator,
                       commandes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Salit les commandes et note chaque anomalie injectée dans un journal."""
    an = cfg["anomalies"]
    df = commandes.copy()
    journal = []

    def noter(i, type_anomalie, colonne, avant, apres):
        journal.append({"id_commande": df.at[i, "id_commande"], "type_anomalie": type_anomalie,
                        "colonne": colonne, "valeur_originale": avant, "valeur_injectee": apres})

    # 1. Quantités saisies en milliers (F05, 1er semestre 2024)
    m = an["quantite_en_milliers"]
    qtes = ["qte_commandee", "qte_livree", "qte_conforme"]
    df[qtes] = df[qtes].astype("Float64")
    masque = ((df["id_facconnier"] == m["facconnier"])
              & (df["date_commande"] >= pd.Timestamp(m["date_debut"]))
              & (df["date_commande"] <= pd.Timestamp(m["date_fin"])))
    for i in df.index[masque]:
        noter(i, "quantite_en_milliers", "qte_commandee",
              df.at[i, "qte_commandee"], df.at[i, "qte_commandee"] / 1000)
    df.loc[masque, qtes] = df.loc[masque, qtes] / 1000

    # 2. Anomalies ponctuelles, chacune sur des commandes livrées différentes
    candidates = list(rng.permutation(df.index[(df["statut_commande"] == "livrée") & ~masque].to_numpy()))
    n = len(df)

    def tirer(taux: float) -> list:
        k = round(taux * n)
        choisis = candidates[:k]
        del candidates[:k]
        return choisis

    for i in tirer(an["livraison_avant_commande"]):
        avant = df.at[i, "date_livraison"]
        df.at[i, "date_livraison"] = df.at[i, "date_commande"] - pd.Timedelta(days=int(rng.integers(1, 15)))
        noter(i, "livraison_avant_commande", "date_livraison", avant, df.at[i, "date_livraison"])

    for i in tirer(an["quantite_negative_ou_nulle"]):
        avant = df.at[i, "qte_livree"]
        df.at[i, "qte_livree"] = 0 if rng.random() < 0.5 else -avant
        noter(i, "quantite_negative_ou_nulle", "qte_livree", avant, df.at[i, "qte_livree"])

    for i in tirer(an["sku_inconnu"]):
        avant = df.at[i, "sku"]
        df.at[i, "sku"] = (avant.replace("-0", "-", 1) if rng.random() < 0.5
                           else f"DL-XX-{int(rng.integers(900, 1000))}")
        noter(i, "sku_inconnu", "sku", avant, df.at[i, "sku"])

    for i in tirer(an["date_livraison_manquante"]):
        avant = df.at[i, "date_livraison"]
        df.at[i, "date_livraison"] = pd.NaT
        noter(i, "date_livraison_manquante", "date_livraison", avant, None)

    # 3. Doublons : des lignes recopiées à l'identique
    k = round(an["doublons_commandes"] * n)
    idx = rng.choice(df.index.to_numpy(), size=k, replace=False)
    for i in idx:
        noter(i, "doublon", "ligne entière", None, None)
    df = pd.concat([df, df.loc[idx]]).sort_values("date_commande", kind="stable").reset_index(drop=True)

    return df, pd.DataFrame(journal)


def slug(texte: str) -> str:
    """'Cosmétiques du Midi' → 'cosmetiques_du_midi' (pour les noms de fichiers)."""
    sans_accents = "".join(c for c in unicodedata.normalize("NFD", texte)
                           if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", sans_accents.lower()).strip("_")


def formater_dates(serie: pd.Series, format_date: str) -> pd.Series:
    if format_date == "serie_excel":  # nombre de jours depuis le 30/12/1899, comme Excel
        return (serie - pd.Timestamp("1899-12-30")).dt.days.astype("Int64")
    return serie.dt.strftime(format_date)


def exporter_facconniers(cfg: dict, rng: np.random.Generator, commandes: pd.DataFrame) -> None:
    """Un fichier Excel par façonnier, chacun dans son propre format."""
    dossier = RACINE / "data" / "raw" / "facconniers"
    dossier.mkdir(parents=True, exist_ok=True)
    params = {f["id"]: f for f in cfg["facconniers"]}

    for fid, nom_format in FORMAT_PAR_FACCONNIER.items():
        fmt = FORMATS_EXPORT[nom_format]
        sous = commandes[commandes["id_facconnier"] == fid].copy()
        noms = [params[fid]["nom"]] + params[fid]["variantes_nom"]
        sous["fournisseur"] = rng.choice(noms, size=len(sous))  # noms écrits de plusieurs façons

        colonnes = {}
        for col, libelle in zip(COLONNES_EXPORT, fmt["libelles"]):
            valeurs = sous[col]
            if col.startswith("date_"):
                valeurs = formater_dates(valeurs, fmt["format_date"])
            elif col == "cout_unitaire_eur" and fmt["decimale"] == ",":
                valeurs = valeurs.map(lambda x: f"{x:.3f}".replace(".", ","))
            colonnes[libelle] = valeurs.to_numpy()
        sortie = pd.DataFrame(colonnes)
        sortie = sortie.astype(object).where(sortie.notna(), None)  # cellules vides dans Excel

        fichier = dossier / f"{fid}_{slug(params[fid]['nom'])}.xlsx"
        with pd.ExcelWriter(fichier, engine="openpyxl") as writer:
            if fid in FACCONNIERS_ONGLET_PAR_MOIS:
                mois = sous["date_commande"].dt.strftime("%Y-%m").to_numpy()
                for m in sorted(set(mois)):
                    sortie[mois == m].to_excel(writer, sheet_name=m, index=False)
            else:
                sortie.to_excel(writer, sheet_name="export", index=False)
        print(f"  {fichier.name} : {len(sortie)} lignes (format {nom_format})")


def exporter_autres_sources(dim_produit: pd.DataFrame, dim_facconnier: pd.DataFrame,
                            lots: pd.DataFrame, deviations: pd.DataFrame) -> None:
    """ERP (CSV français), système qualité (CSV) et référentiel façonniers (Excel)."""
    raw = RACINE / "data" / "raw"
    for sous_dossier in ["erp", "qualite", "referentiels"]:
        (raw / sous_dossier).mkdir(parents=True, exist_ok=True)

    dim_produit.to_csv(raw / "erp" / "erp_produits.csv", sep=";", decimal=",",
                       index=False, encoding="utf-8-sig")
    lots.to_csv(raw / "qualite" / "qualite_lots.csv", index=False, encoding="utf-8-sig")
    deviations.drop(columns="categorie_6m_verite").to_csv(
        raw / "qualite" / "qualite_deviations.csv", index=False, encoding="utf-8-sig")
    dim_facconnier.to_excel(raw / "referentiels" / "referentiel_facconniers.xlsx", index=False)
    print("  erp_produits.csv, qualite_lots.csv, qualite_deviations.csv, referentiel_facconniers.xlsx")

def sauvegarder(df: pd.DataFrame, nom: str) -> None:
    DOSSIER_VERITE.mkdir(parents=True, exist_ok=True)
    df.to_csv(DOSSIER_VERITE / f"{nom}.csv", index=False, encoding="utf-8-sig")

def generer_commandes(cfg: dict, rng: np.random.Generator,
                      dim_produit: pd.DataFrame,
                      ref_sku_facconnier: pd.DataFrame) -> pd.DataFrame:
    """Crée les commandes de fabrication avec retards et signaux métier."""
    n = cfg["volumes"]["nb_commandes"]
    tolerance = cfg["regles_metier"]["tolerance_retard_jours"]
    signaux = cfg["signaux"]
    params = {f["id"]: f for f in cfg["facconniers"]}
    date_extraction = pd.Timestamp(cfg["projet"]["date_fin"])

    # 1. Produit commandé : quelques références « best-sellers »
    poids = rng.lognormal(0, 0.8, len(dim_produit))
    skus = rng.choice(dim_produit["sku"].to_numpy(), size=n, p=poids / poids.sum())

    # 2. Façonnier : le principal, ou le secondaire dans 25 % des cas s'il existe
    principal = (ref_sku_facconnier[ref_sku_facconnier["role"] == "principal"]
                 .set_index("sku")["id_facconnier"])
    secondaire = (ref_sku_facconnier[ref_sku_facconnier["role"] == "secondaire"]
                  .set_index("sku")["id_facconnier"])
    facconniers = [
        secondaire[sku] if (sku in secondaire.index and rng.random() < 0.25) else principal[sku]
        for sku in skus
    ]

    # 3. Dates de commande : jours ouvrés de la période
    jours_ouvres = pd.bdate_range(cfg["projet"]["date_debut"], cfg["projet"]["date_fin"])
    df = pd.DataFrame({
        "sku": skus,
        "id_facconnier": facconniers,
        "date_commande": pd.to_datetime(rng.choice(jours_ouvres.to_numpy(), size=n)),
    })
    df = df.merge(dim_produit[["sku", "gamme", "prix_standard_eur"]], on="sku", how="left")

    # 4. Date promise = délai contractuel ± 3 jours
    delai = df["id_facconnier"].map(lambda f: params[f]["delai_promis_jours"]) + rng.integers(-3, 4, n)
    df["date_promise"] = df["date_commande"] + pd.to_timedelta(delai, unit="D")

    # 5. Probabilité de retard + signaux métier
    proba = df["id_facconnier"].map(lambda f: params[f]["proba_retard"]).astype(float)

    s_f06 = signaux["chute_otif_f06"]
    masque_f06 = ((df["id_facconnier"] == s_f06["facconnier"])
                  & (df["date_promise"] >= pd.Timestamp(s_f06["date_debut"])))
    proba[masque_f06] = s_f06["proba_retard_apres"]

    s_sol = signaux["saisonnalite_solaire"]
    masque_solaire = (df["gamme"] == s_sol["gamme"]) & df["date_promise"].dt.month.isin(s_sol["mois"])
    proba[masque_solaire] *= s_sol["multiplicateur_retard"]

    en_retard = rng.random(n) < proba.clip(upper=0.9)

    # 6. Date de livraison : dans la tolérance si à l'heure, au-delà sinon
    ecart = np.where(
        en_retard,
        tolerance + 1 + np.round(rng.gamma(2.0, 3.0, n)),  # 3 à ~25 jours de retard
        rng.integers(-5, tolerance + 1, n),                 # de 5 j d'avance à +2 j
    )
    df["date_livraison"] = df["date_promise"] + pd.to_timedelta(ecart, unit="D")

    # 7. Quantités et coût
    qte = rng.lognormal(np.log(40000), 0.6, n).clip(10000, 150000)
    df["qte_commandee"] = (np.round(qte / 500) * 500).astype(int)
    partielle = rng.random(n) < 0.03
    taux_livre = np.where(partielle, rng.uniform(0.85, 0.97, n), 1.0)
    df["qte_livree"] = (np.round(df["qte_commandee"] * taux_livre / 100) * 100).astype(int)
    df["cout_unitaire_eur"] = (df["prix_standard_eur"] * rng.uniform(0.95, 1.08, n)).round(3)

    # 8. Commandes non livrées à la date d'extraction = en cours
    en_cours = df["date_livraison"] > date_extraction
    df["statut_commande"] = np.where(en_cours, "en cours", "livrée")
    df.loc[en_cours, "date_livraison"] = pd.NaT
    df["qte_livree"] = df["qte_livree"].astype("Int64")
    df.loc[en_cours, "qte_livree"] = pd.NA

    # 9. Identifiant chronologique : CMD-2023-00001
    df = df.sort_values("date_commande").reset_index(drop=True)
    numero = df.groupby(df["date_commande"].dt.year).cumcount() + 1
    df["id_commande"] = ("CMD-" + df["date_commande"].dt.year.astype(str)
                         + "-" + numero.astype(str).str.zfill(5))

    colonnes = ["id_commande", "sku", "id_facconnier", "date_commande", "date_promise",
                "date_livraison", "qte_commandee", "qte_livree", "cout_unitaire_eur",
                "statut_commande"]
    return df[colonnes]


def controler_commandes(cfg: dict, commandes: pd.DataFrame, dim_produit: pd.DataFrame) -> None:
    """Affiche les indicateurs de contrôle pour vérifier que les signaux sont bien présents."""
    tolerance = cfg["regles_metier"]["tolerance_retard_jours"]
    livrees = commandes[commandes["statut_commande"] == "livrée"].merge(
        dim_produit[["sku", "gamme"]], on="sku")
    livrees["a_l_heure"] = (livrees["date_livraison"] - livrees["date_promise"]).dt.days <= tolerance

    print("\n--- Contrôle des commandes ---")
    print(f"Commandes : {len(commandes)} dont {(commandes['statut_commande'] == 'en cours').sum()} en cours")
    print("\nTaux 'à l'heure' par façonnier :")
    print(livrees.groupby("id_facconnier")["a_l_heure"].mean().round(3).to_string())

    f06 = livrees[livrees["id_facconnier"] == "F06"]
    avant = f06["date_promise"] < pd.Timestamp(cfg["signaux"]["chute_otif_f06"]["date_debut"])
    print(f"\nF06 à l'heure avant mars 2025 : {f06.loc[avant, 'a_l_heure'].mean():.1%}")
    print(f"F06 à l'heure après mars 2025 : {f06.loc[~avant, 'a_l_heure'].mean():.1%}")

    solaire = livrees[livrees["gamme"] == "Solaire"]
    pic = solaire["date_promise"].dt.month.isin(cfg["signaux"]["saisonnalite_solaire"]["mois"])
    print(f"\nSolaire à l'heure en mars-mai     : {solaire.loc[pic, 'a_l_heure'].mean():.1%}")
    print(f"Solaire à l'heure le reste de l'an : {solaire.loc[~pic, 'a_l_heure'].mean():.1%}")

def main() -> None:
    cfg = charger_config()
    rng = np.random.default_rng(cfg["projet"]["seed"])

    # Partie 1 : référentiels
    dim_facconnier = generer_dim_facconnier(cfg)
    dim_produit, ref_sku_facconnier = generer_produits(cfg, rng)
    dim_date = generer_dim_date(cfg)

    # Partie 2 : commandes
    fact_commande = generer_commandes(cfg, rng, dim_produit, ref_sku_facconnier)

    # Partie 3 : lots et déviations
    fact_lot = generer_lots(cfg, rng, fact_commande, dim_produit)
    fact_commande = ajouter_qte_conforme(fact_commande, fact_lot)
    fact_deviation = generer_deviations(cfg, rng, fact_lot, fact_commande)

    # Sauvegarde de la vérité terrain (données propres)
    for df, nom in [(dim_facconnier, "dim_facconnier"), (dim_produit, "dim_produit"),
                    (ref_sku_facconnier, "ref_sku_facconnier"), (dim_date, "dim_date"),
                    (fact_commande, "fact_commande"), (fact_lot, "fact_lot"),
                    (fact_deviation, "fact_deviation")]:
        sauvegarder(df, nom)

    print(f"Façonniers : {len(dim_facconnier)} | Produits : {len(dim_produit)}")
    controler_commandes(cfg, fact_commande, dim_produit)
    controler_qualite(cfg, fact_commande, fact_lot, fact_deviation, dim_produit)

    # Partie 4 : anomalies et exports « réalistes »
    commandes_sales, journal = injecter_anomalies(cfg, rng, fact_commande)
    journal.to_csv(RACINE / "data" / "reference" / "anomalies_injectees.csv",
                   index=False, encoding="utf-8-sig")

    print("\n--- Anomalies injectées ---")
    print(journal["type_anomalie"].value_counts().to_string())

    print("\n--- Fichiers exportés dans data/raw/ ---")
    exporter_facconniers(cfg, rng, commandes_sales)
    exporter_autres_sources(dim_produit, dim_facconnier, fact_lot, fact_deviation)


if __name__ == "__main__":
    main()