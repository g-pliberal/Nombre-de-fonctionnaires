# Fonction publique : les chiffres

Site d'information du **Parti Libéral Français** qui présente, à partir des seules
sources officielles (Insee, DGAFP, OFGL, Eurostat), le nombre d'agents de la fonction publique
en France, leur masse salariale et leurs retraites : évolution sur longue période, carte par
département, répartition par versant (État, territoriale, hospitalière), par statut
(fonctionnaires, contractuels, militaires…) et par catégorie hiérarchique (A, B, C),
rémunérations avec et sans cotisations ni impôts depuis 1949, détail par ministère, par
collectivité et par département, salaires moyens et plus hautes rémunérations, pensions des
fonctionnaires depuis 1990, comparaisons européennes.

Le site est **statique** (HTML, CSS et JavaScript sans aucune dépendance externe) :
il s'ouvre directement dans un navigateur et s'héberge gratuitement sur
GitHub Pages. Il ne dépose aucun cookie et n'utilise aucun traceur.

## Pages

| Page | Contenu |
| --- | --- |
| `index.html` | L'essentiel : chiffres clés, fonctionnaire ou agent public, les trois versants |
| `evolution.html` | Évolution des effectifs sur longue période, en nombre et pour 1 000 habitants |
| `carte.html` | Carte interactive par département et par année (taux d'administration, effectifs, évolution) |
| `composition.html` | Statuts (fonctionnaires, contractuels…) et catégories A, B, C |
| `masse-salariale.html` | La masse salariale (coût et évolution) : du coût employeur au salaire net, séries depuis 1949, par employeur (État, collectivités, hôpitaux, Sécurité sociale), paie de l'État ligne par ligne, par ministère et par type de collectivité, carte des frais de personnel des collectivités par département, par mission, comparaison européenne |
| `salaires.html` | Les salaires : du brut au net par population, public/privé, déciles, point d'indice depuis 1970, salaires par ministère, collectivité et filière, plus hautes rémunérations (1 % le mieux payé, emplois de direction, dix plus hautes rémunérations publiées par les employeurs) |
| `retraites.html` | Les retraites des fonctionnaires : pensions versées depuis 1990, pensions en paiement, montants, ratio démographique, compte « Pensions » de l'État, taux de cotisation, déficit de la CNRACL, départs et âge de départ |
| `methode.html` | Sources, définitions, limites, téléchargements, accessibilité |

## Consulter le site sur son ordinateur

Double-cliquer sur `index.html` suffit : les données sont chargées sous forme de
fichiers JavaScript (`donnees/site/*.js`), ce qui évite tout serveur.

## Publier sur GitHub Pages

1. Sur GitHub : *Settings* → *Pages*.
2. *Source* : « Deploy from a branch », branche `main`, dossier `/ (root)`.
3. Le site est publié à l'adresse indiquée par GitHub quelques minutes plus tard.

Pour un nom de domaine (ex. `chiffres.partiliberalfrancais.fr`), ajouter un
fichier `CNAME` à la racine et un enregistrement DNS `CNAME` vers
`<compte>.github.io`.

## Organisation des fichiers

```
index.html, evolution.html, carte.html, composition.html, methode.html
masse-salariale.html, salaires.html, retraites.html   rubrique « La masse salariale » (sous-navigation)
assets/
  css/style.css        charte graphique PLF (pétrole, turquoise, safran) et mise en page
  js/app.js            options d'affichage, formats français, tableaux, export CSV
  js/graphiques.js     graphiques SVG accessibles (courbes, barres, gaufre)
  js/carte.js          carte interactive des départements
  js/pages.js          remplissage des pages à partir des données
  js/masse-salariale.js  pages « Coût et évolution » et « Salaires », encadré de la page d'accueil
  js/retraites.js      page « Retraites » (et chiffres clés de la page d'accueil)
  fonts/               Jost et Atkinson Hyperlegible (licence SIL OFL)
  img/logo-plf.svg     logo du parti
donnees/
  csv/                 données propres, téléchargeables (séparateur « ; »), une source par ligne
  site/                mêmes données, au format lu par le site (générées)
  geo/                 fond de carte des départements (généré)
  methodologie_series_nationales.md   extraction des séries nationales : sources, champs, ruptures, contrôles
  methodologie_departements.md        extraction des données départementales : idem
  methodologie_masse_salariale.md     extraction des données de masse salariale : sources, contrôles, calculs, ruptures
  empreintes_fichiers_sources.txt     empreintes SHA-256 des fichiers officiels utilisés
  empreintes_masse_salariale.txt      idem pour la masse salariale (écrit par le script d'extraction)
outils/
  fond_de_carte.py     construit le fond de carte (Lambert-93, encarts outre-mer)
  extraire_masse_salariale.py  télécharge les fichiers officiels (Insee, DGAFP, OFGL, Eurostat) et
                       produit les CSV de la masse salariale, des salaires et des retraites,
                       avec contrôles de cohérence
  construire_donnees.py  transforme donnees/csv/ en donnees/site/
```

## Ce que contiennent les données

- **Séries nationales** : effectifs par versant de 1980 à 2024 (série DGAFP actuelle 1996-2024 et
  série historique 1980-1997, affichées sans « raccord »), statuts 2002-2024, catégories A/B/C
  2010-2024 (et repères 1996-2010), population Insee.
- **Carte** : agents civils par département, 2010-2024 (période homogène, source Siasp), plus
  2005-2009 en option (ancienne méthode, métropole seulement). Les militaires (≈ 313 000) ne sont
  pas localisés par la statistique publique ; Mayotte n'est pas couverte par la source.
- **Masse salariale** : rémunération des salariés des administrations publiques (salaires bruts,
  cotisations effectives et imputées) et impôts sur les salaires, par sous-secteur, 1949-2025
  (comptes nationaux de l'Insee, base 2020) ; PIB, population, dépenses publiques, emploi ;
  dépenses de personnel de l'État ligne par ligne (2008-2025), des collectivités (1996-2025) et des
  hôpitaux (2000-2025) ; salaires moyens bruts et nets (DGAFP, 2004-2024), point d'indice
  (1970-2025) ; rémunérations par fonction (1995-2024) et comparaison européenne (1995-2025,
  Eurostat) ; salaires et effectifs par ministère, type de collectivité et filière (2024) ;
  plus hautes rémunérations (2024-2025) ; frais de personnel des communes, intercommunalités et
  départements par département (OFGL, 2024).
- **Retraites** : pensions versées par les régimes de fonctionnaires (1990-2025), pensions en
  paiement et pension moyenne (2000-2025), ratio démographique (1990-2025), compte « Pensions »
  de l'État et compte de résultat de la CNRACL (2006-2025), taux de cotisation (2000-2025),
  départs (2000-2025) et âge de départ (2015-2025), d'après la DGAFP.
- Chaque chiffre renvoie à sa source dans `donnees/csv/sources.csv` (adresse exacte du fichier
  officiel). Les seuls calculs sont des sommes, des parts, des taux (pour 1 000 habitants, par
  habitant, par emploi, en % du PIB), des évolutions, des conversions en euros constants (indice
  des prix à la consommation de l'Insee) et une estimation du salaire net global, signalée comme
  telle (part du net dans le brut mesurée par la DGAFP).

## Mettre à jour les données (chaque année)

L'Insee et la DGAFP publient les effectifs de l'année N-1 en fin d'année N
(Insee Première sur l'emploi public, rapport annuel de la DGAFP en novembre).

1. Ajouter les nouvelles lignes dans les fichiers de `donnees/csv/`
   (même format, une ligne par année / département / versant), en citant la source
   (`source_id`, à décrire dans `sources.csv` si elle est nouvelle).
   Pour la masse salariale : mettre à jour les adresses des fichiers en tête de
   `outils/extraire_masse_salariale.py` (comptes de la Nation publiés fin mai par l'Insee,
   rapport annuel de la DGAFP publié en octobre-novembre), puis lancer
   `python3 outils/extraire_masse_salariale.py` : le script télécharge les fichiers, contrôle
   les totaux et réécrit les CSV de la masse salariale (et leurs empreintes).
2. Régénérer les fichiers du site :
   ```
   python3 outils/construire_donnees.py
   ```
   Le script vérifie la cohérence (totaux, années, départements) et s'arrête en
   cas d'anomalie.
3. Mettre à jour à la main les quelques chiffres écrits en toutes lettres dans les pages HTML
   (les chiffres clés et les graphiques se mettent à jour seuls).
4. Ouvrir `index.html` pour contrôler, puis publier (commit + push).

Le fond de carte n'a besoin d'être reconstruit qu'en cas de changement des
limites départementales (`python3 outils/fond_de_carte.py`, nécessite Node.js).

## Police du Parti Libéral Français

Le site du PLF utilise la famille *SansSerifFLF* (Richard A. Ware), dont la
licence de diffusion n'est pas claire (« All Rights Reserved »). Ce dépôt utilise
donc **Jost**, police libre au dessin géométrique très proche. Si le parti
dispose des droits, il suffit de remplacer la déclaration `@font-face` « Jost »
en tête de `assets/css/style.css` par les fichiers *SansSerifBldFLF*.

## Accessibilité

Objectif : RGAA 4.1 / WCAG 2.1 niveau AA. Contrastes vérifiés, navigation
complète au clavier (y compris la carte : flèches pour passer d'un département
à son voisin), graphiques doublés de tableaux de données, annonces pour les
lecteurs d'écran, options d'affichage (thème clair ou sombre, grande taille de
texte, police très lisible, espacement aéré), respect du réglage « réduire les
animations ». Le site n'a pas encore fait l'objet d'un audit indépendant.

## Licences

- Données : Insee, DGAFP — Licence Ouverte / Open Licence 2.0 (Etalab) ; Eurostat — réutilisation
  autorisée en citant la source.
- Fond de carte : IGN ADMIN EXPRESS via Etalab (Licence Ouverte 2.0), Natural Earth (domaine public).
- Polices : Jost et Atkinson Hyperlegible — SIL Open Font License 1.1.
