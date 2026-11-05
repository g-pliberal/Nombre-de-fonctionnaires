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
    (France) et en % du PIB (pays européens) ;
  - DGAFP, rapport annuel 2026 : retraites des fonctionnaires (dépenses de pensions, pensions
    en paiement, ratio démographique, CAS Pensions, CNRACL, taux de cotisation, départs),
    salaires par ministère, par type de collectivité et par filière, hautes rémunérations,
    effectifs par ministère ;
  - OFGL (Observatoire des finances et de la gestion publique locales) : frais de personnel
    2024 des communes, groupements à fiscalité propre et départements, par département.

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
import http.client
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
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
OFGL = "https://data.ofgl.fr/api/explore/v2.1/catalog/datasets"
# agrégat « Frais de personnel », exercice 2024 (le champ exer est une date)
OFGL_FILTRE = urllib.parse.quote('agregat="Frais de personnel" and year(exer)=2024')

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
    "dgafp/ra_2026_retraite.zip": f"{DGAFP}/ra_2026_retraite.zip",
    "dgafp/ra_2026_postes.zip": f"{DGAFP}/ra_2026_postes.zip",
    "ofgl/communes_frais_personnel_2024_par_departement.json":
        f"{OFGL}/ofgl-base-communes-consolidee/records?select=dep_code%2C%20sum(montant_bp)%20as%20bp%2C"
        f"%20count(*)%20as%20n&where={OFGL_FILTRE}&group_by=dep_code&limit=200",
    "ofgl/departements_frais_personnel_2024.csv":
        f"{OFGL}/ofgl-base-departements-consolidee/exports/csv?select=dep_code%2Cdep_name%2Clbudg%2Csiren"
        f"%2Cmontant_bp&where={OFGL_FILTRE}&delimiter=%3B",
    "ofgl/groupements_frais_personnel_2024.csv":
        f"{OFGL}/ofgl-base-gfp-consolidee/exports/csv?select=siren%2Cepci_name%2Cnat_juridique%2Cdep_code"
        f"%2Cmontant_bp%2Cptot&where={OFGL_FILTRE}&delimiter=%3B",
}
# Adresses calculées pendant l'exécution (composition des groupements à cheval sur plusieurs départements)
URLS_CALCULEES: dict[str, str] = {}


class Anomalie(Exception):
    pass


def verifier(condition: bool, message: str) -> None:
    if not condition:
        raise Anomalie(message)


# --------------------------------------------------------------------------
# Téléchargement et lecture
# --------------------------------------------------------------------------
def telecharger(url: str, p: Path) -> None:
    """Téléchargement avec reprises (le service de l'OFGL coupe parfois les connexions)."""
    derniere = None
    for essai in range(1, 9):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fonction-publique-les-chiffres/1.0"})
            with urllib.request.urlopen(req, timeout=240) as r:
                octets = r.read()
            verifier(len(octets) > 0, f"réponse vide : {url}")
            verifier(b'"error_code"' not in octets[:500], f"erreur renvoyée par le service : {octets[:300]!r}")
            p.write_bytes(octets)
            return
        except (OSError, http.client.HTTPException) as e:
            derniere = e
            print(f"    essai {essai} échoué ({e}) ; nouvel essai dans {2 * essai} s")
            time.sleep(2 * essai)
    raise Anomalie(f"téléchargement impossible : {url} ({derniere})")


def chemin(nom: str, hors_ligne: bool, url: str | None = None) -> Path:
    if url:
        URLS_CALCULEES[nom] = url
    p = CACHE / nom
    if p.exists() and p.stat().st_size > 0:
        return p
    verifier(not hors_ligne, f"{nom} absent du cache (relancer sans --hors-ligne)")
    p.parent.mkdir(parents=True, exist_ok=True)
    url = url or FICHIERS[nom]
    print(f"  téléchargement de {url}")
    telecharger(url, p)
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
# Outils pour les tableaux « une ligne par série, une colonne par année »
# --------------------------------------------------------------------------
def sans_renvoi(lib: str) -> str:
    """Retire les appels de note : « Pensions civiles (1) », « Non ventilé2 », « FPH1 »."""
    s = re.sub(r"\s*\(\d\)\s*", " ", lib)
    return re.sub(r"(?<=[A-Za-zÀ-ÿ\)])\d$", "", " ".join(s.split())).strip()


def series_annuelles(L: list[list], ncol: int) -> tuple[list[int], list[tuple[str, dict]]]:
    """Renvoie les années et, pour chaque ligne chiffrée, le chemin de libellés des colonnes
    0 à ncol-1 (cellules fusionnées reportées vers le bas, joint par « | ») et les valeurs."""
    i_ent = next((i for i, l in enumerate(L) if len(colonnes_annees(l)) >= 5), None)
    verifier(i_ent is not None, "ligne des années introuvable")
    cols = colonnes_annees(L[i_ent])
    courant = [""] * ncol
    out = []
    for l in L[i_ent + 1:]:
        libs = [texte(l[k]) if k < len(l) else "" for k in range(ncol)]
        if libs[0].startswith(("Source", "Champ", "Lecture", "Note", "NB")):
            break
        for k, lib in enumerate(libs):
            if lib:
                courant[k] = lib
                courant[k + 1:] = [""] * (ncol - k - 1)
        vals = {a: num(l[j]) for j, (a, _) in cols.items() if j < len(l)}
        if any(v is not None for v in vals.values()):
            out.append((" | ".join(c for c in courant if c), vals))
    return sorted({a for a, _ in cols.values()}), out


def serie(S: list[tuple[str, dict]], *motifs: str) -> dict:
    res = [v for lib, v in S if all(re.search(m, lib, re.I) for m in motifs)]
    verifier(len(res) == 1, f"série {motifs} : {len(res)} lignes correspondantes au lieu d'une")
    return res[0]


def annee_titre(L: list[list]) -> int:
    for l in L[:4]:
        for c in l:
            ans = re.findall(r"\b(20\d\d)\b", texte(c))
            if ans:
                return int(ans[-1])
    raise Anomalie("année du tableau introuvable dans le titre")


# --------------------------------------------------------------------------
# 7. Retraites des fonctionnaires (DGAFP, rapport annuel 2026, « Retraites »)
# --------------------------------------------------------------------------
SRC_RET = "DGAFP_RA2026_RETRAITES"


def extraire_retraites(hl: bool) -> None:
    z = chemin("dgafp/ra_2026_retraite.zip", hl)
    fin = classeur(z, "RA2026_Retraites_donnees_comp_situation_financiere.xlsx")

    # F1 : dépenses de pensions par régime, 1990-2025 (millions d'euros)
    annees, S = series_annuelles(lignes(fin, "F1"), 2)
    verifier(annees[0] == 1990, "retraites F1 : début attendu en 1990")
    depenses = {
        "fpe_civils_et_ati": serie(S, r"PCMR", r"civiles et ATI"),
        "fpe_militaires": serie(S, r"PCMR", r"militaires"),
        "ouvriers_etat": serie(S, r"ouvriers"),
        "cnracl": serie(S, r"CNRACL", r"FPT et de la FPH"),
    }
    out = []
    for cle, v in depenses.items():
        for a in annees:
            verifier(v.get(a) is not None, f"retraites F1 : {cle} {a} manquant")
            out.append([a, cle, arrondi(v[a], 3), SRC_RET])
    ecrire_csv("retraites_depenses_pensions.csv", ["annee", "regime", "millions_euros", "source_id"], out)

    # F2 (CAS Pensions de l'État) et F3 (compte de résultat de la CNRACL), 2006-2025
    def compte(feuille: str, entetes: tuple[str, ...]):
        L = lignes(fin, feuille)
        i_ent = next(i for i, l in enumerate(L) if len(colonnes_annees(l)) >= 5)
        cols = colonnes_annees(L[i_ent])
        sens, postes, totaux, resultat = None, [], {}, None
        for l in L[i_ent + 1:]:
            lib = texte(l[0])
            if not lib:
                continue
            if lib.startswith("Source"):
                break
            vals = {a: num(l[j]) for j, (a, _) in cols.items() if j < len(l)}
            if all(v is None for v in vals.values()):
                sens = next((s for s in entetes if lib.lower().startswith(s)), sens)
                continue
            if lib.lower().startswith("total"):
                totaux[sens] = vals
            elif lib.lower().startswith("résultat"):
                resultat = vals
            else:
                postes.append((sens, sans_renvoi(lib), vals))
        return sorted(a for a, _ in cols.values()), postes, totaux, resultat

    def ecrire_compte(nom, an, postes, totaux, resultat, regles, sens_csv, tol):
        out = []
        for sens, lib, vals in postes:
            cles = [c for s, m, c in regles if s == sens and re.search(m, lib)]
            verifier(len(cles) == 1, f"{nom} : ligne « {lib} » non reconnue")
            for a in an:
                if vals.get(a) is not None:
                    out.append([a, sens_csv[sens], cles[0], lib, arrondi(vals[a], 3), SRC_RET])
        for sens in sens_csv:
            verifier(sens in totaux, f"{nom} : total « {sens} » introuvable")
            for a in an:
                s = sum(v.get(a) or 0 for s_, _, v in postes if s_ == sens)
                verifier(abs(s - totaux[sens][a]) <= tol, f"{nom} {sens} {a} : somme {s:.1f} ≠ total {totaux[sens][a]:.1f}")
                out.append([a, sens_csv[sens], "total", f"Total {sens}", arrondi(totaux[sens][a], 3), SRC_RET])
        if resultat:
            s1, s2 = list(sens_csv)
            for a in an:
                verifier(abs(totaux[s2][a] - totaux[s1][a] - resultat[a]) <= 1.5, f"{nom} {a} : résultat incohérent")
                out.append([a, "resultat", "resultat", "Résultat de l'exercice", arrondi(resultat[a], 3), SRC_RET])
        return out

    an2, postes, totaux, _ = compte("F2", ("dépenses", "recettes"))
    regles_cas = [
        ("dépenses", r"^Pensions civiles", "pensions_civiles"),
        ("dépenses", r"^Pensions militaires", "pensions_militaires"),
        ("dépenses", r"invalidité", "allocations_temporaires_invalidite"),
        ("dépenses", r"compensation démographique", "compensation_demographique"),
        ("dépenses", r"Cnav", "transferts_cnav_ircantec"),
        ("dépenses", r"vers la CNRACL", "transfert_cnracl_decentralisation"),
        ("dépenses", r"^Autres", "autres"),
        ("recettes", r"^Cotisations salariales", "cotisations_salariales"),
        ("recettes", r"État employeur", "contribution_etat_employeur"),
        ("recettes", r"La Poste", "la_poste_orange"),
        ("recettes", r"établissements publics", "etablissements_publics_autres_employeurs"),
        ("recettes", r"validations", "validations_services_auxiliaires"),
        ("recettes", r"compensation démographique", "compensation_demographique"),
        ("recettes", r"reçu de la CNRACL", "transfert_cnracl_decentralisation"),
        ("recettes", r"^Autres recettes", "autres"),
    ]
    out = ecrire_compte("retraites F2", an2, postes, totaux, None, regles_cas,
                        {"dépenses": "depense", "recettes": "recette"}, 3)
    # Recoupement : pensions civiles + ATI et pensions militaires du CAS = dépenses de la F1
    # (écarts publiés : -20 M€ en 2013 pour les civils, +10 M€ en 2012 pour les militaires)
    ecarts = []
    for a in an2:
        civ = sum(v[a] for s, lib, v in postes if s == "dépenses" and re.search(r"^Pensions civiles|invalidité", lib))
        mil = next(v[a] for s, lib, v in postes if s == "dépenses" and lib.startswith("Pensions militaires"))
        for nom, x, y in (("civils", civ, depenses["fpe_civils_et_ati"][a]), ("militaires", mil, depenses["fpe_militaires"][a])):
            verifier(abs(x - y) <= 25, f"retraites {a} : CAS {nom} ≠ F1 ({x:.0f} / {y:.0f})")
            if abs(x - y) > 1.5:
                ecarts.append(f"{a} {nom} {x - y:+.0f} M€")
    if ecarts:
        print("  écarts entre le CAS Pensions (F2) et les dépenses de pensions (F1) : " + " ; ".join(ecarts))
    ecrire_csv("retraites_cas_pensions.csv", ["annee", "sens", "poste", "libelle", "millions_euros", "source_id"], out)

    an3, postes, totaux, resultat = compte("F3", ("charges", "produits"))
    verifier(resultat is not None, "retraites F3 : résultat introuvable")
    regles_cnracl = [
        ("charges", r"^Prestations", "prestations"), ("charges", r"^Compensations", "compensations"),
        ("charges", r"article 59", "transferts_article_59"), ("charges", r"^Autres charges", "autres"),
        ("charges", r"gestion courante", "gestion_courante"), ("charges", r"financières", "financieres"),
        ("charges", r"exceptionnelles", "exceptionnelles"),
        ("produits", r"^Cotisations", "cotisations_et_produits_affectes"), ("produits", r"^Compensations", "compensations"),
        ("produits", r"article 59", "transferts_article_59"), ("produits", r"^Autres produits", "autres"),
        ("produits", r"financiers", "financiers"), ("produits", r"exceptionnels", "exceptionnels"),
    ]
    out = ecrire_compte("retraites F3", an3, postes, totaux, resultat, regles_cnracl,
                        {"charges": "charge", "produits": "produit"}, 1.5)
    ecrire_csv("retraites_cnracl_compte.csv", ["annee", "sens", "poste", "libelle", "millions_euros", "source_id"], out)

    # F4 : taux de cotisation, 2000-2025 (%)
    an4, S = series_annuelles(lignes(fin, "F4"), 2)
    taux = {
        ("pcmr", "salarie"): serie(S, r"PCMR", r"cotisation salarié"),
        ("pcmr", "employeur_civils_ministeres"): serie(S, r"PCMR", r"civiles.*ministères"),
        ("pcmr", "employeur_civils_etablissements"): serie(S, r"PCMR", r"opérateurs"),
        ("pcmr", "employeur_militaires"): serie(S, r"PCMR", r"pensions militaires"),
        ("pcmr", "employeur_ati"): serie(S, r"PCMR", r"invalidité"),
        ("ouvriers_etat", "salarie"): serie(S, r"ouvriers", r"salarié"),
        ("ouvriers_etat", "employeur"): serie(S, r"ouvriers", r"employeur"),
        ("cnracl", "salarie"): serie(S, r"CNRACL", r"salarié"),
        ("cnracl", "employeur"): serie(S, r"CNRACL", r"employeur"),
    }
    out = []
    for a in an4:
        p, c, o = taux[("pcmr", "salarie")][a], taux[("cnracl", "salarie")][a], taux[("ouvriers_etat", "salarie")][a]
        verifier(abs(p - c) < 0.001 and abs(p - o) < 0.01, f"retraites F4 {a} : taux salariés différents")
        for (reg, t), v in taux.items():
            if v.get(a) is not None:
                out.append([a, reg, t, arrondi(v[a], 4), SRC_RET])
    ecrire_csv("retraites_taux_cotisation.csv", ["annee", "regime", "taux", "taux_pct", "source_id"], out)

    # F5 : ratio démographique (cotisants / pensionnés de droit direct et dérivé), 1990-2025
    an5, S = series_annuelles(lignes(fin, "F5"), 3)
    regs = [("fpe_civils", (r"PCMR", r"Pensions civiles")), ("fpe_militaires", (r"PCMR", r"Pensions militaires")),
            ("ouvriers_etat", (r"ouvriers",)), ("cnracl_fpt", (r"CNRACL", r"\| FPT \|")),
            ("cnracl_fph", (r"CNRACL", r"\| FPH \|"))]
    out, ecarts = [], []
    for cle, m in regs:
        cot, pen, rat = serie(S, *m, r"cotisants"), serie(S, *m, r"pensionnés"), serie(S, *m, r"ratio")
        for a in an5:
            c, p, r = cot.get(a), pen.get(a), rat.get(a)
            if c is None and p is None:
                continue
            if None not in (c, p, r):  # ratios anciens publiés à 0,1 près
                verifier(abs(r - c / p) <= 0.07, f"retraites F5 {cle} {a} : ratio {r} ≠ {c}/{p}")
                if abs(r - c / p) > 0.051:
                    ecarts.append(f"{cle} {a} : publié {r}, calculé {c / p:.3f}")
            out.append([a, cle, arrondi(c, 3), arrondi(p, 3), arrondi(r, 4), SRC_RET])
    if ecarts:
        print("  ratios démographiques publiés différents du calcul cotisants / pensionnés : " + " ; ".join(ecarts))
    ecrire_csv("retraites_ratio_demographique.csv",
               ["annee", "regime", "cotisants_milliers", "pensionnes_milliers", "ratio_publie", "source_id"], out)

    # Stocks : pensions en paiement au 31 décembre (F3, 2000-2025) et caractéristiques (F1)
    st = classeur(z, "RA2026_Retraites_donnees_com_stocks.xlsx")
    an_s, S = series_annuelles(lignes(st, "F3"), 3)
    regs = [("fpe_civils", (r"PCMR", r"civiles")), ("fpe_militaires", (r"militaires",)), ("ouvriers_etat", (r"ouvriers",)),
            ("cnracl_fpt", (r"CNRACL", r"territoriale")), ("cnracl_fph", (r"CNRACL", r"hospitalière"))]
    out, stock = [], {}
    for cle, m in regs:
        tot, dd, de = serie(S, *m, r"\| Total$"), serie(S, *m, r"\| Droit direct$"), serie(S, *m, r"\| Droit dérivé$")
        stock[cle] = {"direct": dd, "derive": de}
        for a in an_s:
            verifier(abs(tot[a] - dd[a] - de[a]) <= 0.15, f"retraites stocks {cle} {a} : direct + dérivé ≠ total")
            out += [[a, cle, "total", arrondi(tot[a], 3), SRC_RET], [a, cle, "direct", arrondi(dd[a], 3), SRC_RET],
                    [a, cle, "derive", arrondi(de[a], 3), SRC_RET]]
    ecrire_csv("retraites_pensions_en_paiement.csv", ["annee", "regime", "droit", "milliers", "source_id"], out)

    L = lignes(st, "F1")
    an_c = annee_titre(L)
    i_reg = next(i for i, l in enumerate(L) if texte(l[1]).startswith("Pensions civiles"))
    attendus = ["civiles", "militaires", None, "territoriale", "hospitalière"]
    for k, mot in enumerate(attendus):
        if mot:
            verifier(mot in texte(L[i_reg][1 + k]).lower(), f"retraites stocks F1 : colonne {k + 2} inattendue")
    verifier("ouvriers" in texte(L[i_reg - 1][3]).lower(), "retraites stocks F1 : colonne des ouvriers d'État introuvable")
    ordre = ["fpe_civils", "fpe_militaires", "ouvriers_etat", "cnracl_fpt", "cnracl_fph"]
    indicateurs = [(r"^Effectifs", "effectif_milliers"), (r"^Âge moyen des bénéficiaires", "age_moyen"),
                   (r"^Âge moyen de première", "age_premiere_mise_en_paiement"),
                   (r"^Durée moyenne", "duree_services_trimestres"), (r"^Taux moyen", "taux_liquidation_pct"),
                   (r"^Indice moyen", "indice_liquidation"), (r"retraite totale", "pension_mensuelle_moyenne_euros")]
    out, droit = [], None
    for l in L[i_reg + 1:]:
        lib = texte(l[0])
        if lib.startswith("Sources"):
            break
        if lib.startswith("Pensions de droit"):
            droit = "direct" if "direct" in lib else "derive"
            continue
        vals = [num(l[1 + k]) if 1 + k < len(l) else None for k in range(5)]
        if all(v is None for v in vals):
            continue
        ind = [c for m, c in indicateurs if re.search(m, lib)]
        verifier(len(ind) == 1 and droit, f"retraites stocks F1 : ligne « {lib} » non reconnue")
        for cle, v in zip(ordre, vals):
            if v is not None:
                out.append([an_c, cle, droit, ind[0], arrondi(v, 4), SRC_RET])
                if ind[0] == "effectif_milliers":
                    verifier(abs(v - stock[cle][droit][an_c]) < 0.002, f"retraites {cle} {droit} : effectif F1 ≠ F3")
    ecrire_csv(f"retraites_caracteristiques_{an_c}.csv", ["annee", "regime", "droit", "indicateur", "valeur", "source_id"], out)

    # Montants : pension mensuelle moyenne (stocks, y compris accessoires), 2000-2025
    mt = classeur(z, "RA2026_Retraite_donnees_comp_montants_pensions.xlsx")
    L = lignes(mt, "F6")
    i_ent = next(i for i, l in enumerate(L) if len(colonnes_annees(l)) >= 5)
    cols = colonnes_annees(L[i_ent])
    regs = [(r"civiles", "fpe_civils"), (r"militaires", "fpe_militaires"), (r"ouvriers", "ouvriers_etat"),
            (r"FPT", "cnracl_fpt"), (r"FPH", "cnracl_fph")]
    out, reg, montants = [], None, {}
    for l in L[i_ent + 1:]:
        if texte(l[0]).startswith("Source"):
            break
        b = texte(l[1]) if len(l) > 1 else ""
        if not b:
            continue
        if b.lower().startswith("droit"):
            droit = "direct" if "direct" in b else "derive"
        else:
            r_ = [c for m, c in regs if re.search(m, b)]
            verifier(len(r_) == 1, f"retraites montants F6 : « {b} » non reconnu")
            reg, droit = r_[0], "ensemble"
        for j, (a, _) in cols.items():
            v = num(l[j]) if j < len(l) else None
            if v is not None:
                out.append([a, reg, droit, arrondi(v, 2), SRC_RET])
                montants[(reg, droit, a)] = v
    verifier(len({r[1] for r in out}) == 5, "retraites montants F6 : régimes manquants")
    ecrire_csv("retraites_pension_moyenne.csv", ["annee", "regime", "droit", "euros_par_mois", "source_id"], out)
    for cle in ordre:  # recoupement avec les caractéristiques (stocks F1)
        car = next(float(r[4]) for r in csv.reader(open(CSV / f"retraites_caracteristiques_{an_c}.csv", encoding="utf-8"), delimiter=";")
                   if r[1] == cle and r[2] == "direct" and r[3] == "pension_mensuelle_moyenne_euros")
        verifier(abs(car - montants[(cle, "direct", an_c)]) < 0.01, f"retraites {cle} : pension moyenne F1 ≠ F6")

    # Flux : nouvelles pensions (F4, 2000-2025), contractuels (Ircantec) et âge de départ (vue)
    fl = classeur(z, "RA2026_Retraites_donnees_comp_flux.xlsx")
    L = lignes(fl, "F4")
    i_ent = next(i for i, l in enumerate(L) if len(colonnes_annees(l)) >= 5)
    cols = colonnes_annees(L[i_ent])
    regs = [(r"^Pensions civiles", "fpe_civils"), (r"^Pensions militaires", "fpe_militaires"),
            (r"^Ouvriers", "ouvriers_etat"), (r"territoriale", "cnracl_fpt"), (r"hospitalière", "cnracl_fph")]
    out, flux, reg = [], defaultdict(dict), None
    for l in L[i_ent + 1:]:
        if texte(l[0]).startswith("Source"):
            break
        b = texte(l[1]) if len(l) > 1 else ""
        if not b:
            continue
        if b.startswith("Effectifs"):
            droit = "direct" if "direct" in b else "derive"
        else:
            r_ = [c for m, c in regs if re.search(m, b)]
            verifier(len(r_) == 1, f"retraites flux F4 : « {b} » non reconnu")
            reg, droit = r_[0], "total"
        for j, (a, _) in cols.items():
            v = num(l[j]) if j < len(l) else None
            if v is not None:
                flux[(reg, droit)][a] = v
                out.append([a, reg, droit, arrondi(v, 3), SRC_RET])
    for reg in ordre:
        for a, t in flux[(reg, "total")].items():
            verifier(abs(t - flux[(reg, "direct")][a] - flux[(reg, "derive")][a]) <= 0.11,
                     f"retraites flux {reg} {a} : direct + dérivé ≠ total")
    vue = classeur(z, "ra_2026_vue_flux_de_personnels_retraites.xlsx")
    L = lignes(vue, "Figure 2")
    i_ent = next(i for i, l in enumerate(L) if len(colonnes_annees(l)) >= 5)
    cols = colonnes_annees(L[i_ent])
    regs = [(r"civils", "fpe_civils"), (r"Militaires", "fpe_militaires"), (r"Ouvriers", "ouvriers_etat"),
            (r"^FPT", "cnracl_fpt"), (r"^FPH", "cnracl_fph"), (r"Ircantec", "ircantec")]
    vus = set()
    for l in L[i_ent + 1:]:
        b = texte(l[1]) if len(l) > 1 else ""
        if b.startswith("Source"):
            break
        if not b:
            continue
        r_ = [c for m, c in regs if re.search(m, b)]
        verifier(len(r_) == 1, f"retraites vue figure 2 : « {b} » non reconnu")
        vus.add(r_[0])
        for j, (a, _) in cols.items():
            v = num(l[j]) if j < len(l) else None
            if v is None:
                continue
            if r_[0] == "ircantec":
                out.append([a, "ircantec", "direct", arrondi(v, 3), SRC_RET])
            else:
                verifier(abs(v - flux[(r_[0], "direct")][a]) <= 0.06, f"retraites {r_[0]} {a} : vue ≠ données complémentaires")
    verifier(len(vus) == 6, "retraites vue figure 2 : lignes manquantes")
    ecrire_csv("retraites_nouvelles_pensions.csv", ["annee", "regime", "droit", "milliers", "source_id"], out)

    L = lignes(vue, "Figure 7")
    i_ent = next(i for i, l in enumerate(L) if len(colonnes_annees(l)) >= 5)
    cols = colonnes_annees(L[i_ent])
    motifs = [(r"^Sédentaire", "sedentaire"), (r"^Actif", "actif"), (r"^Carrière longue", "carriere_longue"),
              (r"^Ens", "ensemble")]
    out = []
    for l in L[i_ent + 1:]:
        b = texte(l[1]) if len(l) > 1 else ""
        if b.startswith("Source"):
            break
        if not b:
            continue
        m_ = [c for m, c in motifs if re.search(m, b)]
        verifier(len(m_) == 1, f"retraites vue figure 7 : « {b} » non reconnu")
        for j, (a, _) in cols.items():
            v = num(l[j]) if j < len(l) else None
            if v is not None:
                out.append([a, m_[0], arrondi(v, 3), SRC_RET])
    verifier(len({r[1] for r in out}) == 4, "retraites vue figure 7 : motifs manquants")
    ecrire_csv("retraites_age_depart.csv", ["annee", "motif", "age_moyen", "source_id"], out)


# --------------------------------------------------------------------------
# 8. Salaires par ministère, type de collectivité et filière ; hautes rémunérations ;
#    effectifs par ministère (DGAFP, rapport annuel 2026)
# --------------------------------------------------------------------------
def moyenne_ponderee_ok(parts: list[float], salaires: list[float], ensemble: float, nom: str) -> None:
    verifier(abs(sum(parts) - 100) <= 0.01, f"{nom} : les parts d'effectifs ne totalisent pas 100 ({sum(parts):.3f})")
    m = sum(p * s for p, s in zip(parts, salaires)) / 100
    verifier(abs(m - ensemble) <= 0.5, f"{nom} : moyenne pondérée {m:.2f} ≠ ensemble publié {ensemble:.2f}")


def extraire_detail_salaires(hl: bool) -> None:
    zn = chemin("dgafp/ra_2026_remu_niveaux.zip", hl)
    vue = classeur(zn, "ra_2026_vue_renumerations_niveaux.xlsx")
    SRC = "DGAFP_RA2026_REMU"

    # Figure 6 : ministères et EPA de l'État
    L = lignes(vue, "Figure 6")
    an = annee_titre(L)
    i0 = next(i for i, l in enumerate(L) if texte(l[1]).startswith("Départements ministériels"))
    i_ens = next(i for i, l in enumerate(L) if i > i0 and texte(l[1]) == "Ensemble")
    verifier(texte(L[i0][2]) == "Ministères" and "EPA" in texte(L[i0][4]), "salaires figure 6 : colonnes inattendues")
    verifier("EQTP" in texte(L[i0 + 1][2]) and "net" in texte(L[i0 + 1][3]), "salaires figure 6 : indicateurs inattendus")
    out = []
    for per, jp, js in (("ministeres", 2, 3), ("epa", 4, 5)):
        parts, sal = [], []
        for l in L[i0 + 2:i_ens]:
            lib = sans_renvoi(texte(l[1]))
            if lib:
                parts.append(num(l[jp]))
                sal.append(num(l[js]))
                out.append([an, "fpe", per, lib, arrondi(parts[-1], 4), arrondi(sal[-1], 2), SRC])
        moyenne_ponderee_ok(parts, sal, num(L[i_ens][js]), f"figure 6 {per}")
        out.append([an, "fpe", per, "Ensemble", 100, arrondi(num(L[i_ens][js]), 2), SRC])

    # Figure 8 : FPT par type d'employeur et par filière
    L = lignes(vue, "Figure 8")
    verifier(annee_titre(L) == an, "salaires figure 8 : année différente")
    i_ens = next(i for i, l in enumerate(L) if texte(l[1]) == "Ensemble")
    for dim, jl, jp, js in (("employeur", 1, 2, 3), ("filiere", 5, 6, 7)):
        verifier(num(L[i_ens][jp]) == 100, f"salaires figure 8 {dim} : ligne Ensemble attendue")
        parts, sal = [], []
        for l in L[i_ens + 1:]:
            lib = sans_renvoi(texte(l[jl])) if jl < len(l) else ""
            if not lib or num(l[jp]) is None:
                break
            parts.append(num(l[jp]))
            sal.append(num(l[js]))
            out.append([an, "fpt", dim, lib, arrondi(parts[-1], 4), arrondi(sal[-1], 2), SRC])
        if dim == "employeur":
            moyenne_ponderee_ok(parts, sal, num(L[i_ens][js]), "figure 8 employeurs")
        else:  # la DGAFP ne publie pas toutes les filières (animation, hors filière…)
            verifier(80 < sum(parts) < 100, "figure 8 filières : total inattendu")
        out.append([an, "fpt", dim, "Ensemble", 100, arrondi(num(L[i_ens][js]), 2), SRC])

    # Figure 9 : FPH par filière, hôpitaux / établissements médico-sociaux / ensemble
    L = lignes(vue, "Figure 9")
    verifier(annee_titre(L) == an, "salaires figure 9 : année différente")
    i_sect = next(i for i, l in enumerate(L) if texte(l[2]) == "Hôpitaux publics")
    i_ens = next(i for i, l in enumerate(L) if texte(l[1]) == "Ensemble")
    for sect, jp, js in (("filiere_hopitaux", 2, 3), ("filiere_medico_social", 4, 5), ("filiere", 6, 7)):
        verifier(texte(L[i_sect][jp]) in ("Hôpitaux publics", "Établissements médico-sociaux", "FPH"), "figure 9 : colonnes")
        parts, sal = [], []
        for l in L[i_ens + 1:]:
            lib = sans_renvoi(texte(l[1]))
            if not lib or num(l[jp]) is None:
                break
            parts.append(num(l[jp]))
            sal.append(num(l[js]))
            out.append([an, "fph", sect, lib, arrondi(parts[-1], 4), arrondi(sal[-1], 2), SRC])
        moyenne_ponderee_ok(parts, sal, num(L[i_ens][js]), f"figure 9 {sect}")
        out.append([an, "fph", sect, "Ensemble", 100, arrondi(num(L[i_ens][js]), 2), SRC])
    ecrire_csv(f"salaires_par_employeur_et_filiere_{an}.csv",
               ["annee", "versant", "dimension", "categorie", "part_eqtp_pct", "salaire_net_moyen", "source_id"], out)

    # Encadré 2 : le dernier centile (1 % des postes les mieux rémunérés)
    L = lignes(vue, "E2 - FigA")
    i0 = next(i for i, l in enumerate(L) if texte(l[2]).startswith("Limite inférieure"))
    out = []
    for l in L[i0 + 1:]:
        lib = texte(l[1])
        if lib.startswith("Source"):
            break
        if lib in ("FPE", "FPT", "FPH", "Ensemble FP"):
            out.append([an, {"Ensemble FP": "ensemble"}.get(lib, lib.lower()), arrondi(num(l[2]), 2),
                        arrondi(num(l[3]), 2), arrondi(num(l[4]), 2), SRC])
    verifier(len(out) == 4, "encadré 2 figure A : 4 lignes attendues")
    ecrire_csv(f"hautes_remunerations_dernier_centile_{an}.csv",
               ["annee", "versant", "seuil_net_mensuel", "net_moyen", "net_median", "source_id"], out)

    L = lignes(vue, "E2 - FigB")
    i0 = next(i for i, l in enumerate(L) if texte(l[2]).startswith("Ensemble de la fonction publique"))
    out, groupe, sommes = [], None, defaultdict(lambda: [0.0, 0.0, 0.0])
    for l in L[i0 + 1:]:
        lib = sans_renvoi(texte(l[1]))
        if lib.startswith("Source"):
            break
        if not lib:
            continue
        v = [num(l[j]) for j in (2, 3, 4)]
        if all(x is None for x in v):
            groupe = lib
            continue
        out.append([an, groupe, lib] + [arrondi(x, 3) for x in v] + [SRC])
        for k in range(3):
            sommes[groupe][k] += v[k]
    verifier(set(sommes) == {"Sexe", "Statut", "Âge"}, "encadré 2 figure B : groupes inattendus")
    for g, s in sommes.items():
        verifier(all(abs(x - 100) <= 0.01 for x in s), f"encadré 2 figure B {g} : total ≠ 100")
    ecrire_csv(f"hautes_remunerations_profil_{an}.csv",
               ["annee", "groupe", "modalite", "ensemble_fp_pct", "dix_pour_cent_mieux_payes_pct",
                "un_pour_cent_mieux_payes_pct", "source_id"], out)

    L = lignes(vue, "E2 - FigC")
    i0 = next(i for i, l in enumerate(L) if texte(l[2]).startswith("Salaire net moyen"))
    out, parent = [], None
    for l in L[i0 + 1:]:
        lib = sans_renvoi(texte(l[1]))
        if lib.startswith("Source"):
            break
        if not lib:
            continue
        if lib in ("Catégorie A+", "Hors A+"):
            niveau, parent = 0, lib
        elif parent == "Catégorie A+" and lib in ("FPE", "FPT", "FPH"):
            niveau = 1
        else:
            niveau = 2 if parent == "Catégorie A+" else 1
        out.append([an, niveau, lib, arrondi(num(l[2]), 2), arrondi(num(l[3]), 3), arrondi(num(l[4]), 3), SRC])
    part = {r[2]: float(r[5]) for r in out if r[1] <= 1}
    verifier(abs(part["Catégorie A+"] + part["Hors A+"] - 100) <= 0.01, "encadré 2 figure C : A+ + hors A+ ≠ 100")
    verifier(abs(part["FPE"] + part["FPT"] + part["FPH"] - part["Catégorie A+"]) <= 0.01, "encadré 2 figure C : A+")
    ecrire_csv(f"hautes_remunerations_corps_{an}.csv",
               ["annee", "niveau", "corps_ou_emploi", "salaire_net_moyen", "part_des_agents_dans_le_dernier_centile_pct",
                "part_du_dernier_centile_pct", "source_id"], out)

    # Salaires des emplois et corps A+ (données complémentaires, figure 10)
    wb = classeur(zn, "ra_2026_remu_niveaux_donnees_comp.xlsx")
    L = lignes(wb, "Figure 10")
    verifier(annee_titre(L) == an, "figure 10 : année différente")
    i0 = next(i for i, l in enumerate(L) if texte(l[1]) == "Salaire brut moyen")
    verifier(texte(L[i0][3]) == "Salaire net moyen" and texte(L[i0][4]) == "Salaire net médian", "figure 10 : colonnes")
    out = []
    for l in L[i0 + 1:]:
        lib = sans_renvoi(texte(l[0]))
        if lib.startswith("Source"):
            break
        if not lib or num(l[1]) is None:
            continue
        niveau = (0 if lib.startswith("Total") else 1 if lib.startswith("Catégorie A+") else
                  2 if re.match(r"Encadrement supérieur et emplois de di|Enseignement supérieur|Médecins territoriaux", lib) else 3)
        out.append([an, niveau, lib, arrondi(num(l[1]), 2), arrondi(num(l[2]), 3), arrondi(num(l[3]), 2),
                    arrondi(num(l[4]), 2), SRC])
    verifier(len(out) >= 15, "figure 10 : lignes manquantes")
    ecrire_csv(f"salaires_a_plus_{an}.csv",
               ["annee", "niveau", "corps_ou_emploi", "brut_moyen", "part_primes_pct", "net_moyen", "net_median", "source_id"],
               out)

    # Les dix plus hautes rémunérations publiées par les employeurs (2025)
    L = lignes(vue, "E2 - FigD")
    an_d = annee_titre(L)
    i0 = next(i for i, l in enumerate(L) if texte(l[2]).startswith("Moyenne de la somme"))
    synth = {}
    for l in L[i0 + 1:]:
        lib = texte(l[1])
        if lib.startswith("Source"):
            break
        m = re.match(r"(FPE|FPT|FPH)\s*:", lib)
        if m:
            synth[m.group(1)] = (num(l[2]), num(l[3]), num(l[4]), sans_renvoi(lib))
    verifier(set(synth) == {"FPE", "FPT", "FPH"}, "encadré 2 figure D : versants manquants")
    for v, (moy, mens, _, _) in synth.items():
        verifier(abs(moy / 120 - mens) <= 0.5, f"encadré 2 figure D {v} : mensuel ≠ somme / 120")
    wb = classeur(zn, "ra_2026_remu_niveaux_donnees_comp_hautes_remu.xlsx")
    verifier(annee_titre(lignes(wb, "FPE")) == an_d, "dix plus hautes rémunérations : année différente")
    out = []
    L = lignes(wb, "FPE")
    i0 = next(i for i, l in enumerate(L) if texte(l[0]) == "Département ministériel")
    sommes = []
    for l in L[i0 + 1:]:
        lib = texte(l[0])
        if not lib or lib.startswith(("*", "Source")):
            break
        s, f, h = num(l[1]), num(l[2]), num(l[3])
        if lib == "Ensemble":
            verifier(abs(s - sum(sommes) / len(sommes)) <= 1, "dix plus hautes rémunérations FPE : moyenne")
            verifier(abs(s - synth["FPE"][0]) <= 1, "dix plus hautes rémunérations FPE : ≠ figure D")
            continue
        verifier(f + h == 10, f"dix plus hautes rémunérations {lib} : {f} + {h} ≠ 10")
        sommes.append(s)
        out.append([an_d, "fpe", "", lib, arrondi(s, 2), int(f), int(h), SRC])
    L = lignes(wb, "FPH")
    i0 = next(i for i, l in enumerate(L) if texte(l[0]).startswith("SIREN"))
    for l in L[i0 + 1:]:
        if not texte(l[0]) or texte(l[0]).startswith("Source"):
            break
        f, h = num(l[3]), num(l[4])
        verifier(f + h == 10, f"dix plus hautes rémunérations {texte(l[1])} : {f} + {h} ≠ 10")
        out.append([an_d, "fph", texte(l[0]), texte(l[1]), arrondi(num(l[2]), 2), int(f), int(h), SRC])
    verifier(sum(1 for r in out if r[1] == "fph") >= 100, "dix plus hautes rémunérations FPH : lignes manquantes")
    ecrire_csv(f"dix_plus_hautes_remunerations_{an_d}.csv",
               ["annee", "versant", "siren", "employeur", "somme_dix_plus_hautes_brutes_euros", "femmes", "hommes",
                "source_id"], out)
    ecrire_csv(f"dix_plus_hautes_remunerations_synthese_{an_d}.csv",
               ["annee", "versant", "champ", "moyenne_somme_dix_plus_hautes_euros", "brut_mensuel_moyen_euros",
                "part_femmes_pct", "source_id"],
               [[an_d, v.lower(), synth[v][3], arrondi(synth[v][0], 2), arrondi(synth[v][1], 2), arrondi(synth[v][2], 1), SRC]
                for v in ("FPE", "FPT", "FPH")])

    # Effectifs des départements ministériels par statut (postes, figure 2 « statut »)
    zp = chemin("dgafp/ra_2026_postes.zip", hl)
    wb = classeur(zp, "ra2026_caracteristiques_postes_donnees_comp_FPE.xlsx")
    L = lignes(wb, "Figure 2 statut")
    i_ent = next(i for i, l in enumerate(L) if texte(l[1]) == "Fonctionnaires")
    an_e, an_p = annee_entete(L[i_ent - 1][1])[0], annee_entete(L[i_ent - 1][6])[0]
    verifier(texte(L[i_ent][2]) == "Contractuels" and texte(L[i_ent][3]).startswith("Militaires")
             and texte(L[i_ent][5]) == "Total", "effectifs par ministère : colonnes inattendues")
    out, total = [], None
    for l in L[i_ent + 1:]:
        lib = sans_renvoi(texte(l[0]))
        if not lib or lib.startswith("Source"):
            break
        v = [num(l[j]) for j in range(1, 7)]
        verifier(abs(sum(v[:4]) - v[4]) <= 0.003, f"effectifs par ministère {lib} : somme des statuts ≠ total")
        if lib == "Total":
            total = v
            continue
        if lib.startswith("Total hors enseignants"):
            out.append([an_e, lib, 0] + [arrondi(x, 3) for x in v] + ["DGAFP_RA2026_POSTES"])
            continue
        niveau = 1 if re.match(r"Solidarités|Travail", lib) else 0
        out.append([an_e, lib, niveau] + [arrondi(x, 3) for x in v] + ["DGAFP_RA2026_POSTES"])
    verifier(total is not None, "effectifs par ministère : ligne Total introuvable")
    s0 = sum(float(r[7]) for r in out if r[2] == 0 and not r[1].startswith("Total"))
    verifier(abs(s0 - total[4]) <= 0.01, f"effectifs par ministère : somme {s0:.3f} ≠ total {total[4]:.3f}")
    soc = next(float(r[7]) for r in out if r[1] == "Ministères sociaux")
    verifier(abs(sum(float(r[7]) for r in out if r[2] == 1) - soc) <= 0.002, "effectifs : ministères sociaux ≠ somme")
    out.append([an_e, "Total", 0] + [arrondi(x, 3) for x in total] + ["DGAFP_RA2026_POSTES"])
    ecrire_csv(f"effectifs_par_ministere_{an_e}.csv",
               ["annee", "ministere", "niveau", "fonctionnaires_milliers", "contractuels_milliers", "militaires_milliers",
                "autres_milliers", "total_milliers", f"total_{an_p}_milliers", "source_id"], out)


# --------------------------------------------------------------------------
# 9. Frais de personnel des collectivités locales par département (OFGL, 2024)
# --------------------------------------------------------------------------
def departement_de_commune(insee: str) -> str:
    return insee[:3] if insee.startswith("97") else insee[:2]


def lire_csv_ofgl(p: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(p.read_text(encoding="utf-8-sig")), delimiter=";"))


def extraire_ofgl(hl: bool) -> None:
    SRC = "OFGL_COMPTES_2024"
    an = 2024
    noms, pop = {}, {}
    with open(CSV / "departements_population.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            noms[r["code"]] = r["departement"]
            if r["annee_1er_janvier"] == str(an):
                pop[r["code"]] = int(r["population"])
    verifier(len(noms) == 101 and len(pop) == 101, "departements_population.csv : 101 départements attendus")

    # Communes (agrégées par département par le service de l'OFGL)
    d = json.loads(chemin("ofgl/communes_frais_personnel_2024_par_departement.json", hl).read_text(encoding="utf-8"))
    communes = {r["dep_code"]: float(r["bp"] or 0) for r in d["results"]}
    verifier(set(communes) == set(noms), "OFGL communes : départements manquants ou inconnus")

    # Départements : la Ville de Paris (75, déjà comptée parmi les communes) et la Métropole de Lyon
    # (691, déjà comptée parmi les groupements) sont écartées pour ne pas les compter deux fois.
    departements, ecartes, alsace = {}, [], None
    for r in lire_csv_ofgl(chemin("ofgl/departements_frais_personnel_2024.csv", hl)):
        code, m = r["dep_code"], float(r["montant_bp"] or 0)
        if code in ("75", "691"):
            ecartes.append((code, r["lbudg"], m))
            continue
        if code == "67A":  # Collectivité européenne d'Alsace : Bas-Rhin et Haut-Rhin réunis depuis 2021
            alsace = m
            continue
        verifier(code in noms and code not in departements, f"OFGL départements : code {code} inattendu")
        departements[code] = m
    verifier(alsace is not None and "67" not in departements and "68" not in departements,
             "OFGL départements : Collectivité européenne d'Alsace attendue (67A)")
    for code in ("67", "68"):  # répartie au prorata de la population au 1er janvier 2024
        departements[code] = alsace * pop[code] / (pop["67"] + pop["68"])
    verifier(len(ecartes) == 2, "OFGL départements : Ville de Paris et Métropole de Lyon attendues")
    verifier(abs(communes["75"] - next(m for c, _, m in ecartes if c == "75")) < 1, "Ville de Paris : montants différents")
    sans_dep = sorted(set(noms) - set(departements) - {"75"})
    verifier(sans_dep == ["2A", "2B", "972", "973"], f"OFGL départements : absents inattendus {sans_dep}")

    # Groupements à fiscalité propre (y compris Métropole du Grand Paris et établissements publics territoriaux)
    gfp = lire_csv_ofgl(chemin("ofgl/groupements_frais_personnel_2024.csv", hl))
    verifier(len({r["siren"] for r in gfp}) == len(gfp), "OFGL groupements : doublons")
    lyon = [r for r in gfp if r["epci_name"] == "Métropole de Lyon"]
    verifier(len(lyon) == 1 and abs(float(lyon[0]["montant_bp"]) - next(m for c, _, m in ecartes if c == "691")) < 1,
             "Métropole de Lyon : montants différents entre les bases")
    multi = [r for r in gfp if "," in r["dep_code"]]
    liste = ",".join(f'"{r["siren"]}"' for r in multi)
    where = urllib.parse.quote(f"year(annee)=2024 and siren_epci in ({liste})")
    url = (f"{OFGL}/detail_compositions_intercommunales_2012_2025/exports/csv?select=siren_epci%2Cinsee%2Cptot"
           f"&where={where}&delimiter=%3B")
    compo = lire_csv_ofgl(chemin("ofgl/composition_groupements_multidepartementaux_2024.csv", hl, url))
    pops = defaultdict(lambda: defaultdict(int))
    for r in compo:
        pops[r["siren_epci"]][departement_de_commune(r["insee"])] += int(float(r["ptot"] or 0))
    groupements = defaultdict(float)
    detail = []
    for r in gfp:
        m = float(r["montant_bp"] or 0)
        codes = r["dep_code"].split(",")
        if len(codes) == 1:
            verifier(codes[0] in noms, f"OFGL groupements : département {codes[0]} inconnu")
            groupements[codes[0]] += m
            continue
        p = pops.get(r["siren"])
        verifier(p and set(p) == set(codes), f"composition de {r['epci_name']} ({r['siren']}) incohérente : {dict(p or {})}")
        tot = sum(p.values())
        for c in sorted(p):
            groupements[c] += m * p[c] / tot
            detail.append([an, r["siren"], r["epci_name"], c, p[c], arrondi(p[c] / tot, 6), arrondi(m * p[c] / tot, 2), SRC])
    tot_gfp = sum(float(r["montant_bp"] or 0) for r in gfp)
    verifier(abs(sum(groupements.values()) - tot_gfp) < 1, "OFGL groupements : la répartition ne redonne pas le total")

    # Recoupement avec les totaux nationaux de la DGCL repris par la DGAFP (milliards, arrondis à 0,1)
    with open(CSV / "depenses_personnel_collectivites.csv", encoding="utf-8") as f:
        dgcl = next(r for r in csv.DictReader(f, delimiter=";") if r["annee"] == str(an))
    for nom, val, cle in (("communes", sum(communes.values()), "communes"), ("groupements", tot_gfp, "groupements"),
                          ("départements", sum(departements.values()), "departements")):
        verifier(abs(val / 1e9 - float(dgcl[cle])) <= 0.06, f"OFGL {nom} : {val / 1e9:.3f} Md€ ≠ DGCL {dgcl[cle]}")

    notes = {
        "75": "Ville de Paris : commune et département réunis, comptés une seule fois (communes)",
        "69": "Métropole de Lyon comptée avec les groupements ; le département du Rhône hors métropole avec les départements",
        "2A": "pas de conseil départemental : la collectivité de Corse est comptée avec les régions (non incluses)",
        "2B": "pas de conseil départemental : la collectivité de Corse est comptée avec les régions (non incluses)",
        "972": "pas de conseil départemental : la collectivité territoriale de Martinique est comptée avec les régions (non incluses)",
        "973": "pas de conseil départemental : la collectivité territoriale de Guyane est comptée avec les régions (non incluses)",
        "976": "le Département de Mayotte exerce aussi les compétences d'une région",
        "67": "Collectivité européenne d'Alsace (Bas-Rhin et Haut-Rhin réunis) répartie au prorata de la population",
        "68": "Collectivité européenne d'Alsace (Bas-Rhin et Haut-Rhin réunis) répartie au prorata de la population",
    }
    out = []
    for code in sorted(noms, key=lambda c: (len(c) > 2 and c.startswith("97"), c)):
        c_, g_, d_ = communes.get(code, 0.0), groupements.get(code, 0.0), departements.get(code)
        out.append([an, code, noms[code], arrondi(c_, 2), arrondi(g_, 2), "" if d_ is None else arrondi(d_, 2),
                    arrondi(c_ + g_ + (d_ or 0), 2), notes.get(code, ""), SRC])
    ecrire_csv("depenses_personnel_locales_departements_2024.csv",
               ["annee", "code", "departement", "communes_euros", "groupements_fiscalite_propre_euros", "departement_euros",
                "total_euros", "note", "source_id"], out)
    ecrire_csv("groupements_multidepartementaux_2024.csv",
               ["annee", "siren", "groupement", "code_departement", "population_communes_membres", "part",
                "frais_personnel_affectes_euros", "source_id"], detail)


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
        extraire_retraites(hl)
        extraire_detail_salaires(hl)
        extraire_ofgl(hl)
        lignes_ = [f"# Empreintes SHA-256 des fichiers officiels utilisés pour la masse salariale "
                   f"(téléchargés le {date.today().isoformat()} ; outils/extraire_masse_salariale.py)."]
        for nom, url in list(FICHIERS.items()) + list(URLS_CALCULEES.items()):
            p = CACHE / nom
            if p.exists():
                lignes_.append(f"  {sha256(p)}  {nom}  <{url}>")
        EMPREINTES.write_text("\n".join(lignes_) + "\n", encoding="utf-8")
        print(f"  {EMPREINTES.relative_to(RACINE)}")
        print("Terminé. Lancer ensuite : python3 outils/construire_donnees.py")
        return 0
    except Anomalie as e:
        print(f"ANOMALIE : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
