"""Gabarits de descriptions de déviations, par catégorie Ishikawa (6M).

Vocabulaire inspiré des motifs de rappel réels openFDA
(CGMP deviations, contamination, sterility, out of specification...).
"""
import re
import unicodedata

import numpy as np

GABARITS = {
    "Matière": [
        "Matière première {mp} non conforme à la spécification ({param}) à réception",
        "Excipient {mp} contaminé, signalé par le fournisseur après utilisation",
        "Certificat d'analyse du lot fournisseur de {mp} absent ou incomplet",
        "Écart de {param} sur la matière première {mp}, hors limites du cahier des charges",
        "Présence de particules étrangères dans le fût de {mp}",
        "Article de conditionnement non conforme : {article} défectueux",
        "Lot de {mp} utilisé alors qu'il était en statut quarantaine",
        "Odeur anormale constatée sur {mp} à la pesée",
    ],
    "Méthode": [
        "Étape de {etape} réalisée hors procédure : {ecart_methode}",
        "Instruction de fabrication non suivie lors de l'étape de {etape}",
        "Temps de {etape} dépassé par rapport au dossier de lot",
        "Ordre d'introduction des phases inversé pendant l'étape de {etape}",
        "Procédure de nettoyage non appliquée entre deux campagnes",
        "Paramètre de procédé non enregistré lors de l'étape de {etape}",
        "Dossier de lot incomplet : signature manquante à l'étape de {etape}",
        "Mode opératoire obsolète utilisé pour l'étape de {etape}",
    ],
    "Machine": [
        "Panne de la {machine} pendant l'étape de {etape}",
        "Dérive de vitesse de la {machine} détectée en cours de production",
        "Fuite constatée sur la {machine}",
        "Arrêt non planifié de la {machine} suite à une alarme",
        "Maintenance préventive de la {machine} non réalisée à échéance",
        "Usure d'une pièce de la {machine} provoquant des défauts de {defaut}",
        "Défaut d'étanchéité de la {machine}",
        "Capteur de la {machine} hors service",
    ],
    "Main-d'œuvre": [
        "Opérateur non habilité affecté au poste de {etape}",
        "Erreur de saisie de l'opérateur sur la quantité de {mp}",
        "Formation de l'opérateur à la procédure de {etape} non à jour",
        "Mauvaise manipulation lors de l'étape de {etape} par un intérimaire",
        "Oubli de vérification par l'opérateur avant le lancement",
        "Port des équipements de protection non conforme en zone de fabrication",
        "Erreur d'étiquetage manuel par l'opérateur",
        "Double vérification non réalisée par le second opérateur",
    ],
    "Milieu": [
        "Température de la salle de {etape} hors limites ({valeur})",
        "Humidité relative excessive en zone de fabrication",
        "Contamination microbiologique détectée lors du contrôle d'environnement",
        "Écart de pression différentielle entre zones",
        "Comptage particulaire hors limites en salle propre",
        "Infiltration d'eau constatée dans l'atelier de {etape}",
        "Présence d'insectes signalée en zone de stockage",
        "Panne de la climatisation de la zone de {etape}",
    ],
    "Mesure": [
        "Balance de pesée hors étalonnage utilisée pour {mp}",
        "Résultat de {param} hors spécification (OOS) au contrôle qualité",
        "Instrument de mesure de {param} non qualifié",
        "Écart entre deux mesures de {param} sur le même échantillon",
        "Méthode analytique non validée utilisée pour le dosage",
        "Thermomètre de contrôle défectueux en cours de {etape}",
        "Erreur de calcul dans le rapport d'analyse du lot",
        "Échantillonnage non représentatif pour le contrôle de {param}",
    ],
}

VARIABLES = {
    "mp": ["glycérine", "parfum", "conservateur", "filtre UV", "huile minérale",
           "émulsifiant", "eau purifiée", "actif apaisant", "tensioactif", "beurre de karité"],
    "param": ["pH", "viscosité", "densité", "teneur en actif", "aspect", "odeur",
              "charge microbienne", "teneur en eau"],
    "article": ["flacon", "tube", "bouchon pompe", "étui", "notice", "étiquette"],
    "etape": ["pesée", "fabrication", "émulsion", "homogénéisation", "refroidissement",
              "remplissage", "conditionnement", "filtration"],
    "ecart_methode": ["vitesse d'agitation non respectée", "température de phase non contrôlée",
                      "durée d'homogénéisation raccourcie", "contrôle intermédiaire omis"],
    "machine": ["remplisseuse", "cuve de fabrication", "turbine d'homogénéisation",
                "machine d'étiquetage", "boucheuse", "ligne d'encartonnage", "pompe de transfert"],
    "defaut": ["remplissage", "bouchage", "étiquetage", "scellage"],
    "valeur": ["28 °C", "31 °C", "12 °C", "8 °C"],
}

CONTEXTES = [
    "Lot placé en quarantaine",
    "Investigation ouverte",
    "Impact qualité en cours d'évaluation",
    "Production arrêtée deux heures",
    "Responsable qualité informé",
    "Aucun impact sur la sécurité du consommateur identifié à ce stade",
]

# Indices trompeurs : vocabulaire d'une autre catégorie, pour rendre la classification réaliste
INDICES_CROISES = {
    "Matière": "sur le lot fournisseur",
    "Méthode": "selon le dossier de lot",
    "Machine": "après redémarrage de la ligne",
    "Main-d'œuvre": "constaté par l'opérateur",
    "Milieu": "en zone de production",
    "Mesure": "confirmé par analyse",
}

ABREVIATIONS = {
    "Matière première": "MP",
    "matière première": "MP",
    "Température": "T°",
    "température": "T°",
    "opérateur": "opé",
    "fabrication": "fab",
    "conditionnement": "condit.",
    "procédure": "proc.",
    "spécification": "spec",
    "Maintenance": "Maint.",
}

def _elision(texte: str) -> str:
    """Remplace « de » par « d' » devant une voyelle ou un h : de émulsion → d'émulsion."""
    return re.sub(r"\bde (?=[aeiouyhéèêàâîôûAEIOUYHÉÈÊ])", "d'", texte)

def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def _faute_de_frappe(texte: str, rng: np.random.Generator) -> str:
    """Inverse deux lettres voisines dans un mot de plus de 5 lettres."""
    mots = texte.split()
    candidats = [i for i, mot in enumerate(mots) if len(mot) > 5]
    if not candidats:
        return texte
    i = int(rng.choice(candidats))
    mot = mots[i]
    j = int(rng.integers(1, len(mot) - 2))
    mots[i] = mot[:j] + mot[j + 1] + mot[j] + mot[j + 2:]
    return " ".join(mots)


def generer_description(categorie: str, rng: np.random.Generator) -> str:
    gabarit = str(rng.choice(GABARITS[categorie]))
    valeurs = {cle: str(rng.choice(options)) for cle, options in VARIABLES.items()}
    texte = gabarit.format(**valeurs)
    texte = _elision(texte)

    if rng.random() < 0.5:
        texte += ". " + str(rng.choice(CONTEXTES))
    if rng.random() < 0.12:
        autre = str(rng.choice([c for c in INDICES_CROISES if c != categorie]))
        texte += f" ({INDICES_CROISES[autre]})"
    if rng.random() < 0.30:
        for long, court in ABREVIATIONS.items():
            texte = texte.replace(long, court)
    if rng.random() < 0.20:
        texte = _sans_accents(texte)
    if rng.random() < 0.15:
        texte = texte.lower()
    if rng.random() < 0.10:
        texte = _faute_de_frappe(texte, rng)
    return texte