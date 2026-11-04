/* ==========================================================================
   Remplissage des pages « L'essentiel », « Évolution » et « Statuts et
   catégories » à partir de donnees/site/national.js (et departements.js).
   ========================================================================== */
(function () {
  "use strict";
  const PLF = window.PLF;
  const G = PLF.graphiques;

  const VERSANTS = [
    { id: "fpe", libelle: "État", long: "Fonction publique de l'État", couleur: "--c-fpe" },
    { id: "fpt", libelle: "Territoriale", long: "Fonction publique territoriale", couleur: "--c-fpt" },
    { id: "fph", libelle: "Hospitalière", long: "Fonction publique hospitalière", couleur: "--c-fph" },
  ];
  const STATUTS = [
    { id: "fonctionnaires", libelle: "Fonctionnaires", couleur: "--c-fonctionnaires" },
    { id: "contractuels", libelle: "Contractuels", couleur: "--c-contractuels" },
    { id: "militaires", libelle: "Militaires", couleur: "--c-militaires" },
    { id: "autres", libelle: "Autres statuts", couleur: "--c-autres" },
  ];
  const CATEGORIES = [
    { id: "A", libelle: "Catégorie A", couleur: "--c-a" },
    { id: "B", libelle: "Catégorie B", couleur: "--c-b" },
    { id: "C", libelle: "Catégorie C", couleur: "--c-c" },
    { id: "ind", libelle: "Indéterminée", couleur: "--c-ind" },
  ];

  function remplirCles(cles) {
    document.querySelectorAll("[data-cle]").forEach((n) => {
      const v = cles[n.dataset.cle];
      if (v == null) return;
      // Dans les chiffres clés, l'unité (« millions ») est affichée plus petite.
      const m = n.classList.contains("chiffre__valeur") && /^(.+?)\s(millions?)$/.exec(v);
      if (m) {
        n.textContent = m[1] + " ";
        const u = document.createElement("span");
        u.className = "chiffre__unite";
        u.textContent = m[2];
        n.appendChild(u);
      } else n.textContent = v;
    });
  }
  function legende(ul, items, tirets) {
    if (!ul) return;
    ul.innerHTML = items.map((it) => `<li><span class="${it.trait ? "legende__trait" + (it.tirets || tirets ? " legende__trait--tirets" : "") : "legende__carre"}" style="${it.trait ? `color:${PLF.couleur(it.couleur)}` : `background:${PLF.couleur(it.couleur)}`}"></span>${it.libelle}</li>`).join("");
    document.addEventListener("plf:affichage", () => legende(ul, items, tirets), { once: true });
  }
  const dernierIndice = (arr) => { for (let i = arr.length - 1; i >= 0; i--) if (arr[i] != null) return i; return -1; };

  /* ======================= Page « L'essentiel » ======================= */
  function accueil(N) {
    remplirCles(N.cles);
    // Gaufre « sur 100 agents »
    const zone = document.getElementById("gaufre");
    if (zone && N.statuts) {
      const S = N.statuts;
      const i = dernierIndice(S.versants.ensemble.fonctionnaires);
      const total = STATUTS.reduce((a, s) => a + (S.versants.ensemble[s.id][i] || 0), 0);
      const parts = STATUTS.map((s) => ({ libelle: s.libelle, couleur: s.couleur, valeur: (100 * (S.versants.ensemble[s.id][i] || 0)) / total }));
      const dessiner = () => {
        const arrondis = G.gaufre(zone, { parts, titre: "Sur 100 agents publics : " + parts.map((p, k) => `${Math.round(p.valeur)} ${p.libelle.toLowerCase()}`).join(", ") });
        document.getElementById("gaufre-legende").innerHTML = parts.map((p, k) => `<li><span class="legende__carre" style="background:${PLF.couleur(p.couleur)}"></span><span><b class="gaufre-nombre">${arrondis[k]}</b> ${p.libelle.toLowerCase()}<br><small>${PLF.fmt.nombre(S.versants.ensemble[STATUTS[k].id][i])} personnes</small></span></li>`).join("");
      };
      dessiner();
      document.addEventListener("plf:affichage", dessiner);
      const note = document.getElementById("gaufre-note");
      if (note) note.textContent = `Lecture : sur 100 agents de la fonction publique fin ${S.annees[i]}, ${Math.round(parts[0].valeur)} sont fonctionnaires. Champ : ${S.champ}. Source : ${S.source}.`;
    }
    // Barre de répartition par versant
    const barre = document.getElementById("barre-versants");
    if (barre) {
      const E = N.effectifs.actuelle;
      const i = dernierIndice(E.total);
      const dessiner = () => {
        barre.innerHTML = VERSANTS.map((v) => {
          const part = (100 * E[v.id][i]) / E.total[i];
          const fond = PLF.couleur(v.couleur);
          return `<span style="width:${part}%;background:${fond};color:${PLF.texteSur(fond)}">${v.libelle} ${PLF.fmt.pourcent(part, 0)}</span>`;
        }).join("");
      };
      dessiner();
      document.addEventListener("plf:affichage", dessiner);
      barre.setAttribute("aria-label", "Répartition des agents : " + VERSANTS.map((v) => `${v.long} ${PLF.fmt.pourcent((100 * E[v.id][i]) / E.total[i], 0)}`).join(", "));
    }
    // Au-delà de la fonction publique
    const large = document.getElementById("emploi-large");
    if (large && N.emploiPublicLarge) {
      const L = N.emploiPublicLarge;
      const groupes = [];
      L.lignes.forEach((l) => {
        let g = groupes.find((x) => x.nom === l.ensemble);
        if (!g) groupes.push((g = { nom: l.ensemble, total: 0, lignes: [] }));
        g.total += l.milliers;
        g.lignes.push(l);
      });
      const couleurs = ["--c-fpe", "--c-militaires", "--c-fpt", "--c-fph"];
      const total = groupes.reduce((a, g) => a + g.total, 0);
      const dessiner = () => {
        large.querySelector(".barre-repartition").innerHTML = groupes.map((g, k) => {
          const fond = PLF.couleur(couleurs[k]);
          const part = (100 * g.total) / total;
          return `<span style="width:${part}%;background:${fond};color:${PLF.texteSur(fond)}" title="${g.nom}">${part > 9 ? PLF.fmt.pourcent(part, 0) : ""}</span>`;
        }).join("");
        large.querySelector(".legende").innerHTML = groupes.map((g, k) => `<li><span class="legende__carre" style="background:${PLF.couleur(couleurs[k])}"></span><span><b>${g.nom}</b> : ${PLF.fmt.nombre(g.total * 1000)} personnes${g.lignes.length > 1 ? ` <small>(${g.lignes.map((l) => `${l.composante.replace(/ \(.*\)/, "")} ${PLF.fmt.nombre(l.milliers * 1000)}`).join(" ; ")})</small>` : ""}</span></li>`).join("");
      };
      dessiner();
      document.addEventListener("plf:affichage", dessiner);
      large.querySelector(".barre-repartition").setAttribute("aria-label", groupes.map((g) => `${g.nom} : ${PLF.fmt.nombre(g.total * 1000)} personnes`).join(", "));
      large.querySelector(".figure__note").textContent = `Effectifs au 31 décembre ${L.annee}, France hors Mayotte. La fonction publique est comptée ici avec ses bénéficiaires de contrats aidés. Source : ${L.source}, figure 3 « Place de l'emploi public dans l'économie ».`;
    }
    // Petite carte d'appel (décorative, la vraie carte est sur carte.html)
    const visuel = document.getElementById("appel-visuel");
    if (visuel && window.PLF_DONNEES.fond_de_carte && window.PLF_DONNEES.departements) miniCarte(visuel);
  }

  function miniCarte(conteneur) {
    const geo = window.PLF_DONNEES.fond_de_carte;
    const D = window.PLF_DONNEES.departements;
    const i = D.annees.length - 1;
    const c = geo.cadres.metro;
    const pal = ["#fdf6d8", "#dce5ac", "#97d6a4", "#50baa1", "#21968b", "#006e73"];
    const taux = {};
    Object.keys(D.departements).forEach((code) => {
      const d = D.departements[code];
      taux[code] = d.ensemble[i] != null && d.population[i] ? (1000 * d.ensemble[i]) / d.population[i] : null;
    });
    const vals = Object.values(taux).filter((v) => v != null).sort((a, b) => a - b);
    const q = [1, 2, 3, 4, 5].map((k) => vals[Math.floor((k * vals.length) / 6)]);
    let svg = `<svg viewBox="0 0 ${c.largeur} ${c.hauteur}" role="presentation" style="max-height:22rem;display:block;margin:auto">`;
    Object.keys(geo.departements).forEach((code) => {
      const g = geo.departements[code];
      if (g.cadre !== "metro") return;
      const v = taux[code];
      let k = 0;
      while (k < q.length && v >= q[k]) k++;
      svg += `<path d="${g.d}" fill="${v == null ? "#ccc" : pal[k]}" stroke="#003340" stroke-width="1.2" vector-effect="non-scaling-stroke"/>`;
    });
    conteneur.innerHTML = svg + "</svg>";
  }

  /* ======================= Page « Évolution » ======================= */
  function evolution(N) {
    remplirCles(N.cles);
    const E = N.effectifs;
    const zone = document.getElementById("graphique-evolution");
    if (!zone) return;
    const annees = E.annees;
    const pop = E.population;
    const debutActuelle = annees[E.actuelle.total.findIndex((v) => v != null)];
    const interpolees = new Set(E.interpolees);
    const noteAnnee = (a) => {
      const k = annees.indexOf(a);
      const notes = [];
      if (E.historique.total[k] != null && E.actuelle.total[k] != null) notes.push("Les deux séries se recouvrent cette année-là : l'écart vient de la différence de champ.");
      else if (E.historique.total[k] != null) notes.push("Série historique (champ différent de la série actuelle).");
      if (interpolees.has(a)) notes.push("Année estimée par la DGAFP (moyenne des années voisines).");
      return notes.join(" ");
    };
    const etat = { mesure: "nombre", mode: "courbes" };
    const parHabitant = (vals) => vals.map((v, k) => (v == null || !pop[k] ? null : (1000 * v) / pop[k]));
    function series() {
      const conv = etat.mesure === "taux" ? parHabitant : (x) => x;
      if (etat.mode === "empile") {
        // Empilement : uniquement la série actuelle, pour ne pas additionner deux champs différents.
        return VERSANTS.map((v) => ({ id: v.id, libelle: v.libelle, couleur: v.couleur, valeurs: conv(E.actuelle[v.id]) }));
      }
      return VERSANTS.flatMap((v) => [
        { id: v.id, libelle: v.libelle, libelleCourt: v.libelle, couleur: v.couleur, valeurs: conv(E.actuelle[v.id]) },
        { id: v.id + "-h", libelle: `${v.libelle} (série historique)`, couleur: v.couleur, valeurs: conv(E.historique[v.id]), tirets: true, sansEtiquette: true, epaisseur: 2.2 },
      ]);
    }
    function cfg() {
      const taux = etat.mesure === "taux";
      const empile = etat.mode === "empile";
      const debut = empile ? annees.indexOf(debutActuelle) : taux ? pop.findIndex((p) => p != null) : 0;
      const garde = (arr) => arr.slice(debut);
      const s = series().map((x) => Object.assign({}, x, { valeurs: garde(x.valeurs) }));
      return {
        annees: garde(annees),
        series: s,
        empile,
        formatAxe: taux ? (v) => PLF.fmt.nombre(v) : PLF.fmt.axeMillions,
        formatValeur: taux ? PLF.fmt.decimal1 : PLF.fmt.nombre,
        titreAxeY: taux ? "Agents pour 1 000 habitants" : "Nombre d'agents",
        yMin: 0,
        ruptures: empile ? [] : [{ annee: debutActuelle, court: "changement de série" }],
        noteAnnee,
        titreAccessible: `Agents de la fonction publique par versant, ${taux ? "pour 1 000 habitants" : "en nombre"}, de ${annees[debut]} à ${annees[annees.length - 1]}`,
      };
    }
    const graphique = G.courbes(zone, cfg());
    const legendeEvol = () => legende(document.getElementById("evol-legende"),
      etat.mode === "empile" ? VERSANTS.map((v) => ({ libelle: v.long, couleur: v.couleur }))
        : VERSANTS.map((v) => ({ libelle: v.long, couleur: v.couleur, trait: true })).concat([{ libelle: `Pointillés : série historique ${annees[0]}-${E.annees[dernierIndice(E.historique.total)]}`, couleur: "--texte-doux", trait: true, tirets: true }]));
    legendeEvol();
    const note = document.getElementById("evol-note");
    const majNote = () => {
      const base = `Trait plein : ${E.series.actuelle.court} — ${E.series.actuelle.champ}. Pointillés : ${E.series.historique.court} — ${E.series.historique.champ}.`;
      const extra = etat.mode === "empile" ? ` Le mode empilé ne montre que la série actuelle (${debutActuelle}-${annees[annees.length - 1]}), pour ne pas additionner deux champs différents.` : "";
      const extraTaux = etat.mesure === "taux" ? ` Pour 1 000 habitants : population au 1er janvier de l'année suivante, France hors Mayotte (disponible à partir de ${annees[pop.findIndex((p) => p != null)]}). ${N.populationSource}.` : "";
      note.textContent = `${base}${extra}${extraTaux} Sources : ${E.series.actuelle.source} ; ${E.series.historique.source}.`;
    };
    majNote();
    document.querySelector("#figure-evolution .figure__controles").addEventListener("change", (e) => {
      if (e.target.name === "evol-mesure") etat.mesure = e.target.value;
      if (e.target.name === "evol-mode") etat.mode = e.target.value;
      graphique.maj(cfg());
      legendeEvol();
      majNote();
    });

    // Tableau
    const lignes = () => annees.map((a, k) => ({
      annee: a,
      fpe: E.actuelle.fpe[k], fpt: E.actuelle.fpt[k], fph: E.actuelle.fph[k], total: E.actuelle.total[k],
      taux: pop[k] && E.actuelle.total[k] != null ? (1000 * E.actuelle.total[k]) / pop[k] : null,
      hist: E.historique.total[k],
      htaux: pop[k] && E.historique.total[k] != null ? (1000 * E.historique.total[k]) / pop[k] : null,
      note: interpolees.has(a) ? "estimée (DGAFP)" : "",
    }));
    const table = PLF.tableau({
      legende: "Agents de la fonction publique au 31 décembre, par versant (série actuelle) et total de la série historique",
      colonnes: [
        { titre: "Année", cle: "annee" },
        { titre: "État", cle: "fpe", format: PLF.fmt.nombre },
        { titre: "Territoriale", cle: "fpt", format: PLF.fmt.nombre },
        { titre: "Hospitalière", cle: "fph", format: PLF.fmt.nombre },
        { titre: "Total", cle: "total", format: PLF.fmt.nombre },
        { titre: "Pour 1 000 hab.", cle: "taux", format: PLF.fmt.decimal1 },
        { titre: "Total, série historique", cle: "hist", format: PLF.fmt.nombre },
        { titre: "Pour 1 000 hab. (historique)", cle: "htaux", format: PLF.fmt.decimal1 },
        { titre: "Remarque", cle: "note", texte: true, format: (v) => v || "" },
      ],
      lignes: lignes(),
    });
    PLF.blocDonnees(document.getElementById("evol-donnees"), {
      table,
      csvNom: "fonction-publique-effectifs-par-versant.csv",
      csvEntetes: ["annee", "serie", "fpe", "fpt", "fph", "total", "population_1er_janvier_suivant"],
      csvLignes: () => {
        const l = [];
        annees.forEach((a, k) => {
          if (E.historique.total[k] != null) l.push([a, "historique", E.historique.fpe[k], E.historique.fpt[k], E.historique.fph[k], E.historique.total[k], pop[k]]);
          if (E.actuelle.total[k] != null) l.push([a, "actuelle", E.actuelle.fpe[k], E.actuelle.fpt[k], E.actuelle.fph[k], E.actuelle.total[k], pop[k]]);
        });
        return l;
      },
    });

    // Variation annuelle, calculée à l'intérieur d'une même série seulement
    const zv = document.getElementById("graphique-variation");
    if (zv) {
      const an = [], valeurs = [];
      annees.forEach((a, k) => {
        if (k === 0 || annees[k - 1] !== a - 1) return;
        const serie = a < debutActuelle ? E.historique : a > debutActuelle ? E.actuelle : null;
        an.push(a);
        valeurs.push(serie && serie.total[k] != null && serie.total[k - 1] != null ? serie.total[k] - serie.total[k - 1] : null);
      });
      G.colonnes(zv, {
        annees: an, valeurs, libelle: "Variation",
        formatValeur: (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + PLF.fmt.nombre(Math.abs(v)) + " agents",
        formatAxe: (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + PLF.fmt.nombre(Math.abs(v)),
        couleurPositive: "--c-fpt", couleurNegative: "--c-fph",
        ruptures: [{ annee: debutActuelle, court: "changement de série" }],
        noteAnnee: (a) => (a === debutActuelle ? "Changement de série : variation non calculée." : interpolees.has(a) || interpolees.has(a - 1) ? "Calculée avec une année estimée par la DGAFP : variation lissée." : ""),
        titreAccessible: "Variation annuelle du nombre total d'agents",
      });
      document.getElementById("variation-note").textContent = `Jusqu'en ${debutActuelle - 1} : série historique ; à partir de ${debutActuelle + 1} : série actuelle. Pas de variation calculée en ${debutActuelle} (changement de série) ni entre 1980 et 1982 (1981 manquant). Les années ${[...interpolees].join(", ")} étant estimées par la DGAFP, les variations qui les encadrent sont lissées.`;
      const t2 = PLF.tableau({
        legende: "Variation annuelle du nombre total d'agents",
        colonnes: [
          { titre: "Année", cle: "annee" },
          { titre: "Variation (agents)", cle: "v", format: (v) => (v == null ? "non calculée" : (v > 0 ? "+" : v < 0 ? "−" : "") + PLF.fmt.nombre(Math.abs(v))) },
        ],
        lignes: an.map((a, k) => ({ annee: a, v: valeurs[k] })),
      });
      PLF.blocDonnees(document.getElementById("variation-donnees"), { table: t2 });
    }
  }

  /* ======================= Page « Statuts et catégories » ======================= */
  function composition(N) {
    remplirCles(N.cles);
    const S = N.statuts;
    const C = N.categories;
    const libVersants = [{ id: "ensemble", libelle: "Ensemble" }].concat(VERSANTS);

    // 1. Statuts, dernière année
    const zs = document.getElementById("graphique-statuts");
    if (zs && S) {
      const i = dernierIndice(S.versants.ensemble.fonctionnaires);
      const series = STATUTS.map((s) => ({ id: s.id, libelle: s.libelle, couleur: s.couleur, valeurs: libVersants.map((v) => S.versants[v.id][s.id][i]) }));
      G.barres(zs, { categories: libVersants.map((v) => v.libelle === "Ensemble" ? "Ensemble" : v.libelle), series, pourcent: true, titreAccessible: `Répartition des agents par statut et par versant, fin ${S.annees[i]}` });
      legende(document.getElementById("statuts-legende"), STATUTS);
      document.getElementById("statuts-note").textContent = `Champ : ${S.champ}. Source : ${S.source}.`;
      const t = PLF.tableau({
        legende: `Agents par statut et par versant, fin ${S.annees[i]}`,
        colonnes: [{ titre: "Versant", cle: "v", texte: true }].concat(STATUTS.map((s) => ({ titre: s.libelle, cle: s.id, format: PLF.fmt.nombre }))).concat([{ titre: "Part des fonctionnaires", cle: "part", format: (v) => PLF.fmt.pourcent(v, 1) }]),
        lignes: libVersants.map((v) => {
          const l = { v: v.id === "ensemble" ? "Ensemble" : v.long };
          let tot = 0;
          STATUTS.forEach((s) => { l[s.id] = S.versants[v.id][s.id][i]; tot += l[s.id] || 0; });
          l.part = tot ? (100 * l.fonctionnaires) / tot : null;
          return l;
        }),
      });
      PLF.blocDonnees(document.getElementById("statuts-donnees"), { table: t, csvNom: `statuts-par-versant-${S.annees[i]}.csv`, csvEntetes: ["versant"].concat(STATUTS.map((s) => s.id)), csvLignes: libVersants.map((v) => [v.id].concat(STATUTS.map((s) => S.versants[v.id][s.id][i]))) });
    }

    // 2. Part des contractuels dans le temps
    const zse = document.getElementById("graphique-statuts-evol");
    if (zse && S) {
      const part = (vid) => S.annees.map((_, k) => {
        const tot = STATUTS.reduce((a, s) => a + (S.versants[vid][s.id][k] || 0), 0);
        const c = S.versants[vid].contractuels[k];
        return c == null || !tot ? null : (100 * c) / tot;
      });
      const series = [{ id: "ensemble", libelle: "Ensemble", couleur: "--c-total", valeurs: part("ensemble"), tirets: true }]
        .concat(VERSANTS.map((v) => ({ id: v.id, libelle: v.libelle, couleur: v.couleur, valeurs: part(v.id) })));
      G.courbes(zse, { annees: S.annees, series, formatAxe: (v) => v + " %", formatValeur: (v) => PLF.fmt.pourcent(v, 1), titreAxeY: "Part des contractuels (%)", yMin: 0, ruptures: S.ruptures || [], titreAccessible: "Part des contractuels parmi les agents, par versant" });
      legende(document.getElementById("statuts-evol-legende"), series.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: true, tirets: s.tirets })));
      document.getElementById("statuts-evol-note").textContent = `Champ : ${S.champ}. Source : ${S.source}.`;
      const t = PLF.tableau({
        legende: "Part des contractuels parmi les agents (%)",
        colonnes: [{ titre: "Année", cle: "a" }].concat(series.map((s) => ({ titre: s.libelle, cle: s.id, format: (v) => PLF.fmt.pourcent(v, 1) }))),
        lignes: S.annees.map((a, k) => { const l = { a }; series.forEach((s) => (l[s.id] = s.valeurs[k])); return l; }),
      });
      PLF.blocDonnees(document.getElementById("statuts-evol-donnees"), {
        table: t, csvNom: "statuts-par-versant-par-annee.csv",
        csvEntetes: ["annee", "versant"].concat(STATUTS.map((s) => s.id)),
        csvLignes: () => { const l = []; S.annees.forEach((a, k) => libVersants.forEach((v) => l.push([a, v.id].concat(STATUTS.map((s) => S.versants[v.id][s.id][k]))))); return l; },
      });
    }

    // 3. Catégories, dernière année
    const zc = document.getElementById("graphique-categories");
    const cats = C ? CATEGORIES.filter((c) => libVersants.some((v) => C.versants[v.id] && C.versants[v.id][c.id] && C.versants[v.id][c.id].some((x) => x))) : [];
    if (zc && C) {
      const i = dernierIndice(C.versants.ensemble.A);
      const series = cats.map((c) => ({ id: c.id, libelle: c.libelle, couleur: c.couleur, valeurs: libVersants.map((v) => C.versants[v.id][c.id][i]) }));
      G.barres(zc, { categories: libVersants.map((v) => v.libelle), series, pourcent: true, titreAccessible: `Répartition des agents par catégorie hiérarchique et par versant, fin ${C.annees[i]}` });
      legende(document.getElementById("cat-legende"), cats);
      document.getElementById("cat-sous-titre").textContent = `En % des agents de chaque versant (${C.champ}).`;
      document.getElementById("cat-note").textContent = `Source : ${C.source}.`;
      const t = PLF.tableau({
        legende: `Agents par catégorie hiérarchique et par versant, fin ${C.annees[i]}`,
        colonnes: [{ titre: "Versant", cle: "v", texte: true }].concat(cats.map((c) => ({ titre: c.libelle, cle: c.id, format: PLF.fmt.nombre }))),
        lignes: libVersants.map((v) => { const l = { v: v.id === "ensemble" ? "Ensemble" : v.long }; cats.forEach((c) => (l[c.id] = C.versants[v.id][c.id][i])); return l; }),
      });
      PLF.blocDonnees(document.getElementById("cat-donnees"), { table: t, csvNom: `categories-par-versant-${C.annees[i]}.csv`, csvEntetes: ["versant"].concat(cats.map((c) => c.id)), csvLignes: libVersants.map((v) => [v.id].concat(cats.map((c) => C.versants[v.id][c.id][i]))) });
    }

    // 4. Catégories dans le temps (aires empilées en %)
    const zce = document.getElementById("graphique-cat-evol");
    if (zce && C) {
      const choix = document.getElementById("cat-evol-versants");
      choix.innerHTML = libVersants.map((v, k) => `<label><input type="radio" name="cat-versant" value="${v.id}"${k === 0 ? " checked" : ""}>${v.id === "ensemble" ? "Les trois" : v.libelle}</label>`).join("");
      let versant = "ensemble";
      const cfg = () => ({
        annees: C.annees,
        series: cats.map((c) => ({ id: c.id, libelle: c.libelle, couleur: c.couleur, valeurs: C.versants[versant][c.id] })),
        empile: true, pourcent: true, titreAxeY: "Part (%)", ruptures: C.ruptures || [],
        titreAccessible: `Répartition par catégorie hiérarchique, ${versant === "ensemble" ? "ensemble des trois versants" : libVersants.find((v) => v.id === versant).long}, de ${C.annees[0]} à ${C.annees[C.annees.length - 1]}`,
      });
      const g = G.courbes(zce, cfg());
      legende(document.getElementById("cat-evol-legende"), cats);
      let table;
      const lignes = () => C.annees.map((a, k) => {
        const l = { a };
        let tot = 0;
        cats.forEach((c) => (tot += C.versants[versant][c.id][k] || 0));
        cats.forEach((c) => (l[c.id] = tot && C.versants[versant][c.id][k] != null ? (100 * C.versants[versant][c.id][k]) / tot : null));
        return l;
      });
      choix.addEventListener("change", (e) => {
        versant = e.target.value;
        g.maj(cfg());
        PLF.majTableau(table, lignes());
        table.caption.textContent = `Répartition par catégorie (%) — ${versant === "ensemble" ? "ensemble des trois versants" : libVersants.find((v) => v.id === versant).long}`;
      });
      document.getElementById("cat-evol-note").textContent = `${C.noteEvolution || ""} Source : ${C.source}.`;
      // Repères plus anciens (sources et champs différents)
      const zr = document.getElementById("cat-reperes");
      if (zr && C.reperes && C.reperes.length) {
        const nomV = { ensemble: "Ensemble", fpe: "État", fpt: "Territoriale", fph: "Hospitalière" };
        const tr = PLF.tableau({
          legende: "Repères avant 2010 : répartition par catégorie (%), sources et champs différents de la série 2010-2024",
          colonnes: [
            { titre: "Année", cle: "annee" },
            { titre: "Fonction publique", cle: "v", texte: true },
            { titre: "A", cle: "A", format: (v) => PLF.fmt.pourcent(v, 1) },
            { titre: "B", cle: "B", format: (v) => PLF.fmt.pourcent(v, 1) },
            { titre: "C", cle: "C", format: (v) => PLF.fmt.pourcent(v, 1) },
            { titre: "Indéterminée", cle: "ind", format: (v) => (v == null ? "–" : PLF.fmt.pourcent(v, 1)) },
            { titre: "Source", cle: "source", texte: true },
          ],
          lignes: C.reperes.map((r) => Object.assign({}, r, { v: nomV[r.versant] })),
        });
        PLF.blocDonnees(zr, { resume: "Repères plus anciens (1996-2010)", table: tr });
      }
      table = PLF.tableau({
        legende: "Répartition par catégorie (%) — ensemble des trois versants",
        colonnes: [{ titre: "Année", cle: "a" }].concat(cats.map((c) => ({ titre: c.libelle, cle: c.id, format: (v) => PLF.fmt.pourcent(v, 1) }))),
        lignes: lignes(),
      });
      PLF.blocDonnees(document.getElementById("cat-evol-donnees"), {
        table, csvNom: "categories-par-versant-par-annee.csv",
        csvEntetes: ["annee", "versant"].concat(cats.map((c) => c.id)),
        csvLignes: () => { const l = []; C.annees.forEach((a, k) => libVersants.forEach((v) => l.push([a, v.id].concat(cats.map((c) => C.versants[v.id][c.id][k]))))); return l; },
      });
    }
  }

  function demarrer() {
    let N;
    try { N = PLF.donnees("national"); } catch (e) {
      const m = document.getElementById("contenu");
      if (m) m.insertAdjacentHTML("afterbegin", `<p class="conteneur erreur">${e.message}</p>`);
      return;
    }
    const page = document.body.dataset.page;
    if (page === "accueil") accueil(N);
    else if (page === "evolution") evolution(N);
    else if (page === "composition") composition(N);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", demarrer);
  else demarrer();
})();
