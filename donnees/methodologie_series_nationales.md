# Effectifs de la fonction publique – séries nationales : sources, champs et ruptures

> **Document de travail : extraction des données.** Ce document décrit comment les chiffres ont été extraits des fichiers officiels (adresses exactes, onglets, champs, contrôles, ruptures). Les fichiers intermédiaires qu'il cite (`national_versants.csv, national_statuts.csv`…) ont servi à produire les fichiers propres du dossier `donnees/csv/`, qui sont ceux utilisés par le site. Les scripts d'extraction et les fichiers bruts téléchargés ne sont pas conservés dans le dépôt ; les empreintes SHA-256 des fichiers officiels utilisés figurent dans `donnees/empreintes_fichiers_sources.txt`.

Constitution : novembre 2026. Toutes les valeurs des CSV proviennent de fichiers officiels téléchargés
(xlsx/xls/pdf) listés ci-dessous ; les seules opérations effectuées sont : conversion milliers → personnes,
sommes ou différences de colonnes publiées (signalées « calcul » dans la colonne `note`) et parts calculées
(`part_pct = calcul`). Aucune valeur n'a été saisie de mémoire. Empreintes SHA-256 des fichiers sources : `donnees/empreintes_fichiers_sources.txt`.

## 1. Fichiers produits

| Fichier | Contenu | Années couvertes |
|---|---|---|
| `national_versants.csv` | Effectifs physiques au 31/12 par versant (FPE, FPT, FPH) et total, une ligne par (série, année, version) | 1980, 1982-2024 (1981 absent ; plusieurs séries se recoupent) |
| `national_statuts.csv` | Effectifs (ou parts) par statut : fonctionnaires (titulaires), militaires, contractuels, autres catégories et statuts, contrats aidés ; détail 1980-1998 (ouvriers d'État, assistantes maternelles, médecins...) | 1980-1998 (années paires surtout), 2002-2024 |
| `national_categories.csv` | Effectifs et/ou parts par catégorie hiérarchique A (dont A+), B, C, indéterminée | 1980-1998 (par composante), 1996, 1999-2001, 2003, 2004, 2006, 2007, 2009, 2010-2024 |
| `national_etp.csv` | Équivalents temps plein (ETP au 31/12 ou volume de travail annuel EQTP) | 1980, 1984-1996 (années paires), 1997, 2000, 2001, 2006, 2007, 2016-2024 |
| `population_insee.csv` | Population au 1er janvier (Insee) : métropole, DOM, Mayotte, France hors Mayotte | 1975-2026 (DOM à partir de 1990) |
| `taux_administration.csv` | Agents pour 1 000 habitants (calcul) + taux d'administration officiel DGAFP (ETP civils / 1 000 hab.) | 1980-2024 selon la série ; officiel 2011-2024 |
| `controles.txt` | Résultat des contrôles automatiques (OK / DOCUMENTE / ECART) | – |
| `sha256_fichiers_sources.txt` | Empreintes des fichiers bruts utilisés | – |

### Colonnes
- `serie` : identifiant d'une série homogène (même source, même champ, même méthode).
- `annee` : année de l'observation (au 31 décembre sauf mention contraire).
- `version` : vide si une seule valeur ; sinon millésime (« 2021 Classique », « 2021 Moderne », « 2022 millésime 2023 »...) ou « revisee (r) » (valeur Insee recalculée pour être comparable à l'année suivante).
- `fpe`, `fpt`, `fph`, `total` (versants/ETP), `effectif`, `part_pct` (statuts/catégories) : nombre de personnes physiques (ou d'ETP dans `national_etp.csv`) ; parts en %.
- `contrats_aides` : `inclus` / `exclus` (bénéficiaires de contrats aidés : CES, CEC, CUI-CAE, emplois d'avenir...).
- `champ` : libellé court du champ ; détail dans la rubrique de la source ci-dessous.
- `unite_source` : unité/précision dans le fichier d'origine (ex. « milliers, 1 décimale » = précision ±50 personnes).
- `note` : ruptures, interpolations, calculs, incohérences du tableau source.
- `source_id` : renvoie au catalogue (section 3).

## 2. Quelle série utiliser ?

- **Série longue homogène la plus récente (1996-2024, hors contrats aidés)** : `DGAFP_RA2026_retropolee`. Niveaux rétropolés par la DGAFP à la méthodologie 2024 (chaînage des évolutions). **1997, 1999, 2001 et 2003 sont interpolés** (moyenne géométrique des années encadrantes, vérifié) : ce ne sont pas des observations. Avant 2009, sources FGE/Colter/DADS/SAE.
- **Avec contrats aidés et décomposition par statut (2011-2024)** : `INSEE_SIASP_y_c_CA_publie` (+ `..._revise` pour mesurer les évolutions 2020→2021, 2021→2022, 2022→2023 et 2023→2024 à méthode constante).
- **1980-1997** : deux séries officielles non raccordables directement aux séries actuelles :
  - `DGAFP_SL1980_1998_sens_large` (annuelle) – champ large (La Poste/France Télécom, enseignants du privé, EPIC, emplois secondaires de la FPT) ;
  - `CC2009_DGAFP_emplois_principaux` et `INSEE_ES2003` (quelques années) – champ étroit (ni La Poste/France Télécom, ni enseignants du privé).
  - `DGAFP_SL1980_1998_hors_PTT` retire La Poste/France Télécom (calcul) mais reste plus large que le champ actuel.
- Ne pas mettre bout à bout des niveaux de séries différentes sans le signaler : voir les écarts chiffrés en section 4.

## 3. Catalogue des sources (`source_id`)

### INSEE_CC_2493501 – Insee, « Effectifs dans la fonction publique par versant et ministère – Données annuelles de 2011 à 2024 » (Chiffres-clés)
- Page : https://www.insee.fr/fr/statistiques/2493501 – paru le 10/02/2026.
- Fichier : https://www.insee.fr/fr/statistiques/fichier/2493501/marc-empl-eff-fonc-pub.xlsx
- Onglets : « Figure 1 » (effectifs en milliers par versant et statut : fonctionnaires et militaires / contractuels hors contrats aidés / bénéficiaires de contrats aidés / autres catégories et statuts / ensemble), « Figure 2 » (répartition en % : catégorie hiérarchique, statut, sexe, âge, temps de travail ; militaires publiés à part de 2011 à 2017 seulement), « Figure 3 » (par ministère, non reprise).
- Champ : France hors Mayotte, postes principaux non annexes au 31 décembre (Figure 2 : postes principaux, y compris bénéficiaires de contrats aidés) ; source Siasp 2011 à 2024.
- Notes de la source : niveaux non totalement comparables d'un millésime à l'autre (changements déclaratifs, applicatifs et de concepts) ; les colonnes « 2020¹ (r) » à « 2023¹ (r) » sont recalculées pour être comparables à l'année suivante. Catégorie : attribuée aux non-titulaires selon leur code grade ; **tous les bénéficiaires de contrats aidés sont classés en C**. À partir de 2018, les militaires sont inclus dans « Fonctionnaires » (« nd » pour les militaires).
- Séries : `INSEE_SIASP_y_c_CA_publie`, `INSEE_SIASP_y_c_CA_revise`, `INSEE_SIASP_hors_CA_publie`, `INSEE_SIASP_hors_CA_revise` (hors CA = « Ensemble » – « Bénéficiaires de contrats aidés », calcul) ; statuts/catégories : `INSEE_SIASP_publie`, `INSEE_SIASP_revise`.

### INSEE_IP2094 (et INSEE_IP2052, IP2003, IP1947, IP1897, IP1842, IP1797, IP1741) – Insee Première « L'emploi dans la fonction publique en N »
| Publication | Page | Fichier | Paru le |
|---|---|---|---|
| n°2094 (2024) | https://www.insee.fr/fr/statistiques/8732435 | https://www.insee.fr/fr/statistiques/fichier/8732435/IP2094.xlsx | 10/02/2026 |
| n°2052 (2023) | https://www.insee.fr/fr/statistiques/8572076 | https://www.insee.fr/fr/statistiques/fichier/8572076/IP2052.xlsx | 27/05/2025 |
| n°2003 (2022) | https://www.insee.fr/fr/statistiques/8214842 | https://www.insee.fr/fr/statistiques/fichier/8214842/IP2003.xlsx | 10/07/2024 |
| n°1947 (2021) | https://www.insee.fr/fr/statistiques/7621088 | https://www.insee.fr/fr/statistiques/fichier/7621088/donnees_insee_premiere_n1947.xlsx | 23/05/2023 |
| n°1897 (2020) | https://www.insee.fr/fr/statistiques/6215551 | https://www.insee.fr/fr/statistiques/fichier/6215551/ip1897.xlsx | 17/03/2022 |
| n°1842 (2019) | https://www.insee.fr/fr/statistiques/5232488 | https://www.insee.fr/fr/statistiques/fichier/5232488/ip1842.xlsx | 15/03/2021 |
| n°1797 (2018) | https://www.insee.fr/fr/statistiques/4477497 | https://www.insee.fr/fr/statistiques/fichier/4477497/ip1797.xlsx | 08/04/2020 |
| n°1741 (2017) | https://www.insee.fr/fr/statistiques/3747060 | https://www.insee.fr/fr/statistiques/fichier/3747060/ip1741.xls | 13/03/2019 |
- Onglet « Figure 1 » : effectifs au 31/12 (postes principaux) et **volume de travail en EQTP (tout poste actif dans l'année)**, y compris / hors contrats aidés, années N-1 et N → `national_etp.csv` (séries `INSEE_IP_EQTP_IPxxxx`). IP2094 « Figure 3 » : parts par statut en 2024 avec militaires séparés → `national_statuts.csv` (série `INSEE_IP2094`).
- Champ : France hors Mayotte ; Siasp.
- Attention : les niveaux d'EQTP changent fortement d'une publication à l'autre (passage à la DSN, ajustements) ; chaque publication ne doit servir qu'à l'évolution N-1 → N.

### DGAFP_RA2026_EFF – DGAFP, Rapport annuel sur l'état de la fonction publique, édition 2026, vue « L'évolution des effectifs de la fonction publique en 2024 »
- Page du rapport : https://www.fonction-publique.gouv.fr/toutes-les-publications/rapport-annuel-sur-letat-de-la-fonction-publique-edition-2026 (date de parution : 15 octobre 2026).
- Page de la vue : https://www.fonction-publique.gouv.fr/toutes-les-publications/levolution-des-effectifs-de-la-fonction-publique-en-2024-0
- Fichier : https://www.fonction-publique.gouv.fr/files/files/publications/vue-rapport-annuel/2026/ra_2026_effectifs.zip → `RA_2026_effectifs_donnees_comp_FP.xlsx` (modifié le 24/08/2026).
- Onglets utilisés : « Figure 5 » (effectifs physiques par versant en distinguant les EPA, **1996-2024**, milliers, hors contrats aidés, sources FGE, Colter, DADS, Siasp, enquêtes SAE ; traitement DGAFP-SDessi) → `DGAFP_RA2026_retropolee` ; « Figure 4 » (2011-2024 avec et hors contrats aidés) → `DGAFP_RA2026_retropolee_y_c_CA` ; « Figure 6 » (bénéficiaires de contrats aidés 2011-2024) ; « Figure 3 » (place de l'emploi public, contrôles).
- Champ : emplois principaux, tous statuts, France (hors Mayotte), hors bénéficiaires de contrats aidés (sauf Figure 4 « avec contrats aidés »).
- Notes de la source : depuis 2009 les trois versants sont issus de Siasp ; élèves de l'École polytechnique dans les EPA depuis 2005 ; militaires volontaires comptés dans la FPE depuis 2004 ; bascule progressive des AESH des EPA (lycées) vers les ministères en 2023-2024 ; onglet AVERTISSEMENT : séries rétropolées = niveaux recalculés à partir des évolutions annuelles à méthodologie constante.

### DGAFP_RA2026_POSTES – même rapport, vue « Caractéristiques et localisation des postes de la fonction publique en 2024 »
- Page : https://www.fonction-publique.gouv.fr/toutes-les-publications/caracteristiques-et-localisation-des-postes-de-la-fonction-publique-en-2024-0 (15 octobre 2026).
- Fichier : https://www.fonction-publique.gouv.fr/files/files/publications/vue-rapport-annuel/2026/ra_2026_postes.zip → `ra2026_caracteristiques_postes_donnees_comp_FP.xlsx` (modifié le 19/08/2026).
- Onglets : « Figure 1 statut » (fonctionnaires / contractuels / militaires / autres catégories et statuts par versant, **2002-2024**, rétropolé, milliers) → `DGAFP_RA2026_retropolee` (statuts) ; « Figure 1 catégorie » (A, dont A+, B, C, indéterminée, 2011-2024 avec deux niveaux pour 2021, 2022 et 2023) → `DGAFP_RA2026_niveaux_par_millesime` (catégories et versants) ; « Figure 4 loc » (taux d'administration civile, ETP pour 1 000 habitants, 2011-2024) ; « Figure 5 loc » (emploi public à Mayotte, enquête Emploi).
- Champ : emplois principaux, tous statuts, France (hors Mayotte), hors contrats aidés. FPT : les militaires (sapeurs-pompiers de Marseille) sont regroupés avec les fonctionnaires (secret statistique). « Autres catégories et statuts » : enseignants et documentalistes du privé sous contrat et ouvriers d'État (FPE), assistants maternels et familiaux (FPT), médecins (FPH), apprentis (trois versants).
- Notes de la source : 2017, liste A+ révisée ; 2021 « Moderne » : PU-PH classés en FPH ; dégradation de l'identification de la catégorie dans la FPE avec la DSN ; ajouts successifs de corps à la catégorie A+ (2022, 2023, 2024).

### DGAFP_SL2021 – DGAFP, « Séries longues » de l'édition 2021 du rapport annuel (données jusqu'au 31/12/2019), archive du portail de la fonction publique
- Page de liste (archive) : https://www.fonction-publique.gouv.fr/files/files/ArchivePortailFP/www.fonction-publique.gouv.fr/series-longues.html
- Fichiers (préfixe `https://www.fonction-publique.gouv.fr/files/files/ArchivePortailFP/www.fonction-publique.gouv.fr/files/files/statistiques/series_longues/series-longues-2021/`) :
  - `FT1.2-SL_Effectifs_ensemble_FP.xlsx`, onglet « Figure 1.2-2 » (effectifs physiques des trois versants au 31/12 : 1996, 1998, 2000, 2002, 2004-2019) → `DGAFP_SL2021_niveaux_publies` (versants) ;
  - `FT2.1-SL_Statut.xlsx`, onglet « Statut » (Figure 2.1-1 : fonctionnaires, contractuels, militaires, autres catégories et statuts dont ouvriers d'État, part des non-titulaires : 2002, 2004-2019) → statuts ;
  - `FT2.2-SL_Categories_hierarchiques.xlsx`, onglet « Effectifs » (A, dont A+, B, C, indéterminée : 2010-2019) → catégories ;
  - `FT1.1-SL_Effectifs.xlsx` (contrats aidés 2010-2019, place de l'emploi public 2011-2018 : contrôles).
- Fichiers modifiés le 07-08/09/2021 (métadonnées). Champ : emplois principaux, tous statuts, métropole et DOM (hors Mayotte), hors COM et étranger, hors bénéficiaires de contrats aidés. Sources FGE, Colter, DADS, Siasp, Insee ; enquêtes SAE, Drees ; traitement DGAFP.
- Les valeurs non entières avant 2009 sont des estimations raccordées par la DGAFP. Pas de données 1997, 1999, 2001, 2003.
- Version antérieure consultée (non utilisée dans les CSV) : séries longues de l'édition 2018 sur data.gouv.fr / data.economie.gouv.fr (https://www.data.gouv.fr/datasets/effectifs-de-la-fonction-publique-depuis-2004 ; fichier https://data.economie.gouv.fr/api/v2/catalog/datasets/effectifs-dans-la-fonction-publique/attachments/ft1_2_sl_effectifs_ensemble_fp_1_xls) : identique à SL2021 pour 1996-2015, seule l'année 2016 a été révisée depuis.

### DGAFP_SL1980_1998 – DGAFP (bureau des statistiques, des études et de l'évaluation), « Séries longues sur l'emploi dans la fonction publique 1980-1998 » (A. Brenot Ouldali, avec T. Auran, P. Massal, É. Troestler), collection RésulStats
- Fichier (archive du portail DGAFP) : https://www.fonction-publique.gouv.fr/files/files/ArchivePortailFP/www.fonction-publique.gouv.fr/files/files/statistiques/resulstats/resulstats_series-longues_2007.pdf (l'ancienne adresse https://www.fonction-publique.gouv.fr/files/files/statistiques/resulstats/resulstats_series-longues_2007.pdf renvoie aujourd'hui une erreur 404). Page de liste : https://www.fonction-publique.gouv.fr/files/files/ArchivePortailFP/www.fonction-publique.gouv.fr/resulstats.html
- Date : non imprimée dans le document ; PDF créé le 07/01/2005 (métadonnées) ; données 1980-1998, 1997 provisoire/estimé, 1998 partiel ; deuxième édition (la première, 1980-1996, datait de juin 1998).
- Tableaux utilisés : 1-1 (composantes, milliers : 1980, 1982-1997) ; 1-7 (FPE au sens large par statut, années paires 1980-1996 + 1997) ; 2-1 (ministères civils par statut, 1980-1998) ; 2-16 (Défense par statut) ; 2-34 (FPT par statut, 1984-1997) ; 2-42 (FPH) ; 2-3, 2-18, 2-23, 2-36, 2-43 (niveaux hiérarchiques A/B/C ou D) ; 3-1 (ETP).
- Champ (« fonction publique au sens large ») : effectifs réels au 31/12, hors emplois aidés (CES, CEC, CEV, emplois-jeunes) ; FPE = ministères civils + Défense (hors contingent) + établissements publics nationaux y compris EPIC non marchands + P&T (puis La Poste et France Télécom à partir du 01/01/1991) + enseignants du privé sous contrat ; métropole, DOM-TOM et étranger ; FPT = régions, départements, communes, établissements publics locaux administratifs ou industriels et commerciaux, régies, organismes privés à financement public prédominant ; métropole et DOM ; **y compris emplois secondaires** et assistantes maternelles ; FPH = hôpitaux publics et maisons de retraite publiques, y compris médecins et internes. Sources : fichiers de paie de l'État (Insee), enquête Colter (Insee), SAE/H80 et EHPA (Drees).
- Ruptures signalées par la source : FPH 1990 (étudiants hospitaliers de 2e partie de DCEM exclus, 11 600 en 1989) ; EPN 1996 (changement de méthode de collecte) ; 1997 provisoire.
- Incohérences internes relevées (laissées telles quelles, signalées en `note`) : Tableau 1-7, la colonne « Tous ministères » classe les militaires non titulaires parmi les titulaires (écart de 41 505 en 1980) contrairement au total FPE ; Tableau 2-23 (EPN, 1988-1994) : somme des niveaux > total publié ; Tableau 1-2 donne des totaux 1995-1997 légèrement différents du Tableau 1-1 (5 308,1 contre 5 306,9 milliers en 1995).
- Les parts calculées par catégorie incluent le niveau « inconnu » au dénominateur ; les tableaux de parts publiés (2-4, 2-19, 2-24, 2-37) l'excluent.

### CC2009 – Cour des comptes, « Les effectifs de l'État 1980-2008 – Un état des lieux », rapport public thématique, décembre 2009
- Fichier : https://www.vie-publique.fr/files/rapport/pdf/094000601.pdf (« Fait à la Cour, le 9 décembre 2009 »).
- Tableau 2 « Évolution de l'emploi public » (1980, 1986, 1990, 1996, 2000, 2006, 2007 ; sources Insee, Drees, DHOS – traitement DGAFP) → `CC2009_DGAFP_emplois_principaux` ; Tableau 3 (ETP, 1986-2007) → `CC2009_ETP` ; Tableau 14 (structure par catégorie 1996 et 2007) → catégories.
- Champ : emplois principaux, tous statuts, hors emplois aidés ; FPE sans La Poste/France Télécom et **sans les enseignants du privé sous contrat** (99 650 en 1980, 154 000 en 2006 selon la note du tableau) ; FPH hors non-titulaires sur crédits de remplacement. Le total ETP 1996 publié (4 178 877) est inférieur de 303 à la somme des versants.

### INSEE_ES2003 – Insee, Économie et Statistique n°369-370 (2003), P. Raynaud, « L'emploi public est tiré par la fonction publique territoriale »
- Fichier : https://www.insee.fr/fr/statistiques/fichier/1376009/es369d.pdf
- Tableau 1 (effectifs en millions : 1980, 1982, 1987, 1997, 2001) et Tableau 2 (1980, 1990, 2001, physiques et ETP).
- Champ : hors emplois aidés ; FPE = ministères + EPA nationaux ; FPT = emplois principaux des collectivités et EPA locaux (hors ASA) ; FPH y compris praticiens hospitaliers et établissements d'hébergement pour personnes âgées. Arrondi à 10 000. Même base que CC2009 (1980 : 3,86 millions).

### DGAFP_CHIFFRES_CLES_2005 / 2008 / 2009 / 2011 / 2012 – DGAFP, « Fonction publique : chiffres clés » (archive)
- Fichiers (préfixe `https://www.fonction-publique.gouv.fr/files/files/ArchivePortailFP/www.fonction-publique.gouv.fr/files/files/statistiques/chiffres_cles/pdf/`) : `Chiffres_cles_2005.pdf` (tableau « Répartition par catégorie hiérarchique des effectifs des trois fonctions publiques au 31 décembre 2003 », avec effectifs par statut), `Chiffres_cles_2008.pdf` (données 2006), `Chiffres_cles_2009.pdf` (2007), `chiffres_cles_2011-v2.pdf` (2009), `chiffres-cles-2012.pdf` (2010) : puces de synthèse « x % en catégorie A, y % en B, z % en C ». Page de liste : https://www.fonction-publique.gouv.fr/files/files/ArchivePortailFP/www.fonction-publique.gouv.fr/collection-fonction-publique-faits-et-chiffres-chiffres-cles-archives.html
- Champ : trois fonctions publiques, emplois principaux, hors emplois aidés (ensemble seulement ; les graphiques par versant ne sont pas chiffrés dans les PDF).

### DGAFP_RA2005_2006 – DGAFP, Rapport annuel « Fonction publique : faits et chiffres 2005-2006 », chapitre « Les trois fonctions publiques »
- Fichier : https://www.fonction-publique.gouv.fr/files/files/ArchivePortailFP/www.fonction-publique.gouv.fr/files/files/statistiques/rapports_annuels/2005-2006/RA_2005-2006_trois_FP.pdf
- T 1-5 « Répartition par statut et catégorie hiérarchique des effectifs des trois fonctions publiques au 31-12-2004 » (résultats provisoires ; FPT : répartition de tous les emplois appliquée aux emplois principaux ; FPH : répartition de 2001 appliquée aux effectifs 2004).

### DGAFP_RA2002 – DGAFP, Rapport annuel 2002 « La fonction publique de l'État »
- Fichier : https://www.fonction-publique.gouv.fr/files/files/ArchivePortailFP/www.fonction-publique.gouv.fr/files/files/statistiques/rapports_annuels/ran02.pdf (PDF créé le 24/07/2003).
- Tableau 2-3 « Répartition par catégorie hiérarchique des effectifs des trois fonctions publiques au 31 décembre 2001 » : en réalité années mêlées selon les notes (ministères 31/12/2001, EPA 31/12/2000, FPT et FPH 31/12/1999). La ligne « FPE+FPT+FPH » de ce tableau est incohérente (parts A+B+C = 87 %) et n'a pas été reprise ; pas de répartition publiée pour l'ensemble FPH.

### INSEE_POP_2026 – Insee, « Estimation de la population au 1er janvier 2026 – Séries par région, département, sexe et âge de 1975 à 2026 »
- Page : https://www.insee.fr/fr/statistiques/8721456 (paru le 13/01/2026). Fichier : https://www.insee.fr/fr/statistiques/fichier/8721456/estim-pop-nreg-sexe-gca-1975-2026.xlsx (un onglet par année, colonne « Total » de l'ensemble).
- 1975-1989 : métropole uniquement ; DOM à partir de 1990 ; Mayotte intégrée au champ France à partir de 2014 (`pop_france_hors_mayotte` = métropole et DOM – Mayotte, calcul) ; 2024-2026 provisoires.

## 4. Ruptures de série et écarts chiffrés entre sources

1. **Changement de sources en 2009** : avant 2009, FGE (fichier général de l'État, Insee), Colter (collectivités territoriales), DADS et enquêtes SAE/H80/EHPA (Drees) ; depuis 2009, Siasp (Insee) pour les trois versants (note de la DGAFP) ; l'Insee diffuse ses séries Siasp à partir de 2011. Les niveaux DGAFP antérieurs à 2009 sont des raccordements.
2. **Passage à la DSN (2021-2023)** : la DGAFP publie deux niveaux pour 2021 (« Classique » / « Moderne »), 2022 (millésime 2022 / 2023) et 2023 (millésime 2023 / 2024) ; l'Insee publie des valeurs révisées (r) pour 2020-2023. Exemples (hors contrats aidés, ensemble) : 2021 = 5 674 392 (Classique) contre 5 669 646 (Moderne) ; 2022 = 5 696 902 contre 5 740 763 ; 2023 = 5 803 862 contre 5 811 255. La série `DGAFP_RA2026_retropolee` neutralise ces sauts en chaînant les évolutions.
3. **Rétropolation non additive** : dans `DGAFP_RA2026_retropolee`, le total publié diffère de la somme FPE+FPT+FPH (jusqu'à +5,6 milliers en 1996, moins de 0,6 millier après 2010) et, pour les statuts (2002-2024), la somme des statuts diffère du total (au plus −14,3 milliers soit −0,27 % pour l'ensemble en 2005 ; −8,0 milliers soit −0,41 % pour la FPT en 2015). Chaque composante est rétropolée séparément.
4. **Années interpolées** : `DGAFP_RA2026_retropolee` 1997, 1999, 2001, 2003 (versants) et 2003 (statuts) = moyennes géométriques des années paires encadrantes ; aucune observation n'existe pour ces années dans les séries DGAFP récentes.
5. **Champ des années 1980-1998** : la série `DGAFP_SL1980_1998_sens_large` inclut P&T puis La Poste/France Télécom (482 000 en 1980, 439 700 en 1997), les enseignants du privé (109 000 en 1980), les EPIC nationaux et locaux et les emplois secondaires de la FPT. En 1996 (année commune) : SL1980-1998 = 5 372 300 ; hors P&T = 4 923 000 ; DGAFP rétropolée = 4 636 128 ; Cour des comptes/DGAFP 2008 = 4 489 862. L'écart entre la série DGAFP actuelle et la série Cour des comptes (146 266 en 1996) est du même ordre que les enseignants du privé sous contrat (145 900 en 1996 dans SL1980-1998), inclus dans la première et exclus de la seconde.
6. **1981 absent** de toutes les sources trouvées ; avant 1984 les détails statut FPT/FPH n'existent pas.
7. **Contrats aidés** : Insee et DGAFP ne classent pas de la même façon une partie des agents des EPA de l'État en 2011-2012 : DGAFP « place de l'emploi public » et « catégories » comptent 134 500 (2011) et 135 300 (2012) bénéficiaires, l'Insee 117 300 et 117 500 ; d'où un niveau FPE « hors contrats aidés » inférieur d'environ 17 000 dans `DGAFP_RA2026_niveaux_par_millesime` pour 2011-2012. La DGAFP signale aussi un reclassement d'environ 20 000 assistants d'éducation en contrats non aidés en 2017.
8. **Écarts Insee/DGAFP en 2024 (hors contrats aidés)** : Insee chiffres-clés 5 852 449 (calcul Ensemble – CA), Insee Première n°2094 5 850 900, DGAFP 5 848 291 ; y compris contrats aidés : chiffres-clés 5 878 246, Insee Première 5 876 700. Écarts non documentés (≤ 0,1 %).
9. **Catégories** : sauts visibles dans les séries (FPH 2010-2011 : hausse de A ; FPT et FPH 2019 : bascule B → A ; FPH 2021 : bascule C → B), à rapprocher de reclassements statutaires de corps entiers (explication de contexte, non fournie dans les fichiers) : ce ne sont pas des créations ou suppressions d'emplois ; la catégorie « indéterminée » augmente fortement dans la FPE après la DSN (67 967 en 2024). Les séries 1980-1998 utilisent des « niveaux » A/B/C ou D par composante, sans agrégat FP.
10. **EQTP Insee** : non comparables d'une publication à l'autre (ex. FP 2021 : 5 393,6 milliers dans IP1947 contre 5 496,0 dans IP2003).

## 5. Points d'attention méthodologiques

- **Agents ≠ fonctionnaires.** « Effectifs de la fonction publique » = tous les agents (fonctionnaires, militaires, contractuels, autres statuts). Au sens strict, un fonctionnaire est un **titulaire** : fin 2024, la DGAFP compte 3 745 836 fonctionnaires sur 5 848 291 agents (hors contrats aidés), plus 312 854 militaires, 1 407 727 contractuels et 381 874 « autres catégories et statuts » (série rétropolée ; somme non strictement additive). L'Insee publie « fonctionnaires et militaires » ensemble à partir de 2018.
- **Militaires** : comptés dans la FPE (militaires volontaires inclus depuis 2004 ; appelés du contingent exclus de la série 1980-1998) ; les sapeurs-pompiers militaires de Marseille sont comptés avec les fonctionnaires de la FPT. L'Insee ne publie plus les militaires à part depuis 2018 (sauf Insee Première n°2094 pour 2024 : 12,1 % de la FPE).
- **Enseignants du privé sous contrat** : contractuels de droit public rémunérés par l'État, inclus dans la FPE (« autres catégories et statuts ») dans les séries Siasp/DGAFP actuelles, mais exclus de la série Cour des comptes 2009 / Insee 2003.
- **Autres catégories et statuts** : ouvriers d'État, enseignants du privé (FPE), assistants maternels et familiaux (FPT), médecins hospitaliers (FPH), apprentis.
- **Contrats aidés** : les séries DGAFP sont hors contrats aidés ; l'Insee publie les deux. Leur nombre a fortement varié (Insee : 197 700 fin 2015, 25 797 fin 2024), ce qui change les évolutions y compris contrats aidés.
- **Mayotte** : exclue de toutes les séries Siasp (France hors Mayotte). Ordre de grandeur (DGAFP, enquête Emploi Mayotte, personnes de 15-64 ans, non comparable) : 22 000 agents en 2024 dont 12 000 dans la FPE.
- **Personnes physiques, postes principaux** : une personne = un poste principal au 31/12 (pas de double compte), sauf la FPT de la série 1980-1998 qui inclut les emplois secondaires. Les ETP et EQTP sont dans un fichier séparé.
- **La Poste et France Télécom** : ministère des P&T jusqu'en 1990 (agents de l'État), exploitants publics à partir de 1991 ; exclus de toutes les séries actuelles ; inclus dans la série 1980-1998 « au sens large ».
- **Taux d'administration** : le taux officiel DGAFP (76,8 ETP civils pour 1 000 habitants en 2024) porte sur les agents civils en ETP, hors militaires et hors contrats aidés ; les ratios de `taux_administration.csv` calculés à partir des effectifs physiques (y compris militaires) sont plus élevés (85,3 en 2024 avec la série DGAFP). Avant 1990, la population disponible est celle de la métropole seule (ratio surestimé).
- **Avant 1980** : les rapports annuels 1975-1990 de la fonction publique existent dans l'archive DGAFP (https://www.fonction-publique.gouv.fr/files/files/ArchivePortailFP/www.fonction-publique.gouv.fr/rapports-annuels-sur-letat-de-la-fonction-publique-archives.html), mais ce sont des scans dont l'OCR est défectueux et les concepts différents (enquête Emploi, effectifs budgétaires) : non repris. Le chiffre de « 3,9 millions en 1980 » parfois cité (État et collectivités locales, mars 1980, rapport annuel 1980, Tableau I) provient de l'enquête Emploi, concept différent des séries ci-dessus.

## 6. Contrôles effectués

- Sommes internes de chaque tableau (versants = total, statuts = total, catégories = total) : 317 contrôles OK ; 118 écarts publiés dans les sources et signalés en `note` (rétropolation non additive) ; 0 écart non expliqué (`controles.txt`).
- Relecture indépendante de 29 cellules des fichiers bruts avec une autre chaîne de lecture (pandas) : 29/29 identiques (`scripts/verify_spotchecks.py`).
- Comparaison Insee chiffres-clés / Insee Première n°2094 / DGAFP pour 2024 (section 4, point 8) ; comparaison Cour des comptes / DGAFP 1996 (point 5) ; SL2018 / SL2021 (identiques sauf 2016).

## 7. Limites connues

- Pas de série annuelle unique et homogène de 1980 à 2024 : deux blocs officiels (1980-1997 champ large ; 1996-2024 champ actuel) qui se recouvrent en 1996-1997 avec un écart de niveau important (section 4, point 5). Aucun raccordement n'a été fabriqué.
- 1981 manquant ; 1997, 1999, 2001, 2003 seulement interpolés dans la série DGAFP actuelle (1997 et 2001 existent toutefois dans d'autres séries : SL1980-1998 pour 1997, Insee 2003 arrondi pour 1997 et 2001) ; pour 1998-2001, statuts et catégories ne sont que partiels (rapport 2002, années mêlées 1999-2001).
- Statuts : pas de décomposition fonctionnaires/contractuels par versant entre 1998 et 2001 ; avant 1984, pas de détail FPT/FPH ; l'Insee ne sépare plus les militaires depuis 2018 (la DGAFP oui).
- Catégories par versant : années 2002-2003, 2005-2006 et 2008-2009 non couvertes (seules des parts pour l'ensemble des trois versants en 2003, 2006, 2007, 2009) ; avant 1998, uniquement par composante (ministères civils, Défense, EPN, FPT, personnel non médical de la FPH), sans agrégat FP.
- ETP : séries discontinues (concepts différents : ETP au 31/12, volume de travail annuel en EQTP), aucun ETP national trouvé pour 2008-2015 dans les fichiers téléchargés.
- Population : DOM non disponibles avant 1990 dans le fichier Insee utilisé.
