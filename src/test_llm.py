"""Test rapide de la connexion à l'API Gemini."""
import os

from dotenv import load_dotenv
from google import genai

load_dotenv()
cle = os.getenv("GEMINI_API_KEY")
if not cle:
    raise SystemExit("Clé introuvable : vérifie le fichier .env à la racine du projet.")

client = genai.Client(api_key=cle)
reponse = client.models.generate_content(
    model="gemini-flash-latest",
    contents=(
        "Classe cette déviation de fabrication cosmétique dans une seule catégorie parmi "
        "Matière, Méthode, Machine, Main-d'œuvre, Milieu, Mesure. Réponds par le mot seul. "
        "Déviation : « Panne de la mélangeuse pendant l'étape d'émulsion »"
    ),
)
print("Réponse du modèle :", reponse.text)