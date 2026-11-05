# Masse salariale publique : sources, extraction, contrôles et ruptures

> **Document de travail : extraction des données de la page « La masse salariale ».** Toutes les
> valeurs viennent de fichiers officiels téléchargés le 5 novembre 2026 par
> `outils/extraire_masse_salariale.py`, qui lit les cellules publiées, écrit les CSV de
> `donnees/csv/` et s'arrête si un contrôle échoue. Les fichiers bruts restent dans `.cache/sources/`
> (non versionné) ; leurs empreintes SHA-256 sont dans `donnees/empreintes_masse_salariale.txt`.
> `outils/construire_donnees.py` transforme ensuite les CSV en `donnees/site/masse_salariale.js`.

## 1. Fichiers produits

| Fichier | Contenu | Années | Source (`source_id`) |
|---|---|---|---|
| `masse_salariale_comptes_nationaux.csv` | D1, D11, D12, D121, D122, D291 par secteur (S13, S1311, S13111, S13112, S1313, S1314), milliards d'euros courants | 1949-2025 (État et ODAC, D291 : 1978-2025) | `INSEE_CN2025_APU` |
| `agregats_comptes_nationaux.csv` | PIB, population moyenne, prix à la consommation (base 100 en 2025), dépenses publiques totales, emploi des APU en personnes et en ETP (par sous-secteur) | 1949-2025 (dépenses : 1959- ; emploi : 1978- ; sous-secteurs : 2006-2024) | `INSEE_CN2025_PIB`, `INSEE_CN2025_DEPENSES`, `INSEE_IPC_CONVERTISSEUR` |
| `remunerations_apu_dont.csv` | D1 des collectivités locales et des organismes dépendant des assurances sociales (hôpitaux, France Travail…) | 2013-2025 | `DGAFP_RA2026_DEPENSES` (figure 1) |
| `depenses_personnel_etat.csv` | Titre 2 du budget général, 32 lignes (codes de la nomenclature budgétaire 210 à 239), pensions versées, budget de l'État | 2008-2025 | `DGAFP_RA2026_DEPENSES` (figure 2) |
| `remunerations_activite_etat.csv` | Rémunérations d'activité de l'État par statut et par nature | 2008-2025 | `DGAFP_RA2026_DEPENSES` (figure 4) |
| `depenses_personnel_collectivites.csv` | Régions, départements, communes, groupements à fiscalité propre ; dépenses totales | 1996-2025 | `DGAFP_RA2026_DEPENSES` (figure 5) |
| `charges_personnel_hopitaux.csv` | Établissements publics de santé : rémunérations (non médical, médical), charges sociales, impôts et taxes, autres ; dépenses totales | 2000-2025 | `DGAFP_RA2026_DEPENSES` (figure 6) |
| `salaires_moyens_fonction_publique.csv` | Salaires mensuels bruts et nets moyens en EQTP par versant et population, avec les deux mesures publiées pour 2021-2023 | 2015-2024 (FPE : 2004-2024) | `DGAFP_RA2026_REMU` (figures 4 et FPE 13) |
| `salaires_2024_fonction_publique.csv` | 2024 : brut et net moyens, médiane, déciles, part des effectifs, par versant, statut, catégorie, sexe, âge | 2024 | `DGAFP_RA2026_REMU` (vue, figure 1) |
| `deciles_salaires_public_prive_2024.csv` | Déciles du salaire net, FPE, FPT, FPH, fonction publique, secteur privé | 2024 | `DGAFP_RA2026_REMU` (vue, figure 5) |
| `decomposition_salaire_fonctionnaires_2024.csv` | Fonctionnaires : brut, traitement, primes, cotisations salariales, CSG-CRDS, net | 2024 | `DGAFP_RA2026_REMU` (vue, figure 10) |
| `salaires_nets_public_prive_euros_constants.csv` | Salaire net moyen en euros constants de 2024, fonction publique et privé | 2011-2024 | `DGAFP_RA2026_EVOL` (figure 0) |
| `point_indice.csv` | Valeur annuelle moyenne de l'indice 100 | 1970-2025 | `DGAFP_SL2021_POINT` (1970-2020), `DGAFP_RA2026_EVOL` (2021-2025, calcul) |
| `remunerations_par_fonction.csv` | D1 des APU par fonction COFOG (10 fonctions, 69 sous-fonctions), millions d'euros | 1995-2024 | `EUROSTAT_COFOG` |
| `remuneration_publique_europe.csv` | D1 des APU en % du PIB, 34 pays et agrégats | 1995-2025 | `EUROSTAT_GOV_MAIN` |

Les adresses exactes des fichiers sont dans `donnees/csv/sources.csv` et en tête du script.

## 2. Comment chaque tableau est lu

- **Insee 7.301 à 7.306** (comptes de secteur) : partie « Compte d'exploitation », rubrique
  « Emplois » ; lignes repérées par le code de l'opération (colonne A) ; années lues dans la ligne
  d'en-tête. Le titre du tableau doit contenir le code du secteur attendu.
- **Insee 1.115** : lignes `POP` et `B1GQ` (la première, en euros courants ; le script vérifie que ce
  n'est pas la ligne en volume). **1.108 / 1.109** : lignes `S13`, `S13111`, `S13112`, `S1313`, `S1314`.
  **3.201** : lignes « Total des dépenses » et « Rémunération des salariés (D1) ».
- **Prix** : série Insee 011813530 (coefficients du convertisseur franc-euro, base 100 en 2025),
  lue au format SDMX.
- **DGAFP** : les classeurs sont lus directement dans les archives zip ; les lignes sont repérées par
  leur libellé (ou par le code budgétaire pour le titre 2), les colonnes par l'année d'en-tête
  (« 2023* », « 2016(a) », « 2021 Moderne »… sont reconnus).
- **Eurostat** : API de diffusion, format JSON-stat (`gov_10a_exp` et `gov_10a_main`).

## 3. Contrôles automatiques (le script s'arrête s'ils échouent)

- Pour chaque secteur et chaque année : D11 + D12 = D1 et D121 + D122 = D12 (à 2 millions d'euros
  près, arrondis de publication).
- APUC + APUL + ASSO = APU, et État + ODAC = APUC pour D1 (opération non consolidée).
- Le D1 du tableau 3.201 est identique à celui du tableau 7.301 pour chaque année.
- Figure 1 de la DGAFP = comptes de l'Insee pour chaque secteur et chaque année 1978-2025
  (écart maximal constaté : 0,5 million d'euros).
- Titre 2 : somme des lignes de rémunérations d'activité, du CAS Pensions, des cotisations et total
  général (à 2 millions d'euros près).
- Collectivités et hôpitaux : somme des composantes = ensemble (à 60 millions d'euros près, les
  montants récents étant publiés arrondis à 100 millions).
- Décomposition des salaires : traitement + primes = brut et brut − cotisations − CSG-CRDS = net.
- Point d'indice : la moyenne recalculée à partir des dates de revalorisation redonne la série longue
  de la DGAFP pour 2018-2020.
- Eurostat : somme des 10 fonctions = total ; total identique à l'Insee à 1 million d'euros près
  pour 1999-2022 (écarts signalés pour 1995-1998 et 2024, voir ci-dessous) ; part de la France en
  2025 identique au rapport D1 / PIB de l'Insee (à 0,1 point près).

Relecture indépendante : 28 cellules des fichiers bruts ont été relues avec une autre chaîne de
lecture (pandas, positions de cellules saisies à la main) et comparées aux CSV : 28/28 identiques
après prise en compte de la précision publiée.

## 4. Calculs

- **Euros constants** : montant × prix(2025) / prix(année).
- **Parts** : D1 / PIB ; D1 / dépenses publiques totales.
- **Par habitant** : D1 / population moyenne de l'année ; **par emploi** : D1 / emploi en ETP / 12.
- **Salaire net global (estimation)** : D11 × (salaire net moyen / salaire brut moyen de l'ensemble
  de la fonction publique en 2024 selon la DGAFP, soit 2 741,90 / 3 382,20 = 81,07 %). Appliqué à
  2025, dernière année des comptes ; le champ des comptes nationaux (y compris les caisses de
  Sécurité sociale) est un peu plus large que celui de la DGAFP.
- **« Sur 100 € »** : parts de D1 + D291, arrondies au plus fort reste (somme exacte de 100).
- **Point d'indice 2021-2025** : moyenne des 12 valeurs mensuelles, la valeur d'un mois étant celle
  de la dernière revalorisation intervenue au plus tard le 1er du mois.

## 5. Ruptures et points d'attention

1. **Comptes nationaux base 2020** : séries rétropolées par l'Insee jusqu'en 1949, homogènes ; 2024
   semi-définitif, 2025 provisoire.
2. **Autonomie des universités (2009-2012)** : transfert de rémunérations de l'État vers les ODAC
   (emploi en ETP de l'État −95 000 et des ODAC +78 000 entre 2009 et 2010).
3. **Titre 2 de l'État** : l'enseignement privé sous contrat est inclus ; à partir de 2012, les CLD
   sont imputés sur le traitement brut et les stagiaires comptés avec les fonctionnaires.
   Figure 4 : en 2024, la DGAFP ajoute à la ligne des contractuels ceux en CDI hors enseignement
   privé (0,9 Md€ en 2019, 2,8 Md€ en 2024) ; le total publié n'inclut pas la ligne « non réparti »
   en 2014 et en 2022-2025.
4. **Collectivités** : collectivités uniques de Martinique et de Guyane (2016), collectivité de Corse
   (2018), Ville de Paris (2019) : changements de niveau sans effet sur le total.
5. **Hôpitaux** : depuis 2006, les reports de charges ne sont plus dans les « autres charges ».
6. **Salaires** : deux mesures publiées pour 2021, 2022 et 2023 (passage à la DSN), toutes deux
   conservées dans `salaires_moyens_fonction_publique.csv` (colonne `version`) ; la page utilise les
   niveaux 2024 et la série en euros constants 2011-2024 publiée par la DGAFP. FPE : fichier général
   de l'État avant 2009, Siasp ensuite. Champ : EQTP, hors militaires, apprentis, assistants maternels et familiaux,
   internes et externes des hôpitaux, y compris contrats aidés.
7. **Eurostat COFOG** : pour 1995-1998 (écarts de +0,9 à +1,7 Md€ et de −1,1 à −1,4 Md€) et pour
   2024 (−0,9 Md€), le total diffère de la dernière version de l'Insee (transmission antérieure).
8. **Comparaisons européennes** : elles dépendent de la part des services publics confiés à des
   organismes privés financés par des fonds publics (hôpitaux, écoles, crèches, maisons de retraite).
