#!/usr/bin/env python3
"""Construit le fond de carte des départements utilisé par la page carte.html.

Résultat : donnees/geo/fond_de_carte.json

Sources géographiques (téléchargées automatiquement dans .cache/geo/) :
  - Contours administratifs 2025 d'Etalab, dérivés d'ADMIN EXPRESS (IGN),
    version généralisée à 100 m. Licence Ouverte 2.0.
    https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/
  - Natural Earth 1:10m « Admin 0 – Countries » (domaine public), pour les
    pays voisins dessinés en gris clair (simple repère visuel).

Projections, comme sur les cartes de l'Insee et de l'IGN :
  - Métropole et zoom « Paris et petite couronne » : Lambert-93 (EPSG:2154)
  - Guadeloupe et Martinique : UTM 20 Nord (EPSG:5490)
  - Guyane : UTM 22 Nord (EPSG:2972)
  - La Réunion : UTM 40 Sud (EPSG:2975)
  - Mayotte : UTM 38 Sud (EPSG:4471)

Chaque cadre (métropole, encarts d'outre-mer, zoom parisien) a ses propres
coordonnées, exprimées en kilomètres depuis le coin haut-gauche du cadre :
l'échelle graphique se calcule donc directement.

Prérequis : Python 3.9+ et Node.js (le script appelle « npx mapshaper »).
Usage : python3 outils/fond_de_carte.py
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CACHE = RACINE / ".cache" / "geo"
SORTIE = RACINE / "donnees" / "geo" / "fond_de_carte.json"
MAPSHAPER = ["npx", "--yes", "mapshaper@0.6.102"]

URL_DEPTS = ("https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/"
             "2025/geojson/departements-100m.geojson.gz")
URL_PAYS = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
            "master/geojson/ne_10m_admin_0_countries.geojson")

DROM = ["971", "972", "973", "974", "976"]
COM = ["975", "977", "978", "984", "986", "987", "988", "989"]
PETITE_COURONNE = ["75", "92", "93", "94"]
GRANDE_COURONNE = ["77", "78", "91", "95"]

# Un cadre = un petit SVG. « simplif » : tolérance de généralisation (mètres),
# adaptée à la taille d'affichage du cadre. « marge » : fraction ajoutée
# autour de l'emprise. « carre » : force un cadre carré (encarts).
CADRES = {
    "metro": {"nom": "France métropolitaine", "epsg": "EPSG:2154",
              "simplif": 600, "marge": 0.035, "carre": False,
              "contexte_lonlat": (-9.5, 39.5, 14.5, 53.5)},
    "idf": {"nom": "Paris et petite couronne", "epsg": "EPSG:2154",
            "simplif": 40, "marge": 0.08, "carre": True,
            "contexte_lonlat": None},
    "971": {"nom": "Guadeloupe", "epsg": "EPSG:5490", "simplif": 150,
            "marge": 0.08, "carre": True,
            "contexte_lonlat": (-62.6, 15.3, -60.6, 16.9)},
    "972": {"nom": "Martinique", "epsg": "EPSG:5490", "simplif": 120,
            "marge": 0.12, "carre": True,
            "contexte_lonlat": (-61.8, 13.9, -60.4, 15.3)},
    "973": {"nom": "Guyane", "epsg": "EPSG:2972", "simplif": 900,
            "marge": 0.06, "carre": True,
            "contexte_lonlat": (-56.5, 1.0, -50.0, 6.6)},
    "974": {"nom": "La Réunion", "epsg": "EPSG:2975", "simplif": 120,
            "marge": 0.1, "carre": True,
            "contexte_lonlat": None},
    "976": {"nom": "Mayotte", "epsg": "EPSG:4471", "simplif": 60,
            "marge": 0.12, "carre": True,
            "contexte_lonlat": (-45.6, -13.3, -44.7, -12.4)},
}

# Libellés de repérage (mers, pays voisins) : longitude, latitude.
REPERES = {
    "metro": [
        {"texte": "Manche", "lonlat": (-2.6, 49.75), "type": "mer"},
        {"texte": "Océan Atlantique", "lonlat": (-3.2, 45.2), "type": "mer"},
        {"texte": "Mer Méditerranée", "lonlat": (5.4, 42.3), "type": "mer"},
        {"texte": "Espagne", "lonlat": (-1.2, 42.35), "type": "pays"},
        {"texte": "Italie", "lonlat": (8.6, 44.9), "type": "pays"},
        {"texte": "Suisse", "lonlat": (7.6, 46.75), "type": "pays"},
        {"texte": "Allemagne", "lonlat": (8.6, 49.4), "type": "pays"},
        {"texte": "Belgique", "lonlat": (4.7, 50.55), "type": "pays"},
        {"texte": "Royaume-Uni", "lonlat": (-1.2, 51.05), "type": "pays"},
    ],
    "973": [
        {"texte": "Suriname", "lonlat": (-55.6, 4.1), "type": "pays"},
        {"texte": "Brésil", "lonlat": (-51.0, 2.0), "type": "pays"},
    ],
}


def telecharger(url: str, cible: Path) -> Path:
    """Télécharge une fois (avec quelques nouvelles tentatives) puis garde en cache."""
    if cible.exists() and cible.stat().st_size > 0:
        return cible
    cible.parent.mkdir(parents=True, exist_ok=True)
    print(f"Téléchargement de {url}")
    derniere_erreur = None
    for essai in range(6):
        try:
            requete = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(requete, timeout=300) as reponse:
                donnees = reponse.read()
            if url.endswith(".gz"):
                import gzip
                donnees = gzip.decompress(donnees)
            cible.write_bytes(donnees)
            return cible
        except Exception as erreur:  # réseau instable : on réessaie
            derniere_erreur = erreur
            print(f"  essai {essai + 1} échoué : {erreur}")
    raise SystemExit(f"Impossible de télécharger {url} : {derniere_erreur}")


def mapshaper(*arguments: str) -> None:
    commande = [*MAPSHAPER, *arguments, "-quiet"]
    resultat = subprocess.run(commande, capture_output=True, text=True)
    if resultat.returncode != 0:
        print(resultat.stdout, resultat.stderr, file=sys.stderr)
        raise SystemExit("mapshaper a échoué")


def lire(chemin: Path) -> dict:
    return json.loads(chemin.read_text(encoding="utf-8"))


def entites(geojson: dict) -> list[dict]:
    """Entités d'un GeoJSON, que mapshaper écrive une FeatureCollection,
    une GeometryCollection (sans attributs) ou rien du tout (découpage vide)."""
    if geojson.get("type") == "FeatureCollection":
        return [f for f in geojson.get("features", []) if f.get("geometry")]
    if geojson.get("type") == "GeometryCollection":
        return [{"type": "Feature", "properties": {}, "geometry": g}
                for g in geojson.get("geometries", []) if g]
    return []


def filtre_codes(codes: list[str]) -> str:
    return f"{json.dumps(codes)}.indexOf(code) > -1"


def anneaux(geometrie: dict):
    """Renvoie la liste des anneaux (listes de points) d'un polygone/multipolygone."""
    if geometrie is None:
        return []
    if geometrie["type"] == "Polygon":
        return list(geometrie["coordinates"])
    if geometrie["type"] == "MultiPolygon":
        return [anneau for poly in geometrie["coordinates"] for anneau in poly]
    if geometrie["type"] == "LineString":
        return [geometrie["coordinates"]]
    if geometrie["type"] == "MultiLineString":
        return list(geometrie["coordinates"])
    raise ValueError(geometrie["type"])


def emprise(geojson: dict):
    xs, ys = [], []
    for entite in geojson["features"]:
        for anneau in anneaux(entite["geometry"]):
            for x, y in anneau:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


class Repere:
    """Passe des mètres projetés aux kilomètres du cadre (origine en haut à gauche)."""

    def __init__(self, xmin: float, ymax: float):
        self.xmin, self.ymax = xmin, ymax

    def point(self, x: float, y: float) -> tuple[int, int]:
        # coordonnées en dixièmes de kilomètre (entiers) pour un arrondi exact
        return round((x - self.xmin) / 100), round((self.ymax - y) / 100)

    def chemin(self, geometrie: dict, fermer: bool = True) -> str:
        morceaux = []
        for anneau in anneaux(geometrie):
            pts = [self.point(x, y) for x, y in anneau]
            # supprime les doublons consécutifs créés par l'arrondi
            propres = [pts[0]]
            for p in pts[1:]:
                if p != propres[-1]:
                    propres.append(p)
            if fermer and len(propres) > 1 and propres[-1] == propres[0]:
                propres.pop()
            if len(propres) < (3 if fermer else 2):
                continue
            x0, y0 = propres[0]
            d = [f"M{fmt(x0)} {fmt(y0)}"]
            px, py = x0, y0
            rel = []
            for x, y in propres[1:]:
                rel.append(f"{fmt(x - px)} {fmt(y - py)}".replace(" -", "-"))
                px, py = x, y
            d.append("l" + " ".join(rel).replace(" -", "-"))
            if fermer:
                d.append("z")
            morceaux.append("".join(d))
        return "".join(morceaux)


def fmt(dixiemes: int) -> str:
    """12 -> '1.2', -5 -> '-.5', 30 -> '3'."""
    signe = "-" if dixiemes < 0 else ""
    v = abs(dixiemes)
    entier, dec = divmod(v, 10)
    if dec == 0:
        return f"{signe}{entier}"
    if entier == 0:
        return f"{signe}.{dec}"
    return f"{signe}{entier}.{dec}"


def projeter_lonlat(epsg: str, lonlat_points: list[tuple[float, float]]):
    """Projette quelques points (libellés) avec mapshaper, sans dépendance Python."""
    entree = CACHE / "_points.json"
    sortie = CACHE / "_points_proj.json"
    entree.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {"i": i},
                      "geometry": {"type": "Point", "coordinates": list(p)}}
                     for i, p in enumerate(lonlat_points)]}))
    mapshaper(str(entree), "-proj", epsg, "-o", str(sortie), "format=geojson", "force")
    res = lire(sortie)
    return [tuple(f["geometry"]["coordinates"]) for f in res["features"]]


def echelle_ronde(largeur_km: float) -> int:
    """Longueur « ronde » de l'échelle graphique, ~20 % de la largeur du cadre."""
    cible = largeur_km * 0.2
    puissance = 10 ** math.floor(math.log10(cible))
    for facteur in (5, 2, 1):
        if facteur * puissance <= cible:
            return int(facteur * puissance)
    return int(puissance)


def construire() -> None:
    depts = telecharger(URL_DEPTS, CACHE / "departements-100m.geojson")
    pays = telecharger(URL_PAYS, CACHE / "ne_10m_admin_0_countries.geojson")
    travail = CACHE / "travail"
    travail.mkdir(parents=True, exist_ok=True)

    tous = lire(depts)
    codes_metro = sorted(f["properties"]["code"] for f in tous["features"]
                         if f["properties"]["code"] not in DROM + COM)
    assert len(codes_metro) == 96, len(codes_metro)

    resultat = {
        "meta": {
            "description": "Fond de carte des 101 départements (coordonnées en km, origine en haut à gauche de chaque cadre).",
            "sources": [
                "Contours administratifs 2025, Etalab d'après IGN ADMIN EXPRESS — Licence Ouverte 2.0",
                "Natural Earth 1:10m Admin 0 — domaine public (pays voisins)",
            ],
            "genere_par": "outils/fond_de_carte.py",
        },
        "cadres": {},
        "departements": {},
    }

    for cle, cfg in CADRES.items():
        codes = codes_metro if cle == "metro" else (PETITE_COURONNE if cle == "idf" else [cle])
        poly = travail / f"{cle}_poly.json"
        pts = travail / f"{cle}_pts.json"
        mapshaper(str(depts), "-filter", filtre_codes(codes), "-proj", cfg["epsg"],
                  "-simplify", f"interval={cfg['simplif']}", "keep-shapes",
                  "-o", str(poly), "format=geojson", "precision=1", "force")
        mapshaper(str(depts), "-filter", filtre_codes(codes), "-proj", cfg["epsg"],
                  "-points", "inner", "-o", str(pts), "format=geojson", "precision=1", "force")
        geo_poly, geo_pts = lire(poly), lire(pts)

        xmin, ymin, xmax, ymax = emprise(geo_poly)
        larg, haut = xmax - xmin, ymax - ymin
        mx, my = larg * cfg["marge"], haut * cfg["marge"]
        xmin, xmax, ymin, ymax = xmin - mx, xmax + mx, ymin - my, ymax + my
        if cfg["carre"]:
            cote = max(xmax - xmin, ymax - ymin)
            cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
            xmin, xmax, ymin, ymax = cx - cote / 2, cx + cote / 2, cy - cote / 2, cy + cote / 2
        repere = Repere(xmin, ymax)
        largeur_km = (xmax - xmin) / 1000
        hauteur_km = (ymax - ymin) / 1000

        cadre = {
            "nom": cfg["nom"],
            "projection": cfg["epsg"],
            "largeur": round(largeur_km, 1),
            "hauteur": round(hauteur_km, 1),
            "echelle_km": echelle_ronde(largeur_km),
            "contexte": [],
            "reperes": [],
        }

        # Pays voisins (gris clair) découpés à l'emprise du cadre.
        if cfg["contexte_lonlat"]:
            ctx = travail / f"{cle}_contexte.json"
            lo0, la0, lo1, la1 = cfg["contexte_lonlat"]
            mapshaper(str(pays), "-filter", "ADM0_A3 != 'FRA'",
                      "-clip", f"bbox={lo0},{la0},{lo1},{la1}",
                      "-proj", cfg["epsg"],
                      "-clip", f"bbox={xmin},{ymin},{xmax},{ymax}",
                      "-simplify", f"interval={cfg['simplif'] * 1.5}", "keep-shapes",
                      "-o", str(ctx), "format=geojson", "precision=1", "force")
            for f in entites(lire(ctx)):
                d = repere.chemin(f["geometry"])
                if d:
                    cadre["contexte"].append({"pays": f["properties"].get("NAME_FR") or f["properties"].get("NAME"), "d": d})

        # Départements voisins du zoom parisien (grande couronne), en gris.
        if cle == "idf":
            ctx = travail / "idf_contexte.json"
            mapshaper(str(depts), "-filter", filtre_codes(GRANDE_COURONNE), "-proj", cfg["epsg"],
                      "-clip", f"bbox={xmin},{ymin},{xmax},{ymax}",
                      "-simplify", f"interval={cfg['simplif']}", "keep-shapes",
                      "-o", str(ctx), "format=geojson", "precision=1", "force")
            for f in entites(lire(ctx)):
                cadre["contexte"].append({"departement": f["properties"]["code"],
                                          "nom": f["properties"]["nom"],
                                          "d": repere.chemin(f["geometry"])})

        # Limites de régions (métropole) et contour du pays.
        if cle == "metro":
            reg = travail / "metro_regions.json"
            mapshaper(str(depts), "-filter", filtre_codes(codes), "-proj", cfg["epsg"],
                      "-simplify", f"interval={cfg['simplif']}", "keep-shapes",
                      "-dissolve", "region", "-innerlines",
                      "-o", str(reg), "format=geojson", "precision=1", "force")
            cadre["limites_regions"] = "".join(repere.chemin(f["geometry"], fermer=False)
                                               for f in entites(lire(reg)))
            # Emprise du zoom parisien, rappelée par un petit cadre sur la carte.
            ip = travail / "idf_emprise.json"
            mapshaper(str(depts), "-filter", filtre_codes(PETITE_COURONNE), "-proj", cfg["epsg"],
                      "-o", str(ip), "format=geojson", "precision=1", "force")
            a, b, c, e = emprise(lire(ip))
            m = 4000
            p0, p1 = repere.point(a - m, e + m), repere.point(c + m, b - m)
            cadre["rappel_zoom_idf"] = [p0[0] / 10, p0[1] / 10, (p1[0] - p0[0]) / 10, (p1[1] - p0[1]) / 10]

        # Libellés de repérage.
        if cle in REPERES:
            projetes = projeter_lonlat(cfg["epsg"], [r["lonlat"] for r in REPERES[cle]])
            for r, (x, y) in zip(REPERES[cle], projetes):
                px, py = repere.point(x, y)
                cadre["reperes"].append({"texte": r["texte"], "type": r["type"],
                                         "x": px / 10, "y": py / 10})

        resultat["cadres"][cle] = cadre

        points = {f["properties"]["code"]: f["geometry"]["coordinates"] for f in geo_pts["features"]}
        for f in geo_poly["features"]:
            code = f["properties"]["code"]
            px, py = repere.point(*points[code])
            entree = {"cadre": cle, "d": repere.chemin(f["geometry"]), "pt": [px / 10, py / 10]}
            if cle == "idf":
                resultat["departements"][code]["zoom"] = entree
            else:
                resultat["departements"][code] = {
                    "nom": f["properties"]["nom"],
                    "region": f["properties"]["region"],
                    **entree,
                }

    assert len(resultat["departements"]) == 101, len(resultat["departements"])
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps(resultat, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Écrit : {SORTIE.relative_to(RACINE)} ({SORTIE.stat().st_size / 1024:.0f} ko)")


if __name__ == "__main__":
    construire()
