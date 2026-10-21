"""Classification des déviations qualité par cause (méthode des 6M) avec un LLM (Google Gemini).

Le script lit les descriptions en texte libre de data/processed/fact_deviation.csv, les envoie
au modèle par paquets, et enregistre pour chaque déviation : la catégorie 6M, un niveau de
confiance et une justification courte.

Les résultats sont sauvegardés au fur et à mesure : si le script s'arrête (quota, coupure
réseau...), il suffit de le relancer, il reprend là où il s'était arrêté. Le notebook
d'évaluation relit ensuite le CSV, sans rappeler l'API.

Usage (depuis la racine du projet) :
    python src/classifier_deviations.py                  # mode zero-shot
    python src/classifier_deviations.py --mode few-shot  # avec 12 exemples annotés
    python src/classifier_deviations.py --limite 50      # essai sur 50 déviations

La clé API est lue dans le fichier .env (GEMINI_API_KEY), jamais écrite dans le code.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
PROCESSED = RACINE / "data" / "processed"
VERITE = RACINE / "data" / "reference" / "verite"

CATEGORIES = ["Matière", "Méthode", "Machine", "Main-d'œuvre", "Milieu", "Mesure"]
CONFIANCES = ["haute", "moyenne", "basse"]

CONSIGNES = """Tu es expert(e) qualité dans l'industrie cosmétique (BPF, ISO 22716).
Tu classes des déviations de fabrication selon la méthode des 6M (diagramme d'Ishikawa),
en retenant la CAUSE PREMIÈRE décrite, pas la conséquence.

Définitions :
- Matière : matières premières, excipients, articles de conditionnement (flacon, tube, étiquette
  fournie...), certificats d'analyse fournisseur, lots de matière non conformes ou en quarantaine
  utilisés à tort.
- Méthode : procédures, instructions et modes opératoires (non suivis, obsolètes, incomplets),
  ordre des étapes, temps de procédé, dossier de lot incomplet, nettoyage non appliqué.
- Machine : équipements de production (panne, dérive, fuite, usure, capteur, maintenance non faite).
- Main-d'œuvre : erreurs humaines, habilitation ou formation des opérateurs, oubli de
  vérification, erreur de saisie ou d'étiquetage manuel.
- Milieu : environnement de production (température et humidité des salles, climatisation,
  contamination de l'environnement, pression différentielle, particules, nuisibles, infiltrations).
- Mesure : instruments de mesure et contrôles qualité (étalonnage, qualification, résultat hors
  spécification, méthode analytique, échantillonnage, erreur de calcul d'analyse).

Les descriptions peuvent contenir des abréviations (MP = matière première, opé = opérateur,
fab = fabrication...), des fautes de frappe ou des mots sans accents. Les phrases de suivi ajoutées
à la fin (« Lot placé en quarantaine », « Investigation ouverte »...) décrivent la suite donnée,
pas la cause : ne t'en sers pas pour classer.

Réponds uniquement avec un tableau JSON, un objet par déviation, dans le même ordre :
[{"id": "...", "categorie": "<une des 6 catégories exactement>",
  "confiance": "haute|moyenne|basse", "justification": "<10 mots maximum>"}]"""

SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "categorie": {"type": "string", "enum": CATEGORIES},
            "confiance": {"type": "string", "enum": CONFIANCES},
            "justification": {"type": "string"},
        },
        "required": ["id", "categorie", "confiance", "justification"],
    },
}


def charger_cle():
    from dotenv import load_dotenv

    load_dotenv(RACINE / ".env")
    cle = os.getenv("GEMINI_API_KEY")
    if not cle:
        sys.exit("Clé introuvable : ajoute GEMINI_API_KEY=... dans le fichier .env à la racine du projet.")
    return cle


def choisir_exemples(n_par_categorie=2, graine=42):
    """Exemples annotés pour le mode few-shot.

    Dans un vrai projet, un expert qualité annoterait une douzaine de déviations à la main.
    Ici, on simule cet expert en tirant 2 exemples par catégorie dans la table de vérité.
    Ces exemples sont exclus de l'évaluation (voir le notebook 02).
    """
    verite = pd.read_csv(VERITE / "fact_deviation.csv")
    exemples = verite.groupby("categorie_6m_verite").sample(n_par_categorie, random_state=graine)
    exemples = exemples[["id_deviation", "description_libre", "categorie_6m_verite"]]
    exemples.to_csv(PROCESSED / "exemples_few_shot.csv", index=False, encoding="utf-8")
    return exemples


def construire_prompt(paquet, exemples=None):
    texte = CONSIGNES
    if exemples is not None:
        lignes = [f'- « {r.description_libre} » -> {r.categorie_6m_verite}' for r in exemples.itertuples()]
        texte += "\n\nExemples annotés par un expert qualité :\n" + "\n".join(lignes)
    deviations = [{"id": r.id_deviation, "description": r.description_libre} for r in paquet.itertuples()]
    texte += "\n\nDéviations à classer :\n" + json.dumps(deviations, ensure_ascii=False, indent=0)
    return texte


def appeler_llm(client, modele, prompt):
    from google.genai import types

    reponse = client.models.generate_content(
        model=modele,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_json_schema=SCHEMA,
        ),
    )
    return reponse.text


def lire_reponse(texte, ids_attendus):
    """Vérifie la réponse du modèle et ne garde que les lignes valides."""
    try:
        donnees = json.loads(texte)
    except (json.JSONDecodeError, TypeError):
        return []
    valides = []
    for d in donnees if isinstance(donnees, list) else []:
        if (isinstance(d, dict) and d.get("id") in ids_attendus
                and d.get("categorie") in CATEGORIES and d.get("confiance") in CONFIANCES):
            valides.append({"id_deviation": d["id"], "categorie_ia": d["categorie"],
                            "confiance": d["confiance"], "justification": str(d.get("justification", ""))[:200]})
    return valides


def classer(mode, modele, taille_paquet, pause, limite, appel=appeler_llm, client=None):
    deviations = pd.read_csv(PROCESSED / "fact_deviation.csv")[["id_deviation", "description_libre"]]
    exemples = choisir_exemples() if mode == "few-shot" else None
    if limite:
        deviations = deviations.head(limite)

    sortie = PROCESSED / f"deviations_classees_{mode.replace('-', '_')}.csv"
    deja = pd.read_csv(sortie) if sortie.exists() else pd.DataFrame(columns=["id_deviation"])
    a_faire = deviations[~deviations["id_deviation"].isin(deja["id_deviation"])]
    print(f"Mode {mode} | modèle {modele} | {len(deja)} déjà classées | {len(a_faire)} à classer")
    if a_faire.empty:
        print("Rien à faire : toutes les déviations sont déjà classées.")
        return sortie

    if client is None:
        from google import genai
        client = genai.Client(api_key=charger_cle())

    for debut in range(0, len(a_faire), taille_paquet):
        paquet = a_faire.iloc[debut:debut + taille_paquet]
        prompt = construire_prompt(paquet, exemples)
        resultats = []
        for tentative in range(1, 6):
            try:
                resultats = lire_reponse(appel(client, modele, prompt), set(paquet["id_deviation"]))
                break
            except Exception as erreur:  # quota (429), surcharge (503), réseau...
                message = str(erreur)
                if "429" in message and ("per day" in message.lower() or "PerDay" in message):
                    print("\nQuota journalier atteint. Les résultats sont sauvegardés : relance le script demain.")
                    return sortie
                attente = 15 * tentative
                print(f"\n  Erreur ({message[:120]}...). Nouvel essai dans {attente} s.")
                time.sleep(attente)

        if resultats:
            lignes = pd.DataFrame(resultats).assign(modele=modele, mode=mode)
            lignes.to_csv(sortie, mode="a", header=not sortie.exists(), index=False, encoding="utf-8")
        fait = min(debut + taille_paquet, len(a_faire))
        manquantes = len(paquet) - len(resultats)
        print(f"  {fait}/{len(a_faire)} traitées" + (f" ({manquantes} à reprendre)" if manquantes else ""), flush=True)
        time.sleep(pause)

    total = pd.read_csv(sortie)
    reste = len(deviations) - total["id_deviation"].isin(deviations["id_deviation"]).sum()
    print(f"\nTerminé : {len(total)} déviations dans {sortie.name}."
          + (f" {reste} n'ont pas eu de réponse valide : relance le script pour les reprendre." if reste else ""))
    return sortie


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["zero-shot", "few-shot"], default="zero-shot")
    parser.add_argument("--modele", default="gemini-flash-latest",
    help="nom du modèle Gemini (voir la liste avec client.models.list())")
    parser.add_argument("--taille-paquet", type=int, default=25)
    parser.add_argument("--pause", type=float, default=6.0, help="secondes entre deux appels (quota gratuit)")
    parser.add_argument("--limite", type=int, default=0, help="ne classer que les N premières déviations (essai)")
    args = parser.parse_args()
    classer(args.mode, args.modele, args.taille_paquet, args.pause, args.limite)
