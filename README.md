# Fonction publique : les chiffres

Site d'information du **Parti Libéral Français** qui présente, à partir des seules
sources officielles (Insee, DGAFP), le nombre d'agents de la fonction publique
en France : évolution sur longue période, carte par département, répartition par
versant (État, territoriale, hospitalière), par statut (fonctionnaires,
contractuels, militaires…) et par catégorie hiérarchique (A, B, C).

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
assets/
  css/style.css        charte graphique PLF (pétrole, turquoise, safran) et mise en page
  js/app.js            options d'affichage, formats français, tableaux, export CSV
  js/graphiques.js     graphiques SVG accessibles (courbes, barres, gaufre)
  js/carte.js          carte interactive des départements
  js/pages.js          remplissage des pages à partir des données
  fonts/               Jost et Atkinson Hyperlegible (licence SIL OFL)
  img/logo-plf.svg     logo du parti
donnees/
  csv/                 données propres, téléchargeables (séparateur « ; »), une source par ligne
  site/                mêmes données, au format lu par le site (générées)
  geo/                 fond de carte des départements (généré)
  methodologie_series_nationales.md   extraction des séries nationales : sources, champs, ruptures, contrôles
  methodologie_departements.md        extraction des données départementales : idem
  empreintes_fichiers_sources.txt     empreintes SHA-256 des fichiers officiels utilisés
outils/
  fond_de_carte.py     construit le fond de carte (Lambert-93, encarts outre-mer)
  construire_donnees.py  transforme donnees/csv/ en donnees/site/
```

## Ce que contiennent les données

- **Séries nationales** : effectifs par versant de 1980 à 2024 (série DGAFP actuelle 1996-2024 et
  série historique 1980-1997, affichées sans « raccord »), statuts 2002-2024, catégories A/B/C
  2010-2024 (et repères 1996-2010), population Insee.
- **Carte** : agents civils par département, 2010-2024 (période homogène, source Siasp), plus
  2005-2009 en option (ancienne méthode, métropole seulement). Les militaires (≈ 313 000) ne sont
  pas localisés par la statistique publique ; Mayotte n'est pas couverte par la source.
- Chaque chiffre renvoie à sa source dans `donnees/csv/sources.csv` (adresse exacte du fichier
  officiel). Les seuls calculs sont des sommes, des parts, des taux pour 1 000 habitants et des
  évolutions.

## Mettre à jour les données (chaque année)

L'Insee et la DGAFP publient les effectifs de l'année N-1 en fin d'année N
(Insee Première sur l'emploi public, rapport annuel de la DGAFP en novembre).

1. Ajouter les nouvelles lignes dans les fichiers de `donnees/csv/`
   (même format, une ligne par année / département / versant), en citant la source
   (`source_id`, à décrire dans `sources.csv` si elle est nouvelle).
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

- Données : Insee, DGAFP — Licence Ouverte / Open Licence 2.0 (Etalab).
- Fond de carte : IGN ADMIN EXPRESS via Etalab (Licence Ouverte 2.0), Natural Earth (domaine public).
- Polices : Jost et Atkinson Hyperlegible — SIL Open Font License 1.1.
