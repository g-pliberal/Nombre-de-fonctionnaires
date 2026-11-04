# Effectifs de la fonction publique par département (2005-2024) : sources, méthode, contrôles

> **Document de travail : extraction des données.** Ce document décrit comment les chiffres ont été extraits des fichiers officiels (adresses exactes, onglets, champs, contrôles, ruptures). Les fichiers intermédiaires qu'il cite (`dept_effectifs.csv, population_dep.csv`…) ont servi à produire les fichiers propres du dossier `donnees/csv/`, qui sont ceux utilisés par le site. Les scripts d'extraction et les fichiers bruts téléchargés ne sont pas conservés dans le dépôt ; les empreintes SHA-256 des fichiers officiels utilisés figurent dans `donnees/empreintes_fichiers_sources.txt`.

Fichiers téléchargés le 4 novembre 2026. Toutes les valeurs proviennent des fichiers officiels listés en section 2.
Les seules valeurs calculées (et signalées comme telles) sont les taux en personnes physiques (`taux_pp_calcule*`),
les sommes de contrôle et les conversions d'unités (milliers vers unités).

## 1. Fichiers produits

| Fichier | Contenu | Couverture |
|---|---|---|
| `dept_effectifs.csv` | Effectifs physiques au 31/12 par département et versant (FPE civils, FPT, FPH, Total civils), avec toutes les versions publiées et une colonne `retenu_carte` (1 valeur recommandée par année x département x versant) | 2005-2024. 96 départements métropolitains en 2005-2009 (94 pour FPH et Total en 2009 : 04 et 06 exclus), 100 (métropole + 971-974) en 2010-2024. Mayotte (976) : enquête Emploi, non comparable, `retenu_carte=0` |
| `population_dep.csv` | Population au 1er janvier (Insee, estimations localisées) | 2005-2026, 101 départements (Mayotte à partir de 2014) |
| `dept_statut.csv` | Effectifs par département et statut (fonctionnaires / contractuels / autres catégories et statuts) | 2018, 2020, 2021 (par versant, avec ETP) ; 2022, 2023, 2024 (ensemble FP seulement) |
| `dept_categorie_fpe_2009.csv` | Répartition A/B/C/indéterminée (en %) de la FPE seule (ministères, et ensemble FPE) | 2009 seulement, métropole + DOM |
| `region_effectifs.csv` | Lignes régionales et agrégats publiés (régions 2016 en 2010-2024 ; anciennes régions, DOM, COM, étranger, militaires en 2005-2009) | 2005-2024 |
| `dept_taux_publies.csv` | Tous les taux d'administration publiés retrouvés (par édition), départements + régions + agrégats | 2009-2024 |
| `controles.csv`, `controle_taux_etp.csv`, `controles_notes.txt` | Résultats des contrôles (section 4) | |
| `_sources.json` | Correspondance `source_id` -> URL du fichier et page de publication (lisible par machine) | |

### Colonnes de `dept_effectifs.csv`

- `annee` : année des données (effectifs au 31 décembre ; Mayotte : 2e trimestre, moyenne annuelle en 2024).
- `code_dep`, `nom_dep` : référentiel Insee (01…95, 2A, 2B, 971…974, 976).
- `versant` : `FPE` = fonction publique de l'État, agents civils seulement (militaires exclus) ; `FPT` ; `FPH` ; `Total` = FPE civils + FPT + FPH. Pour Mayotte : `FPE`, `FPT+FPH`, `Total`.
- `effectif` : personnes physiques, postes principaux, tel que publié (converti en unités). 2005-2008 : la source publie des décimales (estimations), conservées à 0,1 près.
- `taux_admin_publie` : taux d'administration PUBLIÉ par la DGAFP = agents civils **en équivalent temps plein (ETP) pour 1 000 habitants**, et non en personnes physiques. Série unique et homogène : série rétropolée de l'édition 2026 (2011-2024). Vide avant 2011 (les taux publiés plus anciens, de base différente, sont dans `dept_taux_publies.csv`). Mayotte 2024 : 69, chiffre du texte de l'édition 2026 (personnes, non corrigé de la quotité).
- `taux_unite`, `taux_source_id` : unité et source du taux.
- `champ`, `source_id`, `onglet` : champ statistique, source (section 2), onglet / tableau.
- `version` : millésime ou méthode (pré-Siasp ; FGE + Siasp ; Siasp classique ; Siasp moderne ; millésime 2022/2023/2024 ; 2019 initial / révisé).
- `precision` : `unité`, `centaine` (valeurs publiées en milliers à une décimale) ou `décimales publiées (estimation)`.
- `retenu_carte` : 1 = valeur recommandée pour la carte (règle en section 3) ; 0 = autre version publiée, Mayotte ou valeur jugée erronée.
- `segment` : période homogène (`2005-2008 pré-Siasp`, `2009 mixte FGE/Siasp`, `2010-2020 Siasp classique`, `2021-2024 Siasp moderne / DSN`). Il y a une rupture de série à chaque changement de segment.
- `alerte` : anomalie ou rupture identifiée (variation annuelle de plus de 10 %, valeurs vraisemblablement erronées, ruptures de source).
- `population_1janv_n` : population Insee au 1er janvier de l'année N.
- `taux_pp_calcule` : **calcul propre** = effectif / population au 1er janvier N x 1 000 (personnes physiques ; même date de population que la DGAFP, voir 4.3).
- `taux_pp_calcule_pop_n1` : idem avec la population au 1er janvier N+1.

## 2. Sources (`source_id`)

Préfixe des fichiers archivés de l'ancien portail : `ARCH = https://www.fonction-publique.gouv.fr/files/files/ArchivePortailFP/www.fonction-publique.gouv.fr`

### DGAFP_RA2026_LOC (source principale 2019-2024 et taux 2011-2024)
- Fichier : https://www.fonction-publique.gouv.fr/files/files/publications/vue-rapport-annuel/2026/ra_2026_postes.zip (fichiers `ra2026_caracteristiques_postes_donnees_comp_FP.xlsx`, `_FPE.xlsx`, `_FPT.xlsx`, `_FPH.xlsx`)
- Page : https://www.fonction-publique.gouv.fr/toutes-les-publications/caracteristiques-et-localisation-des-postes-de-la-fonction-publique-en-2024-0 (Rapport annuel sur l'état de la fonction publique, édition 2026, « Caractéristiques et localisation des postes de la fonction publique en 2024 » ; date affichée sur la page : 15 octobre 2026 ; fichiers modifiés en août-octobre 2026).
- Onglets : `Figure 1 loc` (FP, FPE, FPT, FPH : effectifs physiques par département 2011-2024, en milliers ; 2011-2019 à une décimale, soit arrondis à la centaine ; à partir de 2020 trois décimales, soit l'unité ; colonnes doubles pour 2021 Classique/Moderne, 2022 millésime 2022/2023, 2023 millésime 2023/2024) ; `Figure 4 loc` (FP) et `Figure 2 loc` (FPE, FPT, FPH) : taux d'administration en ETP pour 1 000 habitants 2011-2024, série rétropolée (une valeur par an) ; `Figure 3 loc` (FP) : statut 2024 ; `Figure 5 loc` (FP) : emploi public à Mayotte 2009, 2013-2024 ; `Figure 1 statut` (FP) : totaux nationaux 2002-2024 y compris militaires (rétropolés), utilisés pour les contrôles.
- Champ : emplois principaux, agents civils, situés en France (hors Mayotte), hors bénéficiaires de contrats aidés, hors emplois non localisés ; département de fonction ; « les effectifs des militaires ne sont pas localisables ».
- Notes de la source : avertissement DSN (depuis 2022, Siasp est alimenté par les DSN ; révision de l'emploi 2023 de +7 400 pour l'ensemble de la FP entre millésimes) ; note (2) des taux : « La mesure du volume de travail a été particulièrement impactée par le passage de la DSN » (2022-2024) ; « les adjoints techniques territoriaux des établissements d'enseignement peuvent être mal localisés dans leur département de fonction (3 % des agents territoriaux) ».

### DGAFP_RA2026_PDF
- Fichier : https://www.fonction-publique.gouv.fr/files/files/publications/vue-rapport-annuel/2026/ra_2026_postes.pdf (même page). Utilisé pour : taux France 2024 = 77 ETP/1 000 hab. (81 avec les militaires), Paris 158, Mayotte 2024 = 69 emplois publics pour 1 000 habitants (encadré 3, non corrigé de la quotité), définitions.

### DGAFP_RA2025_LOC, DGAFP_RA2024_LOC, DGAFP_RA2023_LOC, DGAFP_RA2022_LOC (éditions 2025 à 2022)
- RA2025 : https://www.fonction-publique.gouv.fr/files/files/publications/vue-rapport-annuel/ra_2025-caracteristiques_postes.zip ; page https://www.fonction-publique.gouv.fr/toutes-les-publications/les-caracteristiques-et-la-localisation-des-postes-de-la-fonction-publique-en-2023 (23 octobre 2025). Données 2023 (millésime 2023). Onglets utilisés : `Figure 2 loc` (contrôle), `Figure 3 loc` (statut 2023), `Figure 4 loc` / `Figure 2 loc` (taux publiés, arrondis à l'unité, niveaux non rétropolés, versions 2021 C/M et 2022 millésimes 2022/2023).
- RA2024 : https://www.fonction-publique.gouv.fr/files/files/publications/vue-rapport-annuel/ra_2024-caracteristiques_postes.zip ; page https://www.fonction-publique.gouv.fr/toutes-les-publications/les-caracteristiques-et-la-localisation-des-postes-de-la-fonction-publique-en-2022 (15 novembre 2024). Données 2022 (millésime 2022). `Figure 2 loc` (contrôle), `Figure 3 loc` (statut 2022).
- RA2023 : https://www.fonction-publique.gouv.fr/files/files/publications/vue-rapport-annuel/caracteristiques_postes_0.zip ; page https://www.fonction-publique.gouv.fr/toutes-les-publications/les-caracteristiques-et-la-localisation-des-postes-de-la-fonction-publique-en-2021 (15 décembre 2023). Données 2021 (classique). `Figure 2 loc` (effectifs + ETP par versant, contrôle), `Figure 3/4/5 loc` (fonctionnaires / contractuels / autres, par versant, avec ETP).
- RA2022 : https://www.fonction-publique.gouv.fr/files/files/publications/vue-rapport-annuel/caracteristiques_postes.zip ; page https://www.fonction-publique.gouv.fr/toutes-les-publications/caracteristiques-et-localisation-des-postes-de-la-fonction-publique-en-2020 (8 novembre 2022). Données 2020, publiées en milliers à une décimale. `Figure 3/4/5 loc` (statut 2020 par versant, avec ETP ; précision : centaine).

### DGAFP_SL2021_LOC (source principale 2010-2018, version initiale de 2019, taux d'origine 2010-2019)
- Fichier : ARCH + `/files/files/statistiques/series_longues/series-longues-2021/FT1.2-3-SL_Localisation_ensemble.xlsx`
- Page : ARCH + `/series-longues.html` (séries longues DGAFP 2021 ; fichier modifié le 13/10/2021).
- Onglets : `Effectifs 3FP`, `Effectifs FPE`, `Effectifs FPT`, `Effectifs FPH` (unités, 2010-2019) ; `Taux d'administration 3FP/FPE/FPT/FPH` (ETP pour 1 000 hab., 2010-2019, pleine précision) ; `Effectifs Mayotte`.
- Champ : emplois principaux, agents civils, situés en France (hors Mayotte), hors contrats aidés ; militaires non localisables.
- Contrôle : 2011-2018 identiques (après arrondi à la centaine) à l'édition 2026 (0 écart sur 3 200 couples). 2019 : version initiale, révisée ensuite (voir 3).

### DGAFP_RA2017_FT12 … DGAFP_RA2021_FT12 (éditions 2017 à 2021, une année chacune : 2015 à 2019)
- 2015 : ARCH + `/files/files/statistiques/rapports_annuels/2017/FT1-2_fonction-publique.xlsx` ; page ARCH + `/rapport-annuel-2017-faits-et-chiffres-fiches-thematiques-excel.html`
- 2016 : ARCH + `/files/files/statistiques/rapports_annuels/2018/xls/FT1-2_fonction-publique.xlsx` ; page ARCH + `/rapport-annuel-2018-faits-et-chiffres-fiches-thematiques-excel.html`
- 2017 : ARCH + `/files/files/statistiques/rapports_annuels/2019/xls/FT1.2_fonction-publique.xlsx` ; page ARCH + `/rapport-annuel-2019-faits-et-chiffres-fiches-thematiques-excel.html`
- 2018 : ARCH + `/files/files/statistiques/rapports_annuels/2020/FT1.2_fonction-publique.xlsx` (`DGAFP_RA2020_FT12`) ; page ARCH + `/rapport-annuel-2020-faits-et-chiffres-fiches-thematiques-excel-0.html`
- 2019 : ARCH + `/files/files/statistiques/rapports_annuels/2021/FT1.2_fonction-publique.xlsx` ; page ARCH + `/rapport-annuel-2021-faits-et-chiffres-fiches-thematiques-excel.html`
- Onglets : `Figure 1.2-3` (effectifs physiques ET ETP par département et versant, unités, + totaux France civils et y compris militaires) ; `Sources 1.2-8 à 11` (taux d'administration ETP par département, code département) ; édition 2020 : `complémentaire Fig 1.2-3 (fonc)/(cont)/(autr)` (statut 2018).
- Utilisation : contrôles (révisions, reconstitution des taux), taux « d'époque » dans `dept_taux_publies.csv`, statut 2018. Les valeurs d'effectifs retenues pour 2015-2018 sont celles des séries longues (millésime définitif).

### DGAFP_RA2011_COMPL_DEP (2005-2009)
- Fichier : ARCH + `/files/files/statistiques/rapports_annuels/2010-2011/xls/RA2010-2011_COMPLEMENT_Effectifs_physiques_ETP_3FP_dep_2005_2009_20120530.xls`
- Page : ARCH + `/fonction-publique/fonction-publique-france-40.html` (Rapport annuel 2010-2011, « Faits et chiffres : fiches thématiques (Excel) » ; compléments mis en ligne le 30/05/2012).
- Onglets `2005` à `2009` (« Tableau 1.2-1 : Effectifs physiques et équivalents temps plein des trois fonctions publiques par région et par département au 31 décembre N »).
- Champ : hors emplois aidés, emplois principaux, tous statuts ; FPE agents civils y compris EPA nationaux (militaires non ventilés par département, donnés seulement par agrégat) ; FPT y compris EPA locaux et assistantes maternelles ; FPH y compris médecins. Sources : 2005-2008 FGE, Colter, DADS, enquête SAE ; 2009 FGE (FPE) + Siasp (FPT, FPH). DOM fournis uniquement en agrégat ; lignes séparées COM (« TOM ») et étranger.

### DGAFP_RA2010_COMPL_2008 (DOM 2008, version alternative)
- Fichier : ARCH + `/files/files/statistiques/rapports_annuels/2009-2010/xls/FT%201.2_COMPLEMENT_3FP_RA2009_2010-revuVP.xls`, onglet `Tableau 1.2-1` (2008).
- Page : ARCH + `/fonction-publique/fonction-publique-france-24.html` (Rapport annuel 2009-2010). Fichier enregistré le 27/05/2011.
- Seule source trouvée avec les 4 DOM par département avant 2010 ; millésime 2008 différent de celui de l'édition 2010-2011 (289 couples département x versant métropolitains sur 384 diffèrent de plus de 0,5) : DOM 2008 en `retenu_carte=0`. L'onglet `Tableau 1.2-2 COMP` (taux 2008) a des colonnes manifestement décalées sur une partie des lignes : non utilisé.

### DGAFP_RA2011_FT12 (taux 2009)
- Fichier : ARCH + `/files/files/statistiques/rapports_annuels/2010-2011/xls/RA2010_2011_FT1.2_Emploi_3FP_DEF_INTERNET.xls` ; même page que ci-dessus.
- Onglets `SCarte1.2-1` (3FP), `SCarte1.2-2` (FPE), `SCarte 1.2-3` (FPT), `Scarte 1.2-4` (FPH) : taux d'administration ETP 2009 des 96 départements métropolitains (DOM : moyenne seulement, 78,9 ‰). Onglet `T 1.2-1 Eff 3FP phy ETP regions` (régions 2009).

### DGAFP_RA2011_FT22_COMPL (catégories, FPE 2009)
- Fichier : ARCH + `/files/files/statistiques/rapports_annuels/2010-2011/xls/RA2010-2011_FT2.2_CAT_HIERAR_COMPLEMENT_20120530.xls`, onglet `Tableau 2.2-2` (répartition A/B/C en % des ministères et de l'ensemble FPE par département, 31/12/2009 ; source FGE ; hors préfecture de police de Paris).

### INSEE_ESTIM_POP_2026 (population)
- Fichier : https://www.insee.fr/fr/statistiques/fichier/8721456/estim-pop-dep-sexe-gca-1975-2026.xlsx (colonne « Ensemble - Total » de chaque onglet annuel).
- Page : https://www.insee.fr/fr/statistiques/8721456 (« Estimation de la population au 1er janvier 2026 », paru le 13/01/2026 ; données actualisées au 23/12/2025).
- Notes de la source : 2006-2023 issus du recensement (définitifs), 2024-2026 provisoires ; Mayotte intégrée à partir de 2014 et estimée sans le recensement de fin 2025 ; Guadeloupe hors Saint-Martin et Saint-Barthélemy. (La page 1893198 citée en piste ne contient que l'édition janvier 2023.)

### Pistes vérifiées sans résultat exploitable
- data.gouv.fr, jeu « Effectifs de la fonction publique par département depuis 2010 » (DGAFP, 2019) : renvoie vers data.economie.gouv.fr (connexion refusée depuis l'environnement) ; contenu antérieur aux séries longues 2021, qui ont été utilisées à la place.
- Insee (Melodi, recherche insee.fr) : pas de données Siasp d'effectifs par département ; uniquement national ou salaires.
- Révision 2019 en unités : non publiée (éditions 2022 à 2026 en milliers à une décimale).
- Éditions 2011-2012 et 2012-2013 : fichiers Excel non retrouvés dans l'archive (années 2010-2011 couvertes par les séries longues). vie-publique.fr (PDF 2010-2011) bloqué par une protection anti-robot.

## 3. Valeurs retenues pour la carte (`retenu_carte = 1`)

Règle : pour chaque année, la valeur du millésime le plus récent publié, en unités quand elle existe.

| Années | Valeur retenue | Autres versions conservées (`retenu_carte=0`) |
|---|---|---|
| 2005-2008 | RA 2010-2011, compléments (métropole) | DOM 2008 de l'édition 2009-2010 |
| 2009 | RA 2010-2011 (métropole) | 04 et 06 FPH/Total exclus (valeurs vraisemblablement interverties) |
| 2010-2018 | Séries longues 2021 (unités, millésime définitif) | — |
| 2019 | Édition 2026, révisé (centaines) | Séries longues 2021, initial (unités) |
| 2020 | Édition 2026 (unités, Siasp classique) | — |
| 2021 | Édition 2026, « Moderne » | « Classique » |
| 2022 | Édition 2026, millésime 2023 | millésime 2022 |
| 2023 | Édition 2026, millésime 2024 | millésime 2023 |
| 2024 | Édition 2026, millésime 2024 | — |
| Mayotte | aucune (enquête Emploi, non comparable) | 2009, 2013-2024 |

## 4. Contrôles

### 4.1 Sommes
- Somme des 100 départements = « Total France entière, agents civils » publié, 2010-2019, pour les 4 versants : écart 0 (un écart de 1 en 2014).
- Édition 2026 : somme des 96 départements = « Total métropole » publié (FPT, FPH, chaque version 2020-2024) : écart 0.
- FPE + FPT + FPH = Total pour toutes les lignes retenues (0 écart).
- Somme des départements + militaires publiés vs total national tous statuts (édition 2026, `Figure 1 statut`) : écart de 33 agents en 2024 et de 15 en 2023 (emplois non localisés), de 9 754 en 2022, d'environ 40 000 à 43 000 en 2010-2020 et de 58 555 en 2021. Avant 2023, l'écart vient surtout de la rétropolation des totaux nationaux de l'édition 2026. Avec les totaux non rétropolés publiés à l'époque (éditions 2017 et 2019), la somme des départements est égale au total France civils (2015 : 5 150 292 ; 2017 : 5 216 760) et le total y compris militaires vaut 5 450 619 (2015) et 5 525 902 (2017), soit environ 300 000 à 309 000 militaires non localisables.
- 2005-2009 : agents hors départements publiés séparément (2005 : 14 902 civils en COM, 29 262 à l'étranger, 343 106 militaires en métropole).
- Éditions antérieures vs valeurs retenues : 2021 classique = RA2023, 2022 millésime 2022 = RA2024, 2023 millésime 2023 = RA2025 (0 écart sur 400). Valeurs initiales révisées l'année suivante : 2016 (204/400 couples différents, max. Doubs Total 42 903 -> 44 782), 2018 (313/400, max. Bouches-du-Rhône FPT 64 796 -> 65 993), 2019 (Paris 332 693 -> 333 700) ; 2015 et 2017 inchangés.
- Statut : somme des statuts = total (2020-2024, 0 écart). 2018 : statut issu de l'édition initiale (RA2020), donc différent des effectifs 2018 retenus (millésime révisé) ; incohérence interne à la source pour Loire-Atlantique FPH 2018 (somme des statuts 22 527 contre 22 345).

### 4.2 Taux recalculés vs taux publiés (`controle_taux_etp.csv`)
En recalculant ETP publiés / population Insee au 1er janvier N, on retrouve les taux publiés de la même édition : écart médian de -0,02 % (2009), -0,01 % (2015), +0,20 % (2016), -0,03 % (2017), -0,23 % (2018) et -0,15 % (2019). Entre 92 et 100 départements sur 96-100 sont à moins de 1 %. Avec la population au 1er janvier N+1, l'accord est moins bon (73 à 88 départements à moins de 1 %). Mayotte 2024 : 22 000 / 320 646 (population au 1/1/2024) = 68,6, publié 69 ; avec la population au 1/1/2025 on obtiendrait 66,8.

### 4.3 Méthode DGAFP du taux d'administration (constat)
Définition DGAFP : « nombre d'agents civils de la fonction publique (converti en équivalent temps plein) pour 1 000 habitants », rapporté à « la population totale de ce même territoire ». La date de la population n'est pas indiquée dans les fichiers. Empiriquement (4.2), c'est l'estimation Insee de population au **1er janvier de l'année N** (dans sa version disponible à la date de publication) qui est utilisée pour des effectifs au 31 décembre N. `taux_pp_calcule` suit cette convention ; `taux_pp_calcule_pop_n1` utilise le 1er janvier N+1.

### 4.4 Valeurs de contrôle (France hors Mayotte, agents civils)

| | 2011 | 2019 | 2024 |
|---|---|---|---|
| Effectifs (somme des départements) | 5 057 683 | 5 301 600 | 5 535 404 |
| Taux publié, ETP (série rétropolée éd. 2026) | 74,2 | 75,7 | 76,8 |
| Taux publié, ETP (niveau d'origine, séries longues 2021) | 72,0 | 73,4 | — |
| Taux calculé, personnes physiques (pop. 1/1/N) | 77,9 | 79,1 | 81,0 |

| Département | Effectif 2011 / 2019 / 2024 | Taux ETP publié (éd. 2026) 2011 / 2019 / 2024 | Taux PP calculé 2011 / 2019 / 2024 |
|---|---|---|---|
| Paris (75) | 329 345 / 333 700 / 337 175 | 141,4 / 147,9 / 158,3 | 146,4 / 154,1 / 161,7 |
| Guyane (973) | 19 695 / 25 600 / 27 819 | 81,2 / 88,3 / 92,5 | 82,9 / 90,9 / 93,9 |
| La Réunion (974) | 66 365 / 75 500 / 80 427 | 77,0 / 84,1 / 85,7 | 80,1 / 87,7 / 89,6 |
| Creuse (23) | 10 113 / 10 300 / 10 560 | 76,8 / 82,9 / 87,5 | 82,5 / 88,3 / 91,5 |

## 5. Points d'attention

1. **ETP et personnes physiques.** Les effectifs sont en personnes physiques. Le taux d'administration publié est en ETP. Le taux en personnes physiques calculé ici dépasse le taux ETP publié (série 2026) de 5 à 6 % en médiane, et de 0 à 10 % selon les départements, chaque année de 2011 à 2024 (France 2019 : 79,1 contre 75,7). Par rapport aux taux ETP publiés à l'époque (non rétropolés), l'écart médian est d'environ 8 % (de 1 à 12 %).
2. **Taux rétropolés.** La série de taux de l'édition 2026 (2011-2024) est rétropolée à partir des niveaux 2022-2024, dont la mesure du volume de travail (ETP) a été modifiée par le passage à la DSN (note de la source). Les niveaux d'avant 2022 dépassent donc les taux publiés à l'époque : +2,7 % en médiane, de -1,5 % à +6,5 % selon les départements (France 2011 : 74,2 contre 72,0 ; Paris 2019 : 147,9 contre 143,0). Il ne faut pas mélanger dans une même animation des taux de différentes éditions : `taux_admin_publie` ne contient que la série 2026. Les autres séries sont dans `dept_taux_publies.csv`.
3. **Militaires** : exclus des données départementales (« non localisables » ; environ 300 000 à 360 000 selon les années, dont 303 000 à 326 000 en 2010-2024). Le taux national avec militaires est de 81 ETP/1 000 hab. en 2024 contre 77 sans. L'emploi public des départements qui accueillent beaucoup de militaires est donc sous-estimé.
4. **Non localisés, COM et étranger** : hors champ. En 2005-2009 ils sont publiés à part (environ 42 000 à 44 000 civils : 13 900 à 14 900 en COM, 27 900 à 29 300 à l'étranger). Depuis 2022, les « emplois non localisés » sont exclus ; d'après les totaux 2023-2024 ils sont négligeables (15 à 33).
5. **Paris et Île-de-France** : administrations centrales, sièges d'établissements publics et grands hôpitaux sont comptés à leur lieu de travail, d'où un taux de 141 à 158 ETP pour 1 000 habitants à Paris entre 2011 et 2024 (146 à 162 en personnes physiques). Rupture de localisation de la FPH en Île-de-France entre 2007 et 2008 (Paris FPH 98 078 -> 59 568 ; Hauts-de-Seine 6 523 -> 18 011 ; Val-de-Marne 11 083 -> 26 074) : les données 2005-2007 de 75/92/93/94 (FPH, Total) ne sont pas comparables.
6. **Corse** : 2A et 2B sont toujours séparés (aucune source agrégée en « 20 »). En 2018, transfert apparent d'agents FPT de la Haute-Corse (-23 %) vers la Corse-du-Sud (+17 %), probablement lié à la création de la Collectivité de Corse au 1er janvier 2018 (inférence).
7. **Mayotte** : hors du champ de toutes les publications DGAFP fondées sur Siasp (« France hors Mayotte »), donc absente des données départementales. Les seuls chiffres sont ceux de l'enquête Emploi Mayotte (Insee, personnes de 15-64 ans, 2e trimestre ; enquête rénovée et moyenne annuelle en 2024 ; collecte 2023 dégradée) : 12 800 en 2009, 17 600 en 2013, 22 100 en 2020, 22 000 en 2024. Ils ne sont pas comparables (`retenu_carte=0`).
8. **DOM avant 2010** : pas de détail par département en 2005-2007 ni en 2009 (agrégat DOM seulement). 2008 est disponible dans une autre édition (non retenu).
9. **Ruptures de série** : 2008->2009 (FPT et FPH passent de Colter/DADS/SAE à Siasp) ; 2009->2010 (FPE passe de FGE à Siasp : +6,4 % au niveau national, et +43 % en Vendée, +28 % dans le Morbihan, +25 % en Maine-et-Loire) ; 2020->2021 (Siasp classique -> moderne) ; 2021->2022 et 2022->2023, parce que les valeurs retenues enchaînent des millésimes DSN différents (+1,46 % et +1,37 % au niveau national, en partie méthodologiques). D'après les avertissements des éditions 2025 et 2026, les évolutions à méthode constante se lisent ainsi : 2020->2021 avec « 2021 Classique » ; 2021->2022 avec « 2021 Moderne » et « 2022 millésime 2022 » ; 2022->2023 avec les deux « millésime 2023 » ; 2023->2024 avec « 2023 millésime 2024 ». Le millésime 2023 ajoute 33 400 postes FPT, surtout des contractuels, aux effectifs du 31/12/2022 (éléments de rémunération déclarés en retard). Le millésime 2024 révise l'emploi 2023 de +7 400 et exclut les postes qui ne perçoivent qu'une indemnité. Toutes ces versions figurent dans `dept_effectifs.csv` (`retenu_carte=0` pour les plus anciennes). Pour une animation homogène, 2010-2024 est la période recommandée (Siasp), en signalant 2021. Les années 2005-2009 ne sont pas comparables (sources, champ et localisation différents).
10. **Anomalies signalées dans la colonne `alerte`** : 2009, permutation probable des effectifs FPH entre les Alpes-de-Haute-Provence et les Alpes-Maritimes dans le fichier source (exclue de la carte) ; Var 2022 (millésime 2023 supérieur d'environ 8 000 agents FPE aux millésimes 2022 et 2024) ; Guyane 2021 version moderne (FPT 6 727 contre 8 345) ; Vosges 2020 (point bas) ; Territoire de Belfort et Doubs 2017 (FPH) ; Somme 2016 (FPT -18 %) ; Lot-et-Garonne 2016 et 2019 (FPE). Seule la permutation de 2009 est jugée erronée ; les autres valeurs restent retenues avec un avertissement. Les explications marquées « inférence » ne sont pas documentées par la DGAFP.
11. **Précision** : 2019 (révisé) est arrondi à la centaine (écart d'au plus 50 agents, soit moins de 0,7 % pour le plus petit département). 2005-2008 sont des estimations publiées avec des décimales.
12. **Localisation imparfaite** : les adjoints techniques territoriaux des établissements d'enseignement (3-4 % de la FPT) peuvent être mal localisés (note DGAFP).
13. **Population** : estimations Insee de janvier 2026 (2006-2023 définitives, 2024-2026 provisoires). La DGAFP a utilisé les estimations disponibles à la date de chaque publication, ce qui explique de petits écarts (en général moins de 1 %) entre taux publiés et taux recalculés.
14. **Catégories A/B/C** : pas de données publiées par département pour les trois versants. Seule existe la FPE en 2009 (pourcentages, source FGE) dans `dept_categorie_fpe_2009.csv`. Statut (fonctionnaires / contractuels / autres) par département : 2018, 2020-2024 (`dept_statut.csv`) ; 2019 non trouvé.
15. **Avant 2005** : pas de données départementales trouvées pour les trois versants.
