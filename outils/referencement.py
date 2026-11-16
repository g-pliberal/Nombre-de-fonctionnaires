#!/usr/bin/env python3
"""Fichiers destinés aux moteurs de recherche, régénérés à partir des pages du site.

Sorties :
  sitemap.xml   plan du site : toutes les pages HTML publiées (racine et sous-dossiers),
                sauf celles marquées <meta name="robots" content="noindex"> (page 404…).
                Une nouvelle page y entre donc d'elle-même, sans rien modifier ici.
  robots.txt    autorise tout et indique l'adresse du plan du site.
  404.html      balise <base> : la page d'erreur est servie à n'importe quelle adresse
                du site, ses liens doivent donc partir de la racine du site.
  methode.html  description schema.org « Dataset » (JSON-LD), lue par Google Dataset
                Search, entre <!-- donnees-structurees:debut --> et <!-- donnees-structurees:fin -->.
                La liste des fichiers téléchargeables est reprise de la section
                « Télécharger les données » de la page, la liste des sources de
                donnees/csv/sources.csv et la date de mise à jour de donnees/site/national.js.

Ce script est lancé à la fin de outils/construire_donnees.py ; on peut aussi le lancer seul :
  python3 outils/referencement.py

Adresse du site : en cas de nom de domaine propre (fichier CNAME), changer ADRESSE_SITE
ci-dessous puis relancer construire_donnees.py et images_partage.py.
"""
from __future__ import annotations

import csv
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit

RACINE = Path(__file__).resolve().parent.parent

# Adresse publique du site, avec la barre finale (reprise par images_partage.py).
ADRESSE_SITE = "https://g-pliberal.github.io/Nombre-de-fonctionnaires/"
NOM_SITE = "Fonction publique : les chiffres"

# Dossiers qui ne contiennent pas de pages du site.
DOSSIERS_EXCLUS = {"assets", "donnees", "outils", "node_modules"}

DEBUT, FIN = "<!-- donnees-structurees:debut -->", "<!-- donnees-structurees:fin -->"
NOINDEX = re.compile(r'<meta\b[^>]*\bname="robots"[^>]*\bcontent="[^"]*\bnoindex', re.I)


class Anomalie(Exception):
    pass


def indexable(texte: str) -> bool:
    return not NOINDEX.search(texte)


def pages_publiees() -> list[Path]:
    """Pages HTML du site à déclarer aux moteurs de recherche, index.html en tête."""
    pages = []
    for p in RACINE.rglob("*.html"):
        rel = p.relative_to(RACINE)
        if rel.parts[0] in DOSSIERS_EXCLUS or any(x.startswith(".") for x in rel.parts):
            continue
        if indexable(p.read_text(encoding="utf-8")):
            pages.append(rel)
    return sorted(pages, key=lambda r: (r.as_posix() != "index.html", r.as_posix()))


def adresse(rel: Path) -> str:
    chemin = rel.as_posix()
    if rel.name == "index.html":
        chemin = chemin[: -len("index.html")]
    return ADRESSE_SITE + quote(chemin)


def ecrire(chemin: Path, contenu: str) -> None:
    if not chemin.exists() or chemin.read_text(encoding="utf-8") != contenu:
        chemin.write_text(contenu, encoding="utf-8")
        print(f"  {chemin.relative_to(RACINE)} mis à jour")


def plan_du_site(pages: list[Path]) -> str:
    lignes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lignes += [f"  <url><loc>{html.escape(adresse(p))}</loc></url>" for p in pages]
    return "\n".join(lignes + ["</urlset>", ""])


def robots() -> str:
    return f"User-agent: *\nAllow: /\n\nSitemap: {ADRESSE_SITE}sitemap.xml\n"


def maj_404() -> None:
    """La page 404 peut être servie à /un/chemin/quelconque : ses liens relatifs partent
    de la racine du site grâce à <base href>."""
    page = RACINE / "404.html"
    if not page.exists():
        return
    texte = page.read_text(encoding="utf-8")
    base = f'<base href="{urlsplit(ADRESSE_SITE).path}">'
    nouveau, n = re.subn(r'<base href="[^"]*">', base, texte, count=1)
    if not n:
        raise Anomalie("404.html : balise <base href> introuvable")
    ecrire(page, nouveau)


def texte_brut(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def date_mise_a_jour() -> str:
    js = (RACINE / "donnees" / "site" / "national.js").read_text(encoding="utf-8")
    m = re.search(r'"maj":\s*"(\d{4}-\d{2}-\d{2})"', js)
    if not m:
        raise Anomalie("donnees/site/national.js : date de mise à jour (maj) introuvable")
    return m.group(1)


def donnees_structurees(methode: str) -> dict:
    """Description schema.org Dataset de l'ensemble des données téléchargeables."""
    section = methode.split('id="telecharger"', 1)
    if len(section) != 2:
        raise Anomalie("methode.html : section « telecharger » introuvable")
    liste = re.search(r'<ul class="telechargements">(.*?)</ul>', section[1], re.S)
    if not liste:
        raise Anomalie("methode.html : liste des téléchargements introuvable")
    fichiers = []
    for li in re.findall(r"<li>(.*?)</li>", liste.group(1), re.S):
        m = re.search(r'<a href="([^"]+)"[^>]*>(.*?)</a>\s*<span>(.*)</span>', li, re.S)
        if not m:
            raise Anomalie(f"methode.html : téléchargement illisible : {li[:80]}")
        lien, nom, desc = m.group(1), texte_brut(m.group(2)), texte_brut(m.group(3))
        if not (RACINE / lien).exists():
            raise Anomalie(f"methode.html : fichier téléchargeable absent : {lien}")
        format_ = {".csv": "text/csv", ".json": "application/json", ".js": "text/javascript",
                   ".txt": "text/plain", ".md": "text/markdown"}.get(Path(lien).suffix, "application/octet-stream")
        fichiers.append({"@type": "DataDownload", "name": nom, "description": desc,
                         "encodingFormat": format_, "contentUrl": ADRESSE_SITE + lien})
    if not fichiers:
        raise Anomalie("methode.html : aucun fichier téléchargeable")

    annees = [int(a) for f in fichiers for a in re.findall(r"\b(19[4-9]\d|20[0-9]\d)\b", f["description"])]
    with open(RACINE / "donnees" / "csv" / "sources.csv", encoding="utf-8", newline="") as f:
        sources = list(csv.DictReader(f, delimiter=";"))
    producteurs = list(dict.fromkeys(s["producteur"] for s in sources))
    fondements = list(dict.fromkeys(s["page"] or s["fichier"] for s in sources if (s["page"] or s["fichier"]).startswith("http")))

    return {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": "Fonction publique en France : effectifs, masse salariale, salaires et retraites",
        "alternateName": NOM_SITE,
        "description": (
            "Données officielles sur la fonction publique en France, rassemblées et mises en forme "
            "à partir de la statistique publique (" + ", ".join(producteurs) + ") : nombre d'agents "
            "publics par versant (État, territoriale, hospitalière), par statut (fonctionnaires, "
            "contractuels, militaires) et par catégorie A, B, C, effectifs par département, "
            "masse salariale des administrations publiques depuis 1949, dépenses de personnel de "
            "l'État, des collectivités et des hôpitaux, salaires moyens, point d'indice, plus hautes "
            "rémunérations, retraites des fonctionnaires et comparaison européenne de l'emploi "
            "public. Chaque ligne indique sa source (fichier officiel exact). Fichiers CSV, "
            "séparateur point-virgule, encodage UTF-8."
        ),
        "url": ADRESSE_SITE + "methode.html#telecharger",
        "sameAs": "https://github.com/g-pliberal/Nombre-de-fonctionnaires",
        "keywords": [
            "fonction publique", "fonctionnaires", "agents publics", "emploi public", "effectifs",
            "contractuels", "catégories A B C", "masse salariale", "rémunérations", "salaires",
            "point d'indice", "retraites", "pensions", "départements", "France", "Europe",
        ],
        "inLanguage": "fr",
        "isAccessibleForFree": True,
        "license": "https://www.etalab.gouv.fr/licence-ouverte-open-licence/",
        "creditText": "Sources : " + ", ".join(producteurs) + " ; mise en forme : Parti Libéral Français.",
        "creator": {"@type": "Organization", "name": "Parti Libéral Français",
                    "url": "https://partiliberalfrancais.fr/"},
        "publisher": {"@type": "Organization", "name": "Parti Libéral Français",
                      "url": "https://partiliberalfrancais.fr/"},
        "spatialCoverage": {"@type": "Place", "name": "France"},
        "temporalCoverage": f"{min(annees)}/{max(annees)}",
        "dateModified": date_mise_a_jour(),
        "isBasedOn": fondements,
        "distribution": fichiers,
    }


def maj_methode() -> None:
    page = RACINE / "methode.html"
    texte = page.read_text(encoding="utf-8")
    contenu = json.dumps(donnees_structurees(texte), ensure_ascii=False, indent=1).replace("</", "<\\/")
    bloc = f'{DEBUT}\n<script type="application/ld+json">\n{contenu}\n</script>\n{FIN}'
    if DEBUT in texte:
        i, j = texte.index(DEBUT), texte.index(FIN) + len(FIN)
        nouveau = texte[:i] + bloc + texte[j:]
    else:
        nouveau = texte.replace("</head>", bloc + "\n</head>", 1)
    ecrire(page, nouveau)


def construire() -> None:
    """Appelé par construire_donnees.py (lève Anomalie en cas de problème)."""
    ecrire(RACINE / "sitemap.xml", plan_du_site(pages_publiees()))
    ecrire(RACINE / "robots.txt", robots())
    maj_404()
    maj_methode()


def main() -> int:
    try:
        construire()
    except Anomalie as e:
        print(f"ANOMALIE : {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
