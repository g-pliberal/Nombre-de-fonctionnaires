#!/usr/bin/env python3
"""Télécharge les fichiers officiels permettant de comparer l'emploi public en France et dans
les autres pays européens, et en extrait les CSV propres de donnees/csv/.

Sources (toutes publiques, réutilisation libre en citant la source) :
  - OCDE, Panorama des administrations publiques (« Government at a Glance »), mises à jour
    annuelles : emploi dans les administrations publiques, en milliers de personnes et en %
    de l'emploi total (jeu DF_GOV_EMPPS_REP_YU) ;
  - OCDE, comptes nationaux : emploi par sous-secteur des administrations publiques
    (administration centrale, États fédérés, administrations locales, sécurité sociale ;
    jeu DF_TABLE12_EMPDC) ;
  - Eurostat, comptes nationaux : population moyenne de l'année (jeu nama_10_pe, POP_NC) ;
  - Insee, comptes nationaux (déjà extraits par outils/extraire_masse_salariale.py) : emploi
    des administrations publiques françaises, pour le recoupement et les sous-secteurs.

Le script ne fait que lire des valeurs publiées. Il contrôle les recoupements (France OCDE
contre Insee, part publiée contre emploi publié, somme des sous-secteurs) et s'arrête en cas
d'anomalie. Les seuls calculs (taux pour 1 000 habitants, parts des sous-secteurs) sont faits
par outils/construire_donnees.py.

Usage :
    python3 outils/extraire_europe.py              # télécharge si besoin
    python3 outils/extraire_europe.py --hors-ligne # n'utilise que le cache
Les fichiers téléchargés sont conservés dans .cache/sources/ (non versionné) ; leurs
empreintes SHA-256 sont écrites dans donnees/empreintes_europe.txt.
Ensuite : python3 outils/construire_donnees.py
"""
from __future__ import annotations

import csv
import hashlib
import http.client
import json
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CSV = RACINE / "donnees" / "csv"
CACHE = RACINE / ".cache" / "sources"
EMPREINTES = RACINE / "donnees" / "empreintes_europe.txt"

OCDE = "https://sdmx.oecd.org/public/rest/data"
EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

FICHIERS = {
    "ocde/gaag_emploi_public_yu.csv": f"{OCDE}/OECD.GOV.GIP,DSD_GOV@DF_GOV_EMPPS_REP_YU,1.0/all?format=csvfile",
    "ocde/cn_emploi_sous_secteurs_apu.csv": f"{OCDE}/OECD.SDD.NAD,DSD_NASEC10@DF_TABLE12_EMPDC,1.1/all?format=csvfile",
    "eurostat/nama_10_pe_POP_NC.json":
        f"{EUROSTAT}/nama_10_pe?format=JSON&lang=fr&na_item=POP_NC&unit=THS_PER&sinceTimePeriod=2000",
}

# Pays européens (Union européenne, AELE, Royaume-Uni) : code ISO à 3 lettres (OCDE) -> code
# Eurostat. Chypre et Malte ne sont pas membres de l'OCDE et ne figurent pas dans ses tableaux ;
# le Liechtenstein non plus.
PAYS = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "HRV": "HR", "CZE": "CZ", "DNK": "DK", "EST": "EE",
    "FIN": "FI", "FRA": "FR", "DEU": "DE", "GRC": "EL", "HUN": "HU", "IRL": "IE", "ITA": "IT",
    "LVA": "LV", "LTU": "LT", "LUX": "LU", "NLD": "NL", "POL": "PL", "PRT": "PT", "ROU": "RO",
    "SVK": "SK", "SVN": "SI", "ESP": "ES", "SWE": "SE",
    "ISL": "IS", "NOR": "NO", "CHE": "CH", "GBR": "UK",
}
NOMS_HORS_EUROSTAT = {"UK": "Royaume-Uni"}
UE = {v for k, v in PAYS.items() if k not in ("ISL", "NOR", "CHE", "GBR")}
SOUS_SECTEURS = {"S1311": "Administration centrale", "S1312": "États fédérés",
                 "S1313": "Administrations locales", "S1314": "Administrations de sécurité sociale"}


class Anomalie(Exception):
    pass


def verifier(condition: bool, message: str) -> None:
    if not condition:
        raise Anomalie(message)


def telecharger(url: str, p: Path) -> None:
    derniere = None
    for essai in range(1, 7):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fonction-publique-les-chiffres/1.0",
                                                       "Accept-Language": "fr"})
            with urllib.request.urlopen(req, timeout=240) as r:
                octets = r.read()
            verifier(len(octets) > 0, f"réponse vide : {url}")
            p.write_bytes(octets)
            return
        except (OSError, http.client.HTTPException) as e:
            derniere = e
            print(f"    essai {essai} échoué ({e}) ; nouvel essai dans {3 * essai} s")
            time.sleep(3 * essai)
    raise Anomalie(f"téléchargement impossible : {url} ({derniere})")


def chemin(nom: str, hors_ligne: bool) -> Path:
    p = CACHE / nom
    if p.exists() and p.stat().st_size > 0:
        return p
    verifier(not hors_ligne, f"{nom} absent du cache (relancer sans --hors-ligne)")
    p.parent.mkdir(parents=True, exist_ok=True)
    print(f"  téléchargement de {FICHIERS[nom]}")
    telecharger(FICHIERS[nom], p)
    return p


def sdmx_csv(p: Path) -> list[dict]:
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def arrondi(v: float, dec: int = 3) -> str:
    r = round(v, dec)
    if r == int(r):
        return str(int(r))
    return f"{r:.{dec}f}".rstrip("0").rstrip(".")


def ecrire_csv(nom: str, entetes: list[str], lignes_: list[list]) -> None:
    with open(CSV / nom, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(entetes)
        for l in lignes_:
            w.writerow(["" if v is None else v for v in l])
    print(f"  donnees/csv/{nom} ({len(lignes_)} lignes)")


def insee_emploi() -> dict[str, dict[int, float]]:
    """Emploi des administrations publiques françaises (Insee, comptes nationaux), déjà extrait."""
    out: dict[str, dict[int, float]] = defaultdict(dict)
    with open(CSV / "agregats_comptes_nationaux.csv", encoding="utf-8", newline="") as f:
        for l in csv.DictReader(f, delimiter=";"):
            if l["indicateur"].startswith("emploi_S13"):
                out[l["indicateur"][len("emploi_"):]][int(l["annee"])] = float(l["valeur"])
    verifier(bool(out.get("S13")), "emploi Insee des administrations publiques introuvable")
    return out


def population(hl: bool) -> tuple[dict, dict]:
    d = json.loads(chemin("eurostat/nama_10_pe_POP_NC.json", hl).read_text(encoding="utf-8"))
    ids, taille = d["id"], d["size"]
    cats = {k: list(d["dimension"][k]["category"]["index"].keys()) for k in ids}
    noms = d["dimension"]["geo"]["category"]["label"]
    out: dict[str, dict[int, float]] = defaultdict(dict)
    for g in cats["geo"]:
        for a in cats["time"]:
            i = 0
            for k, s in zip(ids, taille):
                c = {"geo": g, "time": a}.get(k, cats[k][0])
                verifier(len(cats[k]) == 1 or k in ("geo", "time"), f"dimension inattendue {k}")
                i = i * s + cats[k].index(c)
            v = d["value"].get(str(i))
            if v is not None:
                out[g][int(a)] = float(v)
    return out, noms


def main() -> int:
    hl = "--hors-ligne" in sys.argv
    try:
        print("Extraction des données de comparaison européenne :")
        insee = insee_emploi()
        pop, noms = population(hl)
        nom = lambda c: NOMS_HORS_EUROSTAT.get(c) or noms[c]

        # 1. OCDE, Panorama des administrations publiques : emploi public et part dans l'emploi total
        L = sdmx_csv(chemin("ocde/gaag_emploi_public_yu.csv", hl))
        emp: dict[str, dict[int, float]] = defaultdict(dict)
        part: dict[str, dict[int, float]] = defaultdict(dict)
        for l in L:
            if l["MEASURE"] != "EMPG" or l["SECTOR"] != "S13" or l["REF_AREA"] not in PAYS or l["OBS_VALUE"] == "":
                continue
            verifier(l["FREQ"] == "A", f"fréquence inattendue {l['FREQ']}")
            v, a, c = float(l["OBS_VALUE"]), int(l["TIME_PERIOD"]), PAYS[l["REF_AREA"]]
            if l["UNIT_MEASURE"] == "PS":
                verifier(l["UNIT_MULT"] == "3", "unité inattendue (milliers attendus)")
                emp[c][a] = v
            elif l["UNIT_MEASURE"] == "PT_EMP":
                verifier(l["UNIT_MULT"] == "0", "unité inattendue (% attendu)")
                if v == 0:  # Suisse 2009-2010 : valeur nulle publiée = donnée manquante
                    print(f"  {c} {a} : part publiée égale à 0, ignorée (donnée manquante)")
                    continue
                verifier(3 < v < 45, f"{c} {a} : part de l'emploi public invraisemblable ({v})")
                part[c][a] = v
        verifier(set(part) >= {"FR", "DE", "IT", "ES", "SE"}, "pays manquants dans le Panorama de l'OCDE")
        # Recoupement : l'OCDE reprend pour la France l'emploi des comptes nationaux de l'Insee
        # (identique jusqu'en 2022 ; en 2023-2024, écart d'au plus 0,12 % avec les comptes publiés en 2026,
        # probablement une transmission antérieure à la révision annuelle).
        for a, v in sorted(emp["FR"].items()):
            if a in insee["S13"]:
                verifier(abs(v - insee["S13"][a]) <= 0.002 * insee["S13"][a],
                         f"France {a} : OCDE {v} ≠ Insee {insee['S13'][a]} milliers")
        # Recoupement : emploi public / part publiée = emploi total plausible (> emploi public).
        for c in part:
            for a, p in part[c].items():
                if a in emp[c]:
                    verifier(emp[c][a] / (p / 100) > emp[c][a], f"{c} {a} : incohérence part / effectif")
        out = []
        for c in sorted(set(emp) | set(part), key=nom):
            for a in sorted(set(emp[c]) | set(part[c])):
                out.append([a, c, nom(c), arrondi(emp[c][a]) if a in emp[c] else "",
                            arrondi(part[c][a], 2) if a in part[c] else "", "OCDE_GAAG_EMPLOI"])
        ecrire_csv("emploi_public_europe.csv",
                   ["annee", "code_pays", "pays", "emploi_apu_milliers", "part_emploi_total_pct", "source_id"], out)

        # 2. Population (Eurostat, comptes nationaux)
        out = []
        for c in sorted(set(PAYS.values()), key=nom):
            for a in sorted(pop.get(c, {})):
                if a >= 2007:
                    out.append([a, c, nom(c), arrondi(pop[c][a], 1), "EUROSTAT_POP_CN"])
        verifier(2024 in pop["FR"] and abs(pop["FR"][2024] - 68_600) < 1500, "population française 2024 invraisemblable")
        ecrire_csv("population_europe.csv", ["annee", "code_pays", "pays", "population_milliers", "source_id"], out)

        # 3. Sous-secteurs des administrations publiques (OCDE, comptes nationaux ; France : Insee)
        L = sdmx_csv(chemin("ocde/cn_emploi_sous_secteurs_apu.csv", hl))
        ss: dict[tuple[str, int], dict[str, float]] = defaultdict(dict)
        for l in L:
            if l["REF_AREA"] not in PAYS or l["OBS_VALUE"] == "" or l["TRANSACTION"] != "EMP":
                continue
            verifier(l["UNIT_MEASURE"] == "PS" and l["UNIT_MULT"] == "3", "unité inattendue (milliers de personnes)")
            ss[(PAYS[l["REF_AREA"]], int(l["TIME_PERIOD"]))][l["SECTOR"]] = float(l["OBS_VALUE"])
        for a in insee["S13"]:  # France : Insee (l'OCDE ne publie pas le détail)
            if all(a in insee[k] for k in ("S13111", "S13112", "S1313", "S1314")):
                ss[("FR", a)] = {"S13": insee["S13"][a], "S1311": insee["S13111"][a] + insee["S13112"][a],
                                 "S1313": insee["S1313"][a], "S1314": insee["S1314"][a], "_insee": 1}
        out = []
        for (c, a), v in sorted(ss.items(), key=lambda x: (nom(x[0][0]), x[0][1])):
            detail = {k: v[k] for k in SOUS_SECTEURS if k in v}
            if "S13" not in v or len(detail) < 2:
                continue
            somme = sum(detail.values())
            verifier(abs(somme - v["S13"]) <= 0.005 * v["S13"] + 0.2,
                     f"{c} {a} : somme des sous-secteurs {somme:.1f} ≠ total {v['S13']:.1f}")
            src = "INSEE_CN2025_PIB" if v.get("_insee") else "OCDE_CN_EMPLOI_SOUS_SECTEURS"
            out.append([a, c, nom(c), "S13", "Ensemble des administrations publiques", arrondi(v["S13"]), src])
            for k, lib in SOUS_SECTEURS.items():
                if k in detail:
                    out.append([a, c, nom(c), k, lib, arrondi(detail[k]), src])
        ecrire_csv("emploi_public_europe_sous_secteurs.csv",
                   ["annee", "code_pays", "pays", "code_secteur", "secteur", "emploi_milliers", "source_id"], out)

        lignes_ = [f"# Empreintes SHA-256 des fichiers officiels utilisés pour la comparaison européenne "
                   f"(téléchargés le {date.today().isoformat()} ; outils/extraire_europe.py)."]
        for n, url in FICHIERS.items():
            p = CACHE / n
            if p.exists():
                lignes_.append(f"  {hashlib.sha256(p.read_bytes()).hexdigest()}  {n}  <{url}>")
        EMPREINTES.write_text("\n".join(lignes_) + "\n", encoding="utf-8")
        print(f"  {EMPREINTES.relative_to(RACINE)}")
        print("Terminé. Lancer ensuite : python3 outils/construire_donnees.py")
        return 0
    except Anomalie as e:
        print(f"ANOMALIE : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
