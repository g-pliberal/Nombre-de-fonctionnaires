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
    }

    return {
        "maj": date.today().isoformat(),
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
        "cles": cles,
    }


def main() -> int:
    try:
        cat = sources()
        geo = json.loads(GEO.read_text(encoding="utf-8"))
        print("Construction des données du site :")
        national = construire_national(cat)
        ecrire_js("national", national)
        if (CSV / "masse_salariale_comptes_nationaux.csv").exists():
            ecrire_js("masse_salariale", construire_masse_salariale(cat))
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
