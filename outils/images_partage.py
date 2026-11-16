#!/usr/bin/env python3
"""Fabrique l'image de partage (Open Graph / réseaux sociaux) de chaque page du site
et ajoute dans chaque page HTML les balises qui la déclarent.

Chaque image montre le chiffre clé de la page. Les chiffres ne sont jamais saisis à la
main : ils sont lus dans les fichiers produits par outils/construire_donnees.py
(donnees/site/*.js, objet « cles »), c'est-à-dire exactement ceux affichés sur le site.
Lancer ce script après construire_donnees.py, à chaque mise à jour des données.

Sorties :
  assets/img/partage/<page>.png    une image 1200 × 630 par page
  <page>.html                      bloc de balises entre <!-- partage:debut --> et <!-- partage:fin -->

Dépendance : Pillow (pip install pillow). Le logo utilisé est assets/img/logo-plf-240.png,
version matricielle de assets/img/logo-plf.svg.

Usage : python3 outils/images_partage.py
"""
from __future__ import annotations

import csv
import html
import json
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    sys.exit("Ce script a besoin de Pillow : pip install pillow")

RACINE = Path(__file__).resolve().parent.parent
SITE = RACINE / "donnees" / "site"
POLICES = RACINE / "assets" / "fonts"
SORTIE = RACINE / "assets" / "img" / "partage"
LOGO = RACINE / "assets" / "img" / "logo-plf-240.png"

# Adresse publique du site, avec la barre finale. Les réseaux sociaux exigent une adresse
# complète pour l'image : en cas de nom de domaine propre (fichier CNAME), changer cette
# ligne puis relancer le script.
ADRESSE_SITE = "https://g-pliberal.github.io/Nombre-de-fonctionnaires/"
NOM_SITE = "Fonction publique : les chiffres"

LARGEUR, HAUTEUR = 1200, 630
MARGE = 72

# Charte graphique (assets/css/style.css)
PETROLE = (0, 51, 64)
PETROLE_CLAIR = (10, 90, 98)
TURQUOISE = (5, 193, 173)
SAFRAN = (233, 197, 61)
BLANC = (255, 255, 255)
GRIS_CLAIR = (196, 216, 220)

DEBUT, FIN = "<!-- partage:debut -->", "<!-- partage:fin -->"


class Anomalie(Exception):
    pass


# --------------------------------------------------------------------------
# Lecture des données du site
def lire_site(nom: str) -> dict:
    texte = (SITE / f"{nom}.js").read_text(encoding="utf-8")
    m = re.search(r"window\.PLF_DONNEES\.\w+\s*=\s*(\{.*\});\s*$", texte, re.S)
    if not m:
        raise Anomalie(f"donnees/site/{nom}.js : format inattendu")
    return json.loads(m.group(1))


class Cles(dict):
    """Dictionnaire des chiffres clés : une clé absente arrête le script."""

    def __init__(self, source: str, valeurs: dict):
        super().__init__(valeurs)
        self.source = source

    def __missing__(self, cle):
        raise Anomalie(f"chiffre clé « {cle} » absent de donnees/site/{self.source}.js")


def producteurs() -> list[str]:
    with open(RACINE / "donnees" / "csv" / "sources.csv", encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    # Du plus cité au moins cité ; à égalité, dans l'ordre de sources.csv (résultat stable).
    return lignes, sorted(dict.fromkeys(l["producteur"] for l in lignes), key=lambda p: -sum(l["producteur"] == p for l in lignes))


def cartes() -> dict:
    N = lire_site("national")
    M = lire_site("masse_salariale")
    R = lire_site("retraites")
    U = lire_site("europe")
    D = lire_site("departements")
    n, m, r = Cles("national", N["cles"]), Cles("masse_salariale", M["cles"]), Cles("retraites", R["cles"])
    d = Cles("departements", D["cles"])
    u = Cles("europe", U["cles"])

    def grand(texte):
        """« 5,85 millions » -> ("5,85", "millions")."""
        t = texte.split(" ", 1)
        return (t[0], t[1]) if len(t) == 2 and t[1][:1].isalpha() else (texte, "")

    E = N["effectifs"]
    i_ref = E["annees"].index(int(n["annee_ref"]))
    courbe = [(a, v) for a, v in zip(E["annees"][i_ref:], E["actuelle"]["total"][i_ref:]) if v is not None]

    lignes_sources, prods = producteurs()

    c = {}
    c["index"] = dict(
        question="Combien y a-t-il de fonctionnaires en France ?",
        valeur=grand(n["total_millions"]),
        libelle=f"d'agents publics fin {n['annee']}",
        detail=f"dont {n['fonctionnaires_millions']} de fonctionnaires au sens strict ({n['fonctionnaires_part']})",
        source="Sources : DGAFP, Insee",
    )
    c["evolution"] = dict(
        question="Comment le nombre d'agents a-t-il évolué ?",
        valeur=(n["croissance_depuis_ref"], ""),
        libelle=f"d'agents publics entre {n['annee_ref']} et {n['annee']}",
        detail=f"La population a augmenté de {n['croissance_pop_depuis_ref']} sur la même période.",
        source="Sources : DGAFP, Insee",
        courbe=courbe,
    )
    c["carte"] = dict(
        question="Où travaillent les agents publics ?",
        valeur=(d["dep_taux_france"], ""),
        libelle=f"agents publics civils pour 1 000 habitants en {d['dep_derniere_annee']}",
        detail=f"De {d['dep_taux_min']} ({d['dep_nom_min']}) à {d['dep_taux_max']} ({d['dep_nom_max']}) selon le département.",
        source="Sources : DGAFP, Insee",
    )
    c["composition"] = dict(
        question="Qui sont les agents publics ?",
        valeur=(n["fonctionnaires_part"], ""),
        libelle="des agents publics sont fonctionnaires",
        detail=(f"{n['fonctionnaires_millions']} de fonctionnaires et {n['contractuels_millions']} "
                f"de contractuels fin {n['annee_statuts']}."),
        source="Source : DGAFP",
    )
    c["masse-salariale"] = dict(
        question="Combien coûtent les agents publics ?",
        valeur=grand(m["ms_d1"]),
        libelle=f"d'euros de rémunérations publiques en {m['ms_annee']}",
        detail=f"Cotisations comprises : {m['ms_pct_pib']} du PIB, {m['ms_par_habitant']} par habitant.",
        source="Source : Insee, comptes nationaux",
    )
    c["salaires"] = dict(
        question="Combien gagnent les agents publics ?",
        valeur=(m["ms_net_fp"], ""),
        libelle=f"nets par mois en moyenne en {m['ms_annee_sal']}",
        detail=f"Temps plein, primes comprises. Dans le privé : {m['ms_net_prive']}.",
        source="Sources : DGAFP, Insee",
    )
    c["retraites"] = dict(
        question="Combien coûtent les retraites des fonctionnaires ?",
        valeur=grand(r["rt_depenses"]),
        libelle=f"d'euros de pensions versées en {r['rt_annee']}",
        detail=f"État, collectivités et hôpitaux : {r['rt_pct_pib']} du PIB.",
        source="Source : DGAFP",
    )
    c["europe"] = dict(
        question="Plus d'agents publics que nos voisins ?",
        valeur=(u["eu_fr_part"], ""),
        libelle=f"de l'emploi est dans les administrations publiques en France ({u['eu_annee']})",
        detail=f"{u['eu_de_part']} en Allemagne, {u['eu_se_part']} en Suède. France : {u['eu_fr_rang_part']}.",
        source="Sources : OCDE, Eurostat, Insee",
    )
    c["idees-recues"] = dict(
        question="Mieux payés que dans le privé ? Plus nombreux qu'avant ?",
        valeur=(m["ms_net_fp"], ""),
        libelle=f"nets par mois en moyenne dans le public, {m['ms_net_prive']} dans le privé ({m['ms_annee_sal']})",
        detail=(f"{n['croissance_depuis_ref']} d'agents publics depuis {n['annee_ref']}, "
                f"{n['croissance_pop_depuis_ref']} d'habitants : onze idées reçues face aux chiffres officiels."),
        source="Sources : Insee, DGAFP, OCDE, Eurostat",
    )
    c["methode"] = dict(
        question="Sources, définitions et limites",
        valeur=(str(len(lignes_sources)), ""),
        libelle="publications officielles citées",
        detail=", ".join(prods[:-1]) + " et " + prods[-1] + " : chaque chiffre renvoie à sa source.",
        source="Toutes les données sont téléchargeables",
    )
    return c


# --------------------------------------------------------------------------
# Dessin
def police(fichier: str, taille: int, graisse: int | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(POLICES / fichier), taille)
    if graisse is not None:
        f.set_variation_by_axes([graisse])
    return f


def jost(taille: int, graisse: int) -> ImageFont.FreeTypeFont:
    return police("jost-latin-variable.woff2", taille, graisse)


def ajuster(texte: str, fabrique, taille: int, largeur: int, mini: int):
    """Plus grande police (≤ taille) pour que le texte tienne sur une ligne."""
    while taille >= mini:
        f = fabrique(taille)
        if f.getlength(texte) <= largeur:
            return f
        taille -= 2
    raise Anomalie(f"texte trop long pour l'image : « {texte} »")


def lignes(texte: str, f, largeur: int, maxi: int) -> list[str]:
    mots, res, cour = texte.split(" "), [], ""
    for mot in mots:
        essai = (cour + " " + mot).strip()
        if f.getlength(essai) <= largeur or not cour:
            cour = essai
        else:
            res.append(cour)
            cour = mot
    res.append(cour)
    if len(res) > maxi:
        raise Anomalie(f"texte trop long pour l'image : « {texte} »")
    return res


def courbe(d: ImageDraw.ImageDraw, points, boite, k: int) -> None:
    x0, y0, x1, y1 = boite
    annees = [a for a, _ in points]
    vals = [v for _, v in points]
    vmin, vmax = min(vals), max(vals)
    marge = (vmax - vmin) * 0.1 or 1
    vmin -= marge
    vmax += marge

    def xy(a, v):
        return (x0 + (a - annees[0]) / (annees[-1] - annees[0]) * (x1 - x0),
                y1 - (v - vmin) / (vmax - vmin) * (y1 - y0))

    pts = [xy(a, v) for a, v in points]
    d.polygon(pts + [(x1, y1), (x0, y1)], fill=PETROLE_CLAIR)
    d.line(pts, fill=TURQUOISE, width=4 * k, joint="curve")
    for (x, y) in (pts[0], pts[-1]):
        d.ellipse((x - 7 * k, y - 7 * k, x + 7 * k, y + 7 * k), fill=SAFRAN)
    f = police("atkinson-hyperlegible-700.woff2", 24 * k)
    d.text((pts[0][0], y1 + 12 * k), str(annees[0]), font=f, fill=GRIS_CLAIR, anchor="lt")
    d.text((pts[-1][0], y1 + 12 * k), str(annees[-1]), font=f, fill=GRIS_CLAIR, anchor="rt")


def dessiner(c: dict) -> Image.Image:
    # Rendu à 2× puis réduction : traits et textes plus nets.
    k = 2
    im = Image.new("RGB", (LARGEUR * k, HAUTEUR * k), PETROLE)
    d = ImageDraw.Draw(im)
    # halo discret, comme l'en-tête du site
    for r, teinte in ((900, (2, 62, 76)), (620, (5, 72, 84)), (380, (8, 82, 92))):
        cx, cy = int(LARGEUR * 0.92 * k), int(HAUTEUR * 0.12 * k)
        d.ellipse((cx - r * k, cy - r * k, cx + r * k, cy + r * k), fill=teinte)

    S = lambda v: int(v * k)  # noqa: E731
    utile = LARGEUR - 2 * MARGE
    if c.get("courbe"):
        utile = 660

    # En-tête : logo + nom du site
    x = MARGE
    if LOGO.exists():
        logo = Image.open(LOGO).convert("RGBA")
        h = S(56)
        logo = logo.resize((round(logo.width * h / logo.height), h), Image.LANCZOS)
        im.paste(logo, (S(MARGE), S(52)), logo)
        x = MARGE + logo.width / k + 18
    d.text((S(x), S(52)), "Parti Libéral Français", font=jost(S(24), 600), fill=SAFRAN)
    d.text((S(x), S(82)), NOM_SITE, font=jost(S(26), 500), fill=BLANC)

    # Question (titre de la page)
    fq = ajuster(c["question"], lambda t: jost(S(t), 600), 40, S(LARGEUR - 2 * MARGE), 28)
    d.text((S(MARGE), S(185)), c["question"], font=fq, fill=TURQUOISE, anchor="ls")

    # Chiffre clé
    nombre, unite = c["valeur"]
    y_base = 355
    fv = ajuster(nombre + (" " + unite if unite else ""), lambda t: jost(S(t), 700), 150, S(utile), 80)
    d.text((S(MARGE), S(y_base)), nombre, font=fv, fill=SAFRAN, anchor="ls")
    if unite:
        fu = jost(int(fv.size * 0.52), 600)
        d.text((S(MARGE) + fv.getlength(nombre + " "), S(y_base)), unite, font=fu, fill=SAFRAN, anchor="ls")

    # Libellé et détail
    fl = ajuster(c["libelle"], lambda t: police("atkinson-hyperlegible-700.woff2", S(t)), 40, S(utile), 28)
    d.text((S(MARGE), S(y_base + 80)), c["libelle"], font=fl, fill=BLANC, anchor="ls")
    fd = police("atkinson-hyperlegible-400.woff2", S(28))
    y = y_base + 132
    for l in lignes(c["detail"], fd, S(utile), 2):
        d.text((S(MARGE), S(y)), l, font=fd, fill=GRIS_CLAIR, anchor="ls")
        y += 38

    if c.get("courbe"):
        courbe(d, c["courbe"], (S(800), S(250), S(LARGEUR - MARGE), S(470)), k)

    # Pied : source et adresse
    d.rectangle((0, S(HAUTEUR - 70), S(LARGEUR), S(HAUTEUR)), fill=(0, 36, 46))
    d.rectangle((0, S(HAUTEUR - 70), S(LARGEUR), S(HAUTEUR - 64)), fill=SAFRAN)
    fp = police("atkinson-hyperlegible-400.woff2", S(24))
    d.text((S(MARGE), S(HAUTEUR - 31)), c["source"], font=fp, fill=GRIS_CLAIR, anchor="lm")
    adresse = re.sub(r"^https?://|/$", "", ADRESSE_SITE)
    d.text((S(LARGEUR - MARGE), S(HAUTEUR - 31)), adresse, font=fp, fill=BLANC, anchor="rm")

    return im.resize((LARGEUR, HAUTEUR), Image.LANCZOS)


# --------------------------------------------------------------------------
# Balises HTML
def texte_alt(c: dict) -> str:
    nombre, unite = c["valeur"]
    v = (nombre + " " + unite).strip().replace(" ", " ")
    return f"{c['question']} {v} {c['libelle']}. {c['detail']}".replace(" ", " ")


def balises(page: str, c: dict) -> str:
    url_page = ADRESSE_SITE + ("" if page == "index" else f"{page}.html")
    url_img = ADRESSE_SITE + f"assets/img/partage/{page}.png"
    a = lambda s: html.escape(s, quote=True)  # noqa: E731
    return "\n".join([
        DEBUT,
        f'<meta property="og:site_name" content="{a(NOM_SITE)}">',
        f'<meta property="og:url" content="{a(url_page)}">',
        f'<meta property="og:image" content="{a(url_img)}">',
        '<meta property="og:image:type" content="image/png">',
        f'<meta property="og:image:width" content="{LARGEUR}">',
        f'<meta property="og:image:height" content="{HAUTEUR}">',
        f'<meta property="og:image:alt" content="{a(texte_alt(c))}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:image" content="{a(url_img)}">',
        f'<meta name="twitter:image:alt" content="{a(texte_alt(c))}">',
        FIN,
    ])


def mettre_a_jour_html(page: str, bloc: str) -> bool:
    chemin = RACINE / f"{page}.html"
    texte = chemin.read_text(encoding="utf-8")
    if DEBUT in texte:
        nouveau = re.sub(re.escape(DEBUT) + r".*?" + re.escape(FIN), lambda _: bloc, texte, count=1, flags=re.S)
    else:
        m = re.search(r'<meta property="og:locale"[^>]*>\n', texte)
        if not m:
            raise Anomalie(f"{page}.html : balise og:locale introuvable")
        nouveau = texte[:m.end()] + bloc + "\n" + texte[m.end():]
    if nouveau != texte:
        chemin.write_text(nouveau, encoding="utf-8")
        return True
    return False


def main() -> int:
    try:
        tout = cartes()
        pages = sorted(p.stem for p in RACINE.glob("*.html"))
        manquantes = set(pages) - set(tout)
        if manquantes:
            raise Anomalie(f"pas d'image de partage prévue pour : {', '.join(sorted(manquantes))}")
        SORTIE.mkdir(parents=True, exist_ok=True)
        for page in pages:
            c = tout[page]
            dessiner(c).save(SORTIE / f"{page}.png", optimize=True)
            modifie = mettre_a_jour_html(page, balises(page, c))
            print(f"  assets/img/partage/{page}.png" + ("  (balises mises à jour)" if modifie else ""))
    except Anomalie as e:
        print(f"ANOMALIE : {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
