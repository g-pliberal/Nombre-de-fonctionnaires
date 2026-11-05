#!/usr/bin/env python3
"""Télécharge les fichiers officiels sur la masse salariale publique et en extrait
les CSV propres de donnees/csv/ (séparateur « ; », une source par ligne).

Sources (toutes publiques, Licence Ouverte / réutilisation libre) :
  - Insee, comptes nationaux annuels (base 2020), « Les comptes de la Nation en 2025 » :
    comptes des administrations publiques et de leurs sous-secteurs (1949-2025), PIB,
    population, emploi, dépenses publiques ;
  - Insee, indice des prix à la consommation (coefficients du convertisseur franc-euro) ;
  - DGAFP, rapport annuel sur l'état de la fonction publique, édition 2026 : dépenses de
    personnel (État, collectivités, hôpitaux), salaires bruts et nets, point d'indice ;
  - DGAFP, séries longues de l'édition 2021 : valeur du point d'indice depuis 1970 ;
  - Eurostat : rémunération des salariés des administrations publiques par fonction
    (France) et en % du PIB (pays européens).

Le script ne fait que lire des cellules publiées, convertir des unités et, quand c'est
signalé, des calculs simples (sommes, moyennes annuelles de valeurs publiées). Il
contrôle la cohérence des tableaux (sommes de lignes, recoupements entre sources) et
s'arrête en cas d'anomalie.

Usage :
    python3 outils/extraire_masse_salariale.py              # télécharge si besoin
    python3 outils/extraire_masse_salariale.py --hors-ligne # n'utilise que le cache
Les fichiers téléchargés sont conservés dans .cache/sources/ (non versionné) ; leurs
empreintes SHA-256 sont écrites dans donnees/empreintes_masse_salariale.txt.
Ensuite : python3 outils/construire_donnees.py
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

import openpyxl

RACINE = Path(__file__).resolve().parent.parent
CSV = RACINE / "donnees" / "csv"
CACHE = RACINE / ".cache" / "sources"
EMPREINTES = RACINE / "donnees" / "empreintes_masse_salariale.txt"

INSEE = "https://www.insee.fr/fr/statistiques/fichier"
DGAFP = "https://www.fonction-publique.gouv.fr/files/files/publications/vue-rapport-annuel/2026"
DGAFP_SL = ("https://www.fonction-publique.gouv.fr/files/files/ArchivePortailFP/www.fonction-publique.gouv.fr/"
            "files/files/statistiques/series_longues/series-longues-2021")
EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

# nom local -> adresse officielle
FICHIERS = {
    "insee/T_7301_fr.xlsx": f"{INSEE}/8988833/T_7301_fr.xlsx",
    "insee/T_7302_fr.xlsx": f"{INSEE}/8988833/T_7302_fr.xlsx",
    "insee/T_7303_fr.xlsx": f"{INSEE}/8988833/T_7303_fr.xlsx",
    "insee/T_7304_fr.xlsx": f"{INSEE}/8988833/T_7304_fr.xlsx",
    "insee/T_7305_fr.xlsx": f"{INSEE}/8988833/T_7305_fr.xlsx",
    "insee/T_7306_fr.xlsx": f"{INSEE}/8988833/T_7306_fr.xlsx",
    "insee/t_3201_fr.xlsx": f"{INSEE}/8988845/t_3201_fr.xlsx",
    "insee/ipc_coefficient_011813530.xml": "https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/011813530",
    "insee/T_1108_fr.xlsx": f"{INSEE}/8988797/T_1108_fr.xlsx",
    "insee/T_1109_fr.xlsx": f"{INSEE}/8988797/T_1109_fr.xlsx",
    "insee/T_1115_fr.xlsx": f"{INSEE}/8988797/T_1115_fr.xlsx",
    "dgafp/ra_2026_remu_niveaux.zip": f"{DGAFP}/ra_2026_remu_niveaux.zip",
    "dgafp/ra_2026_remu_evolutions.zip": f"{DGAFP}/ra_2026_remu_evolutions.zip",
    "dgafp/FT6.2-SL_Traitement_indiciaire.xlsx": f"{DGAFP_SL}/FT6.2-SL_Traitement_indiciaire.xlsx",
    "eurostat/gov_10a_exp_FR_S13_D1.json":
        f"{EUROSTAT}/gov_10a_exp?format=JSON&lang=fr&geo=FR&sector=S13&na_item=D1&unit=MIO_EUR",
    "eurostat/gov_10a_main_S13_D1PAY_PC_GDP.json":
        f"{EUROSTAT}/gov_10a_main?format=JSON&lang=fr&sector=S13&na_item=D1PAY&unit=PC_GDP",
}


class Anomalie(Exception):
    pass


def verifier(condition: bool, message: str) -> None:
    if not condition:
        raise Anomalie(message)


# --------------------------------------------------------------------------
# Téléchargement et lecture
# --------------------------------------------------------------------------
def chemin(nom: str, hors_ligne: bool) -> Path:
    p = CACHE / nom
    if p.exists() and p.stat().st_size > 0:
        return p
    verifier(not hors_ligne, f"{nom} absent du cache (relancer sans --hors-ligne)")
    p.parent.mkdir(parents=True, exist_ok=True)
    print(f"  téléchargement de {FICHIERS[nom]}")
    req = urllib.request.Request(FICHIERS[nom], headers={"User-Agent": "fonction-publique-les-chiffres/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        p.write_bytes(r.read())
    return p


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def classeur(p: Path, membre: str | None = None):
    if membre:
        with zipfile.ZipFile(p) as z:
            octets = z.read(membre)
    else:
        octets = p.read_bytes()
    return openpyxl.load_workbook(io.BytesIO(octets), read_only=True, data_only=True)


def lignes(wb, feuille: str) -> list[list]:
    return [list(r) for r in wb[feuille].iter_rows(values_only=True)]


def texte(v) -> str:
    return "" if v is None else " ".join(str(v).split())


def num(v):
    """Valeur numérique publiée, ou None (« /// », « - », « (5) - », vide…)."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    m = re.fullmatch(r"(?:\(\d+\))?(-?\d+(?:\.\d+)?(?:e-?\d+)?)", s)
    return float(m.group(1)) if m else None


def annee_entete(v):
    """« 2023* », « 2016(a) », « 2021 Classique » -> (2023, libellé complet)."""
    s = texte(v)
    m = re.match(r"^((?:19|20)\d\d)(?!\d)", s)
    return (int(m.group(1)), s) if m else None


def colonnes_annees(ligne: list) -> dict[int, tuple[int, str]]:
    return {j: a for j, c in enumerate(ligne) if (a := annee_entete(c))}


def arrondi(v, dec=6):
    if v is None:
        return ""
    r = round(v, dec)
    if r == int(r) and abs(r) >= 1:
        return str(int(r))
    return f"{r:.{dec}f}".rstrip("0").rstrip(".")


def ecrire_csv(nom: str, entetes: list[str], lignes_: list[list]) -> None:
    with open(CSV / nom, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(entetes)
        for l in lignes_:
            w.writerow(["" if v is None else v for v in l])
    print(f"  donnees/csv/{nom} ({len(lignes_)} lignes)")


# --------------------------------------------------------------------------
# 1. Comptes des administrations publiques (Insee, tableaux 7.301 à 7.306)
# --------------------------------------------------------------------------
SECTEURS = [("S13", "T_7301"), ("S1311", "T_7302"), ("S13111", "T_7303"),
            ("S13112", "T_7304"), ("S1313", "T_7305"), ("S1314", "T_7306")]
OPERATIONS = ["D1", "D11", "D12", "D121", "D122", "D291"]


def compte_exploitation(p: Path) -> tuple[str, dict[str, dict[int, float]]]:
    """Lit la partie « Compte d'exploitation / Emplois » d'un compte de secteur Insee."""
    wb = classeur(p)
    feuille = next(n for n in wb.sheetnames if n.startswith("T_"))
    L = lignes(wb, feuille)
    titre = texte(L[0][0])
    verifier("Milliard d'euros" in texte(L[1][0]), f"{p.name} : unité inattendue")
    i_an = next(i for i, l in enumerate(L) if len(colonnes_annees(l)) > 40)
    cols = colonnes_annees(L[i_an])
    debut = next(i for i, l in enumerate(L) if texte(l[1]) == "Compte d'exploitation")
    fin = next(i for i, l in enumerate(L) if texte(l[1]).startswith("Compte d'affectation"))
    emplois = next(i for i in range(debut, fin) if texte(L[i][1]) == "Emplois")
    res = {}
    for l in L[emplois + 1:fin]:
        code = texte(l[0])
        if code in OPERATIONS and code not in res:
            res[code] = {a: num(l[j]) for j, (a, _) in cols.items() if num(l[j]) is not None}
    verifier(set(OPERATIONS) <= set(res), f"{p.name} : opérations manquantes {set(OPERATIONS) - set(res)}")
    return titre, res


def extraire_comptes(hl: bool) -> dict:
    comptes = {}
    titres = {}
    for sect, tab in SECTEURS:
        titres[sect], comptes[sect] = compte_exploitation(chemin(f"insee/{tab}_fr.xlsx", hl))
        verifier(f"({sect})" in titres[sect], f"{tab} : secteur attendu {sect}, lu « {titres[sect]} »")
    lignes_ = []
    for sect, _ in SECTEURS:
        c = comptes[sect]
        for a in sorted(c["D1"]):
            d1, d11, d12 = c["D1"][a], c["D11"].get(a), c["D12"].get(a)
            d121, d122 = c["D121"].get(a), c["D122"].get(a)
            # Contrôles : D1 = D11 + D12 et D12 = D121 + D122 (arrondis de publication : 2 millions)
            verifier(abs(d11 + d12 - d1) <= 0.002, f"{sect} {a} : D11 + D12 ≠ D1")
            verifier(abs(d121 + d122 - d12) <= 0.002, f"{sect} {a} : D121 + D122 ≠ D12")
            lignes_.append([a, sect, arrondi(d1, 3), arrondi(d11, 3), arrondi(d12, 3), arrondi(d121, 3),
                            arrondi(d122, 3), arrondi(c["D291"].get(a), 3), "INSEE_CN2025_APU"])
    # Sous-secteurs : APU = APUC + APUL + ASSO ; APUC = État + ODAC (D1 n'est pas consolidé)
    for a in comptes["S13"]["D1"]:
        s = sum(comptes[x]["D1"][a] for x in ("S1311", "S1313", "S1314"))
        verifier(abs(s - comptes["S13"]["D1"][a]) <= 0.004, f"{a} : APUC + APUL + ASSO ≠ APU")
        if a in comptes["S13111"]["D1"]:
            s = comptes["S13111"]["D1"][a] + comptes["S13112"]["D1"][a]
            verifier(abs(s - comptes["S1311"]["D1"][a]) <= 0.003, f"{a} : État + ODAC ≠ APUC")
    ecrire_csv("masse_salariale_comptes_nationaux.csv",
               ["annee", "secteur", "remuneration_salaries_D1", "salaires_bruts_D11",
                "cotisations_employeurs_D12", "cotisations_effectives_D121", "cotisations_imputees_D122",
                "impots_sur_salaires_D291", "source_id"], lignes_)
    return comptes


# --------------------------------------------------------------------------
# 2. Agrégats : PIB, population, prix, dépenses publiques, emploi (Insee)
# --------------------------------------------------------------------------
def ligne_code(L: list, code: str, libelle_commence: str | None = None, apres: int = 0):
    for i in range(apres, len(L)):
        l = L[i]
        if texte(l[0]) == code and (libelle_commence is None or texte(l[1]).startswith(libelle_commence)):
            return i, l
    raise Anomalie(f"ligne {code} / {libelle_commence} introuvable")


def extraire_agregats(hl: bool, comptes: dict) -> None:
    out = []  # annee, indicateur, valeur, unite, source_id

    # PIB et population (tableau 1.115)
    wb = classeur(chemin("insee/T_1115_fr.xlsx", hl))
    L = lignes(wb, "T_1115")
    cols = colonnes_annees(L[3])
    _, pop = ligne_code(L, "POP", "Population")
    _, pib = ligne_code(L, "B1GQ", "Produit intérieur brut en milliards d'euros")
    verifier("2020" not in texte(pib[1]), "1.115 : la ligne du PIB lue est en volume")
    for j, (a, _) in sorted(cols.items(), key=lambda x: x[1][0]):
        out.append([a, "pib", arrondi(num(pib[j]), 3), "milliards d'euros courants", "INSEE_CN2025_PIB"])
        out.append([a, "population", arrondi(num(pop[j]), 1),
                    "milliers de personnes (moyenne annuelle, France)", "INSEE_CN2025_PIB"])

    # Prix à la consommation : coefficients du convertisseur franc-euro de l'Insee (série 011813530,
    # indice des prix à la consommation y compris tabac, base 100 la dernière année), comme la DGAFP
    # et l'Insee pour exprimer les salaires en euros constants.
    xml = chemin("insee/ipc_coefficient_011813530.xml", hl).read_text(encoding="utf-8")
    verifier('IDBANK="011813530"' in xml and "Coefficient de transformation" in xml, "série des prix inattendue")
    ipc = {int(a): float(v) for a, v in re.findall(r'TIME_PERIOD="(\d{4})" OBS_VALUE="([0-9.]+)"', xml)}
    base = int(re.search(r"Base (\d{4})", xml).group(1))
    verifier(ipc.get(base) == 100.0, "prix : l'année de base doit valoir 100")
    for a in sorted(comptes["S13"]["D1"]):
        verifier(a in ipc, f"prix : année {a} absente")
        out.append([a, "prix_consommation", arrondi(ipc[a], 2), f"indice base 100 en {base}", "INSEE_IPC_CONVERTISSEUR"])

    # Emploi des administrations publiques (tableaux 1.108 en personnes, 1.109 en ETP)
    for tab, feuille, ind, unite in [("T_1108", "T_1108", "emploi", "milliers de personnes"),
                                     ("T_1109", "T_1109 en niveau", "emploi_etp", "milliers d'équivalents temps plein")]:
        wb = classeur(chemin(f"insee/{tab}_fr.xlsx", hl))
        feuille = feuille if feuille in wb.sheetnames else next(n for n in wb.sheetnames if n.startswith("T"))
        L = lignes(wb, feuille)
        cols = colonnes_annees(L[3])
        for sect in ["S13", "S13111", "S13112", "S1313", "S1314"]:
            _, l = ligne_code(L, sect)
            for j, (a, _) in sorted(cols.items(), key=lambda x: x[1][0]):
                if num(l[j]) is not None:
                    out.append([a, f"{ind}_{sect}", arrondi(num(l[j]), 1), unite, "INSEE_CN2025_PIB"])

    # Dépenses publiques totales (tableau 3.201)
    L = lignes(classeur(chemin("insee/t_3201_fr.xlsx", hl)), "t_3201")
    cols = colonnes_annees(L[2])
    tot = next(l for l in L if texte(l[1]) == "Total des dépenses")
    d1 = next(l for l in L if texte(l[1]).startswith("Rémunération des salariés (D1)"))
    for j, (a, _) in sorted(cols.items(), key=lambda x: x[1][0]):
        out.append([a, "depenses_publiques", arrondi(num(tot[j]), 4), "milliards d'euros courants",
                    "INSEE_CN2025_DEPENSES"])
        # Recoupement : le D1 du tableau 3.201 est celui du compte des APU (7.301)
        verifier(abs(num(d1[j]) - comptes["S13"]["D1"][a]) <= 0.002, f"{a} : D1 différent entre 3.201 et 7.301")

    out.sort(key=lambda l: (l[1], l[0]))
    ecrire_csv("agregats_comptes_nationaux.csv", ["annee", "indicateur", "valeur", "unite", "source_id"], out)


# --------------------------------------------------------------------------
# 3. DGAFP : dépenses de personnel (rapport annuel 2026)
# --------------------------------------------------------------------------
MEMBRE_DEPENSES = "ra_2026_remu_niveaux_donnees_comp_depenses.xlsx"


def extraire_depenses_dgafp(hl: bool, comptes: dict) -> None:
    wb = classeur(chemin("dgafp/ra_2026_remu_niveaux.zip", hl), MEMBRE_DEPENSES)

    # Figure 1 : recoupement avec l'Insee et « dont » collectivités locales / hôpitaux (2013-2025)
    L = lignes(wb, "Figure 1")
    cols = colonnes_annees(L[2])
    bloc = L[3:12]
    corresp = {"Administrations publiques centrales": "S1311", "dont État": "S13111",
               "Administrations publiques locales": "S1313", "Administrations de Sécurité sociale": "S1314",
               "Toutes administrations publiques": "S13"}
    dont = []
    for l in bloc:
        lib = texte(l[0])
        for debut, sect in corresp.items():
            if lib.startswith(debut):
                for j, (a, _) in cols.items():
                    if num(l[j]) is not None:
                        verifier(abs(num(l[j]) - comptes[sect]["D1"][a]) <= 0.01,
                                 f"DGAFP figure 1 {lib} {a} : écart avec l'Insee")
        if lib.startswith("dont collectivités locales") or lib.startswith("dont organismes dépendant"):
            cle = "collectivites_locales" if "collectivités" in lib else "organismes_dependant_assurances_sociales"
            for j, (a, _) in cols.items():
                if num(l[j]) is not None:
                    dont.append([a, cle, arrondi(num(l[j]), 4), "DGAFP_RA2026_DEPENSES"])
    verifier(len(dont) >= 26, "DGAFP figure 1 : lignes « dont » introuvables")
    ecrire_csv("remunerations_apu_dont.csv", ["annee", "composante", "remuneration_salaries_D1", "source_id"],
               sorted(dont))

    # Figure 2 : détail du titre 2 de l'État (2008-2025)
    L = lignes(wb, "Figure 2")
    cols = colonnes_annees(L[2])
    rubriques = [
        # (libellé ou code DB, clé, groupe, niveau)
        ("Rémunérations d’activité", "remunerations_activite", "remunerations_activite", 1),
        ("210", "traitement_brut", "remunerations_activite", 2),
        ("211", "nbi", "remunerations_activite", 2),
        ("212", "indemnite_residence", "remunerations_activite", 2),
        ("213", "supplement_familial", "remunerations_activite", 2),
        ("214", "majorations", "remunerations_activite", 2),
        ("215", "indemnites_indexees", "remunerations_activite", 2),
        ("216", "indemnites_non_indexees", "remunerations_activite", 2),
        ("Rémunérations d'activité non ventilées", "remunerations_non_ventilees", "remunerations_activite", 2),
        ("Cotisations et contributions sociales", "cotisations", "cotisations", 1),
        ("Contributions d'équilibre au CAS Pensions", "cas_pensions", "cotisations", 2),
        ("221", "cas_pensions_civils_ati", "cotisations", 3),
        ("222", "cas_pensions_militaires", "cotisations", 3),
        ("225", "fspoeie_cas_cultes", "cotisations", 3),
        ("220", "contribution_exceptionnelle_cas", "cotisations", 3),
        ("223", "rafp", "cotisations", 2),
        ("224", "cotisations_fspoeie", "cotisations", 2),
        ("226", "cotisations_retraites_autres", "cotisations", 2),
        ("227", "cotisations_securite_sociale", "cotisations", 2),
        ("228", "fnal_cnaf_csa", "cotisations", 2),
        ("229", "cotisations_autres", "cotisations", 2),
        ("Prestations sociales et allocations diverses", "prestations", "prestations", 1),
        ("231", "prestations_sociales", "prestations", 2),
        ("232", "remboursement_transport", "prestations", 2),
        ("233", "capital_deces", "prestations", 2),
        ("234", "cfa_caa", "prestations", 2),
        ("236", "allocation_retour_emploi", "prestations", 2),
        ("238", "accidents_travail", "prestations", 2),
        ("239-237", "prestations_autres", "prestations", 2),
        ("Total des dépenses de personnel (titre 2)", "total_titre2", "total", 0),
        ("Pensions civiles, militaires et ouvriers d'État", "pensions_versees", "annexe", 0),
        ("Budget de l'État", "budget_etat", "annexe", 0),
    ]
    libelles = {}
    valeurs = {}
    for cle_src, cle, groupe, niveau in rubriques:
        # Colonne A : code de la nomenclature budgétaire (« 210 »…) ; colonne B : libellé.
        if cle_src[:3].isdigit():
            l = next(l for l in L[3:40] if texte(l[0]) == cle_src)
        else:
            l = next(l for l in L[3:40] if not texte(l[0]) and texte(l[1]).startswith(cle_src))
        libelles[cle] = re.sub(r"\s*\(\d\)$", "", texte(l[1]))
        valeurs[cle] = {a: num(l[j]) for j, (a, _) in cols.items()}
    lignes_ = []
    for a in sorted({a for a, _ in cols.values()}):
        v = {c: valeurs[c][a] for c in valeurs}
        # Contrôles de sommes (au million d'euros près)
        s = sum(v[c] or 0 for c, g, n in [(r[1], r[2], r[3]) for r in rubriques] if g == "remunerations_activite" and n == 2)
        verifier(abs(s - v["remunerations_activite"]) < 0.002, f"titre 2 {a} : rémunérations d'activité")
        s = v["cas_pensions_civils_ati"] + v["cas_pensions_militaires"] + v["fspoeie_cas_cultes"] + (v["contribution_exceptionnelle_cas"] or 0)
        verifier(abs(s - v["cas_pensions"]) < 0.002, f"titre 2 {a} : CAS Pensions")
        s = v["cas_pensions"] + sum(v[c] or 0 for c in ["rafp", "cotisations_fspoeie", "cotisations_retraites_autres",
                                                         "cotisations_securite_sociale", "fnal_cnaf_csa", "cotisations_autres"])
        verifier(abs(s - v["cotisations"]) < 0.002, f"titre 2 {a} : cotisations")
        s = v["remunerations_activite"] + v["cotisations"] + v["prestations"]
        verifier(abs(s - v["total_titre2"]) < 0.002, f"titre 2 {a} : total")
        for cle_src, cle, groupe, niveau in rubriques:
            if v[cle] is not None:
                lignes_.append([a, cle, libelles[cle], groupe, niveau, arrondi(v[cle], 6), "DGAFP_RA2026_DEPENSES"])
    ecrire_csv("depenses_personnel_etat.csv",
               ["annee", "rubrique", "libelle", "groupe", "niveau", "montant_milliards", "source_id"], lignes_)

    # Figure 4 : rémunérations d'activité de l'État par statut et nature (2008-2025)
    L = lignes(wb, "Figure 4")
    cols = colonnes_annees(L[2])
    postes = [
        ("Rémunérations principales", "remunerations_principales", 1),
        ("Fonctionnaires", "fonctionnaires", 2), ("Stagiaires", "stagiaires", 2),
        ("Contractuels", "contractuels", 2), ("Ouvriers d'État", "ouvriers_etat", 2),
        ("Enseignants de l'enseignement privé sous contrat", "enseignants_prive", 2),
        ("Militaires", "militaires", 2),
        ("Rémunérations à l'acte, à la tâche, à l'heure", "remunerations_acte", 2),
        ("Autres rémunérations", "autres_remunerations", 2),
        ("Charges connexes à la rémunération principale", "charges_connexes", 1),
        ("Primes et indemnités", "primes_indemnites", 1),
        ("Personnels civils", "primes_civils", 2), ("Personnels militaires", "primes_militaires", 2),
        ("Non réparti", "non_reparti", 1),
        ("Total rémunérations d’activité", "total_remunerations_activite", 0),
    ]
    lignes_ = []
    vals = {}
    for debut, cle, niveau in postes:
        l = next(l for l in L[3:43] if texte(l[0]).startswith(debut))
        vals[cle] = {a: num(l[j]) for j, (a, _) in cols.items()}
        for j, (a, _) in cols.items():
            if num(l[j]) is not None:
                lignes_.append([a, cle, re.sub(r"\s*\(\d\)|\s*:$", "", texte(l[0])), niveau, arrondi(num(l[j]), 6),
                                "DGAFP_RA2026_DEPENSES"])
    hors_non_reparti = []
    for a in sorted({a for a, _ in cols.values()}):
        s = sum(vals[c][a] or 0 for c in ["remunerations_principales", "charges_connexes", "primes_indemnites"])
        t = vals["total_remunerations_activite"][a]
        # Le total publié inclut la ligne « non réparti » certaines années seulement (source).
        if abs(s - t) < 0.003 and abs(vals["non_reparti"][a] or 0) >= 0.003:
            hors_non_reparti.append(str(a))
        else:
            verifier(abs(s + (vals["non_reparti"][a] or 0) - t) < 0.003, f"figure 4 {a} : total")
    if hors_non_reparti:
        print("  figure 4 (État) : total publié hors ligne « non réparti » en " + ", ".join(hors_non_reparti))
    lignes_.sort(key=lambda l: (l[0], [p[1] for p in postes].index(l[1])))
    ecrire_csv("remunerations_activite_etat.csv",
               ["annee", "poste", "libelle", "niveau", "montant_milliards", "source_id"], lignes_)

    # Figure 5 : dépenses de personnel des collectivités locales (1996-2025)
    L = lignes(wb, "Figure 5")
    cols = colonnes_annees(L[2])
    noms = [("Régions", "regions"), ("Départements", "departements"), ("Communes", "communes"),
            ("Groupements", "groupements"), ("Ensemble des dépenses de personnel", "ensemble"),
            ("Dépenses totales", "depenses_totales")]
    vals = {cle: {a: num(next(l for l in L[3:10] if texte(l[0]).startswith(deb))[j]) for j, (a, _) in cols.items()}
            for deb, cle in noms}
    lignes_ = []
    for j, (a, lib) in sorted(cols.items(), key=lambda x: x[1][0]):
        s = sum(vals[c][a] for c in ["regions", "departements", "communes", "groupements"])
        verifier(abs(s - vals["ensemble"][a]) < 0.06, f"collectivités {a} : somme ≠ ensemble ({s} / {vals['ensemble'][a]})")
        note = "provisoire" if "*" in lib else ""
        m = re.search(r"\(([a-d])\)", lib)
        if m:
            note = {"a": "Martinique et Guyane passent des départements aux régions (collectivités uniques)",
                    "b": "les deux départements de Corse fusionnent avec la collectivité de Corse (classée en région)",
                    "c": "la Ville de Paris remplace la commune et le département de Paris (classée en commune)"}[m.group(1)]
        lignes_.append([a] + [arrondi(vals[c][a], 6) for _, c in noms] + [note, "DGAFP_RA2026_DEPENSES"])
    ecrire_csv("depenses_personnel_collectivites.csv",
               ["annee"] + [c for _, c in noms] + ["note", "source_id"], lignes_)

    # Figure 6 : charges de personnel des établissements publics de santé (2000-2025)
    L = lignes(wb, "Figure 6")
    cols = colonnes_annees(L[2])
    noms = [("Rémunérations du personnel non médical", "remunerations_non_medical"),
            ("Rémunérations du personnel médical", "remunerations_medical"),
            ("Charges de sécurité sociale", "charges_sociales"),
            ("Impôts, taxes", "impots_taxes"), ("Autres charges", "autres_charges"),
            ("Ensemble des charges de personnel", "ensemble"), ("Dépenses totales", "depenses_totales")]
    vals = {cle: {a: num(next(l for l in L[3:11] if texte(l[0]).startswith(deb))[j]) for j, (a, _) in cols.items()}
            for deb, cle in noms}
    lignes_ = []
    for j, (a, lib) in sorted(cols.items(), key=lambda x: x[1][0]):
        s = sum(vals[c][a] for c, _ in [(n[1], 0) for n in noms[:5]])
        verifier(abs(s - vals["ensemble"][a]) < 0.06, f"hôpitaux {a} : somme ≠ ensemble ({s} / {vals['ensemble'][a]})")
        note = "provisoire" if "**" in lib else ""
        lignes_.append([a] + [arrondi(vals[c][a], 6) for _, c in noms] + [note, "DGAFP_RA2026_DEPENSES"])
    ecrire_csv("charges_personnel_hopitaux.csv", ["annee"] + [c for _, c in noms] + ["note", "source_id"], lignes_)


# --------------------------------------------------------------------------
# 4. DGAFP : salaires (rapport annuel 2026)
# --------------------------------------------------------------------------
def cle_population(lib: str) -> str:
    t = lib.lower().strip().replace(",", "")
    table = {
        "ensemble": "ensemble", "pcs cadres et professions intellectuelles supérieures": "pcs_cadres",
        "pcs professions intermédiaires": "pcs_intermediaires", "pcs employés et ouvriers": "pcs_employes_ouvriers",
        "fonctionnaires": "fonctionnaires", "fonctionnaires de catégorie a": "fonctionnaires_a",
        "fonctionnaires de catégorie b": "fonctionnaires_b", "fonctionnaires de catégorie c": "fonctionnaires_c",
        "contractuels": "contractuels", "autres catégories et statuts": "autres_statuts",
        "ensemble hors bénéficiaires de contrats aidés": "ensemble_hors_contrats_aides",
        "bénéficiaires de contrats aidés": "contrats_aides", "femmes": "femmes", "hommes": "hommes",
        "moins de 30 ans": "moins_30", "30-39 ans": "30_39", "40-49 ans": "40_49", "50-59 ans": "50_59",
        "60 ans et plus": "60_plus", "60 ans ou plus": "60_plus",
        "ensemble france métropolitaine": "metropole", "ensemble dom": "dom",
    }
    t = re.sub(r"\d$", "", t).strip()
    t = t.replace("fonction publique de l’état (fpe)", "fpe").replace("fonction publique territoriale (fpt)", "fpt")
    t = t.replace("fonction publique hospitalière (fph)", "fph").replace("ensemble fonction publique (fp)", "fp")
    if t in ("fp", "fpe", "fpt", "fph"):
        return t
    t = re.sub(r"^dont catégorie ([abc])$", r"fonctionnaires de catégorie \1", t)
    verifier(t in table, f"population inconnue : « {lib} »")
    return table[t]


def extraire_salaires(hl: bool) -> None:
    zn = chemin("dgafp/ra_2026_remu_niveaux.zip", hl)
    ze = chemin("dgafp/ra_2026_remu_evolutions.zip", hl)
    wb = classeur(zn, "ra_2026_remu_niveaux_donnees_comp.xlsx")

    # Niveaux 2015-2024 par versant (figure 4) et FPE 2004-2024 (figure 13)
    out = []
    L = lignes(wb, "Figure 4")
    i_ent = next(i for i, l in enumerate(L) if texte(l[0]) == "Indicateur")
    cols = colonnes_annees(L[i_ent])
    for l in L[i_ent + 1:]:
        ind = texte(l[0])
        if not ind.startswith("salaire mensuel"):
            continue
        indic = "brut" if "brut" in ind else "net"
        pop = cle_population(texte(l[2]))
        for j, (a, lib) in cols.items():
            if num(l[j]) is not None:
                version = lib[4:].strip()
                out.append([a, version, texte(l[1]).lower(), pop, indic, arrondi(num(l[j]), 2), "DGAFP_RA2026_REMU"])
    L = lignes(wb, "FPE - Figure 13")
    cols = colonnes_annees(L[2])
    champ = None
    for l in L[3:18]:
        lib = texte(l[0])
        if lib.startswith("FPE"):
            champ = "fpe_ministeres" if "ministères" in lib else "fpe"
            continue
        if lib.startswith("Salaire moyen"):
            indic = "brut" if "brut" in lib else "net"
            pop = "ensemble"
        elif lib.startswith("- dont fonctionnaires"):
            pop = "fonctionnaires"
        else:
            continue
        for j, (a, libc) in cols.items():
            if num(l[j]) is not None and not (champ == "fpe" and a >= 2015):  # 2015-2024 : déjà dans la figure 4
                out.append([a, libc[4:].strip(), champ, pop, indic, arrondi(num(l[j]), 2), "DGAFP_RA2026_REMU"])
    out.sort(key=lambda l: (l[2], l[3], l[4], l[0], l[1]))
    ecrire_csv("salaires_moyens_fonction_publique.csv",
               ["annee", "version", "champ", "population", "indicateur", "euros_mensuels", "source_id"], out)

    # Contrôle croisé : FPE ensemble 2015-2024 identique entre figures 4 et 13
    f13 = {(l[0], l[1], l[3], l[4]): l[5] for l in out if l[2] == "fpe"}
    verifier(f13.get((2024, "", "ensemble", "net")) == "3018.06", "salaire net FPE 2024 attendu 3018,06 €")

    # Distribution et niveaux 2024 (vue, figure 1) et déciles public / privé (vue, figure 5)
    wv = classeur(zn, "ra_2026_vue_renumerations_niveaux.xlsx")
    L = lignes(wv, "Figure 1")
    i_ent = next(i for i, l in enumerate(L) if texte(l[2]).startswith("Structure des effectifs"))
    out = []
    for l in L[i_ent + 1:]:
        lib = texte(l[1])
        if not lib or l[3] is None:
            continue
        pop = cle_population(lib)
        out.append([2024, pop] + [arrondi(num(l[k]), 2) for k in range(2, 10)] + ["DGAFP_RA2026_REMU"])
    verifier(len(out) >= 18, "vue figure 1 : lignes manquantes")
    ecrire_csv("salaires_2024_fonction_publique.csv",
               ["annee", "population", "part_eqtp_pct", "brut_moyen", "net_moyen", "net_median", "net_d1",
                "net_q1", "net_q3", "net_d9", "source_id"], out)

    L = lignes(wv, "Figure 5")
    i_ent = next(i for i, l in enumerate(L) if texte(l[2]) == "FPE")
    noms = {texte(c): j for j, c in enumerate(L[i_ent]) if c}
    out = []
    for l in L[i_ent + 1:]:
        d = texte(l[1])
        if re.fullmatch(r"D[1-9]", d):
            out.append([2024, d, num(l[noms["FPE"]]), num(l[noms["FPT"]]), num(l[noms["FPH"]]),
                        num(l[noms["Fonction publique"]]), num(l[noms["Secteur privé"]]), "DGAFP_RA2026_REMU"])
    verifier(len(out) == 9, "vue figure 5 : 9 déciles attendus")
    ecrire_csv("deciles_salaires_public_prive_2024.csv",
               ["annee", "decile", "fpe", "fpt", "fph", "fonction_publique", "secteur_prive", "source_id"],
               [[l[0], l[1]] + [arrondi(v, 0) for v in l[2:7]] + [l[7]] for l in out])

    # Décomposition du salaire des fonctionnaires (vue, figure 10)
    L = lignes(wv, "Figure 10")
    i_ent = next(i for i, l in enumerate(L) if texte(l[3]) == "FPE")
    noms = {texte(c): j for j, c in enumerate(L[i_ent]) if c}
    rubr = [("Salaire brut", "salaire_brut"), ("- Traitement brut", "traitement_brut"),
            ("- Primes et rémunérations annexes", "primes"),
            ("- Cotisations salariales", "cotisations_salariales"), ("- CSG et CRDS", "csg_crds"),
            ("Salaire net de prélèvements", "salaire_net")]
    out = []
    cat = None
    tmp = {}
    for l in L[i_ent + 1:]:
        if texte(l[1]):
            cat = {"Ensemble": "ensemble", "Cat. A": "A", "Cat. B": "B", "Cat. C": "C"}.get(texte(l[1]), texte(l[1]))
        lib = texte(l[2])
        for deb, cle in rubr:
            if lib.startswith(deb):
                for v in ["FPE", "FPT", "FPH", "Ensemble FP"]:
                    tmp.setdefault((cat, v), {})[cle] = num(l[noms[v]])
    for (cat, v), d in tmp.items():
        verifier(abs(d["traitement_brut"] + d["primes"] - d["salaire_brut"]) < 0.01, f"fig. 10 {cat} {v} : brut")
        verifier(abs(d["salaire_brut"] - d["cotisations_salariales"] - d["csg_crds"] - d["salaire_net"]) < 0.01,
                 f"fig. 10 {cat} {v} : net")
        vv = {"FPE": "fpe", "FPT": "fpt", "FPH": "fph", "Ensemble FP": "fp"}[v]
        out.append([2024, vv, cat] + [arrondi(d[c], 2) for _, c in rubr] + ["DGAFP_RA2026_REMU"])
    verifier(len(out) == 16, "vue figure 10 : 16 combinaisons attendues")
    ecrire_csv("decomposition_salaire_fonctionnaires_2024.csv",
               ["annee", "versant", "categorie"] + [c for _, c in rubr] + ["source_id"], out)

    # Salaires nets en euros constants, public et privé, 2011-2024 (évolutions, figure 0)
    wb = classeur(ze, "ra_2026_remu_evolutions_donnees_comp.xlsx")
    L = lignes(wb, "Figure 0")
    verifier("euros constant" in texte(L[1][0]), "figure 0 : unité inattendue")
    cols = colonnes_annees(L[2])
    series = {texte(l[0]): l for l in L[3:9]}
    out = []
    for j, (a, _) in sorted(cols.items(), key=lambda x: x[1][0]):
        out.append([a] + [arrondi(num(series[k][j]), 0) for k in ["FP", "FPE", "FPT", "FPH", "Secteur privé"]]
                   + ["DGAFP_RA2026_EVOL"])
    ecrire_csv("salaires_nets_public_prive_euros_constants.csv",
               ["annee", "fonction_publique", "fpe", "fpt", "fph", "secteur_prive", "source_id"], out)


# --------------------------------------------------------------------------
# 5. Point d'indice (DGAFP) : moyenne annuelle de la valeur de l'indice 100
# --------------------------------------------------------------------------
MOIS = {"janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "août": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12}


def extraire_point(hl: bool, derniere: int) -> None:
    wb = classeur(chemin("dgafp/FT6.2-SL_Traitement_indiciaire.xlsx", hl))
    L = lignes(wb, "F 6.2-1 Source Valeur pt indice")
    out = []
    for l in L:
        a = annee_entete(l[0])
        if a and num(l[1]):
            out.append([a[0], arrondi(num(l[1]), 2), "", "DGAFP_SL2021_POINT"])
    verifier(out[0][0] == 1970 and out[-1][0] == 2020, "point d'indice : années 1970-2020 attendues")
    # Revalorisations postérieures (rapport 2026) : valeur au 1er jour de chaque mois, puis moyenne annuelle
    wb = classeur(chemin("dgafp/ra_2026_remu_evolutions.zip", hl), "ra_2026_remu_evolutions_donnees_comp_point_indice.xlsx")
    L = lignes(wb, "Figure 1")
    hausses = []
    an = None
    for l in L:
        if annee_entete(l[0]):
            an = annee_entete(l[0])[0]
        if an and texte(l[1]).startswith("1er ") and num(l[3]):
            mois = MOIS[texte(l[1]).split()[1]]
            hausses.append((an, mois, num(l[3])))
    hausses.sort()
    verifier(hausses[-1][:2] == (2023, 7) and abs(hausses[-1][2] - 5907.34) < 0.01, "point : dernière hausse 1er juillet 2023")
    def valeur(a, m):
        v = None
        for (ah, mh, val) in hausses:
            if (ah, mh) <= (a, m):
                v = val
        return v
    # Recoupement : la moyenne recalculée pour 2018-2020 doit égaler la série longue
    for a in (2018, 2019, 2020):
        moy = sum(valeur(a, m) for m in range(1, 13)) / 12
        verifier(abs(moy - num(next(l[1] for l in out if l[0] == a))) < 0.01, f"point {a} : recalcul incohérent")
    for a in range(2021, derniere + 1):
        moy = sum(valeur(a, m) for m in range(1, 13)) / 12
        out.append([a, arrondi(moy, 2), "calcul : moyenne des 12 valeurs mensuelles (revalorisations du rapport 2026)",
                    "DGAFP_RA2026_EVOL"])
    ecrire_csv("point_indice.csv", ["annee", "valeur_annuelle_indice_100_euros", "note", "source_id"], out)


# --------------------------------------------------------------------------
# 6. Eurostat : par fonction (France) et comparaison européenne
# --------------------------------------------------------------------------
def jsonstat(p: Path):
    d = json.loads(p.read_text(encoding="utf-8"))
    ids, taille = d["id"], d["size"]
    cats = {k: list(d["dimension"][k]["category"]["index"].keys()) for k in ids}
    libs = {k: d["dimension"][k]["category"]["label"] for k in ids}

    def val(**coord):
        i = 0
        for k, s in zip(ids, taille):
            i = i * s + cats[k].index(coord[k]) if k in coord else i * s
        return d["value"].get(str(i))
    return d, cats, libs, val


def extraire_eurostat(hl: bool, comptes: dict) -> None:
    d, cats, libs, val = jsonstat(chemin("eurostat/gov_10a_exp_FR_S13_D1.json", hl))
    out = []
    ecarts = []
    for a in cats["time"]:
        tot = val(freq="A", unit="MIO_EUR", sector="S13", cofog99="TOTAL", na_item="D1", geo="FR", time=a)
        if tot is None:
            continue
        # Recoupement avec l'Insee (même concept D1 des APU). Les totaux sont identiques de 1999
        # à 2022 ; Eurostat reprend une version antérieure pour 1995-1998 (écarts de ±1 %) et
        # pour les deux dernières années (transmission antérieure à la révision de mai 2026).
        ecart = tot / 1000 - comptes["S13"]["D1"][int(a)]
        verifier(abs(ecart) < 0.02 * comptes["S13"]["D1"][int(a)], f"Eurostat {a} : total trop différent de l'Insee")
        if abs(ecart) >= 0.05:
            ecarts.append(f"{a} : {ecart:+.3f} Md€")
        s = 0
        for c in cats["cofog99"]:
            v = val(freq="A", unit="MIO_EUR", sector="S13", cofog99=c, na_item="D1", geo="FR", time=a)
            if v is None:
                continue
            niveau = 0 if c == "TOTAL" else (1 if len(c) == 4 else 2)
            if niveau == 1:
                s += v
            out.append([int(a), c, libs["cofog99"][c], niveau, arrondi(v, 1), "EUROSTAT_COFOG"])
        verifier(abs(s - tot) < 1, f"Eurostat {a} : somme des fonctions ≠ total")
    if ecarts:
        print("  écarts Eurostat (par fonction) / Insee sur le total : " + " ; ".join(ecarts))
    ecrire_csv("remunerations_par_fonction.csv",
               ["annee", "code_cofog", "fonction", "niveau", "millions_euros", "source_id"], out)

    d, cats, libs, val = jsonstat(chemin("eurostat/gov_10a_main_S13_D1PAY_PC_GDP.json", hl))
    out = []
    for g in cats["geo"]:
        for a in cats["time"]:
            v = val(freq="A", unit="PC_GDP", sector="S13", na_item="D1PAY", geo=g, time=a)
            if v is not None:
                out.append([int(a), g, libs["geo"][g], arrondi(v, 1), "EUROSTAT_GOV_MAIN"])
    ecrire_csv("remuneration_publique_europe.csv",
               ["annee", "code_pays", "pays", "remuneration_pct_pib", "source_id"], out)


# --------------------------------------------------------------------------
def main() -> int:
    hl = "--hors-ligne" in sys.argv
    try:
        print("Extraction des données de masse salariale :")
        comptes = extraire_comptes(hl)
        extraire_agregats(hl, comptes)
        extraire_depenses_dgafp(hl, comptes)
        extraire_salaires(hl)
        extraire_point(hl, max(comptes["S13"]["D1"]))
        extraire_eurostat(hl, comptes)
        lignes_ = [f"# Empreintes SHA-256 des fichiers officiels utilisés pour la masse salariale "
                   f"(téléchargés le {date.today().isoformat()} ; outils/extraire_masse_salariale.py)."]
        for nom in FICHIERS:
            p = CACHE / nom
            if p.exists():
                lignes_.append(f"  {sha256(p)}  {nom}  <{FICHIERS[nom]}>")
        EMPREINTES.write_text("\n".join(lignes_) + "\n", encoding="utf-8")
        print(f"  {EMPREINTES.relative_to(RACINE)}")
        print("Terminé. Lancer ensuite : python3 outils/construire_donnees.py")
        return 0
    except Anomalie as e:
        print(f"ANOMALIE : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
