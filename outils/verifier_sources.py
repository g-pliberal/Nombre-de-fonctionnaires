#!/usr/bin/env python3
"""Vérifie si les fichiers officiels utilisés par le site ont changé depuis leur téléchargement.

Le script relit les empreintes SHA-256 enregistrées dans donnees/empreintes_*.txt,
re-télécharge chaque fichier à son adresse officielle (Insee, DGAFP, OFGL, OCDE, Eurostat…)
et compare l'empreinte obtenue à celle du dépôt. Il ne modifie aucun fichier du dépôt et
ne touche à aucun chiffre : il signale seulement qu'une source a bougé (nouvelle édition,
révision, fichier déplacé), pour qu'une personne décide s'il faut mettre les données à jour.

Les lignes des fichiers d'empreintes qui indiquent leur adresse (« <https://…> ») sont
téléchargées à cette adresse. Pour donnees/empreintes_fichiers_sources.txt, qui ne les
indique pas, les adresses sont reprises des documents de méthode (table ADRESSES ci-dessous).
Un fichier extrait d'une archive zip (« dossier/archive/fichier.xlsx ») est comparé après
extraction de l'archive téléchargée.

Usage :
    python3 outils/verifier_sources.py                       # rapport à l'écran
    python3 outils/verifier_sources.py --rapport rapport.md  # écrit aussi un rapport Markdown
Code de sortie : 0 si rien n'a changé, 1 si au moins un fichier a changé ou est inaccessible.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "donnees"
FICHIERS_EMPREINTES = sorted(DONNEES.glob("empreintes_*.txt"))

ARCH = "https://www.fonction-publique.gouv.fr/files/files/ArchivePortailFP/www.fonction-publique.gouv.fr/files/files/statistiques"
SL2021 = f"{ARCH}/series_longues/series-longues-2021"
RA2026 = "https://www.fonction-publique.gouv.fr/files/files/publications/vue-rapport-annuel/2026"
INSEE = "https://www.insee.fr/fr/statistiques/fichier"

# Adresses des fichiers de donnees/empreintes_fichiers_sources.txt (d'après
# donnees/methodologie_series_nationales.md et donnees/methodologie_departements.md).
ADRESSES = {
    "insee_2493501_marc-empl-eff-fonc-pub.xlsx": f"{INSEE}/2493501/marc-empl-eff-fonc-pub.xlsx",
    "ip2094/IP2094.xlsx": f"{INSEE}/8732435/IP2094.xlsx",
    "ip2094/IP2052.xlsx": f"{INSEE}/8572076/IP2052.xlsx",
    "ip2094/8214842_IP2003.xlsx": f"{INSEE}/8214842/IP2003.xlsx",
    "ip2094/7621088_donnees_insee_premiere_n1947.xlsx": f"{INSEE}/7621088/donnees_insee_premiere_n1947.xlsx",
    "ip2094/6215551_ip1897.xlsx": f"{INSEE}/6215551/ip1897.xlsx",
    "ip2094/5232488_ip1842.xlsx": f"{INSEE}/5232488/ip1842.xlsx",
    "ip2094/4477497_ip1797.xlsx": f"{INSEE}/4477497/ip1797.xlsx",
    "ip2094/3747060_ip1741.xls": f"{INSEE}/3747060/ip1741.xls",
    "ra2026/ra_2026_effectifs.zip": f"{RA2026}/ra_2026_effectifs.zip",
    "ra2026/ra_2026_postes.zip": f"{RA2026}/ra_2026_postes.zip",
    "ed2026/ra_2026_postes.zip": f"{RA2026}/ra_2026_postes.zip",
    "sl2021/FT1.1-SL_Effectifs.xlsx": f"{SL2021}/FT1.1-SL_Effectifs.xlsx",
    "sl2021/FT1.2-SL_Effectifs_ensemble_FP.xlsx": f"{SL2021}/FT1.2-SL_Effectifs_ensemble_FP.xlsx",
    "sl2021/FT2.1-SL_Statut.xlsx": f"{SL2021}/FT2.1-SL_Statut.xlsx",
    "sl2021/FT2.2-SL_Categories_hierarchiques.xlsx": f"{SL2021}/FT2.2-SL_Categories_hierarchiques.xlsx",
    "sl2021/FT1.2-3-SL_Localisation_ensemble.xlsx": f"{SL2021}/FT1.2-3-SL_Localisation_ensemble.xlsx",
    "datagouv/FT1.2-SL_Effectifs_ensemble_FP.xls":
        "https://data.economie.gouv.fr/api/v2/catalog/datasets/effectifs-dans-la-fonction-publique/attachments/ft1_2_sl_effectifs_ensemble_fp_1_xls",
    "old/resulstats_series-longues_2007.pdf": f"{ARCH}/resulstats/resulstats_series-longues_2007.pdf",
    "old/ccomptes_effectifs_etat_1980_2008.pdf": "https://www.vie-publique.fr/files/rapport/pdf/094000601.pdf",
    "old/insee_es369d.pdf": f"{INSEE}/1376009/es369d.pdf",
    "cc/Chiffres_cles_2005.pdf": f"{ARCH}/chiffres_cles/pdf/Chiffres_cles_2005.pdf",
    "cc/Chiffres_cles_2008.pdf": f"{ARCH}/chiffres_cles/pdf/Chiffres_cles_2008.pdf",
    "cc/Chiffres_cles_2009.pdf": f"{ARCH}/chiffres_cles/pdf/Chiffres_cles_2009.pdf",
    "cc/chiffres_cles_2011-v2.pdf": f"{ARCH}/chiffres_cles/pdf/chiffres_cles_2011-v2.pdf",
    "cc/chiffres-cles-2012.pdf": f"{ARCH}/chiffres_cles/pdf/chiffres-cles-2012.pdf",
    "ra_old/RA_2005-2006_trois_FP.pdf": f"{ARCH}/rapports_annuels/2005-2006/RA_2005-2006_trois_FP.pdf",
    "ra_old/ran02.pdf": f"{ARCH}/rapports_annuels/ran02.pdf",
    "pop/estim-pop-nreg-sexe-gca-1975-2026.xlsx": f"{INSEE}/8721456/estim-pop-nreg-sexe-gca-1975-2026.xlsx",
    "insee_pop/estim-pop-dep-sexe-gca-1975-2026.xlsx": f"{INSEE}/8721456/estim-pop-dep-sexe-gca-1975-2026.xlsx",
    "ed2011/RA2010-2011_COMPLEMENT_Effectifs_physiques_ETP_3FP_dep_2005_2009_20120530.xls":
        f"{ARCH}/rapports_annuels/2010-2011/xls/RA2010-2011_COMPLEMENT_Effectifs_physiques_ETP_3FP_dep_2005_2009_20120530.xls",
}

# Séries de la base BDM de l'Insee (format SDMX) : la réponse porte dans son en-tête l'heure
# à laquelle elle a été préparée, donc ses octets changent à chaque téléchargement. On compare
# alors les observations (période, valeur) à une empreinte de référence, calculée par
# empreinte_observations() (None : pas de référence ; le script affiche alors celle qu'il
# obtient, à recopier ici après avoir vérifié que les valeurs sont celles utilisées).
OBSERVATIONS_SDMX: dict[str, str | None] = {
    "insee/ipc_coefficient_011813530.xml": "567edd0238d657d29cf150a398a34e5772be43f904f0876fb788226d7e721c6b",
}
OBS = re.compile(r'TIME_PERIOD="([^"]+)"\s+OBS_VALUE="([^"]*)"')


def empreinte_observations(contenu: bytes) -> str:
    obs = sorted(OBS.findall(contenu.decode("utf-8", errors="replace")))
    return hashlib.sha256("\n".join(f"{p};{v}" for p, v in obs).encode()).hexdigest()


LIGNE = re.compile(r"^\s*([0-9a-f]{64})\s+(\S+)(?:\s+<(\S+)>)?\s*$")


@dataclass
class Source:
    fichier_empreintes: str
    chemin: str
    empreinte: str
    url: str | None
    membre: str | None = None  # fichier à extraire de l'archive zip téléchargée


@dataclass
class Resultat:
    source: Source
    etat: str  # "identique", "modifié", "inaccessible", "sans adresse"
    detail: str = ""
    nouvelle_empreinte: str = ""


def lire_sources() -> list[Source]:
    sources: list[Source] = []
    for f in FICHIERS_EMPREINTES:
        lignes = [LIGNE.match(l) for l in f.read_text(encoding="utf-8").splitlines()]
        entrees = [(m.group(1), m.group(2), m.group(3)) for m in lignes if m]
        zips = {c: u or ADRESSES.get(c) for _, c, u in entrees if c.endswith(".zip")}
        for empreinte, chemin, url in entrees:
            s = Source(f.name, chemin, empreinte, url or ADRESSES.get(chemin))
            if s.url is None:
                # « ra2026/ra_2026_effectifs/fichier.xlsx » : membre de « ra2026/ra_2026_effectifs.zip »
                archive = str(Path(chemin).parent) + ".zip"
                if archive in zips and zips[archive]:
                    s.url, s.membre = zips[archive], Path(chemin).name
            sources.append(s)
    return sources


def telecharger(url: str, essais: int = 3) -> bytes:
    derniere: Exception | None = None
    for i in range(essais):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fonction-publique-les-chiffres/1.0 (verification des sources)"})
            with urllib.request.urlopen(req, timeout=240) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            derniere = e
            if e.code in (403, 404, 410):
                break
        except Exception as e:  # erreurs réseau passagères
            derniere = e
        time.sleep(5 * (i + 1))
    raise RuntimeError(str(derniere))


def membre_zip(contenu: bytes, nom: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        for info in z.infolist():
            if Path(info.filename).name == nom:
                return z.read(info)
    raise RuntimeError(f"« {nom} » absent de l'archive")


def verifier(sources: list[Source]) -> list[Resultat]:
    cache: dict[str, bytes | Exception] = {}
    resultats = []
    for s in sources:
        if not s.url:
            resultats.append(Resultat(s, "sans adresse", "adresse officielle inconnue : à ajouter dans ADRESSES"))
            continue
        if s.url not in cache:
            try:
                cache[s.url] = telecharger(s.url)
            except Exception as e:
                cache[s.url] = e
        contenu = cache[s.url]
        if isinstance(contenu, Exception):
            resultats.append(Resultat(s, "inaccessible", str(contenu)))
            continue
        try:
            donnees = membre_zip(contenu, s.membre) if s.membre else contenu
        except Exception as e:
            resultats.append(Resultat(s, "inaccessible", str(e)))
            continue
        h = hashlib.sha256(donnees).hexdigest()
        if h == s.empreinte:
            resultats.append(Resultat(s, "identique"))
        elif s.chemin in OBSERVATIONS_SDMX:
            ho = empreinte_observations(donnees)
            ref = OBSERVATIONS_SDMX[s.chemin]
            if ref is None:
                resultats.append(Resultat(s, "sans référence", f"empreinte des observations : {ho}"))
            elif ho == ref:
                resultats.append(Resultat(s, "identique", "observations identiques, seul l'en-tête change"))
            else:
                resultats.append(Resultat(s, "modifié", f"observations modifiées ({len(OBS.findall(donnees.decode('utf-8', 'replace')))} valeurs)", ho))
        else:
            resultats.append(Resultat(s, "modifié", f"{len(donnees):,} octets".replace(",", " "), h))
    return resultats


def rapport(resultats: list[Resultat]) -> str:
    modifies = [r for r in resultats if r.etat == "modifié"]
    autres = [r for r in resultats if r.etat in ("inaccessible", "sans adresse", "sans référence")]
    n_ok = sum(r.etat == "identique" for r in resultats)
    # Empreinte du rapport : permet de ne pas signaler deux fois la même situation.
    cle = hashlib.sha256("\n".join(
        f"{r.etat} {r.source.chemin} {r.nouvelle_empreinte}" for r in modifies + autres
    ).encode()).hexdigest()[:16]
    L = [f"<!-- verifier-sources: {cle} -->",
         f"Vérification automatique des {len(resultats)} fichiers officiels dont les empreintes "
         f"figurent dans `donnees/empreintes_*.txt` : **{len(modifies)} modifié(s)**, "
         f"{len(autres)} inaccessible(s), {n_ok} identique(s).", ""]
    if modifies:
        L += ["### Fichiers modifiés", "",
              "Le producteur a publié une nouvelle version (nouvelle édition, révision ou simple "
              "réenregistrement). Ouvrir le fichier, voir ce qui a changé et, si besoin, mettre à jour "
              "les CSV de `donnees/csv/` (voir « Mettre à jour les données » dans le README).", "",
              "| Fichier | Liste d'empreintes | Taille | Nouvelle empreinte |", "|---|---|---|---|"]
        for r in modifies:
            nom = r.source.chemin + (f" (dans l'archive)" if r.source.membre else "")
            L.append(f"| [`{nom}`]({r.source.url}) | `{r.source.fichier_empreintes}` | {r.detail} | `{r.nouvelle_empreinte[:16]}…` |")
        L.append("")
    if autres:
        L += ["### Fichiers inaccessibles", "",
              "Le fichier n'a pas pu être téléchargé : adresse déplacée (souvent le signe d'une "
              "nouvelle édition), site indisponible, adresse à compléter ou empreinte de référence à ajouter dans OBSERVATIONS_SDMX.", "",
              "| Fichier | Adresse | Erreur |", "|---|---|---|"]
        for r in autres:
            L.append(f"| `{r.source.chemin}` | {r.source.url or '—'} | {r.detail} |")
        L.append("")
    L.append("_Ce message est produit par `outils/verifier_sources.py` (workflow « Veille des sources »). "
             "Aucun chiffre du site n'a été modifié._")
    return "\n".join(L) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--rapport", type=Path, help="écrire le rapport Markdown dans ce fichier")
    args = p.parse_args()
    resultats = verifier(lire_sources())
    for r in resultats:
        print(f"{r.etat:<13} {r.source.chemin}" + (f"  ({r.detail})" if r.detail else ""))
    texte = rapport(resultats)
    if args.rapport:
        args.rapport.write_text(texte, encoding="utf-8")
    return 0 if all(r.etat == "identique" for r in resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
