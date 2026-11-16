"""Fiches des départements : une page HTML par département (departements/<code>.html)
et une page qui les liste (departements/index.html).

Appelé par outils/construire_donnees.py, après la construction des données et la mise
à jour des chiffres des pages : chaque fiche est entièrement générée à partir des mêmes
objets que donnees/site/departements.js et donnees/site/masse_salariale.js, donc à partir
des CSV officiels de donnees/csv/. Aucun chiffre n'est saisi à la main ; ne pas modifier
les fiches à la main, elles sont réécrites à chaque construction (et l'intégration
continue vérifie qu'elles sont à jour).

L'en-tête, le menu, le pied de page et le dialogue « Options d'affichage » sont repris de
carte.html (adresses relatives corrigées), pour rester identiques au reste du site.
Les graphiques sont dessinés par assets/js/departement.js ; sans JavaScript, la fiche
reste complète (chiffres et tableaux sont écrits dans la page).
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Callable

DOSSIER = "departements"
VERSANTS = [("fpe", "Fonction publique de l'État", "État"),
            ("fpt", "Fonction publique territoriale", "Territoriale"),
            ("fph", "Fonction publique hospitalière", "Hospitalière")]
# Frais de personnel des collectivités : mêmes règles de comparabilité que la carte de la page
# « La masse salariale » (assets/js/masse-salariale.js, NIVEAUX) : sans conseil départemental
# (Corse, Martinique, Guyane), le total n'est pas comparable ; la Ville de Paris est comptée
# avec les communes et la métropole de Lyon avec les intercommunalités.
SANS_DEP = ["2A", "2B", "972", "973"]
NIVEAUX_LOC = [
    ("communes", "Communes", ["75"]),
    ("groupements", "Intercommunalités à fiscalité propre", ["69"]),
    ("departement", "Conseil départemental", SANS_DEP + ["75", "69"]),
    ("total", "Ensemble", SANS_DEP),
]
NBSP = " "

e = lambda s: html.escape(str(s), quote=True)  # noqa: E731


def _adresse_site() -> str:
    """Adresse publique du site, définie une seule fois dans outils/referencement.py."""
    from referencement import ADRESSE_SITE
    return ADRESSE_SITE


def _gabarit(racine: Path, verifier: Callable) -> dict:
    """Découpe carte.html en morceaux réutilisables (en-tête, pied, dialogue)."""
    t = (racine / "carte.html").read_text(encoding="utf-8")
    morceaux = {}
    for nom, motif in {
        "debut_head": r"^(.*?<meta name=\"viewport\"[^>]*>\n)",
        "fin_head": r"(<meta name=\"theme-color\".*?)<meta property=\"og:title\"",
        "liens_head": r"(<link rel=\"icon\".*?</head>\n)",
        "entete": r"(<div class=\"evitement\">.*?)<div class=\"conteneur bandeau\">",
        "pied": r"</main>\n\n(<footer.*?</dialog>\n)",
    }.items():
        m = re.search(motif, t, re.S)
        verifier(m is not None, f"carte.html : morceau « {nom} » introuvable (gabarit des fiches)")
        morceaux[nom] = m.group(1)
    # Adresses relatives : les fiches sont un dossier plus bas.
    rel = re.compile(r'\b(href|src)="(?!https?:|#|mailto:|data:|/|\.\./)')
    for k in morceaux:
        morceaux[k] = rel.sub(lambda m: f'{m.group(1)}="../', morceaux[k])
    morceaux["entete"] = morceaux["entete"].replace(' aria-current="page"', "")
    return morceaux


def _page(g: dict, *, titre: str, description: str, url: str, image: dict, page: str, dep: str | None,
          bandeau: str, contenu: str, scripts: list[str]) -> str:
    desc = e(description)
    attr_dep = f' data-dep="{e(dep)}"' if dep else ""
    return (
        g["debut_head"]
        + f"<title>{e(titre)}</title>\n"
        + f'<meta name="description" content="{desc}">\n'
        + g["fin_head"]
        + f'<meta property="og:title" content="{e(titre)}">\n'
        + f'<meta property="og:description" content="{desc}">\n'
        + '<meta property="og:type" content="website">\n<meta property="og:locale" content="fr_FR">\n'
        + f'<meta property="og:site_name" content="{e(image["site"])}">\n'
        + f'<meta property="og:url" content="{e(url)}">\n'
        + f'<meta property="og:image" content="{e(image["url"])}">\n'
        + '<meta property="og:image:type" content="image/png">\n'
        + '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
        + f'<meta property="og:image:alt" content="{e(image["alt"])}">\n'
        + '<meta name="twitter:card" content="summary_large_image">\n'
        + f'<meta name="twitter:image" content="{e(image["url"])}">\n'
        + f'<meta name="twitter:image:alt" content="{e(image["alt"])}">\n'
        + g["liens_head"].replace("</head>\n", "<!-- Page générée par outils/construire_donnees.py "
                                  "(outils/fiches_departements.py) : ne pas modifier à la main. -->\n</head>\n")
        + f'<body data-page="{page}"{attr_dep}>\n'
        + g["entete"]
        + bandeau
        + "\n</header>\n<main id=\"contenu\" tabindex=\"-1\">\n"
        + contenu
        + "\n</main>\n\n"
        + g["pied"]
        + "".join(f'<script src="../{s}"></script>\n' for s in scripts)
        + "</body>\n</html>\n"
    )


def ecrire_fiches(racine: Path, D: dict, C: dict, cles: dict, *, fr: Callable, verifier: Callable) -> int:
    """Écrit departements/<code>.html et departements/index.html. Renvoie le nombre de pages."""
    g = _gabarit(racine, verifier)
    site = _adresse_site()
    annees = D["annees"]
    a0 = D["debutHomogene"]
    i0, i_fin = annees.index(a0), len(annees) - 1
    a_fin = annees[i_fin]
    deps, F = D["departements"], D["france"]
    codes = list(deps)  # déjà dans l'ordre (01, 02, …, 2A, 2B, …, 976)
    verifier(len(codes) == 101, "fiches : 101 départements attendus")
    verifier(sorted(C["codes"]) == sorted(codes), "fiches : départements différents entre effectifs et frais de personnel")
    verifier(cles["dep_taux_france"] == fr(1000 * F["ensemble"][i_fin] / F["population"][i_fin], 1),
             "fiches : taux France différent de celui de la carte")

    def pct_signe(v: float, dec: int = 1) -> str:
        s = fr(abs(v), dec)
        return ("+" if v > 0 and s.strip("0,") else "−" if v < 0 and s.strip("0,") else "") + s + NBSP + "%"

    def taux(serie, pop, i):
        return None if serie[i] is None or not pop[i] else 1000 * serie[i] / pop[i]

    lib_france = "France (hors Mayotte)"
    taux_fr = {v: taux(F[v], F["population"], i_fin) for v in ["ensemble", "fpe", "fpt", "fph"]}
    avec = [c for c in codes if deps[c]["ensemble"][i_fin] is not None]
    t_fin = {c: taux(deps[c]["ensemble"], deps[c]["population"], i_fin) for c in avec}
    ordre_taux = sorted(avec, key=lambda c: -t_fin[c])
    rang = {c: ordre_taux.index(c) + 1 for c in avec}
    evol_fr = 100 * (F["ensemble"][i_fin] / F["ensemble"][i0] - 1)
    evol_pop_fr = 100 * (F["population"][i_fin] / F["population"][i0] - 1)

    # Frais de personnel des collectivités (OFGL)
    idx = {c: k for k, c in enumerate(C["codes"])}
    a_loc = C["annee"]
    pop_fr_loc = sum(C["population"])
    loc_fr = {n: sum(v or 0 for v in C[n]) / pop_fr_loc for n, _, _ in NIVEAUX_LOC}
    verifier(cles["ms_loc_hab"] == fr(loc_fr["total"]) + " €", "fiches : moyenne des frais de personnel différente de la page « La masse salariale »")

    def loc_hab(c, n):
        k = idx[c]
        exclus = next(x for niv, _, x in NIVEAUX_LOC if niv == n)
        v = C[n][k]
        return None if v is None or c in exclus else v / C["population"][k]

    image = {
        "site": "Fonction publique : les chiffres",
        "url": site + "assets/img/partage/carte.png",
        # Même texte que l'image de la carte (outils/images_partage.py, cartes()["carte"]).
        "alt": (f"Où travaillent les agents publics ? {cles['dep_taux_france']} agents publics civils pour 1 000 habitants "
                f"en {cles['dep_derniere_annee']}. De {cles['dep_taux_min']} ({cles['dep_nom_min']}) à "
                f"{cles['dep_taux_max']} ({cles['dep_nom_max']}) selon le département.").replace("\u202f", " "),
    }
    src_eff = e(D["sourceCourte"])
    src_loc = e(C["source"])
    sortie = racine / DOSSIER
    sortie.mkdir(exist_ok=True)
    ecrites = set()

    def ecrire(nom: str, texte: str) -> None:
        chemin = sortie / nom
        if not chemin.exists() or chemin.read_text(encoding="utf-8") != texte:
            chemin.write_text(texte, encoding="utf-8")
        ecrites.add(nom)

    def tableau(legende: str, entetes: list[str], lignes: list[list[str]], haut: bool = False) -> str:
        th = "".join(('<th scope="col" class="texte">' if j == 0 else '<th scope="col">') + f"{h}</th>"
                     for j, h in enumerate(entetes))
        corps = "".join("<tr>" + "".join((f'<th scope="row" class="texte">{x}</th>' if j == 0 else f"<td>{x}</td>")
                                         for j, x in enumerate(l)) + "</tr>\n" for l in lignes)
        return (f'<div class="tableau-defilant{" tableau-defilant--haut" if haut else ""}" tabindex="0" role="region" '
                f'aria-label="{e(re.sub(r"<[^>]+>", "", legende))}">\n<table>\n<caption>{legende}</caption>\n'
                f"<thead><tr>{th}</tr></thead>\n<tbody>\n{corps}</tbody>\n</table>\n</div>")

    def chiffre(valeur: str, libelle: str, detail: str) -> str:
        return (f'      <div class="chiffre">\n        <span class="chiffre__valeur">{valeur}</span>\n'
                f'        <span class="chiffre__libelle">{libelle}</span>\n'
                f'        <span class="chiffre__detail">{detail}</span>\n      </div>\n')

    def section(ident: str, surtitre: str, titre: str, corps: str, alt: bool = False) -> str:
        return (f'<section class="section{" section--alt" if alt else ""}" aria-labelledby="{ident}">\n'
                f'  <div class="conteneur">\n    <p class="surtitre">{surtitre}</p>\n'
                f'    <h2 id="{ident}">{titre}</h2>\n{corps}\n  </div>\n</section>\n')

    def euros(v):
        return "non comparable" if v is None else fr(v) + NBSP + "€"

    def m_euros(v):
        return "–" if v is None else fr(v / 1e6, 1) + NBSP + "M€"

    lignes_index = []
    for n, c in enumerate(codes):
        d = deps[c]
        nom = d["nom"]
        k = idx[c]
        note_loc = C["notes"].get(c)
        precedent, suivant = codes[n - 1], codes[(n + 1) % len(codes)]
        a_des_effectifs = c in avec

        # ---- Chiffres clés ----
        tuiles = ""
        if a_des_effectifs:
            eff = d["ensemble"][i_fin]
            t = t_fin[c]
            ev = 100 * (eff / d["ensemble"][i0] - 1)
            ev_pop = 100 * (d["population"][i_fin] / d["population"][i0] - 1)
            tuiles += chiffre(fr(eff), f"agents publics civils fin {a_fin}",
                              f"État {fr(d['fpe'][i_fin])}, territoriale {fr(d['fpt'][i_fin])}, "
                              f"hospitalière {fr(d['fph'][i_fin])}.")
            tuiles += chiffre(fr(t, 1), f"agents pour 1{NBSP}000 habitants",
                              f"{lib_france} : {cles['dep_taux_france']}. Rang : {rang[c]}<sup>{'er' if rang[c] == 1 else 'e'}</sup> "
                              f"sur {len(avec)} départements (1<sup>er</sup> = taux le plus élevé).")
            tuiles += chiffre(pct_signe(ev), f"d'agents entre {a0} et {a_fin}",
                              f"France : {pct_signe(evol_fr)}. Population du département sur la même période : {pct_signe(ev_pop)}.")
        else:
            j = len(D["mayotte"]["annees"]) - 1
            tuiles += chiffre(fr(D["mayotte"]["valeurs"][j]), f"emplois publics en {D['mayotte']['annees'][j]} (estimation)",
                              "Enquête Emploi de l'Insee : chiffre non comparable avec ceux des autres départements.")
        v_loc = loc_hab(c, "total")
        if v_loc is not None:
            tuiles += chiffre(fr(v_loc) + NBSP + "€", f"de frais de personnel des collectivités par habitant en {a_loc}",
                              f"Moyenne nationale : {cles['ms_loc_hab'].replace(' €', NBSP + '€')}. Communes, intercommunalités et conseil départemental.")
        else:
            tuiles += chiffre(m_euros(C["total"][k]), f"de frais de personnel des communes et intercommunalités en {a_loc}",
                              "Pas de conseil départemental : montant par habitant non comparable avec la moyenne nationale.")
        champ = (f"Emploi public : {e(D['mayotte']['texte'].split('. ')[0])}. Frais de personnel : {src_loc}."
                 if not a_des_effectifs else
                 f"Agents civils au 31 décembre {a_fin}, comptés à leur lieu de travail, hors contrats aidés ; "
                 f"les militaires ne sont pas localisés par département. Taux : agents rapportés à la population au "
                 f"1<sup>er</sup> janvier {a_fin + 1}. Sources : {src_eff} ; frais de personnel : {src_loc}.")
        contenu = section("titre-cles", "L'essentiel", f"Les chiffres clés en {a_fin}",
                          f'    <div class="grille">\n{tuiles}    </div>\n    <p class="figure__note">{champ}</p>')

        if a_des_effectifs:
            # ---- Trois versants ----
            lignes = []
            for v, long, _ in VERSANTS + [("ensemble", "Ensemble des trois versants", "")]:
                lignes.append([long, fr(d[v][i_fin]), fr(100 * d[v][i_fin] / d["ensemble"][i_fin]) + NBSP + "%",
                               fr(taux(d[v], d["population"], i_fin), 1), fr(taux_fr[v], 1)])
            contenu += section(
                "titre-versants", "Les trois versants", "État, collectivités territoriales, hôpitaux",
                '    <p class="section__intro">Combien d\'agents travaillent dans chaque fonction publique, et combien pour '
                f'1{NBSP}000 habitants, comparé à la moyenne nationale.</p>\n'
                + tableau(f"{e(nom)} : agents publics civils par versant au 31 décembre {a_fin}",
                          ["Versant", "Agents", "Part", f"Pour 1{NBSP}000 hab.", f"{lib_france}, pour 1{NBSP}000 hab."], lignes),
                alt=True)

            # ---- Évolution ----
            rows = []
            for i in range(i0, i_fin + 1):
                rows.append([str(annees[i]), fr(d["ensemble"][i]), fr(d["fpe"][i]), fr(d["fpt"][i]), fr(d["fph"][i]),
                             fr(d["population"][i]), fr(taux(d["ensemble"], d["population"], i), 1),
                             fr(taux(F["ensemble"], F["population"], i), 1)])
            alertes = D["alertes"].get(c, {})
            notes = [f"<li><strong>{a}</strong> : {e(alertes[a])}</li>" for a in sorted(alertes) if a >= a0]
            encadre = (f'    <div class="encadre encadre--attention">\n      <p class="encadre__titre">À noter</p>\n'
                       f'      <ul>{"".join(notes)}</ul>\n    </div>\n') if notes else ""
            legende_taux = (f'<ul class="legende"><li><span class="legende__trait" style="color:var(--accent)"></span>{e(nom)}</li>'
                            f'<li><span class="legende__trait legende__trait--tirets" style="color:var(--c-total)"></span>{lib_france}</li></ul>')
            legende_vers = '<ul class="legende">' + "".join(
                f'<li><span class="legende__carre" style="background:var(--c-{v})"></span>{long}</li>' for v, long, _ in VERSANTS) + "</ul>"
            contenu += section(
                "titre-evolution", "L'évolution", f"De {a0} à {a_fin}",
                f'    <p class="section__intro">Le nombre d\'agents a évolué de <strong>{pct_signe(ev)}</strong> dans le département '
                f'entre {a0} et {a_fin}, contre {pct_signe(evol_fr)} en France ; la population, de {pct_signe(ev_pop)} '
                f'(France : {pct_signe(evol_pop_fr)}).</p>\n'
                f'    <figure class="figure" aria-labelledby="titre-fig-taux">\n'
                f'      <h3 class="figure__titre" id="titre-fig-taux">Agents publics civils pour 1{NBSP}000 habitants</h3>\n'
                f'      <p class="figure__sous-titre">{e(nom)} et {lib_france}, {a0}-{a_fin}.</p>\n'
                f'      <div id="graph-taux"></div>\n      {legende_taux}\n    </figure>\n'
                f'    <figure class="figure" aria-labelledby="titre-fig-versants">\n'
                f'      <h3 class="figure__titre" id="titre-fig-versants">Nombre d\'agents par versant</h3>\n'
                f'      <p class="figure__sous-titre">{e(nom)}, au 31 décembre, {a0}-{a_fin}.</p>\n'
                f'      <div id="graph-versants"></div>\n      {legende_vers}\n    </figure>\n'
                + encadre
                + '    <details class="donnees" open>\n      <summary>Les données année par année</summary>\n'
                + tableau(f"{e(nom)} : agents publics civils au 31 décembre et taux pour 1{NBSP}000 habitants, {a0}-{a_fin}",
                          ["Année", "Agents", "État", "Territoriale", "Hospitalière", "Population", f"Pour 1{NBSP}000 hab.",
                           f"{lib_france}, pour 1{NBSP}000 hab."], rows)
                + "\n    </details>\n"
                f'    <p class="figure__note">Période homogène de la source (Siasp) : {a0}-{a_fin}. Les années '
                f'{annees[0]}-{a0 - 1} (ancienne méthode, métropole seulement) restent consultables sur '
                f'<a href="../carte.html#indicateur=taux&amp;versant=ensemble&amp;annee={annees[0]}&amp;dep={e(c)}&amp;anciennes=1">la carte</a>. '
                f"Sources : {src_eff}.</p>")
        else:
            m = D["mayotte"]
            lignes = [[str(a), fr(v)] for a, v in zip(m["annees"], m["valeurs"])]
            contenu += section(
                "titre-mayotte", "Les effectifs", "Une estimation seulement",
                f'    <p class="section__intro">{e(nom)} n\'est pas couvert par la source utilisée pour les autres départements '
                "(système d'information sur les agents des services publics, Siasp). L'enquête Emploi de l'Insee en donne "
                "une estimation, à ne pas comparer aux chiffres des autres fiches : elle compte les personnes de 15 à 64 ans "
                "occupant un emploi public, au 2<sup>e</sup> trimestre.</p>\n"
                + tableau(f"{e(nom)} : emploi public estimé par l'enquête Emploi de l'Insee", ["Année", "Emplois publics"], lignes),
                alt=True)

        # ---- Frais de personnel des collectivités ----
        lignes = []
        for niv, lib, _ in NIVEAUX_LOC:
            montant = C[niv][k]
            lignes.append([lib if niv != "total" else "<strong>Ensemble</strong>", m_euros(montant),
                           euros(loc_hab(c, niv)), euros(loc_fr[niv])])
        contenu += section(
            "titre-collectivites", "Les collectivités", f"Les frais de personnel des collectivités en {a_loc}",
            '    <p class="section__intro">Rémunérations et charges sociales versées par les communes, les intercommunalités '
            "et le conseil départemental (budgets principaux), rapportées à la population. Les régions ne sont pas comptées. "
            f"Population : moyenne des 1<sup>er</sup> janvier {a_loc} et {a_loc + 1}.</p>\n"
            + tableau(f"{e(nom)} : frais de personnel des collectivités locales en {a_loc}",
                      ["Collectivités", "Montant", "Par habitant", "France entière, par habitant"], lignes)
            + (f'\n    <p class="encadre encadre--attention"><strong>À noter :</strong> {e(note_loc)}.</p>' if note_loc else "")
            + f'\n    <p class="figure__note">« Non comparable » : organisation particulière (voir la note). Source : {src_loc}. '
            f'<a href="../masse-salariale.html#departements">Carte des frais de personnel par département</a>.</p>',
            alt=not a_des_effectifs)

        # ---- Pour aller plus loin ----
        lien_carte = f"../carte.html#indicateur=taux&amp;versant=ensemble&amp;annee={a_fin}&amp;dep={e(c)}"
        contenu += section(
            "titre-suite", "Pour aller plus loin", "Comparer avec les autres départements",
            '    <ul class="liste-lecture">\n'
            f'      <li><a class="lien-fleche" href="{lien_carte}">{e(nom)} sur la carte interactive</a></li>\n'
            '      <li><a class="lien-fleche" href="index.html">Toutes les fiches des départements</a></li>\n'
            '      <li><a class="lien-fleche" href="../methode.html#carte-methode">Méthode : comment les agents sont localisés</a></li>\n'
            "    </ul>\n"
            '    <nav class="bandeau__actions" aria-label="Département précédent et suivant">\n'
            f'      <a class="bouton bouton--secondaire" href="{e(precedent)}.html" rel="prev">← {e(deps[precedent]["nom"])} ({e(precedent)})</a>\n'
            f'      <a class="bouton bouton--secondaire" href="{e(suivant)}.html" rel="next">{e(deps[suivant]["nom"])} ({e(suivant)}) →</a>\n'
            "    </nav>",
            alt=a_des_effectifs)

        if a_des_effectifs:
            description = (f"{nom} ({c}) : {fr(d['ensemble'][i_fin])} agents publics civils fin {a_fin}, soit {fr(t_fin[c], 1)} "
                           f"pour 1 000 habitants ({lib_france} : {cles['dep_taux_france']}). Évolution depuis {a0}, "
                           "frais de personnel des collectivités.")
            chapeau = (f"Les agents de la fonction publique qui travaillent dans le département, leur nombre pour 1{NBSP}000 habitants "
                       f"et son évolution depuis {a0}, et les frais de personnel des collectivités locales, comparés à la France entière.")
        else:
            description = (f"{nom} ({c}) : emploi public estimé et frais de personnel des collectivités en {a_loc}.")
            chapeau = ("L'emploi public estimé et les frais de personnel des collectivités locales, comparés à la France entière.")
        bandeau = ('  <div class="conteneur bandeau">\n    <p class="bandeau__surtitre">Fiche département</p>\n'
                   f'    <h1><span class="souligne">{e(nom)}</span> ({e(c)})</h1>\n'
                   f'    <p class="bandeau__chapeau">{chapeau}</p>\n  </div>\n')
        ecrire(f"{c}.html", _page(
            g, titre=f"{nom} ({c}) : agents publics et frais de personnel – Fonction publique : les chiffres",
            description=description, url=f"{site}{DOSSIER}/{c}.html", image=image, page="departement", dep=c,
            bandeau=bandeau, contenu=contenu,
            scripts=["assets/js/app.js", "assets/js/graphiques.js", "donnees/site/departements.js", "assets/js/departement.js"]
            if a_des_effectifs else ["assets/js/app.js"]))

        lien = f'<a href="{e(c)}.html">{e(nom)} ({e(c)})</a>'
        if a_des_effectifs:
            lignes_index.append([lien, fr(d["ensemble"][i_fin]), fr(t_fin[c], 1), str(rang[c]),
                                 pct_signe(100 * (d["ensemble"][i_fin] / d["ensemble"][i0] - 1)), euros(loc_hab(c, "total"))])
        else:
            lignes_index.append([lien, "n.d.", "n.d.", "–", "n.d.", euros(loc_hab(c, "total"))])

    # ---- Liste des fiches ----
    contenu = section(
        "titre-liste", f"{len(codes)} départements", "Choisir un département",
        f'    <p class="section__intro">Chaque fiche présente les agents publics civils du département en {a_fin}, leur nombre pour '
        f"1{NBSP}000 habitants, leur évolution depuis {a0} et les frais de personnel des collectivités locales en {a_loc}, "
        f'comparés à la France entière ({lib_france} : {cles["dep_taux_france"]} agents pour 1{NBSP}000 habitants ; '
        f'frais de personnel : {cles["ms_loc_hab"].replace(" €", NBSP + "€")} par habitant).</p>\n'
        + tableau(f"Les départements : agents publics civils fin {a_fin} et frais de personnel des collectivités en {a_loc}",
                  ["Département", "Agents", f"Pour 1{NBSP}000 hab.", "Rang", f"Évolution depuis {a0}", "Frais de personnel par hab."],
                  lignes_index, haut=True)
        + f'\n    <p class="figure__note">Rang : 1<sup>er</sup> = taux le plus élevé. « n.d. » : Mayotte n\'est pas couverte par la '
        f"source des effectifs. Sources : {src_eff} ; frais de personnel : {src_loc}.</p>")
    bandeau = ('  <div class="conteneur bandeau">\n    <p class="bandeau__surtitre">Fiches départements</p>\n'
               '    <h1>Les agents publics, <span class="souligne">département par département</span></h1>\n'
               f'    <p class="bandeau__chapeau">Une fiche par département : effectifs, taux d\'administration, évolution depuis {a0} '
               "et frais de personnel des collectivités, comparés à la moyenne nationale.</p>\n  </div>\n")
    ecrire("index.html", _page(
        g, titre="Fiches des départements – Fonction publique : les chiffres",
        description=(f"Une fiche par département : agents publics civils fin {a_fin}, taux pour 1 000 habitants, évolution "
                     f"depuis {a0} et frais de personnel des collectivités, comparés à la France entière."),
        url=f"{site}{DOSSIER}/", image=image, page="departements", dep=None, bandeau=bandeau, contenu=contenu,
        scripts=["assets/js/app.js"]))

    # Fiches d'anciens départements (code disparu) : supprimées.
    for f in sortie.glob("*.html"):
        if f.name not in ecrites:
            f.unlink()
    return len(ecrites)
