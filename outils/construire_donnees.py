#!/usr/bin/env python3
"""Construit les fichiers de données lus par le site (donnees/site/*.js) à partir
des CSV de donnees/csv/ et du fond de carte donnees/geo/fond_de_carte.json.

Les données sont écrites sous forme de fichiers JavaScript (et non JSON) pour que
le site fonctionne aussi en ouvrant simplement index.html depuis le disque.

Il recopie aussi dans les pages HTML les chiffres calculés à partir des données
(éléments portant un attribut data-cle, descriptions portant un attribut data-modele) :
après une mise à jour des CSV, aucun chiffre n'est à corriger à la main dans les pages.

Le script contrôle la cohérence des données et s'arrête en cas d'anomalie.
Usage : python3 outils/construire_donnees.py
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CSV = RACINE / "donnees" / "csv"
SITE = RACINE / "donnees" / "site"
GEO = RACINE / "donnees" / "geo" / "fond_de_carte.json"

VERSANTS = ["fpe", "fpt", "fph"]
# Date de mise à jour des données : celle du dernier changement des fichiers sources
# (voir date_mise_a_jour), pas celle de la dernière exécution du script.
DATE_MAJ = date.today().isoformat()
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]
DROM = ["971", "972", "973", "974", "976"]


class Anomalie(Exception):
    pass


def verifier(condition: bool, message: str) -> None:
    if not condition:
        raise Anomalie(message)


def lire(nom: str) -> list[dict]:
    with open(CSV / nom, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def fichier_recent(prefixe: str) -> tuple[str, int]:
    """Fichier « prefixe_AAAA.csv » le plus récent de donnees/csv/ et son année."""
    trouves = sorted((int(m.group(1)), f.name) for f in CSV.glob(f"{prefixe}_*.csv")
                     if (m := re.fullmatch(re.escape(prefixe) + r"_(\d{4})\.csv", f.name)))
    verifier(bool(trouves), f"aucun fichier {prefixe}_AAAA.csv")
    return trouves[-1][1], trouves[-1][0]


def edition_dgafp(source_id: str) -> int:
    """DGAFP_RA2026_EFF -> 2026 (édition du rapport annuel)."""
    m = re.search(r"RA(\d{4})", source_id)
    verifier(m is not None, f"{source_id} : édition du rapport annuel introuvable")
    return int(m.group(1))


def arrondi_effectif(v: float) -> str:
    """2 061 000 -> « 2,06 millions » ; 130 300 -> « 130 000 »."""
    return millions(v) if v >= 1e6 else fr(round(v, -3))


def nombre(v: str):
    if v is None or v.strip() == "":
        return None
    x = float(v.replace(",", "."))
    return int(x) if x.is_integer() else x


def lire_js(nom: str):
    """Relit l'objet d'un fichier donnees/site/<nom>.js déjà généré (None si absent ou illisible)."""
    chemin = SITE / f"{nom}.js"
    if not chemin.exists():
        return None
    prefixe = f"window.PLF_DONNEES.{nom} = "
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if ligne.startswith(prefixe) and ligne.endswith(";"):
            try:
                return json.loads(ligne[len(prefixe):-1])
            except ValueError:
                return None
    return None


def ecrire_js(nom: str, objet) -> None:
    SITE.mkdir(parents=True, exist_ok=True)
    # Date de mise à jour : on garde celle du fichier existant si les données n'ont pas
    # changé, pour que deux constructions successives donnent exactement les mêmes
    # fichiers (construction reproductible, vérifiée par l'intégration continue).
    if isinstance(objet, dict) and "maj" in objet:
        ancien = lire_js(nom)
        if isinstance(ancien, dict) and "maj" in ancien:
            sans_date = lambda o: {k: v for k, v in o.items() if k != "maj"}
            if sans_date(ancien) == sans_date(objet):
                objet = {**objet, "maj": ancien["maj"]}
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
    a_fin = max(actu)
    # Édition du rapport DGAFP d'où vient la dernière année de la série actuelle.
    edition = edition_dgafp(next(l["source_id"] for l in lignes
                                 if l["serie"] == "actuelle" and int(l["annee"]) == a_fin))
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
                "court": f"série actuelle (DGAFP, {min(actu)}-{a_fin})",
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

    # Emploi public au sens large (fichier de l'année la plus récente)
    nom_large, a_large = fichier_recent("emploi_public_au_sens_large")
    large = [{"ensemble": l["ensemble"], "composante": l["composante"], "milliers": nombre(l["effectif_milliers"])}
             for l in lire(nom_large)]

    # Principaux employeurs (Insee, y compris contrats aidés) : page d'accueil
    nom_emp, a_emp = fichier_recent("effectifs_par_employeur")
    emp = {(l["versant"], l["employeur"]): nombre(l[f"effectif_{a_emp}"]) for l in lire(nom_emp)}
    cles_emp = {
        ("fpe", "Ministères"): "emp_fpe_ministeres",
        ("fpe", "Éducation, enseignement et recherche"): "emp_fpe_education",
        ("fpe", "Économie, finances et industrie"): "emp_fpe_economie",
        ("fpe", "Intérieur et défense"): "emp_fpe_interieur",
        ("fpe", "Logement, transports et développement durable"): "emp_fpe_logement",
        ("fpe", "Affaires sociales, santé et travail"): "emp_fpe_social",
        ("fpe", "Autres (y c. Justice)"): "emp_fpe_autres",
        ("fpe", "Établissements publics à caractère administratif"): "emp_fpe_etablissements",
        ("fpt", "Régions"): "emp_fpt_regions",
        ("fpt", "Départements"): "emp_fpt_departements",
        ("fpt", "Secteur communal"): "emp_fpt_communal",
        ("fph", "Hôpitaux"): "emp_fph_hopitaux",
        ("fph", "Établissements médico-sociaux"): "emp_fph_medico_social",
    }
    for k in cles_emp:
        verifier(emp.get(k) is not None, f"{nom_emp} : employeur {k} manquant")
    emp_fpe = next(v for (ver, lib), v in emp.items() if ver == "fpe" and lib.startswith("Fonction publique"))

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
        "source_courte": f"DGAFP (rapport annuel {edition}), Insee",
        "edition_dgafp": str(edition),
        "contractuels_millions_2016": millions(st["ensemble"]["contractuels"][2016]),
        "total_1996_actuelle": millions(actu[1996]["total"]),
        "total_1996_historique": millions(hist[1996]["total"]),
        "large_annee": str(a_large),
        # Fonction publique, contrats aidés compris (somme des deux lignes DGAFP)
        "large_fp_millions": millions(1000 * sum(l["milliers"] for l in large if l["ensemble"] == "Fonction publique")),
        "emp_annee": str(a_emp),
        **{c: arrondi_effectif(emp[k]) for k, c in cles_emp.items()},
        "emp_education_part_fpe": fr(100 * emp[("fpe", "Éducation, enseignement et recherche")] / emp_fpe, 0) + " %",
    }
    return {
        "maj": DATE_MAJ,
        "effectifs": E,
        "statuts": S,
        "categories": C,
        "tauxOfficiel": {"annees": sorted(officiel), "valeurs": [officiel[a] for a in sorted(officiel)],
                         "source": libelle_source(cat, "DGAFP_RA2026_POSTES")},
        "emploiPublicLarge": {"annee": a_large, "lignes": large, "source": libelle_source(cat, "DGAFP_RA2026_EFF")},
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

    # Chiffres cités dans les pages (préfixe dep_)
    a_fin = annees[-1]
    i_fin = len(annees) - 1
    taux_dep = {c: 1000 * D[c]["ensemble"][i_fin] / D[c]["population"][i_fin]
                for c in codes if D[c]["ensemble"][i_fin] is not None}
    c_min, c_max = min(taux_dep, key=taux_dep.get), max(taux_dep, key=taux_dep.get)
    officiel = {int(l["annee"]): nombre(l["etp_civils_pour_1000_habitants"]) for l in lire("taux_administration_officiel.csv")}
    militaires = {int(l["annee"]): nombre(l["militaires"]) for l in lire("statuts_par_versant.csv") if l["versant"] == "ensemble"}
    verifier(a_fin in officiel and a_fin in militaires, f"{a_fin} : taux officiel ou militaires manquants")
    a_may = max(mayotte)
    editions = sorted({edition_dgafp(l["source_id"]) for l in eff if re.search(r"RA\d{4}", l["source_id"])})
    cles = {
        "dep_premiere_annee": str(debut_homogene),
        "dep_derniere_annee": str(a_fin),
        "dep_annee_ancienne": str(annees[0]),
        "dep_taux_france": fr(1000 * F["ensemble"][i_fin] / F["population"][i_fin], 1),
        "dep_taux_officiel": fr(officiel[a_fin], 1),
        "dep_taux_min": fr(taux_dep[c_min]),
        "dep_nom_min": D[c_min]["nom"],
        "dep_taux_max": fr(taux_dep[c_max]),
        "dep_nom_max": D[c_max]["nom"],
        "dep_militaires": fr(round(militaires[a_fin], -3)),
        "dep_mayotte": fr(round(mayotte[a_may], -3)),
        "dep_mayotte_annee": str(a_may),
    }
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
        "champ": (f"Agents civils (les militaires, environ {cles['dep_militaires']}, ne sont pas localisés par département), "
                  "emplois principaux au 31 décembre, hors contrats aidés, comptés à leur lieu de travail. "
                  "Taux : agents rapportés à la population au 1er janvier de l'année suivante."),
        "source": (f"{libelle_source(cat, 'DGAFP_RA2026_LOC')} ; {libelle_source(cat, 'DGAFP_SL2021_LOC')} ; "
                   f"{libelle_source(cat, 'DGAFP_RA2011_COMPL_DEP')} ; population : {libelle_source(cat, 'INSEE_POP_2026')}"),
        "sourceCourte": f"DGAFP (rapports annuels {editions[0]} à {editions[-1]}), Insee (estimations de population)",
        "cles": cles,
    }


# --------------------------------------------------------------------------
# Masse salariale (comptes nationaux, DGAFP, Eurostat) : fichiers produits par
# outils/extraire_masse_salariale.py
# --------------------------------------------------------------------------
SECTEURS_CN = ["S13", "S1311", "S13111", "S13112", "S1313", "S1314"]
OPERATIONS_CN = {"D1": "remuneration_salaries_D1", "D11": "salaires_bruts_D11", "D12": "cotisations_employeurs_D12",
                 "D121": "cotisations_effectives_D121", "D122": "cotisations_imputees_D122",
                 "D291": "impots_sur_salaires_D291"}
COFOG_COURT = {"GF01": "Services généraux", "GF02": "Défense", "GF03": "Ordre et sécurité publics",
               "GF04": "Affaires économiques", "GF05": "Environnement", "GF06": "Logement, équipements collectifs",
               "GF07": "Santé", "GF08": "Culture, loisirs et cultes", "GF09": "Enseignement", "GF10": "Protection sociale"}


def milliards(v: float, dec: int = 0) -> str:
    """370,012 -> « 370 milliards » ; 11,81 -> « 11,8 milliards » (dec=1)."""
    return fr(v, dec) + " milliards"


def pct(v: float, dec: int = 1) -> str:
    return fr(v, dec) + " %"


def construire_masse_salariale(cat: dict) -> dict:
    # 1. Comptes nationaux : rémunérations par sous-secteur des administrations publiques
    cn = defaultdict(dict)
    for l in lire("masse_salariale_comptes_nationaux.csv"):
        cn[l["secteur"]][int(l["annee"])] = {k: nombre(l[c]) for k, c in OPERATIONS_CN.items()}
    annees = sorted(cn["S13"])
    verifier(annees[0] == 1949 and annees == list(range(annees[0], annees[-1] + 1)), "comptes nationaux : années manquantes")
    fin = annees[-1]
    agr = defaultdict(dict)
    for l in lire("agregats_comptes_nationaux.csv"):
        agr[l["indicateur"]][int(l["annee"])] = nombre(l["valeur"])
    for ind in ["pib", "population", "prix_consommation"]:
        verifier(all(a in agr[ind] for a in annees), f"agrégat {ind} incomplet")
    for a in annees:
        s = cn["S13"][a]
        verifier(abs(s["D11"] + s["D12"] - s["D1"]) < 0.003, f"{a} : D11 + D12 ≠ D1")
        verifier(abs(sum(cn[x][a]["D1"] for x in ("S1311", "S1313", "S1314")) - s["D1"]) < 0.005, f"{a} : sous-secteurs")

    def serie(sect, op):
        return [cn[sect][a][op] if a in cn[sect] else None for a in annees]

    def agregat(ind):
        return [agr[ind].get(a) for a in annees]

    secteurs = {s: {op: serie(s, op) for op in OPERATIONS_CN} for s in SECTEURS_CN}
    etp = {s: agregat(f"emploi_etp_{s}") for s in ["S13", "S13111", "S13112", "S1313", "S1314"]}
    emploi = {s: agregat(f"emploi_{s}") for s in ["S13", "S13111", "S13112", "S1313", "S1314"]}
    dont = defaultdict(dict)
    for l in lire("remunerations_apu_dont.csv"):
        dont[l["composante"]][int(l["annee"])] = nombre(l["remuneration_salaries_D1"])
    an_dont = sorted(dont["collectivites_locales"])

    # 2. État (titre 2), collectivités, hôpitaux (DGAFP)
    etat = defaultdict(dict)
    libelles_etat, info_etat = {}, {}
    for l in lire("depenses_personnel_etat.csv"):
        etat[l["rubrique"]][int(l["annee"])] = nombre(l["montant_milliards"])
        libelles_etat[l["rubrique"]] = l["libelle"]
        info_etat[l["rubrique"]] = (l["groupe"], int(l["niveau"]))
    an_etat = sorted(etat["total_titre2"])
    ordre_etat = list(dict.fromkeys(l["rubrique"] for l in lire("depenses_personnel_etat.csv")))
    etat_remu = defaultdict(dict)
    libelles_remu = {}
    for l in lire("remunerations_activite_etat.csv"):
        etat_remu[l["poste"]][int(l["annee"])] = nombre(l["montant_milliards"])
        libelles_remu[l["poste"]] = (l["libelle"], int(l["niveau"]))
    ordre_remu = list(dict.fromkeys(l["poste"] for l in lire("remunerations_activite_etat.csv")))
    coll = lire("depenses_personnel_collectivites.csv")
    hop = lire("charges_personnel_hopitaux.csv")

    # 3. Par fonction et comparaison européenne (Eurostat)
    fonctions = defaultdict(dict)
    infos_f = {}
    for l in lire("remunerations_par_fonction.csv"):
        fonctions[l["code_cofog"]][int(l["annee"])] = nombre(l["millions_euros"])
        infos_f[l["code_cofog"]] = (l["fonction"], int(l["niveau"]))
    an_f = sorted(fonctions["TOTAL"])
    europe = defaultdict(dict)
    noms_pays = {}
    for l in lire("remuneration_publique_europe.csv"):
        europe[l["code_pays"]][int(l["annee"])] = nombre(l["remuneration_pct_pib"])
        noms_pays[l["code_pays"]] = l["pays"]
    an_eu = sorted({a for p in europe.values() for a in p if a >= 1995})
    fr_eu = europe["FR"][fin]
    verifier(abs(fr_eu - 100 * cn["S13"][fin]["D1"] / agr["pib"][fin]) < 0.1, "Eurostat : part de la France ≠ Insee")

    # 4. Salaires (DGAFP)
    s24 = {l["population"]: l for l in lire("salaires_2024_fonction_publique.csv")}
    an_sal = int(next(iter(s24.values()))["annee"])
    deciles = lire("deciles_salaires_public_prive_2024.csv")
    decomp = lire("decomposition_salaire_fonctionnaires_2024.csv")
    pp = lire("salaires_nets_public_prive_euros_constants.csv")
    point = {int(l["annee"]): nombre(l["valeur_annuelle_indice_100_euros"]) for l in lire("point_indice.csv")}

    # Part du salaire brut versée nette aux agents (DGAFP, ensemble de la fonction publique)
    ratio_net = nombre(s24["ensemble"]["net_moyen"]) / nombre(s24["ensemble"]["brut_moyen"])
    verifier(0.75 < ratio_net < 0.85, "rapport net / brut inattendu")

    # 5. Chiffres clés (écrits aussi en toutes lettres dans les pages)
    s = cn["S13"][fin]
    pop, dep = agr["population"][fin], agr["depenses_publiques"][fin]
    prix = agr["prix_consommation"]
    net = s["D11"] * ratio_net
    cout = s["D1"] + s["D291"]
    part = lambda v: 100 * v / cout
    pct_pib = {a: 100 * cn["S13"][a]["D1"] / agr["pib"][a] for a in annees}
    a_max = max(pct_pib, key=pct_pib.get)
    reel_1949 = s["D1"] / (cn["S13"][1949]["D1"] * prix[fin] / prix[1949])
    etp_fin = agr["emploi_etp_S13"][fin]
    a_etp0 = min(a for a in agr["emploi_etp_S13"])
    cout_etp = lambda a: 1e9 * cn["S13"][a]["D1"] / (1e3 * agr["emploi_etp_S13"][a]) / 12 * prix[fin] / prix[a]
    rang = sorted([(v[fin], k) for k, v in europe.items() if fin in v and len(k) == 2 and k not in ("IS", "NO", "CH")],
                  reverse=True)
    rang_fr = [k for _, k in rang].index("FR") + 1
    f_tot = fonctions["TOTAL"][an_f[-1]]
    f_ens = fonctions["GF09"][an_f[-1]]
    f_san = fonctions["GF07"][an_f[-1]]
    e_tot = etat["total_titre2"][an_etat[-1]]
    pt_max_a = max(point, key=lambda a: point[a] / prix[a])
    pt_perte = 100 * (1 - (point[fin] / prix[fin]) / (point[pt_max_a] / prix[pt_max_a]))
    st = s24
    dfp = next(l for l in decomp if l["versant"] == "fp" and l["categorie"] == "ensemble")
    cles = {
        "ms_annee": str(fin),
        "ms_d1": milliards(s["D1"]),
        "ms_d1_long": milliards(s["D1"]) + " d'euros",
        "ms_cout_total": milliards(cout),
        "ms_d11": milliards(s["D11"]),
        "ms_d12": milliards(s["D12"]),
        "ms_d121": milliards(s["D121"]),
        "ms_d122": milliards(s["D122"]),
        "ms_d291": milliards(s["D291"], 1),
        "ms_net": milliards(round(net / 5) * 5),
        "ms_prelevements_salaries": milliards(s["D11"] - net),
        "ms_pct_pib": pct(pct_pib[fin]),
        "ms_pct_depenses": pct(100 * s["D1"] / dep),
        "ms_pct_pib_1949": pct(pct_pib[1949]),
        "ms_pct_pib_max": pct(pct_pib[a_max]),
        "ms_annee_pct_max": str(a_max),
        "ms_par_habitant": fr(round(1e9 * s["D1"] / (1e3 * pop), -1)) + " €",
        "ms_par_habitant_mois": fr(1e9 * s["D1"] / (1e3 * pop) / 12) + " €",
        "ms_par_habitant_1949": fr(round(1e9 * cn["S13"][1949]["D1"] / (1e3 * agr["population"][1949])
                                         * prix[fin] / prix[1949], -1)) + " €",
        "ms_etat_part": pct(100 * cn["S13111"][fin]["D1"] / s["D1"], 0),
        "ms_multiplie_1949": fr(reel_1949, 1),
        "ms_cout_etp_mois": fr(round(cout_etp(fin), -1)) + " €",
        "ms_cout_etp_mois_debut": fr(round(cout_etp(a_etp0), -1)) + " €",
        "ms_annee_etp_debut": str(a_etp0),
        "ms_brut_etp_mois": fr(round(1e9 * s["D11"] / (1e3 * etp_fin) / 12, -1)) + " €",
        "ms_part_net": fr(part(net), 0),
        "ms_part_prelevements": fr(part(s["D11"] - net), 0),
        "ms_part_d121": fr(part(s["D121"]), 0),
        "ms_part_d122": fr(part(s["D122"]), 0),
        "ms_part_d291": fr(part(s["D291"]), 0),
        "ms_etat_d1": milliards(cn["S13111"][fin]["D1"]),
        "ms_etat_d122": milliards(cn["S13111"][fin]["D122"]),
        "ms_apul_d1": milliards(cn["S1313"][fin]["D1"]),
        "ms_asso_d1": milliards(cn["S1314"][fin]["D1"]),
        "ms_odac_d1": milliards(cn["S13112"][fin]["D1"]),
        "ms_ratio_net": fr(100 * ratio_net, 0) + " %",
        "ms_annee_sal": str(an_sal),
        "ms_net_fp": fr(nombre(st["ensemble"]["net_moyen"])) + " €",
        "ms_brut_fp": fr(nombre(st["ensemble"]["brut_moyen"])) + " €",
        "ms_net_fpe": fr(nombre(st["fpe"]["net_moyen"])) + " €",
        "ms_net_fpt": fr(nombre(st["fpt"]["net_moyen"])) + " €",
        "ms_net_fph": fr(nombre(st["fph"]["net_moyen"])) + " €",
        "ms_median_fp": fr(nombre(st["ensemble"]["net_median"])) + " €",
        "ms_net_prive": fr(nombre(pp[-1]["secteur_prive"])) + " €",
        "ms_brut_fonctionnaire": fr(nombre(dfp["salaire_brut"])) + " €",
        "ms_net_fonctionnaire": fr(nombre(dfp["salaire_net"])) + " €",
        "ms_cot_fonctionnaire": fr(nombre(dfp["cotisations_salariales"])) + " €",
        "ms_csg_fonctionnaire": fr(nombre(dfp["csg_crds"])) + " €",
        "ms_part_primes": pct(100 * nombre(dfp["primes"]) / nombre(dfp["salaire_brut"]), 0),
        "ms_net_fp_cst": fr(nombre(pp[-1]["fonction_publique"])) + " €",
        "ms_annee_eu": str(fin),
        "ms_eu_fr": pct(fr_eu),
        "ms_eu_ue": pct(europe["EU27_2020"][fin]),
        "ms_eu_de": pct(europe["DE"][fin]),
        "ms_eu_rang": str(rang_fr),
        "ms_eu_nb": str(len(rang)),
        "ms_annee_f": str(an_f[-1]),
        "ms_f_enseignement": milliards(f_ens / 1000),
        "ms_f_enseignement_part": pct(100 * f_ens / f_tot, 0),
        "ms_f_sante": milliards(f_san / 1000),
        "ms_annee_etat": str(an_etat[-1]),
        "ms_etat_titre2": milliards(e_tot, 1),
        "ms_etat_cas": milliards(etat["cas_pensions"][an_etat[-1]], 1),
        "ms_etat_pensions": milliards(etat["pensions_versees"][an_etat[-1]], 1),
        "ms_coll": milliards(nombre(coll[-1]["ensemble"]), 1),
        "ms_hop": milliards(nombre(hop[-1]["ensemble"]), 1),
        "ms_point_annee_max": str(pt_max_a),
        "ms_point_perte": fr(pt_perte, 0) + " %",
        "ms_pop_multiplie_1949": fr(agr["population"][fin] / agr["population"][1949], 1),
        # Comptes nationaux : l'année N est provisoire, N-1 semi-définitive.
        "ms_annee_semi_def": str(fin - 1),
        "ms_coll_debut": coll[0]["annee"],
        "ms_coll_fin": coll[-1]["annee"],
        "ms_hop_debut": hop[0]["annee"],
        "ms_hop_fin": hop[-1]["annee"],
    }
    detail, carte, hautes, cles_detail = construire_detail(cat)
    cles.update(cles_detail)

    return {
        "maj": DATE_MAJ,
        "cn": {
            "annees": annees, "secteurs": secteurs,
            "pib": agregat("pib"), "population": agregat("population"), "prix": agregat("prix_consommation"),
            "depenses": agregat("depenses_publiques"), "etp": etp, "emploi": emploi,
            "statut": {str(fin - 1): "semi-définitif", str(fin): "provisoire"},
            "dont": {"annees": an_dont, "collectivites": [dont["collectivites_locales"][a] for a in an_dont],
                     "hopitaux": [dont["organismes_dependant_assurances_sociales"][a] for a in an_dont]},
            "source": libelle_source(cat, "INSEE_CN2025_APU"),
            "sourceCourte": "Insee, comptes nationaux annuels (base 2020), comptes de la Nation 2025",
            "sourcePib": libelle_source(cat, "INSEE_CN2025_PIB"),
            "sourceDepenses": libelle_source(cat, "INSEE_CN2025_DEPENSES"),
        },
        "ratioNet": {"annee": an_sal, "valeur": round(ratio_net, 5),
                     "source": libelle_source(cat, "DGAFP_RA2026_REMU")},
        "etat": {
            "annees": an_etat,
            "rubriques": [{"cle": r, "libelle": libelles_etat[r], "groupe": info_etat[r][0], "niveau": info_etat[r][1],
                           "valeurs": [etat[r].get(a) for a in an_etat]} for r in ordre_etat],
            "statuts": {"annees": sorted({a for p in etat_remu.values() for a in p}),
                        "postes": [{"cle": p, "libelle": libelles_remu[p][0], "niveau": libelles_remu[p][1],
                                    "valeurs": [etat_remu[p].get(a) for a in sorted({a for q in etat_remu.values() for a in q})]}
                                   for p in ordre_remu]},
            "source": libelle_source(cat, "DGAFP_RA2026_DEPENSES"),
        },
        "collectivites": {
            "annees": [int(l["annee"]) for l in coll],
            **{k: [nombre(l[k]) for l in coll] for k in ["regions", "departements", "communes", "groupements",
                                                          "ensemble", "depenses_totales"]},
            "notes": {l["annee"]: l["note"] for l in coll if l["note"]},
            "source": libelle_source(cat, "DGAFP_RA2026_DEPENSES"),
        },
        "hopitaux": {
            "annees": [int(l["annee"]) for l in hop],
            **{k: [nombre(l[k]) for l in hop] for k in ["remunerations_non_medical", "remunerations_medical",
                                                         "charges_sociales", "impots_taxes", "autres_charges",
                                                         "ensemble", "depenses_totales"]},
            "notes": {l["annee"]: l["note"] for l in hop if l["note"]},
            "source": libelle_source(cat, "DGAFP_RA2026_DEPENSES"),
        },
        "fonctions": {
            "annees": an_f,
            "total": [fonctions["TOTAL"].get(a) for a in an_f],
            "divisions": [{"code": c, "libelle": infos_f[c][0], "court": COFOG_COURT[c],
                           "valeurs": [fonctions[c].get(a) for a in an_f]}
                          for c in sorted(infos_f) if infos_f[c][1] == 1],
            "groupes": [{"code": c, "parent": c[:4], "libelle": infos_f[c][0],
                         "valeurs": [fonctions[c].get(a) for a in an_f]}
                        for c in sorted(infos_f) if infos_f[c][1] == 2 and any(fonctions[c].values())],
            "source": libelle_source(cat, "EUROSTAT_COFOG"),
        },
        "europe": {
            "annees": an_eu,
            "pays": [{"code": k, "libelle": noms_pays[k], "valeurs": [europe[k].get(a) for a in an_eu]}
                     for k in noms_pays if k not in ("EA19", "EA21")],
            "source": libelle_source(cat, "EUROSTAT_GOV_MAIN"),
        },
        "salaires": {
            "annee": an_sal,
            "populations": {k: {c: nombre(v[c]) for c in ["part_eqtp_pct", "brut_moyen", "net_moyen", "net_median",
                                                            "net_d1", "net_q1", "net_q3", "net_d9"]}
                            for k, v in s24.items()},
            "deciles": {k: [nombre(l[k]) for l in deciles] for k in ["fpe", "fpt", "fph", "fonction_publique", "secteur_prive"]},
            "decomposition": [{k: (nombre(l[k]) if k not in ("versant", "categorie") else l[k])
                               for k in ["versant", "categorie", "salaire_brut", "traitement_brut", "primes",
                                         "cotisations_salariales", "csg_crds", "salaire_net"]} for l in decomp],
            "publicPrive": {"annees": [int(l["annee"]) for l in pp],
                            **{k: [nombre(l[k]) for l in pp] for k in ["fonction_publique", "fpe", "fpt", "fph",
                                                                        "secteur_prive"]}},
            "source": libelle_source(cat, "DGAFP_RA2026_REMU"),
            "sourceEvol": libelle_source(cat, "DGAFP_RA2026_EVOL"),
        },
        "point": {"annees": sorted(point), "valeurs": [point[a] for a in sorted(point)],
                  "source": f"{libelle_source(cat, 'DGAFP_SL2021_POINT')} ; {libelle_source(cat, 'DGAFP_RA2026_EVOL')}"},
        "detail": detail,
        "carte": carte,
        "hautes": hautes,
        "cles": cles,
    }


# Libellés courts (graphiques) des ministères, employeurs territoriaux et filières
COURT = {
    "Éducation nationale et Jeunesse, et Enseignement supérieur et Recherche": "Éducation, recherche",
    "Éducation nationale, Jeunesse, Sports, Enseignement supérieur, Recherche et Innovation": "Éducation, recherche",
    "Intérieur et Outre-mer": "Intérieur, outre-mer", "Intérieur et Outre-Mer": "Intérieur, outre-mer",
    "Ministères économiques et financiers": "Économie et finances",
    "Transition écologique et Cohésion des territoires": "Écologie, territoires",
    "Transition écologique et Cohésion des territoires (hors DGAC*)": "Écologie (hors DGAC)",
    "Agriculture et Souveraineté alimentaire": "Agriculture", "Agriculture et alimentation": "Agriculture",
    "Services du Premier ministre": "Premier ministre", "Services du Premier Ministre": "Premier ministre",
    "Europe et Affaires étrangères": "Affaires étrangères",
    "Solidarités et santé": "dont solidarités, santé", "Travail": "dont travail",
    "Établissements communaux (CCAS, CDE, etc.)": "Établissements communaux",
    "EPCI à fiscalité propre": "Intercommunalités",
    "Autres structures intercommunales (Sivom, Sivu, syndicats mixtes)": "Syndicats intercommunaux",
    "Services départementaux d’incendie et de secours": "Incendie (SDIS)",
    "Centres de gestion et CNFPT": "Centres de gestion, CNFPT",
    "Autres collectivités locales": "Autres (régies…)",
    "Personnels de direction et personnels administratifs": "Direction, administration",
    "Personnels des services de soins": "Services de soins",
    "Personnels médico-techniques": "Médico-techniques",
    "Personnels éducatifs et sociaux": "Éducatifs et sociaux",
    "Personnels techniques et ouvriers": "Techniques et ouvriers",
    "Personnels médicaux": "Médecins",
}


def court(lib: str) -> str:
    return COURT.get(lib, lib)


def construire_detail(cat: dict) -> tuple[dict, dict, dict, dict]:
    """Détail par employeur et filière (salaires DGAFP 2024), effectifs par ministère, hautes
    rémunérations et frais de personnel des collectivités par département (OFGL 2024)."""
    src_remu = libelle_source(cat, "DGAFP_RA2026_REMU")
    groupes = defaultdict(list)
    for l in lire("salaires_par_employeur_et_filiere_2024.csv"):
        groupes[(l["versant"], l["dimension"])].append(l)
    an = int(next(iter(groupes.values()))[0]["annee"])

    def bloc(cle):
        lignes_ = groupes[cle]
        ens = next(l for l in lignes_ if l["categorie"] == "Ensemble")
        cats = [l for l in lignes_ if l["categorie"] != "Ensemble"]
        return {"categories": [l["categorie"] for l in cats], "courts": [court(l["categorie"]) for l in cats],
                "partEqtp": [nombre(l["part_eqtp_pct"]) for l in cats], "salaire": [nombre(l["salaire_net_moyen"]) for l in cats],
                "salaireEnsemble": nombre(ens["salaire_net_moyen"])}

    eff = lire("effectifs_par_ministere_2024.csv")
    an_eff = int(eff[0]["annee"])
    col_prec = next(c for c in eff[0] if c.startswith("total_") and c != "total_milliers")
    detail = {
        "annee": an,
        "ministeres": bloc(("fpe", "ministeres")), "epa": bloc(("fpe", "epa")),
        "fptEmployeurs": bloc(("fpt", "employeur")), "fptFilieres": bloc(("fpt", "filiere")),
        "fphHopitaux": bloc(("fph", "filiere_hopitaux")), "fphMedicoSocial": bloc(("fph", "filiere_medico_social")),
        "fphFilieres": bloc(("fph", "filiere")),
        "effectifs": {
            "annee": an_eff, "anneePrecedente": int(col_prec.split("_")[1]),
            "lignes": [{"libelle": l["ministere"], "court": court(l["ministere"]), "niveau": int(l["niveau"]),
                        **{k: nombre(l[f"{k}_milliers"]) for k in ["fonctionnaires", "contractuels", "militaires", "autres", "total"]},
                        "precedent": nombre(l[col_prec])} for l in eff],
            "source": libelle_source(cat, "DGAFP_RA2026_POSTES"),
        },
        "source": src_remu,
    }
    for k in ("ministeres", "epa", "fptEmployeurs", "fphHopitaux", "fphMedicoSocial", "fphFilieres"):
        b = detail[k]
        verifier(abs(sum(b["partEqtp"]) - 100) < 0.01, f"détail {k} : parts ≠ 100")

    # Hautes rémunérations
    centile = {l["versant"]: {c: nombre(l[c]) for c in ["seuil_net_mensuel", "net_moyen", "net_median"]}
               for l in lire("hautes_remunerations_dernier_centile_2024.csv")}
    profil = [{"groupe": l["groupe"], "modalite": l["modalite"], "ensemble": nombre(l["ensemble_fp_pct"]),
               "top10": nombre(l["dix_pour_cent_mieux_payes_pct"]), "top1": nombre(l["un_pour_cent_mieux_payes_pct"])}
              for l in lire("hautes_remunerations_profil_2024.csv")]
    corps = [{"niveau": int(l["niveau"]), "libelle": l["corps_ou_emploi"].replace(" dont :", ""),
              "net": nombre(l["salaire_net_moyen"]), "partAuDessus": nombre(l["part_des_agents_dans_le_dernier_centile_pct"]),
              "partCentile": nombre(l["part_du_dernier_centile_pct"])} for l in lire("hautes_remunerations_corps_2024.csv")]
    aplus = [{"niveau": int(l["niveau"]), "libelle": l["corps_ou_emploi"], "brut": nombre(l["brut_moyen"]),
              "primes": nombre(l["part_primes_pct"]), "net": nombre(l["net_moyen"]), "median": nombre(l["net_median"])}
             for l in lire("salaires_a_plus_2024.csv")]
    dix = lire("dix_plus_hautes_remunerations_2025.csv")
    synth = {l["versant"]: l for l in lire("dix_plus_hautes_remunerations_synthese_2025.csv")}
    an_dix = int(dix[0]["annee"])
    hautes = {
        "annee": an, "centile": centile, "profil": profil, "corps": corps, "aplus": aplus,
        "dix": {
            "annee": an_dix,
            "employeurs": [{"versant": l["versant"], "siren": l["siren"], "libelle": l["employeur"], "court": court(l["employeur"]),
                            "somme": nombre(l["somme_dix_plus_hautes_brutes_euros"]), "femmes": int(l["femmes"]),
                            "hommes": int(l["hommes"])} for l in dix],
            "synthese": {v: {"champ": s["champ"], "moyenne": nombre(s["moyenne_somme_dix_plus_hautes_euros"]),
                             "mensuel": nombre(s["brut_mensuel_moyen_euros"]), "femmes": nombre(s["part_femmes_pct"])}
                         for v, s in synth.items()},
        },
        "source": src_remu,
    }

    # Carte : frais de personnel des collectivités locales par département (OFGL, 2024)
    loc = lire("depenses_personnel_locales_departements_2024.csv")
    an_loc = int(loc[0]["annee"])
    popd = defaultdict(dict)
    for l in lire("departements_population.csv"):
        popd[l["code"]][int(l["annee_1er_janvier"])] = int(l["population"])
    pop_moy = {c: (p[an_loc] + p[an_loc + 1]) / 2 for c, p in popd.items()}
    verifier(len(loc) == 101 and all(l["code"] in pop_moy for l in loc), "carte : départements manquants")
    carte = {
        "annee": an_loc,
        "codes": [l["code"] for l in loc], "noms": [l["departement"] for l in loc],
        "communes": [round(nombre(l["communes_euros"])) for l in loc],
        "groupements": [round(nombre(l["groupements_fiscalite_propre_euros"])) for l in loc],
        "departement": [None if l["departement_euros"] == "" else round(nombre(l["departement_euros"])) for l in loc],
        "total": [round(nombre(l["total_euros"])) for l in loc],
        "population": [round(pop_moy[l["code"]]) for l in loc],
        "notes": {l["code"]: l["note"] for l in loc if l["note"]},
        "source": libelle_source(cat, "OFGL_COMPTES_2024"),
        "sourcePopulation": "Insee, estimations de population au 1er janvier (moyenne des 1er janvier "
                            f"{an_loc} et {an_loc + 1})",
    }
    tot = sum(carte["total"])
    hab = sum(carte["population"])
    s = centile["ensemble"]
    ph = next(c for c in corps if c["libelle"].startswith("Praticiens hospitaliers"))
    sexe = {p["modalite"]: p for p in profil if p["groupe"] == "Sexe"}
    gouv = next(a for a in aplus if a["libelle"].startswith("Corps et emplois à la décision"))
    def part_masse(b, i):  # part des salaires nets versés = effectifs EQTP x salaire moyen
        return 100 * b["partEqtp"][i] * b["salaire"][i] / sum(p * s for p, s in zip(b["partEqtp"], b["salaire"]))

    mi = detail["ministeres"]
    i_ed = next(i for i, c in enumerate(mi["categories"]) if c.startswith("Éducation"))
    fe = detail["fptEmployeurs"]
    i_co = fe["categories"].index("Communes")
    ff = detail["fptFilieres"]
    i_te = ff["categories"].index("Technique")
    fh = detail["fphHopitaux"]
    i_med = fh["categories"].index("Personnels médicaux")
    i_soi = fh["categories"].index("Personnels des services de soins")
    cles = {
        "ms_min_annee": str(an),
        "ms_min_educ_eqtp": pct(mi["partEqtp"][i_ed], 0),
        "ms_min_educ_masse": pct(part_masse(mi, i_ed), 0),
        "ms_min_educ_sal": fr(mi["salaire"][i_ed]) + " €",
        "ms_min_ens_sal": fr(mi["salaireEnsemble"]) + " €",
        "ms_fpt_communes_eqtp": pct(fe["partEqtp"][i_co], 0),
        "ms_fpt_communes_sal": fr(fe["salaire"][i_co]) + " €",
        "ms_fpt_tech_eqtp": pct(ff["partEqtp"][i_te], 0),
        "ms_fpt_tech_sal": fr(ff["salaire"][i_te]) + " €",
        "ms_fph_med_eqtp": pct(fh["partEqtp"][i_med], 0),
        "ms_fph_med": fr(fh["salaire"][i_med]) + " €",
        "ms_fph_soins": fr(fh["salaire"][i_soi]) + " €",
        "ms_eff_min_annee": str(an_eff),
        "ms_loc_annee": str(an_loc),
        "ms_loc_total": milliards(tot / 1e9, 1),
        "ms_loc_hab": fr(tot / hab) + " €",
        "ms_centile_annee": str(an),
        "ms_centile_seuil": fr(s["seuil_net_mensuel"]) + " €",
        "ms_centile_moyen": fr(s["net_moyen"]) + " €",
        "ms_centile_median": fr(s["net_median"]) + " €",
        "ms_centile_ph": pct(ph["partCentile"], 0),
        "ms_centile_hommes": pct(sexe["Hommes"]["top1"], 0),
        "ms_centile_hommes_ens": pct(sexe["Hommes"]["ensemble"], 0),
        "ms_dix_annee": str(an_dix),
        "ms_dix_fpe_mensuel": fr(nombre(synth["fpe"]["brut_mensuel_moyen_euros"])) + " €",
        "ms_dix_fpt_mensuel": fr(nombre(synth["fpt"]["brut_mensuel_moyen_euros"])) + " €",
        "ms_dix_fph_mensuel": fr(nombre(synth["fph"]["brut_mensuel_moyen_euros"])) + " €",
        "ms_gouv_net": fr(gouv["net"]) + " €",
        "ms_gouv_brut": fr(gouv["brut"]) + " €",
    }
    return detail, carte, hautes, cles


# --------------------------------------------------------------------------
# Retraites des fonctionnaires (DGAFP, rapport annuel 2026)
# --------------------------------------------------------------------------
LIB_REGIMES = {
    "fpe_civils": ("Fonctionnaires civils de l'État", "Civils de l'État"),
    "fpe_civils_et_ati": ("Fonctionnaires civils de l'État (y c. allocations temporaires d'invalidité)", "Civils de l'État"),
    "fpe_militaires": ("Militaires", "Militaires"),
    "ouvriers_etat": ("Ouvriers d'État", "Ouvriers d'État"),
    "cnracl": ("Fonctionnaires territoriaux et hospitaliers (CNRACL)", "Territoriaux et hospitaliers"),
    "cnracl_fpt": ("Fonctionnaires territoriaux (CNRACL)", "Territoriaux"),
    "cnracl_fph": ("Fonctionnaires hospitaliers (CNRACL)", "Hospitaliers"),
    "ircantec": ("Contractuels (Ircantec, retraite complémentaire)", "Contractuels (Ircantec)"),
}


def construire_retraites(cat: dict) -> dict:
    src = libelle_source(cat, "DGAFP_RA2026_RETRAITES")
    agr = defaultdict(dict)
    for l in lire("agregats_comptes_nationaux.csv"):
        agr[l["indicateur"]][int(l["annee"])] = nombre(l["valeur"])

    def tableau(nom, cle_val, *dims):
        """{(dim1, dim2…): {annee: valeur}}"""
        t = defaultdict(dict)
        for l in lire(nom):
            t[tuple(l[d] for d in dims)][int(l["annee"])] = nombre(l[cle_val])
        return t

    dep = tableau("retraites_depenses_pensions.csv", "millions_euros", "regime")
    an_dep = sorted(next(iter(dep.values())))
    fin = an_dep[-1]
    regs_dep = ["fpe_civils_et_ati", "fpe_militaires", "ouvriers_etat", "cnracl"]
    verifier(all(set(dep[(r,)]) == set(an_dep) for r in regs_dep), "retraites : années de dépenses incomplètes")
    verifier(all(a in agr["pib"] and a in agr["prix_consommation"] for a in an_dep), "retraites : PIB ou prix manquants")
    total_dep = {a: sum(dep[(r,)][a] for r in regs_dep) for a in an_dep}

    stocks = tableau("retraites_pensions_en_paiement.csv", "milliers", "regime", "droit")
    an_st = sorted(stocks[("fpe_civils", "total")])
    regs5 = ["fpe_civils", "fpe_militaires", "ouvriers_etat", "cnracl_fpt", "cnracl_fph"]
    ratio = defaultdict(dict)
    for l in lire("retraites_ratio_demographique.csv"):
        ratio[l["regime"]][int(l["annee"])] = (nombre(l["cotisants_milliers"]), nombre(l["pensionnes_milliers"]),
                                               nombre(l["ratio_publie"]))
    an_ra = sorted({a for r in ratio.values() for a in r})
    moy = tableau("retraites_pension_moyenne.csv", "euros_par_mois", "regime", "droit")
    an_moy = sorted(moy[("fpe_civils", "ensemble")])
    car = defaultdict(lambda: defaultdict(dict))
    an_car = None
    for l in lire("retraites_caracteristiques_2025.csv"):
        car[l["regime"]][l["droit"]][l["indicateur"]] = nombre(l["valeur"])
        an_car = int(l["annee"])
    taux = tableau("retraites_taux_cotisation.csv", "taux_pct", "regime", "taux")
    an_tx = sorted(taux[("pcmr", "salarie")])
    cas = defaultdict(dict)
    lib_cas = {}
    for l in lire("retraites_cas_pensions.csv"):
        cas[(l["sens"], l["poste"])][int(l["annee"])] = nombre(l["millions_euros"])
        lib_cas[(l["sens"], l["poste"])] = l["libelle"]
    an_cas = sorted(cas[("depense", "total")])
    cn = defaultdict(dict)
    lib_cn = {}
    for l in lire("retraites_cnracl_compte.csv"):
        cn[(l["sens"], l["poste"])][int(l["annee"])] = nombre(l["millions_euros"])
        lib_cn[(l["sens"], l["poste"])] = l["libelle"]
    an_cn = sorted(cn[("resultat", "resultat")])
    flux = tableau("retraites_nouvelles_pensions.csv", "milliers", "regime", "droit")
    an_fl = sorted(flux[("fpe_civils", "direct")])
    age = tableau("retraites_age_depart.csv", "age_moyen", "motif")
    an_age = sorted(age[("ensemble",)])

    def suite(d, annees):
        return [d.get(a) for a in annees]

    prix = agr["prix_consommation"]
    cst = lambda v, a: v * prix[fin] / prix[a]
    a0 = an_dep[0]
    etat_fin = dep[("fpe_civils_et_ati",)][fin] + dep[("fpe_militaires",)][fin]
    tot_st = sum(stocks[(r, "total")][fin] for r in regs5)
    tot_dd = sum(stocks[(r, "direct")][fin] for r in regs5)
    r_ = lambda reg, a: ratio[reg][a][0] / ratio[reg][a][1]
    cnracl_ratio = lambda a: ((ratio["cnracl_fpt"][a][0] + ratio["cnracl_fph"][a][0])
                              / (ratio["cnracl_fpt"][a][1] + ratio["cnracl_fph"][a][1]))
    a_civ0 = min(a for a in an_ra if ratio["fpe_civils"].get(a, (None,))[0] is not None)
    nouveaux = sum(flux[(r, "direct")][fin] for r in regs5)
    cles = {
        "rt_annee": str(fin),
        "rt_depenses": milliards(total_dep[fin] / 1000, 1),
        "rt_depenses_etat": milliards(etat_fin / 1000, 1),
        "rt_depenses_civils": milliards(dep[("fpe_civils_et_ati",)][fin] / 1000, 1),
        "rt_depenses_militaires": milliards(dep[("fpe_militaires",)][fin] / 1000, 1),
        "rt_depenses_ouvriers": milliards(dep[("ouvriers_etat",)][fin] / 1000, 1),
        "rt_depenses_cnracl": milliards(dep[("cnracl",)][fin] / 1000, 1),
        "rt_pct_pib": pct(100 * total_dep[fin] / 1000 / agr["pib"][fin]),
        "rt_pct_pib_debut": pct(100 * total_dep[a0] / 1000 / agr["pib"][a0]),
        "rt_annee_debut": str(a0),
        "rt_multiplie": fr(total_dep[fin] / cst(total_dep[a0], a0), 1),
        "rt_pensions": millions(1000 * tot_st),
        "rt_pensions_direct": millions(1000 * tot_dd),
        "rt_ratio_civils": fr(r_("fpe_civils", fin), 2),
        "rt_ratio_civils_debut": fr(r_("fpe_civils", a_civ0), 2),
        "rt_annee_ratio_civils": str(a_civ0),
        "rt_ratio_cnracl": fr(cnracl_ratio(fin), 2),
        "rt_ratio_cnracl_debut": fr(cnracl_ratio(a0), 2),
        "rt_ratio_fpt": fr(r_("cnracl_fpt", fin), 2),
        "rt_ratio_fph": fr(r_("cnracl_fph", fin), 2),
        "rt_annee_car": str(an_car),
        **{f"rt_pension_{k}": fr(car[r]["direct"]["pension_mensuelle_moyenne_euros"]) + " €"
           for k, r in [("civils", "fpe_civils"), ("militaires", "fpe_militaires"), ("ouvriers", "ouvriers_etat"),
                        ("fpt", "cnracl_fpt"), ("fph", "cnracl_fph")]},
        "rt_age_civils": fr(car["fpe_civils"]["direct"]["age_premiere_mise_en_paiement"], 1) + " ans",
        "rt_taux_etat": pct(taux[("pcmr", "employeur_civils_ministeres")][fin], 2),
        "rt_taux_militaires": pct(taux[("pcmr", "employeur_militaires")][fin], 2),
        "rt_taux_cnracl": pct(taux[("cnracl", "employeur")][fin], 2),
        "rt_taux_ouvriers": pct(taux[("ouvriers_etat", "employeur")][fin], 2),
        "rt_taux_salarie": pct(taux[("pcmr", "salarie")][fin], 2),
        "rt_taux_salarie_debut": pct(taux[("pcmr", "salarie")][an_tx[0]], 2),
        "rt_cas_depenses": milliards(cas[("depense", "total")][an_cas[-1]] / 1000, 1),
        "rt_cas_recettes": milliards(cas[("recette", "total")][an_cas[-1]] / 1000, 1),
        "rt_cas_etat": milliards(cas[("recette", "contribution_etat_employeur")][an_cas[-1]] / 1000, 1),
        "rt_cas_salaries": milliards(cas[("recette", "cotisations_salariales")][an_cas[-1]] / 1000, 1),
        "rt_cnracl_resultat": fr(cn[("resultat", "resultat")][an_cn[-1]] / 1000, 1).replace("-", "−") + " milliards",
        "rt_cnracl_prestations": milliards(cn[("charge", "prestations")][an_cn[-1]] / 1000, 1),
        "rt_cnracl_cotisations": milliards(cn[("produit", "cotisations_et_produits_affectes")][an_cn[-1]] / 1000, 1),
        "rt_nouveaux": fr(round(1000 * nouveaux, -2)),
        "rt_ircantec": fr(round(1000 * flux[("ircantec", "direct")][fin], -2)),
        "rt_age_depart": fr(age[("ensemble",)][an_age[-1]], 1) + " ans",
        "rt_age_depart_debut": fr(age[("ensemble",)][an_age[0]], 1) + " ans",
        "rt_annee_age_debut": str(an_age[0]),
    }
    return {
        "maj": DATE_MAJ,
        "annees": an_dep, "pib": suite(agr["pib"], an_dep), "prix": suite(prix, an_dep),
        "regimes": {k: {"libelle": v[0], "court": v[1]} for k, v in LIB_REGIMES.items()},
        "depenses": {"annees": an_dep, "series": {r: suite(dep[(r,)], an_dep) for r in regs_dep}},
        "stocks": {"annees": an_st, "series": {r: {d: suite(stocks[(r, d)], an_st) for d in ("total", "direct", "derive")}
                                               for r in regs5}},
        "ratio": {"annees": an_ra, "series": {r: {"cotisants": [ratio[r].get(a, (None,) * 3)[0] for a in an_ra],
                                                  "pensionnes": [ratio[r].get(a, (None,) * 3)[1] for a in an_ra],
                                                  "publie": [ratio[r].get(a, (None,) * 3)[2] for a in an_ra]} for r in regs5}},
        "pensionMoyenne": {"annees": an_moy, "series": {r: {d: suite(moy[(r, d)], an_moy) for d in ("ensemble", "direct", "derive")}
                                                         for r in regs5}},
        "caracteristiques": {"annee": an_car, "regimes": {r: {d: dict(v) for d, v in car[r].items()} for r in regs5}},
        "taux": {"annees": an_tx, "series": [{"regime": k[0], "taux": k[1], "valeurs": suite(v, an_tx)} for k, v in taux.items()]},
        "cas": {"annees": an_cas, "postes": [{"sens": k[0], "poste": k[1], "libelle": lib_cas[k], "valeurs": suite(v, an_cas)}
                                             for k, v in cas.items()]},
        "cnracl": {"annees": an_cn, "postes": [{"sens": k[0], "poste": k[1], "libelle": lib_cn[k], "valeurs": suite(v, an_cn)}
                                              for k, v in cn.items()]},
        "flux": {"annees": an_fl, "series": {r: {d: suite(flux[(r, d)], an_fl) for d in ("total", "direct", "derive")}
                                             for r in regs5},
                 "ircantec": suite(flux[("ircantec", "direct")], an_fl)},
        "age": {"annees": an_age, "series": {m: suite(age[(m,)], an_age) for m in ("sedentaire", "actif", "carriere_longue", "ensemble")}},
        "source": src,
        "sourcePib": libelle_source(cat, "INSEE_CN2025_PIB"),
        "cles": cles,
    }


def date_mise_a_jour() -> tuple[str, str]:
    """Garde la date de mise à jour précédente tant que les fichiers sources n'ont pas changé.
    Renvoie (date ISO, empreinte des fichiers sources)."""
    h = hashlib.sha256()
    for f in sorted(CSV.glob("*.csv")) + [GEO]:
        h.update(f.name.encode() + b"\0" + f.read_bytes() + b"\0")
    empreinte = h.hexdigest()
    precedent = lire_js("national") or {}
    if precedent.get("maj") and precedent.get("empreinteSources") in (None, empreinte):
        return precedent["maj"], empreinte
    return date.today().isoformat(), empreinte


def rendu_html(valeur: str, attributs: str) -> str:
    """Même rendu que remplirCles() côté navigateur : dans un chiffre clé, l'unité
    (« millions », « milliards ») est affichée plus petite."""
    m = re.fullmatch(r"(.+?)\s(milliards?|millions?)", valeur)
    if m and re.search(r'class="[^"]*\bchiffre__valeur\b', attributs):
        return f'{html.escape(m.group(1), quote=False)} <span class="chiffre__unite">{m.group(2)}</span>'
    return html.escape(valeur, quote=False)


def mettre_a_jour_pages(cles: dict) -> None:
    """Recopie les chiffres dans les pages HTML :
    - contenu des éléments <x data-cle="cle">…</x> ;
    - attribut content des <meta … data-modele="… {cle} …">.
    Les pages restent ainsi justes sans JavaScript, pour les moteurs de recherche et
    dans les aperçus de partage. Une clé inconnue arrête le script."""
    ouvrante = re.compile(r'<([a-zA-Z][a-zA-Z0-9]*)\b([^>]*\bdata-cle="([^"]+)"[^>]*)>')
    meta = re.compile(r'<meta\b[^>]*\bdata-modele="([^"]*)"[^>]*>')
    for page in sorted(RACINE.glob("*.html")):
        texte = page.read_text(encoding="utf-8")
        sortie, pos = [], 0
        for m in ouvrante.finditer(texte):
            if m.start() < pos:
                continue  # élément data-cle imbriqué dans un autre : déjà remplacé
            balise, attributs, cle = m.groups()
            verifier(cle in cles, f"{page.name} : clé « {cle} » inconnue")
            # Fin de l'élément : balise fermante de même nom, en tenant compte des imbrications.
            niveau, i = 1, m.end()
            balises = re.compile(rf"<(/?){balise}\b[^>]*>")
            while niveau:
                b = balises.search(texte, i)
                verifier(b is not None, f"{page.name} : élément « {cle} » non fermé")
                niveau += -1 if b.group(1) else 1
                i = b.end()
            sortie += [texte[pos:m.end()], rendu_html(cles[cle], attributs), f"</{balise}>"]
            pos = i
        sortie.append(texte[pos:])
        nouveau = "".join(sortie)

        def remplir_meta(m):
            modele = html.unescape(m.group(1))
            for cle in re.findall(r"\{([a-z0-9_]+)\}", modele):
                verifier(cle in cles, f"{page.name} : clé « {cle} » inconnue dans data-modele")
            contenu = html.escape(re.sub(r"\{([a-z0-9_]+)\}", lambda c: cles[c.group(1)], modele))
            contenu = contenu.replace("&#x27;", "'")
            return re.sub(r'\bcontent="[^"]*"', lambda _: f'content="{contenu}"', m.group(0), count=1)

        nouveau = meta.sub(remplir_meta, nouveau)
        if nouveau != texte:
            page.write_text(nouveau, encoding="utf-8")
            print(f"  {page.name} : chiffres mis à jour")


# --------------------------------------------------------------------------
# Comparaison européenne de l'emploi public (OCDE, Eurostat ; France : Insee)
# --------------------------------------------------------------------------
UE_HORS = ("IS", "NO", "CH", "UK")  # pays européens hors Union européenne


def construire_europe(cat: dict) -> dict:
    emp, part, pop, noms = defaultdict(dict), defaultdict(dict), defaultdict(dict), {}
    for l in lire("emploi_public_europe.csv"):
        c, a = l["code_pays"], int(l["annee"])
        noms[c] = l["pays"]
        if l["emploi_apu_milliers"]:
            emp[c][a] = nombre(l["emploi_apu_milliers"])
        if l["part_emploi_total_pct"]:
            part[c][a] = nombre(l["part_emploi_total_pct"])
    for l in lire("population_europe.csv"):
        pop[l["code_pays"]][int(l["annee"])] = nombre(l["population_milliers"])
    annees = sorted({a for d in list(emp.values()) + list(part.values()) for a in d})
    verifier(annees == list(range(annees[0], annees[-1] + 1)), "comparaison européenne : années manquantes")
    fin = max(part["FR"])
    verifier(fin == max(emp["FR"]), "France : dernière année différente pour l'emploi et la part")

    # Recoupement : emploi de l'OCDE pour la France = emploi des administrations publiques de l'Insee
    agr = defaultdict(dict)
    for l in lire("agregats_comptes_nationaux.csv"):
        agr[l["indicateur"]][int(l["annee"])] = nombre(l["valeur"])
    for a, v in emp["FR"].items():
        if a in agr["emploi_S13"]:
            verifier(abs(v - agr["emploi_S13"][a]) <= 0.002 * agr["emploi_S13"][a], f"France {a} : OCDE ≠ Insee")

    def taux(c, a):  # emplois publics pour 1 000 habitants (calcul)
        if a in emp[c] and a in pop[c]:
            return round(1000 * emp[c][a] / pop[c][a], 1)
        return None

    pays = [{"code": c, "libelle": noms[c], "ue": c not in UE_HORS,
             "emploi": [emp[c].get(a) for a in annees],
             "part": [part[c].get(a) for a in annees],
             "taux": [taux(c, a) for a in annees]} for c in sorted(noms, key=lambda k: noms[k])]
    i = annees.index(fin)
    P = {p["code"]: p for p in pays}

    def rang(cle):  # rang de la France parmi les pays ayant une valeur la dernière année
        L = sorted((p for p in pays if p[cle][i] is not None), key=lambda p: -p[cle][i])
        return [p["code"] for p in L].index("FR") + 1, len(L)
    r_part, n_part = rang("part")
    r_taux, n_taux = rang("taux")

    # Sous-secteurs (dernière année disponible pour chaque pays)
    ss, src_ss = defaultdict(dict), {}
    for l in lire("emploi_public_europe_sous_secteurs.csv"):
        ss[(l["code_pays"], int(l["annee"]))][l["code_secteur"]] = nombre(l["emploi_milliers"])
        src_ss[l["code_pays"]] = l["source_id"]
    sous = []
    for c in sorted({k[0] for k in ss}, key=lambda k: noms.get(k, k)):
        a = max(an for (k, an) in ss if k == c)
        v = ss[(c, a)]
        verifier(abs(sum(v.get(k) or 0 for k in SS_CODES) - v["S13"]) <= 0.005 * v["S13"] + 0.2,
                 f"{c} {a} : sous-secteurs incohérents")
        sous.append({"code": c, "libelle": noms.get(c, c), "annee": a, "total": v["S13"],
                     **{k: v.get(k) for k in SS_CODES}, "source": libelle_source(cat, src_ss[c])})
    fs = next(s for s in sous if s["code"] == "FR")

    cles = {
        "eu_annee": str(fin),
        "eu_annee_debut": str(annees[0]),
        "eu_fr_part": pct(P["FR"]["part"][i]),
        "eu_fr_part_debut": pct(P["FR"]["part"][0]),
        "eu_fr_rang_part": f"{r_part}e sur {n_part}",
        "eu_fr_taux": fr(P["FR"]["taux"][i], 0),
        "eu_fr_rang_taux": f"{r_taux}e sur {n_taux}",
        "eu_fr_emploi": millions(1000 * P["FR"]["emploi"][i]),
        "eu_de_part": pct(P["DE"]["part"][i]),
        "eu_de_taux": fr(P["DE"]["taux"][i], 0),
        "eu_de_emploi": millions(1000 * P["DE"]["emploi"][i]),
        "eu_de_pop": fr(pop["DE"][fin] / 1000, 1) + " millions",
        "eu_it_taux": fr(P["IT"]["taux"][i], 0),
        "eu_es_taux": fr(P["ES"]["taux"][i], 0),
        "eu_se_part": pct(P["SE"]["part"][i]),
        "eu_se_taux": fr(P["SE"]["taux"][i], 0),
        "eu_dk_part": pct(P["DK"]["part"][i]),
        "eu_fr_ss_annee": str(fs["annee"]),
        "eu_fr_ss_local": pct(100 * fs["S1313"] / fs["total"], 0),
        "eu_fr_ss_central": pct(100 * fs["S1311"] / fs["total"], 0),
        "eu_fr_ss_secu": pct(100 * fs["S1314"] / fs["total"], 0),
        "eu_nb_pays": str(len(pays)),
    }
    return {
        "annees": annees, "fin": fin, "pays": pays, "sousSecteurs": sous, "cles": cles,
        "sources": {"emploi": libelle_source(cat, "OCDE_GAAG_EMPLOI"),
                    "population": libelle_source(cat, "EUROSTAT_POP_CN"),
                    "insee": libelle_source(cat, "INSEE_CN2025_PIB")},
    }


SS_CODES = ("S1311", "S1312", "S1313", "S1314")


# --------------------------------------------------------------------------
# Page « Idées reçues » : chiffres qui ne figurent pas déjà dans les autres jeux de clés.
# Tous sont lus dans les CSV (ou dans les séries nationales déjà construites) ; aucun n'est saisi.
# --------------------------------------------------------------------------
def construire_idees_recues(national: dict) -> dict:
    E = national["effectifs"]
    a_ref = int(national["cles"]["annee_ref"])
    i_ref = E["annees"].index(a_ref)
    # Même calcul que la page Évolution : effectifs au 31/12 / population au 1er janvier suivant.
    taux_ref = 1000 * E["actuelle"]["total"][i_ref] / E["population"][i_ref]

    # Salaires nets moyens public / privé en euros constants (DGAFP), première et dernière année
    pp = sorted(lire("salaires_nets_public_prive_euros_constants.csv"), key=lambda l: int(l["annee"]))
    debut, fin = pp[0], pp[-1]
    evol = lambda c: 100 * (nombre(fin[c]) / nombre(debut[c]) - 1)  # noqa: E731

    # Déciles du salaire net, public et privé
    nom_dec, a_dec = fichier_recent("deciles_salaires_public_prive")
    dec = {l["decile"]: l for l in lire(nom_dec)}
    verifier(set(dec) == {f"D{i}" for i in range(1, 10)}, f"{nom_dec} : déciles incomplets")

    # Âge moyen de départ des fonctionnaires selon le type d'emploi (DGAFP)
    age = defaultdict(dict)
    for l in lire("retraites_age_depart.csv"):
        age[l["motif"]][int(l["annee"])] = nombre(l["age_moyen"])
    a_age = max(age["ensemble"])

    signe = lambda v: ("+" if v >= 0 else "−") + fr(abs(v), 1) + " %"  # noqa: E731
    cles = {
        "ir_taux_ref": fr(taux_ref, 1),
        "ir_sal_annee_debut": debut["annee"],
        "ir_sal_annee_fin": fin["annee"],
        "ir_net_fp_debut": fr(nombre(debut["fonction_publique"])) + " €",
        "ir_net_prive_debut": fr(nombre(debut["secteur_prive"])) + " €",
        "ir_net_fp_evol": signe(evol("fonction_publique")),
        "ir_net_prive_evol": signe(evol("secteur_prive")),
        "ir_dec_annee": str(a_dec),
        "ir_d1_fp": fr(nombre(dec["D1"]["fonction_publique"])) + " €",
        "ir_d1_prive": fr(nombre(dec["D1"]["secteur_prive"])) + " €",
        "ir_d5_prive": fr(nombre(dec["D5"]["secteur_prive"])) + " €",
        "ir_d9_fp": fr(nombre(dec["D9"]["fonction_publique"])) + " €",
        "ir_d9_prive": fr(nombre(dec["D9"]["secteur_prive"])) + " €",
        "ir_age_annee": str(a_age),
        "ir_age_actif": fr(age["actif"][a_age], 1) + " ans",
        "ir_age_sedentaire": fr(age["sedentaire"][a_age], 1) + " ans",
    }
    return {"cles": cles}


def controler_idees_recues(cles: dict) -> None:
    """Les réponses courtes (« Non », « En moyenne, non »…) de idees-recues.html sont écrites
    à la main : on vérifie ici que les chiffres du moment les confirment toujours. Si une mise à
    jour des données en contredit une, la construction s'arrête et la réponse est à revoir."""
    def v(cle):
        t = re.sub(r"[^0-9,−-]", "", cles[cle]).replace(",", ".").replace("−", "-")
        return float(t)
    tests = {
        "plus qu'avant : agents en hausse plus vite que la population, au-delà de la croissance démographique":
            v("croissance_depuis_ref") > v("croissance_pop_depuis_ref") and v("taux_france") > v("ir_taux_ref"),
        "plus qu'avant : fonctionnaires au sens strict sous leur maximum":
            int(cles["fonctionnaires_max_annee"]) < int(cles["annee"]) and v("fonctionnaires_millions") < v("fonctionnaires_max_millions"),
        "tous fonctionnaires : environ deux sur trois": 55 <= v("fonctionnaires_part") <= 72,
        "ministères : l'État emploie moins de la moitié des agents": v("fpe_nombre") < v("total_millions") / 2,
        "partout : du simple au triple": v("dep_taux_max") >= 3 * v("dep_taux_min"),
        "voisins : plus que l'Allemagne, l'Italie, l'Espagne":
            v("eu_fr_taux") > max(v("eu_de_taux"), v("eu_it_taux"), v("eu_es_taux")) and v("eu_fr_part") > v("eu_de_part"),
        "voisins : moins que la Suède et le Danemark": v("eu_fr_part") < min(v("eu_se_part"), v("eu_dk_part")),
        "mieux payés : salaire net moyen public inférieur au privé": v("ms_net_fp") < v("ms_net_prive"),
        "mieux payés : l'inverse en début de série": v("ir_net_fp_debut") > v("ir_net_prive_debut"),
        "mieux payés : salaires plus resserrés dans le public":
            v("ir_d1_fp") > v("ir_d1_prive") and v("ir_d9_fp") < v("ir_d9_prive"),
        "point d'indice : le salaire moyen a moins baissé que le point": v("ir_net_fp_evol") > -v("ms_point_perte"),
        "mieux payés de la fonction publique : surtout des médecins hospitaliers": v("ms_centile_ph") > 50,
        "masse salariale : la dernière année n'est pas le record": v("ms_pct_pib") < v("ms_pct_pib_max")
            and cles["ms_annee_pct_max"] != cles["ms_annee"],
        "retraite avant 60 ans : âge moyen supérieur à 60 ans": v("rt_age_depart") > 60 and v("ir_age_actif") > 60,
        "cotisations : retenues des fonctionnaires minoritaires, contributions de l'État majoritaires":
            v("rt_cas_salaries") < 0.25 * v("rt_cas_recettes") and v("rt_cas_etat") > 0.5 * v("rt_cas_recettes"),
    }
    for nom, ok in tests.items():
        verifier(ok, f"idees-recues.html : la réponse « {nom} » n'est plus confirmée par les données")


def main() -> int:
    global DATE_MAJ
    try:
        cat = sources()
        geo = json.loads(GEO.read_text(encoding="utf-8"))
        DATE_MAJ, empreinte = date_mise_a_jour()
        print("Construction des données du site :")
        national = construire_national(cat)
        national["empreinteSources"] = empreinte
        ecrire_js("national", national)
        cles = {}
        jeux = [national]
        if (CSV / "masse_salariale_comptes_nationaux.csv").exists():
            jeux.append(construire_masse_salariale(cat))
            ecrire_js("masse_salariale", jeux[-1])
        if (CSV / "retraites_depenses_pensions.csv").exists():
            jeux.append(construire_retraites(cat))
            ecrire_js("retraites", jeux[-1])
        if (CSV / "emploi_public_europe.csv").exists():
            jeux.append(construire_europe(cat))
            ecrire_js("europe", jeux[-1])
        if (CSV / "departements_effectifs.csv").exists():
            jeux.append(construire_departements(cat, geo))
            ecrire_js("departements", jeux[-1])
        ecrire_js("fond_de_carte", geo)
        # Chiffres propres à la page « Idées reçues » (rien n'est écrit dans donnees/site/ :
        # la page n'a pas de graphique, ses chiffres sont recopiés dans le HTML ci-dessous).
        jeux.append(construire_idees_recues(national))
        # Chiffres des pages : toutes les clés, qui ne doivent pas se contredire d'un jeu à l'autre.
        for jeu in jeux:
            for k, v in jeu.get("cles", {}).items():
                verifier(cles.get(k, v) == v, f"clé « {k} » définie deux fois avec des valeurs différentes")
                cles[k] = v
        a, mo, j = (int(x) for x in DATE_MAJ.split("-"))
        cles["date_maj"] = f"{'1er' if j == 1 else j} {MOIS[mo - 1]} {a}"
        controler_idees_recues(cles)
        print("Pages HTML :")
        mettre_a_jour_pages(cles)
        print("Terminé.")
        return 0
    except Anomalie as e:
        print(f"ANOMALIE : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
