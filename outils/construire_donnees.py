#!/usr/bin/env python3
"""Construit les fichiers de données lus par le site (donnees/site/*.js) à partir
des CSV de donnees/csv/ et du fond de carte donnees/geo/fond_de_carte.json.

Les données sont écrites sous forme de fichiers JavaScript (et non JSON) pour que
le site fonctionne aussi en ouvrant simplement index.html depuis le disque.

Le script contrôle la cohérence des données et s'arrête en cas d'anomalie.
Usage : python3 outils/construire_donnees.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CSV = RACINE / "donnees" / "csv"
SITE = RACINE / "donnees" / "site"
GEO = RACINE / "donnees" / "geo" / "fond_de_carte.json"

VERSANTS = ["fpe", "fpt", "fph"]
DROM = ["971", "972", "973", "974", "976"]


class Anomalie(Exception):
    pass


def verifier(condition: bool, message: str) -> None:
    if not condition:
        raise Anomalie(message)


def lire(nom: str) -> list[dict]:
    with open(CSV / nom, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def nombre(v: str):
    if v is None or v.strip() == "":
        return None
    x = float(v.replace(",", "."))
    return int(x) if x.is_integer() else x


def ecrire_js(nom: str, objet) -> None:
    SITE.mkdir(parents=True, exist_ok=True)
    texte = json.dumps(objet, ensure_ascii=False, separators=(",", ":"))
    contenu = ("/* Fichier généré par outils/construire_donnees.py — ne pas modifier à la main. */\n"
               "window.PLF_DONNEES = window.PLF_DONNEES || {};\n"
               f"window.PLF_DONNEES.{nom} = {texte};\n")
    (SITE / f"{nom}.js").write_text(contenu, encoding="utf-8")
    print(f"  donnees/site/{nom}.js ({len(contenu) / 1024:.0f} ko)")


def sources() -> dict:
    return {l["source_id"]: l for l in lire("sources.csv")}


def libelle_source(cat: dict, sid: str) -> str:
    s = cat[sid]
    return f"{s['producteur']}, {s['titre']}"


def millions(v: float, dec: int = 2) -> str:
    """5 848 291 -> « 5,85 millions » ; 1 407 727 -> « 1,41 million » (accord à partir de 2)."""
    return f"{v / 1e6:.{dec}f}".replace(".", ",") + (" millions" if v >= 2e6 else " million")


def fr(n: float, dec: int = 0) -> str:
    """Format français : espace fine insécable pour les milliers, virgule décimale."""
    s = f"{n:,.{dec}f}".replace(",", " ").replace(".", ",")
    return s


# --------------------------------------------------------------------------
def construire_national(cat: dict) -> dict:
    lignes = lire("effectifs_par_versant.csv")
    pop = {int(l["annee_1er_janvier"]): nombre(l["france_hors_mayotte"]) for l in lire("population_france.csv")}

    # Deux séries : « historique » (1980-1997) et « actuelle » (1996-2024).
    series = defaultdict(dict)
    interpolees = set()
    for l in lignes:
        a = int(l["annee"])
        series[l["serie"]][a] = {v: nombre(l[v]) for v in VERSANTS + ["total"]}
        if l["annee_interpolee_par_la_dgafp"] == "oui":
            interpolees.add(a)
        verifier(abs(sum(series[l["serie"]][a][v] for v in VERSANTS) - series[l["serie"]][a]["total"]) < 8000,
                 f"total incohérent {l}")
    hist, actu = series["historique"], series["actuelle"]
    verifier(min(actu) == 1996 and max(actu) >= 2024, "série actuelle incomplète")
    annees = sorted(set(hist) | set(actu))

    def colonne(serie, v):
        return [serie.get(a, {}).get(v) for a in annees]

    def taux(serie):
        # Population au 1er janvier N+1 ≈ population au 31 décembre N (date des effectifs).
        return [round(1000 * serie[a]["total"] / pop[a + 1], 2) if a in serie and pop.get(a + 1) else None for a in annees]

    E = {
        "annees": annees,
        "actuelle": {v: colonne(actu, v) for v in VERSANTS + ["total"]},
        "historique": {v: colonne(hist, v) for v in VERSANTS + ["total"]},
        "population": [pop.get(a + 1) for a in annees],
        "interpolees": sorted(interpolees),
        "series": {
            "actuelle": {
                "court": "série actuelle (DGAFP, 1996-2024)",
                "source": libelle_source(cat, "DGAFP_RA2026_EFF"),
                "champ": "emplois principaux au 31 décembre, tous statuts, France hors Mayotte, hors contrats aidés",
            },
            "historique": {
                "court": "série historique (DGAFP, 1980-1997)",
                "source": libelle_source(cat, "DGAFP_SL1980_1998"),
                "champ": "champ différent de la série actuelle (EPIC non marchands, régies et organismes financés par les collectivités, emplois secondaires des agents territoriaux, outre-mer et étranger pour l'État), hors La Poste et France Télécom",
            },
        },
    }
    a_fin = max(actu)
    tot = actu[a_fin]["total"]

    # Statuts (DGAFP, 2002-2024)
    st = defaultdict(lambda: defaultdict(dict))
    for l in lire("statuts_par_versant.csv"):
        a = int(l["annee"])
        for k in ["fonctionnaires", "contractuels", "militaires", "autres_statuts"]:
            st[l["versant"]][k][a] = nombre(l[k]) or 0
    annees_st = sorted(st["ensemble"]["fonctionnaires"])
    S = {
        "annees": annees_st,
        "versants": {v: {("autres" if k == "autres_statuts" else k): [st[v][k].get(a) for a in annees_st]
                         for k in ["fonctionnaires", "contractuels", "militaires", "autres_statuts"]}
                     for v in ["ensemble"] + VERSANTS},
        "champ": "emplois principaux au 31 décembre, France hors Mayotte, hors contrats aidés",
        "source": libelle_source(cat, "DGAFP_RA2026_EFF"),
        "interpolees": [2003],
    }
    verifier(annees_st[-1] == a_fin, "statuts : dernière année différente des effectifs")

    # Catégories (DGAFP, 2010-2024)
    ca = defaultdict(lambda: defaultdict(dict))
    for l in lire("categories_par_versant.csv"):
        a = int(l["annee"])
        for k in ["A", "B", "C", "indeterminee", "dont_A_plus"]:
            ca[l["versant"]][k][a] = nombre(l[k])
    annees_ca = sorted(ca["ensemble"]["A"])
    C = {
        "annees": annees_ca,
        "versants": {v: {("ind" if k == "indeterminee" else k): [ca[v][k].get(a) for a in annees_ca]
                         for k in ["A", "B", "C", "indeterminee", "dont_A_plus"]}
                     for v in ["ensemble"] + VERSANTS},
        "champ": "tous statuts, hors contrats aidés",
        "source": f"{libelle_source(cat, 'DGAFP_RA2026_POSTES')} ; 2010 : {libelle_source(cat, 'DGAFP_SL2021')}",
        "reperes": [{"annee": int(l["annee"]), "versant": l["versant"],
                     "A": nombre(l["part_A_pct"]), "B": nombre(l["part_B_pct"]), "C": nombre(l["part_C_pct"]),
                     "ind": nombre(l["part_indeterminee_pct"]), "source": libelle_source(cat, l["source_id"])}
                    for l in lire("categories_reperes_avant_2010.csv")],
        "noteEvolution": ("Les sauts visibles en 2011 (hôpital), 2019 (territoriale et hôpital) et 2021 (hôpital) "
                          "viennent de reclassements de métiers entiers (infirmiers, filière sociale, aides-soignants), "
                          "pas de créations d'emplois. Les niveaux 2021-2023 sont ceux de la nouvelle méthode (DSN)."),
    }

    # Taux officiel DGAFP (ETP civils pour 1 000 habitants)
    officiel = {int(l["annee"]): nombre(l["etp_civils_pour_1000_habitants"]) for l in lire("taux_administration_officiel.csv")}

    # Emploi public au sens large (2024)
    large = [{"ensemble": l["ensemble"], "composante": l["composante"], "milliers": nombre(l["effectif_milliers"])}
             for l in lire("emploi_public_au_sens_large_2024.csv")]

    i_fin = annees_st.index(a_fin)
    fonct = st["ensemble"]["fonctionnaires"][a_fin]
    contr = st["ensemble"]["contractuels"][a_fin]
    t_fin = 1000 * tot / pop[a_fin + 1]
    a_ref = 1996
    croissance = 100 * (tot / actu[a_ref]["total"] - 1)
    croissance_pop = 100 * (pop[a_fin + 1] / pop[a_ref + 1] - 1)
    a_c = 2011
    contr_c = st["ensemble"]["contractuels"][a_c]
    fonct_max_a = max(annees_st, key=lambda a: st["ensemble"]["fonctionnaires"][a])
    hors_fp = sum(x["milliers"] for x in large if x["ensemble"] != "Fonction publique")

    cles = {
        "annee": str(a_fin),
        "premiere_annee": str(annees[0]),
        "derniere_annee": str(a_fin),
        "total_millions": millions(tot),
        "total_nombre": fr(tot),
        "fonctionnaires_millions": millions(fonct),
        "fonctionnaires_part": fr(100 * fonct / tot, 0) + " %",
        "contractuels_millions": millions(contr),
        "contractuels_part": fr(100 * contr / tot, 0) + " %",
        "taux_france": fr(t_fin, 1),
        "taux_officiel": fr(officiel[a_fin], 1),
        "annee_ref": str(a_ref),
        "croissance_depuis_ref": ("+" if croissance >= 0 else "−") + fr(abs(croissance), 0) + " %",
        "croissance_pop_depuis_ref": ("+" if croissance_pop >= 0 else "−") + fr(abs(croissance_pop), 0) + " %",
        "annee_statuts": str(a_fin),
        "annee_categories": str(annees_ca[-1]),
        "contractuels_hausse": "+" + fr(100 * (contr / contr_c - 1), 0) + " %",
        "contractuels_annee_ref": str(a_c),
        "fonctionnaires_max_annee": str(fonct_max_a),
        "fonctionnaires_max_millions": millions(st["ensemble"]["fonctionnaires"][fonct_max_a]),
        "hors_fp_millions": fr(hors_fp / 1000, 1).replace(",0", "") + " million" + ("s" if hors_fp >= 2000 else ""),
        "fpe_nombre": millions(actu[a_fin]["fpe"]),
        "fpt_nombre": millions(actu[a_fin]["fpt"]),
        "fph_nombre": millions(actu[a_fin]["fph"]),
        "source_courte": "DGAFP (rapport annuel 2026), Insee",
    }
    return {
        "maj": date.today().isoformat(),
        "effectifs": E,
        "statuts": S,
        "categories": C,
        "tauxOfficiel": {"annees": sorted(officiel), "valeurs": [officiel[a] for a in sorted(officiel)],
                         "source": libelle_source(cat, "DGAFP_RA2026_POSTES")},
        "emploiPublicLarge": {"annee": 2024, "lignes": large, "source": libelle_source(cat, "DGAFP_RA2026_EFF")},
        "populationSource": libelle_source(cat, "INSEE_POP_2026"),
        "cles": cles,
    }


# --------------------------------------------------------------------------
def alertes_utiles(annee: int, texte: str) -> str:
    """Garde les avertissements propres à un département. Les ruptures générales
    (changement de source en 2009-2010) sont expliquées une fois pour toutes sur la carte."""
    gardees = []
    for morceau in (m.strip() for m in texte.split(" | ") if m.strip()):
        if morceau.startswith("Rupture 2008->2009") or morceau.startswith("Rupture 2009->2010"):
            continue
        if morceau.startswith("Rupture de localisation de la FPH en Île-de-France"):
            morceau = ("Avant 2008, une partie des agents hospitaliers de la petite couronne semble comptée à Paris : "
                       "chiffres non comparables avec les années suivantes.")
        elif morceau.startswith("Variation atypique") and annee <= 2010:
            continue
        for phrase in morceau.replace("Rupture 2009->2010 (FPE: FGE -> Siasp).", "").split(". "):
            phrase = phrase.strip().rstrip(".")
            if phrase and not phrase.startswith("Rupture 2009") and not phrase.startswith("Rupture 2008") \
                    and phrase != "Non comparable aux années suivantes" and phrase + "." not in gardees:
                gardees.append(phrase + ".")
    texte = " ".join(gardees)
    texte = (texte.replace("Variation atypique de", "Variation inhabituelle de")
             .replace("(inférence)", "(hypothèse, non confirmée par la DGAFP)")
             .replace("version 'moderne'", "nouvelle méthode")
             .replace("en version classique", "avec l'ancienne méthode"))
    return texte


def construire_departements(cat: dict, geo: dict) -> dict:
    """Effectifs civils par département (les militaires ne sont pas localisés)."""
    eff = lire("departements_effectifs.csv")
    pop = {(int(l["annee_1er_janvier"]), l["code"]): nombre(l["population"]) for l in lire("departements_population.csv")}
    annees = sorted({int(l["annee"]) for l in eff})
    ordre = lambda c: 20.1 if c == "2A" else 20.2 if c == "2B" else float(c)
    codes = sorted(geo["departements"], key=ordre)
    verifier(len(codes) == 101, "le fond de carte doit compter 101 départements")
    index = {(int(l["annee"]), l["code"]): l for l in eff}
    D = {c: {"nom": geo["departements"][c]["nom"], "population": [], "ensemble": [], "fpe": [], "fpt": [], "fph": []}
         for c in codes}
    alertes = defaultdict(dict)
    periode = {}
    for a in annees:
        for c in codes:
            l = index.get((a, c))
            # Population au 1er janvier N+1, la plus proche des effectifs au 31 décembre N.
            D[c]["population"].append(pop.get((a + 1, c)) if l else None)
            if l is None:
                for k in ["ensemble", "fpe", "fpt", "fph"]:
                    D[c][k].append(None)
                continue
            vals = {"fpe": nombre(l["fpe_civils"]), "fpt": nombre(l["fpt"]), "fph": nombre(l["fph"]),
                    "ensemble": nombre(l["total_civils"])}
            if None not in vals.values():
                # 2019 est publié arrondi à la centaine pour chaque versant et pour le total.
                tolerance = 150 if "2019" in l["version"] else 2
                verifier(abs(vals["fpe"] + vals["fpt"] + vals["fph"] - vals["ensemble"]) <= tolerance,
                         f"{a} {c} : FPE + FPT + FPH différent du total")
            verifier(D[c]["population"][-1] is not None, f"{a} {c} : population manquante")
            for k, v in vals.items():
                D[c][k].append(v)
            utiles = alertes_utiles(a, l["alerte"])
            if a == 2018 and c in ("2A", "2B"):
                utiles += (" Probablement lié à la création de la Collectivité de Corse au 1er janvier 2018 "
                           "(hypothèse, non confirmée par la DGAFP).")
            if utiles:
                alertes[c][a] = utiles
            periode[a] = l["periode_homogene"]
    for a in annees:
        i = annees.index(a)
        metro = [c for c in codes if c not in DROM]
        n = sum(1 for c in metro if D[c]["fpe"][i] is not None)
        verifier(n == 96, f"{a} : {n} départements métropolitains seulement")

    # France = somme des départements disponibles (même couverture pour effectifs et population)
    F = {k: [] for k in ["ensemble", "fpe", "fpt", "fph", "population"]}
    couverture = []
    for i, a in enumerate(annees):
        for k in ["ensemble", "fpe", "fpt", "fph"]:
            dispo = [c for c in codes if D[c][k][i] is not None]
            F[k].append(sum(D[c][k][i] for c in dispo))
        dispo = [c for c in codes if D[c]["ensemble"][i] is not None]
        F["population"].append(sum(D[c]["population"][i] for c in dispo))
        couverture.append("metropole" if not any(D[c]["fpe"][i] is not None for c in DROM) else "hors_mayotte")
    # Les totaux « France » ne sont utilisés que si tous les départements disponibles ont un total.
    debut_homogene = next(a for a in annees if periode[a].startswith("2010"))
    mayotte = {int(l["annee"]): nombre(l["emploi_public"]) for l in lire("mayotte_emploi_public.csv")}
    return {
        "annees": annees,
        "debutHomogene": debut_homogene,
        "periodes": [periode[a] for a in annees],
        "couverture": couverture,
        "departements": D,
        "france": F,
        "alertes": alertes,
        "mayotte": {"annees": sorted(mayotte), "valeurs": [mayotte[a] for a in sorted(mayotte)],
                    "texte": ("Mayotte n'est pas couverte par la source (Siasp). L'enquête Emploi de l'Insee, "
                              "non comparable, estime l'emploi public à environ {v} personnes en {a}.")},
        "champ": ("Agents civils (les militaires, environ 313 000, ne sont pas localisés par département), "
                  "emplois principaux au 31 décembre, hors contrats aidés, comptés à leur lieu de travail. "
                  "Taux : agents rapportés à la population au 1er janvier de l'année suivante."),
        "source": (f"{libelle_source(cat, 'DGAFP_RA2026_LOC')} ; {libelle_source(cat, 'DGAFP_SL2021_LOC')} ; "
                   f"{libelle_source(cat, 'DGAFP_RA2011_COMPL_DEP')} ; population : {libelle_source(cat, 'INSEE_POP_2026')}"),
        "sourceCourte": "DGAFP (rapports annuels 2011 à 2026), Insee (estimations de population)",
    }


def main() -> int:
    try:
        cat = sources()
        geo = json.loads(GEO.read_text(encoding="utf-8"))
        print("Construction des données du site :")
        national = construire_national(cat)
        ecrire_js("national", national)
        if (CSV / "departements_effectifs.csv").exists():
            dep = construire_departements(cat, geo)
            ecrire_js("departements", dep)
        ecrire_js("fond_de_carte", geo)
        print("Terminé.")
        return 0
    except Anomalie as e:
        print(f"ANOMALIE : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
