/* ==========================================================================
   Page « Les retraites des fonctionnaires », à partir de donnees/site/retraites.js
   (DGAFP, rapport annuel sur l'état de la fonction publique 2026, d'après le
   Service des retraites de l'État, la CNRACL et le FSPOEIE).
   Seuls calculs : sommes, parts, rapports (cotisants / pensionnés, % du PIB) et
   conversion en euros constants (indice des prix à la consommation de l'Insee).
   ========================================================================== */
(function () {
  "use strict";
  const PLF = window.PLF;
  const G = PLF.graphiques;

  /* ---------- Formats ---------- */
  const nf = (dec) => new Intl.NumberFormat("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  const nfMax = (dec) => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: dec });
  const fmtMd = (v, dec = 1) => (v == null || isNaN(v) ? "n.d." : nf(dec).format(v) + " Md€");
  const fmtAxeMd = (v) => (v === 0 ? "0" : nfMax(1).format(v) + " Md€");
  const fmtEuro = (v) => (v == null || isNaN(v) ? "n.d." : nf(0).format(Math.round(v)) + " €");
  const fmtAxeEuro = (v) => (v === 0 ? "0" : nf(0).format(v) + " €");
  const fmtPct = (v, dec = 1) => (v == null || isNaN(v) ? "n.d." : PLF.fmt.pourcent(v, dec));
  const fmtAxePct = (v) => (v === 0 ? "0" : nfMax(1).format(v) + " %");
  const fmtNb = (v) => (v == null || isNaN(v) ? "n.d." : nf(0).format(Math.round(v)));
  const fmtRatio = (v) => (v == null || isNaN(v) ? "n.d." : nf(2).format(v));
  const arr = (v, dec = 3) => (v == null || isNaN(v) ? null : Math.round(v * 10 ** dec) / 10 ** dec);
  const $ = (id) => document.getElementById(id);

  /* ---------- Outils ---------- */
  function remplirCles(cles) {
    document.querySelectorAll("[data-cle]").forEach((n) => {
      const v = cles[n.dataset.cle];
      if (v == null) return;
      const m = n.classList.contains("chiffre__valeur") && /^(.+?)\s(milliards?|millions?)$/.exec(v);
      if (m) {
        n.textContent = m[1] + " ";
        const u = document.createElement("span");
        u.className = "chiffre__unite";
        u.textContent = m[2];
        n.appendChild(u);
      } else n.textContent = v;
    });
  }
  function legende(ul, items) {
    if (!ul) return;
    ul._items = items;
    const dessiner = () => {
      ul.innerHTML = ul._items.map((it) => `<li><span class="${it.trait ? "legende__trait" + (it.tirets ? " legende__trait--tirets" : "") : "legende__carre"}" style="${it.trait ? `color:${PLF.couleur(it.couleur)}` : `background:${PLF.couleur(it.couleur)}`}"></span>${it.libelle}</li>`).join("");
    };
    dessiner();
    if (!ul._ecoute) {
      document.addEventListener("plf:affichage", dessiner);
      ul._ecoute = true;
    }
  }
  function lireChoix(form, nom) {
    const c = form && form.querySelector(`input[name="${nom}"]:checked`);
    return c ? c.value : null;
  }
  // Arrondi « au plus fort reste » : parts entières dont la somme fait exactement 100.
  function partsEntieres(valeurs) {
    const total = valeurs.reduce((a, b) => a + b, 0);
    const brut = valeurs.map((v) => (100 * v) / total);
    const ent = brut.map(Math.floor);
    let reste = 100 - ent.reduce((a, b) => a + b, 0);
    brut.map((v, i) => [v - Math.floor(v), i]).sort((a, b) => b[0] - a[0]).forEach(([, i]) => { if (reste > 0) { ent[i]++; reste--; } });
    return ent;
  }

  // Régimes regroupés (graphiques) et détaillés (tableaux). La CNRACL réunit les
  // fonctionnaires territoriaux et hospitaliers.
  const GROUPES = [
    { cle: "fpe_civils", couleur: "--ms-1" },
    { cle: "fpe_militaires", couleur: "--ms-3" },
    { cle: "ouvriers_etat", couleur: "--ms-4" },
    { cle: "cnracl", couleur: "--ms-2", membres: ["cnracl_fpt", "cnracl_fph"] },
  ];
  const DETAIL = [
    { cle: "fpe_civils", couleur: "--ms-1" },
    { cle: "fpe_militaires", couleur: "--ms-3" },
    { cle: "ouvriers_etat", couleur: "--ms-4" },
    { cle: "cnracl_fpt", couleur: "--ms-2" },
    { cle: "cnracl_fph", couleur: "--ms-2", tirets: true },
  ];
  const lib = (R, cle) => R.regimes[cle].libelle;
  const court = (R, cle) => R.regimes[cle].court;
  // Somme terme à terme de plusieurs séries (null si une valeur manque).
  const sommeSeries = (listes) => listes[0].map((_, i) => (listes.some((l) => l[i] == null) ? null : listes.reduce((a, l) => a + l[i], 0)));

  /* ======================================================================
     1. Dépenses de pensions depuis 1990
     ====================================================================== */
  function sectionDepenses(R) {
    const zone = $("graphique-rt-depenses");
    if (!zone) return;
    const form = $("figure-rt-depenses").querySelector("form");
    const A = R.depenses.annees;
    const iFin = A.length - 1;
    const prixRef = R.prix[iFin];
    const S = R.depenses.series;
    const regs = [
      { cle: "fpe_civils_et_ati", couleur: "--ms-1" },
      { cle: "fpe_militaires", couleur: "--ms-3" },
      { cle: "ouvriers_etat", couleur: "--ms-4" },
      { cle: "cnracl", couleur: "--ms-2" },
    ];
    const total = A.map((_, i) => regs.reduce((a, r) => a + S[r.cle][i], 0));
    const conv = {
      courants: { f: (v) => v / 1000, axe: fmtAxeMd, val: (v) => fmtMd(v, 1), titre: "Milliards d'euros courants" },
      constants: { f: (v, i) => (v / 1000) * prixRef / R.prix[i], axe: fmtAxeMd, val: (v) => fmtMd(v, 1), titre: `Milliards d'euros de ${A[iFin]}` },
      pib: { f: (v, i) => (100 * v / 1000) / R.pib[i], axe: fmtAxePct, val: (v) => fmtPct(v, 2), titre: "% du PIB" },
    };
    let graph;
    function cfg() {
      const mesure = lireChoix(form, "rt-mesure") || "constants";
      const mode = lireChoix(form, "rt-mode") || "empile";
      const c = conv[mesure];
      const series = regs.map((r) => ({ id: r.cle, libelle: lib(R, r.cle), libelleCourt: court(R, r.cle), couleur: r.couleur, valeurs: S[r.cle].map(c.f) }));
      if (mode === "courbes") series.push({ id: "total", libelle: "Ensemble des régimes", libelleCourt: "Ensemble", couleur: "--ms-autre", tirets: true, valeurs: total.map(c.f) });
      legende($("legende-rt-depenses"), series.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: mode === "courbes", tirets: s.tirets })));
      return {
        annees: A, series, empile: mode === "empile", formatAxe: c.axe, formatValeur: c.val, titreAxeY: c.titre, yMin: 0, hauteur: 380,
        titreAccessible: `Pensions versées par les régimes de retraite des fonctionnaires depuis ${A[0]}, ${c.titre.toLowerCase()}`,
      };
    }
    graph = G.courbes(zone, cfg());
    form.addEventListener("change", () => graph.maj(cfg()));
    $("note-rt-depenses").textContent = `Pensions de retraite de droit direct et de réversion. Fonctionnaires civils de l'État : pensions versées par le Service des retraites de l'État, y compris aux anciens fonctionnaires de La Poste et d'Orange, et allocations temporaires d'invalidité (${fmtMd(R.cas.postes.find((p) => p.poste === "allocations_temporaires_invalidite").valeurs.slice(-1)[0] / 1000, 2)} en ${A[iFin]}). Territoriaux et hospitaliers : pensions de la CNRACL (fonctionnaires travaillant au moins 28 heures par semaine). Ne sont pas comptées : la retraite additionnelle de la fonction publique (sur les primes) et les retraites des contractuels (régime général et Ircantec). Euros constants : indice des prix à la consommation de l'Insee. Sources : ${R.source} ; PIB : ${R.sourcePib}.`;
    const lignes = A.map((a, i) => ({ a, ...Object.fromEntries(regs.map((r) => [r.cle, S[r.cle][i] / 1000])), total: total[i] / 1000, pib: (100 * total[i] / 1000) / R.pib[i], cst: (total[i] / 1000) * prixRef / R.prix[i] }));
    const t = PLF.tableau({
      legende: "Pensions versées par régime (milliards d'euros courants)",
      colonnes: [{ titre: "Année", cle: "a" }].concat(regs.map((r) => ({ titre: court(R, r.cle), cle: r.cle, format: (v) => nf(2).format(v) })))
        .concat([{ titre: "Total", cle: "total", format: (v) => nf(2).format(v) }, { titre: `Total en euros de ${A[iFin]}`, cle: "cst", format: (v) => nf(1).format(v) }, { titre: "% du PIB", cle: "pib", format: (v) => fmtPct(v, 2) }]),
      lignes: lignes.slice().reverse(),
    });
    PLF.blocDonnees($("donnees-rt-depenses"), {
      table: t, csvNom: "retraites-fonctionnaires-depenses-pensions.csv",
      csvEntetes: ["annee"].concat(regs.map((r) => r.cle + "_milliards_euros"), ["total_milliards_euros", `total_milliards_euros_${A[iFin]}`, "total_pct_pib"]),
      csvLignes: lignes.map((l) => [l.a].concat(regs.map((r) => arr(l[r.cle], 4)), [arr(l.total, 4), arr(l.cst, 3), arr(l.pib, 3)])),
    });
  }

  /* ======================================================================
     2. Pensions en paiement
     ====================================================================== */
  function sectionStocks(R) {
    const zone = $("graphique-rt-stocks");
    if (!zone) return;
    const form = $("figure-rt-stocks").querySelector("form");
    const A = R.stocks.annees;
    const S = R.stocks.series;
    const valeurs = (g, droit) => (g.membres ? sommeSeries(g.membres.map((m) => S[m][droit])) : S[g.cle][droit]);
    let graph;
    function cfg() {
      const droit = lireChoix(form, "rt-droit") || "total";
      const series = GROUPES.map((g) => ({ id: g.cle, libelle: lib(R, g.cle), libelleCourt: court(R, g.cle), couleur: g.couleur, valeurs: valeurs(g, droit).map((v) => (v == null ? null : v / 1000)) }));
      legende($("legende-rt-stocks"), series.map((s) => ({ libelle: s.libelle, couleur: s.couleur })));
      return {
        annees: A, series, empile: true, yMin: 0, hauteur: 360,
        formatAxe: (v) => (v === 0 ? "0" : nfMax(1).format(v) + " M"), formatValeur: (v) => fmtNb(v * 1e6),
        titreAxeY: droit === "total" ? "Millions de pensions (droit direct et réversion)" : "Millions de pensions de droit direct",
        titreAccessible: `Nombre de pensions de retraite de fonctionnaires en paiement au 31 décembre, ${A[0]}-${A[A.length - 1]}`,
      };
    }
    graph = G.courbes(zone, cfg());
    form.addEventListener("change", () => graph.maj(cfg()));
    $("note-rt-stocks").textContent = `Pensions en paiement au 31 décembre. Une même personne peut percevoir plusieurs pensions (par exemple après une carrière dans deux fonctions publiques, ou une pension de réversion en plus de sa propre pension) : il s'agit de pensions, pas de personnes. Les pensions de réversion (« droit dérivé ») sont versées aux veufs, veuves et orphelins. Fonctionnaires civils de l'État : y compris les anciens fonctionnaires de La Poste et d'Orange. Source : ${R.source}.`;
    const lignes = A.map((a, i) => {
      const l = { a };
      DETAIL.forEach((d) => { l[d.cle] = S[d.cle].total[i]; l[d.cle + "_dd"] = S[d.cle].direct[i]; });
      l.total = DETAIL.reduce((s, d) => s + S[d.cle].total[i], 0);
      l.direct = DETAIL.reduce((s, d) => s + S[d.cle].direct[i], 0);
      return l;
    });
    const t = PLF.tableau({
      legende: "Pensions en paiement au 31 décembre, droit direct et réversion (nombre)",
      colonnes: [{ titre: "Année", cle: "a" }].concat(DETAIL.map((d) => ({ titre: court(R, d.cle), cle: d.cle, format: (v) => fmtNb(v * 1000) })))
        .concat([{ titre: "Total", cle: "total", format: (v) => fmtNb(v * 1000) }, { titre: "dont droit direct", cle: "direct", format: (v) => fmtNb(v * 1000) }]),
      lignes: lignes.slice().reverse(),
    });
    PLF.blocDonnees($("donnees-rt-stocks"), {
      table: t, csvNom: "retraites-fonctionnaires-pensions-en-paiement.csv",
      csvEntetes: ["annee", "regime", "droit_direct", "droit_derive", "total"],
      csvLignes: () => { const out = []; A.forEach((a, i) => DETAIL.forEach((d) => out.push([a, d.cle, Math.round(S[d.cle].direct[i] * 1000), Math.round(S[d.cle].derive[i] * 1000), Math.round(S[d.cle].total[i] * 1000)]))); return out; },
    });
  }

  /* ======================================================================
     3. Montants des pensions
     ====================================================================== */
  function sectionMontants(R) {
    const C = R.caracteristiques;
    const zb = $("graphique-rt-montant-niveau");
    if (zb) {
      const pens = DETAIL.map((d) => C.regimes[d.cle].direct.pension_mensuelle_moyenne_euros);
      G.barres(zb, {
        categories: DETAIL.map((d) => court(R, d.cle)),
        series: [{ id: "direct", libelle: "Pension de droit direct", couleur: "--ms-1", valeurs: pens }],
        formatValeur: fmtEuro, formatAxe: fmtAxeEuro, libelleValeur: "Pension mensuelle brute moyenne", sansPart: true, hauteurBarre: 30, ecart: 16,
        titreAccessible: `Pension mensuelle brute moyenne de droit direct par régime, au 31 décembre ${C.annee}`,
      });
      $("note-rt-montant-niveau").textContent = `Pensions de droit direct en paiement au 31 décembre ${C.annee}, montant mensuel brut moyen y compris accessoires (majoration pour enfants, par exemple), avant CSG, CRDS et Casa. Les écarts reflètent surtout les carrières : les fonctionnaires de l'État sont plus souvent de catégorie A (enseignants, cadres), les fonctionnaires territoriaux plus souvent de catégorie C ; beaucoup de pensionnés de la CNRACL ont aussi eu une carrière dans le privé et perçoivent d'autres pensions. Source : ${R.source}.`;
      const ind = [
        ["effectif_milliers", "Nombre de pensions", (v) => fmtNb(v * 1000)],
        ["pension_mensuelle_moyenne_euros", "Pension mensuelle brute moyenne", fmtEuro],
        ["age_moyen", "Âge moyen des pensionnés", (v) => nf(1).format(v) + " ans"],
        ["age_premiere_mise_en_paiement", "Âge moyen au départ", (v) => nf(1).format(v) + " ans"],
        ["taux_liquidation_pct", "Taux de liquidation moyen", (v) => fmtPct(v, 1)],
        ["indice_liquidation", "Indice moyen à la liquidation", fmtNb],
        ["duree_services_trimestres", "Durée de services (trimestres)", fmtNb],
      ];
      const lignes = [];
      ["direct", "derive"].forEach((dr) => {
        lignes.push({ ind: dr === "direct" ? "Pensions de droit direct" : "Pensions de réversion (droit dérivé)", _classe: "total" });
        ind.forEach(([k, l, f]) => {
          if (!DETAIL.some((d) => C.regimes[d.cle][dr] && C.regimes[d.cle][dr][k] != null)) return;
          const ligne = { ind: "\u00a0\u00a0\u00a0" + l };
          DETAIL.forEach((d) => { const v = C.regimes[d.cle][dr] && C.regimes[d.cle][dr][k]; ligne[d.cle] = v == null ? "–" : f(v); });
          lignes.push(ligne);
        });
      });
      const t = PLF.tableau({
        legende: `Caractéristiques des pensions en paiement au 31 décembre ${C.annee}`,
        colonnes: [{ titre: "Indicateur", cle: "ind", texte: true }].concat(DETAIL.map((d) => ({ titre: court(R, d.cle), cle: d.cle, format: (v) => (v == null ? "" : v) }))),
        lignes,
      });
      PLF.blocDonnees($("donnees-rt-montant-niveau"), {
        resume: "Afficher le détail (âge, taux de liquidation, réversion…)", table: t, csvNom: `retraites-fonctionnaires-caracteristiques-${C.annee}.csv`,
        csvEntetes: ["regime", "droit", "indicateur", "valeur"],
        csvLignes: () => { const out = []; DETAIL.forEach((d) => ["direct", "derive"].forEach((dr) => Object.entries(C.regimes[d.cle][dr] || {}).forEach(([k, v]) => out.push([d.cle, dr, k, arr(v, 4)])))); return out; },
      });
    }

    const ze = $("graphique-rt-montant-evol");
    if (!ze) return;
    const form = $("figure-rt-montant-evol").querySelector("form");
    const M = R.pensionMoyenne;
    const A = M.annees;
    // Prix : la série de R.prix commence en 1990.
    const prix = (a) => R.prix[R.annees.indexOf(a)];
    const prixRef = R.prix[R.prix.length - 1];
    let graph;
    function cfg() {
      const mesure = lireChoix(form, "rt-montant-mesure") || "constants";
      const series = DETAIL.map((d) => ({
        id: d.cle, libelle: lib(R, d.cle), libelleCourt: court(R, d.cle), couleur: d.couleur, tirets: d.tirets,
        valeurs: M.series[d.cle].ensemble.map((v, i) => (v == null ? null : mesure === "constants" ? v * prixRef / prix(A[i]) : v)),
      }));
      legende($("legende-rt-montant-evol"), series.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: true, tirets: s.tirets })));
      return {
        annees: A, series, formatAxe: fmtAxeEuro, formatValeur: fmtEuro, yMin: 0, hauteur: 360,
        titreAxeY: mesure === "constants" ? `Euros de ${R.annees[R.annees.length - 1]} par mois` : "Euros courants par mois",
        titreAccessible: "Pension mensuelle brute moyenne par régime depuis 2000",
      };
    }
    graph = G.courbes(ze, cfg());
    form.addEventListener("change", () => graph.maj(cfg()));
    $("note-rt-montant-evol").textContent = `Montant mensuel brut moyen de l'ensemble des pensions en paiement (droit direct et réversion), y compris accessoires. La moyenne évolue avec les revalorisations, mais aussi avec l'arrivée de nouveaux retraités aux carrières plus complètes et plus qualifiées que leurs aînés. La moyenne publiée pour les fonctionnaires civils de l'État baisse en 2021 avant de remonter en 2022. Euros constants : indice des prix à la consommation de l'Insee. Source : ${R.source}.`;
    const lignes = A.map((a, i) => ({ a, ...Object.fromEntries(DETAIL.map((d) => [d.cle, M.series[d.cle].ensemble[i]])) }));
    const t = PLF.tableau({
      legende: "Pension mensuelle brute moyenne, droit direct et réversion (euros courants)",
      colonnes: [{ titre: "Année", cle: "a" }].concat(DETAIL.map((d) => ({ titre: court(R, d.cle), cle: d.cle, format: fmtEuro }))),
      lignes: lignes.slice().reverse(),
    });
    PLF.blocDonnees($("donnees-rt-montant-evol"), {
      table: t, csvNom: "retraites-fonctionnaires-pension-moyenne.csv",
      csvEntetes: ["annee", "regime", "droit", "euros_par_mois"],
      csvLignes: () => { const out = []; A.forEach((a, i) => DETAIL.forEach((d) => ["ensemble", "direct", "derive"].forEach((dr) => { const v = M.series[d.cle][dr][i]; if (v != null) out.push([a, d.cle, dr, arr(v, 2)]); }))); return out; },
    });
  }

  /* ======================================================================
     4. Ratio démographique
     ====================================================================== */
  function sectionRatio(R) {
    const zone = $("graphique-rt-ratio");
    if (!zone) return;
    const Q = R.ratio;
    const A = Q.annees;
    const ratio = (cle) => Q.series[cle].cotisants.map((c, i) => (c == null || !Q.series[cle].pensionnes[i] ? null : c / Q.series[cle].pensionnes[i]));
    const series = DETAIL.map((d) => ({ id: d.cle, libelle: lib(R, d.cle), libelleCourt: court(R, d.cle), couleur: d.couleur, tirets: d.tirets, valeurs: ratio(d.cle) }));
    G.courbes(zone, {
      annees: A, series, formatAxe: (v) => nfMax(1).format(v), formatValeur: fmtRatio, yMin: 0, hauteur: 360,
      titreAxeY: "Cotisants pour un pensionné", titreAccessible: "Nombre de cotisants pour un pensionné, par régime, depuis 1990",
    });
    legende($("legende-rt-ratio"), series.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: true, tirets: s.tirets })));
    $("note-rt-ratio").textContent = `Nombre de fonctionnaires en activité qui cotisent au régime, divisé par le nombre de pensions en paiement (droit direct et réversion). Fonctionnaires civils de l'État : données disponibles depuis 2005, sauf 2010 ; militaires : depuis 2014. Sous 1, le régime compte moins de cotisants que de pensionnés. Le rapport est calculé à partir des effectifs publiés ; pour les ouvriers d'État, les ratios publiés pour 1994 et 2001 (0,8 et 0,6) diffèrent un peu de ce calcul (0,74 et 0,54). Source : ${R.source}.`;
    const lignes = A.map((a, i) => {
      const l = { a };
      DETAIL.forEach((d) => { l[d.cle + "_c"] = Q.series[d.cle].cotisants[i]; l[d.cle + "_p"] = Q.series[d.cle].pensionnes[i]; l[d.cle] = series.find((s) => s.id === d.cle).valeurs[i]; });
      return l;
    });
    const fmtK = (v) => (v == null ? "–" : fmtNb(v * 1000));
    const t = PLF.tableau({
      legende: "Cotisants, pensionnés et nombre de cotisants pour un pensionné",
      colonnes: [{ titre: "Année", cle: "a" }].concat(...DETAIL.map((d) => [
        { titre: `${court(R, d.cle)} : cotisants`, cle: d.cle + "_c", format: fmtK },
        { titre: `${court(R, d.cle)} : pensionnés`, cle: d.cle + "_p", format: fmtK },
        { titre: `${court(R, d.cle)} : ratio`, cle: d.cle, format: (v) => (v == null ? "–" : fmtRatio(v)) },
      ])),
      lignes: lignes.slice().reverse(),
    });
    PLF.blocDonnees($("donnees-rt-ratio"), {
      table: t, csvNom: "retraites-fonctionnaires-ratio-demographique.csv",
      csvEntetes: ["annee", "regime", "cotisants", "pensionnes", "cotisants_par_pensionne", "ratio_publie"],
      csvLignes: () => { const out = []; A.forEach((a, i) => DETAIL.forEach((d) => { const s = Q.series[d.cle]; if (s.cotisants[i] == null && s.pensionnes[i] == null) return; out.push([a, d.cle, s.cotisants[i] == null ? null : Math.round(s.cotisants[i] * 1000), s.pensionnes[i] == null ? null : Math.round(s.pensionnes[i] * 1000), arr(lignes[i][d.cle], 4), s.publie[i]]); })); return out; },
    });
  }

  /* ======================================================================
     5. Financement : compte « Pensions » de l'État, taux, CNRACL
     ====================================================================== */
  function sectionFinancement(R) {
    const C = R.cas;
    const A = C.annees;
    const iFin = A.length - 1;
    const poste = (sens, p) => (C.postes.find((x) => x.sens === sens && x.poste === p) || { valeurs: A.map(() => 0) }).valeurs;
    const comp = [
      { cle: "etat", libelle: "L'État employeur (ministères)", detail: "contributions inscrites dans les dépenses de personnel de chaque ministère", couleur: "--ms-1", valeurs: poste("recette", "contribution_etat_employeur") },
      { cle: "salaries", libelle: "Les fonctionnaires eux-mêmes", detail: "retenues sur le traitement (11,10 % du traitement indiciaire)", couleur: "--ms-3", valeurs: poste("recette", "cotisations_salariales") },
      { cle: "etablissements", libelle: "Établissements publics et autres employeurs", detail: "universités, agences, fonctionnaires détachés…", couleur: "--ms-2", valeurs: poste("recette", "etablissements_publics_autres_employeurs") },
      { cle: "poste", libelle: "La Poste et Orange", detail: "pour leurs anciens fonctionnaires", couleur: "--ms-4", valeurs: poste("recette", "la_poste_orange") },
    ];
    const totalRec = poste("recette", "total");
    comp.push({ cle: "autres", libelle: "Autres recettes", detail: "compensation entre régimes, transferts, validations de services", couleur: "--ms-autre", valeurs: totalRec.map((t, i) => t - comp.reduce((a, c) => a + c.valeurs[i], 0)) });

    // Barre « sur 100 € »
    const barre = $("barre-rt-cas");
    if (barre) {
      const vals = comp.map((c) => c.valeurs[iFin]);
      const parts = partsEntieres(vals);
      const tot = vals.reduce((a, b) => a + b, 0);
      const ul = $("legende-rt-cas");
      const dessiner = () => {
        barre.innerHTML = comp.map((c, k) => {
          const fond = PLF.couleur(c.couleur);
          const w = (100 * vals[k]) / tot;
          return `<span style="width:${w}%;background:${fond};color:${PLF.texteSur(fond)}" title="${c.libelle} : ${parts[k]} €">${w >= 7 ? parts[k] + " €" : ""}</span>`;
        }).join("");
        ul.innerHTML = comp.map((c, k) => `<li><span class="legende__carre" style="background:${PLF.couleur(c.couleur)}"></span><span class="decomposition__part">${parts[k] ? parts[k] + " €" : "< 1 €"}</span><span><b>${c.libelle}</b> : ${fmtMd(vals[k] / 1000, 1).replace(" Md€", " milliard" + (vals[k] >= 2000 ? "s" : "") + " d'euros")}<br><small>${c.detail}</small></span></li>`).join("");
      };
      dessiner();
      document.addEventListener("plf:affichage", dessiner);
      barre.setAttribute("aria-label", `Sur 100 euros de recettes du compte Pensions de l'État en ${A[iFin]} : ` + comp.map((c, k) => `${parts[k] ? parts[k] + " euros" : "moins d'un euro"} : ${c.libelle}`).join(" ; "));
      $("note-rt-cas").textContent = `Recettes du compte d'affectation spéciale « Pensions » (pensions civiles et militaires et allocations temporaires d'invalidité) en ${A[iFin]} : ${fmtMd(tot / 1000, 1)}, pour ${fmtMd(poste("depense", "total")[iFin] / 1000, 1)} de dépenses. Source : ${R.source}.`;
    }

    // Recettes du compte Pensions depuis 2006
    const zr = $("graphique-rt-cas-evol");
    if (zr) {
      const series = comp.map((c) => ({ id: c.cle, libelle: c.libelle, couleur: c.couleur, valeurs: c.valeurs.map((v) => v / 1000) }));
      G.courbes(zr, {
        annees: A, series, empile: true, yMin: 0, hauteur: 340, formatAxe: fmtAxeMd, formatValeur: (v) => fmtMd(v, 2), titreAxeY: "Milliards d'euros courants",
        titreAccessible: `Recettes du compte Pensions de l'État par origine, ${A[0]}-${A[iFin]}`,
      });
      legende($("legende-rt-cas-evol"), series.map((s) => ({ libelle: s.libelle, couleur: s.couleur })));
      $("note-rt-cas-evol").textContent = `Les dépenses et recettes de 2006 à 2010 ont été reclassées par la direction du Budget selon la nomenclature de 2011. « Autres recettes » : compensation démographique entre régimes, transferts de la CNRACL, validations de services, subventions (dont un fonds de roulement d'un milliard d'euros en 2006). Source : ${R.source}.`;
      const lignes = A.map((a, i) => ({ a, ...Object.fromEntries(comp.map((c) => [c.cle, c.valeurs[i] / 1000])), rec: totalRec[i] / 1000, dep: poste("depense", "total")[i] / 1000, pens: (poste("depense", "pensions_civiles")[i] + poste("depense", "pensions_militaires")[i]) / 1000 }));
      const t = PLF.tableau({
        legende: "Compte d'affectation spéciale « Pensions » : recettes et dépenses (milliards d'euros courants)",
        colonnes: [{ titre: "Année", cle: "a" }].concat(comp.map((c) => ({ titre: c.libelle, cle: c.cle, format: (v) => nf(2).format(v) })))
          .concat([{ titre: "Total des recettes", cle: "rec", format: (v) => nf(2).format(v) }, { titre: "Total des dépenses", cle: "dep", format: (v) => nf(2).format(v) }, { titre: "dont pensions civiles et militaires", cle: "pens", format: (v) => nf(2).format(v) }]),
        lignes: lignes.slice().reverse(),
      });
      PLF.blocDonnees($("donnees-rt-cas-evol"), {
        table: t, csvNom: "retraites-etat-compte-pensions.csv",
        csvEntetes: ["annee", "sens", "poste", "libelle", "millions_euros"],
        csvLignes: () => { const out = []; A.forEach((a, i) => C.postes.forEach((p) => { if (p.valeurs[i] != null) out.push([a, p.sens, p.poste, p.libelle, arr(p.valeurs[i], 3)]); })); return out; },
      });
    }

    // Taux de cotisation
    const zt = $("graphique-rt-taux");
    if (zt) {
      const T = R.taux;
      const val = (regime, taux) => (T.series.find((s) => s.regime === regime && s.taux === taux) || {}).valeurs;
      const series = [
        { id: "etat", libelle: "État employeur, fonctionnaires civils (ministères)", libelleCourt: "État (civils)", couleur: "--ms-1", valeurs: val("pcmr", "employeur_civils_ministeres") },
        { id: "mil", libelle: "État employeur, militaires", libelleCourt: "État (militaires)", couleur: "--ms-3", valeurs: val("pcmr", "employeur_militaires") },
        { id: "ouv", libelle: "Employeur, ouvriers d'État", libelleCourt: "Ouvriers d'État", couleur: "--ms-4", valeurs: val("ouvriers_etat", "employeur") },
        { id: "cnracl", libelle: "Collectivités et hôpitaux employeurs (CNRACL)", libelleCourt: "CNRACL", couleur: "--ms-2", valeurs: val("cnracl", "employeur") },
        { id: "sal", libelle: "Fonctionnaire (retenue sur le traitement)", libelleCourt: "Fonctionnaire", couleur: "--ms-autre", tirets: true, valeurs: val("pcmr", "salarie") },
      ];
      G.courbes(zt, {
        annees: T.annees, series, formatAxe: fmtAxePct, formatValeur: (v) => fmtPct(v, 2), yMin: 0, hauteur: 380, titreAxeY: "% du traitement indiciaire brut",
        titreAccessible: `Taux de cotisation des employeurs et des fonctionnaires pour la retraite, ${T.annees[0]}-${T.annees[T.annees.length - 1]}`,
      });
      legende($("legende-rt-taux"), series.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: true, tirets: s.tirets })));
      const etab = val("pcmr", "employeur_civils_etablissements");
      const mini = val("pcmr", "employeur_civils_ministeres");
      let iAlign = etab.length - 1;
      while (iAlign > 0 && etab[iAlign - 1] != null && mini[iAlign - 1] != null && Math.abs(etab[iAlign - 1] - mini[iAlign - 1]) < 0.005) iAlign--;
      $("note-rt-taux").textContent = `Taux appliqués au traitement indiciaire brut (hors primes). Avant 2006, l'État payait les pensions de ses fonctionnaires directement sur son budget, sans taux de contribution ; seuls les établissements publics employant des fonctionnaires de l'État versaient une contribution (${fmtPct(etab[0], 0)} en ${T.annees[0]} ; même taux que les ministères depuis ${T.annees[iAlign]}). Depuis 2006, le taux de l'État est fixé chaque année pour équilibrer le compte « Pensions ». Le taux de la CNRACL doit augmenter de 3 points par an jusqu'à 43,65 % en 2028 (décret n° 2025-86 du 30 janvier 2025). Source : ${R.source}.`;
      const lignes = T.annees.map((a, i) => ({ a, ...Object.fromEntries(T.series.map((s) => [s.regime + "_" + s.taux, s.valeurs[i]])) }));
      const noms = { pcmr_salarie: "Fonctionnaires (État et CNRACL)", pcmr_employeur_civils_ministeres: "État, civils (ministères)", pcmr_employeur_civils_etablissements: "Établissements publics de l'État", pcmr_employeur_militaires: "État, militaires", pcmr_employeur_ati: "État, invalidité (ATI)", ouvriers_etat_salarie: "Ouvriers d'État (salariés)", ouvriers_etat_employeur: "Ouvriers d'État (employeur)", cnracl_salarie: "CNRACL (salariés)", cnracl_employeur: "CNRACL (employeurs)" };
      const t = PLF.tableau({
        legende: "Taux de cotisation pour la retraite (% du traitement indiciaire brut)",
        colonnes: [{ titre: "Année", cle: "a" }].concat(T.series.map((s) => ({ titre: noms[s.regime + "_" + s.taux] || s.regime + " " + s.taux, cle: s.regime + "_" + s.taux, format: (v) => (v == null ? "–" : nf(2).format(v)) }))),
        lignes: lignes.slice().reverse(),
      });
      PLF.blocDonnees($("donnees-rt-taux"), {
        table: t, csvNom: "retraites-fonctionnaires-taux-de-cotisation.csv",
        csvEntetes: ["annee", "regime", "taux", "taux_pct"],
        csvLignes: () => { const out = []; T.annees.forEach((a, i) => T.series.forEach((s) => { if (s.valeurs[i] != null) out.push([a, s.regime, s.taux, s.valeurs[i]]); })); return out; },
      });
    }

    // Résultat de la CNRACL
    const zc = $("graphique-rt-cnracl");
    if (zc) {
      const N = R.cnracl;
      const p = (sens, cle) => (N.postes.find((x) => x.sens === sens && x.poste === cle) || {}).valeurs;
      const res = p("resultat", "resultat");
      G.colonnes(zc, {
        annees: N.annees, valeurs: res.map((v) => v / 1000), libelle: "Résultat de l'exercice",
        formatValeur: (v) => (v > 0 ? "+" : "") + fmtMd(v, 2), formatAxe: (v) => (v === 0 ? "0" : nfMax(1).format(v) + " Md€"),
        couleurPositive: "--ms-2", couleurNegative: "--ms-5", hauteur: 300,
        titreAccessible: `Résultat annuel de la CNRACL, ${N.annees[0]}-${N.annees[N.annees.length - 1]}, en milliards d'euros`,
      });
      $("note-rt-cnracl").textContent = `Produits moins charges de l'exercice. Les charges comprennent les pensions versées (« prestations sociales »), la compensation démographique versée aux autres régimes et les frais de gestion ; les produits, surtout les cotisations des employeurs et des agents. En 2012, un produit exceptionnel de 690 millions d'euros (transfert de réserves) améliore le résultat. Source : ${R.source}.`;
      const lignes = N.annees.map((a, i) => ({ a, prest: p("charge", "prestations")[i] / 1000, comp: p("charge", "compensations")[i] / 1000, ch: p("charge", "total")[i] / 1000, cot: p("produit", "cotisations_et_produits_affectes")[i] / 1000, pr: p("produit", "total")[i] / 1000, res: res[i] / 1000 }));
      const f = (v) => nf(2).format(v);
      const t = PLF.tableau({
        legende: "Compte de résultat simplifié de la CNRACL (milliards d'euros courants)",
        colonnes: [{ titre: "Année", cle: "a" }, { titre: "Pensions versées", cle: "prest", format: f }, { titre: "Compensation versée", cle: "comp", format: f }, { titre: "Total des charges", cle: "ch", format: f }, { titre: "Cotisations et produits affectés", cle: "cot", format: f }, { titre: "Total des produits", cle: "pr", format: f }, { titre: "Résultat", cle: "res", format: (v) => (v > 0 ? "+" : "") + f(v) }],
        lignes: lignes.slice().reverse(),
      });
      PLF.blocDonnees($("donnees-rt-cnracl"), {
        table: t, csvNom: "retraites-cnracl-compte-de-resultat.csv",
        csvEntetes: ["annee", "sens", "poste", "libelle", "millions_euros"],
        csvLignes: () => { const out = []; N.annees.forEach((a, i) => N.postes.forEach((q) => { if (q.valeurs[i] != null) out.push([a, q.sens, q.poste, q.libelle, arr(q.valeurs[i], 3)]); })); return out; },
      });
    }
  }

  /* ======================================================================
     6. Départs à la retraite
     ====================================================================== */
  function sectionDeparts(R) {
    const F = R.flux;
    const A = F.annees;
    const zf = $("graphique-rt-flux");
    if (zf) {
      const valeurs = (g) => (g.membres ? sommeSeries(g.membres.map((m) => F.series[m].direct)) : F.series[g.cle].direct);
      const series = GROUPES.map((g) => ({ id: g.cle, libelle: lib(R, g.cle), libelleCourt: court(R, g.cle), couleur: g.couleur, valeurs: valeurs(g).map((v) => (v == null ? null : v * 1000)) }));
      G.courbes(zf, {
        annees: A, series, empile: true, yMin: 0, hauteur: 340, formatAxe: (v) => fmtNb(v), formatValeur: fmtNb, titreAxeY: "Nouveaux retraités par an",
        titreAccessible: `Nouvelles pensions de droit direct de fonctionnaires, ${A[0]}-${A[A.length - 1]}`,
      });
      legende($("legende-rt-flux"), series.map((s) => ({ libelle: s.libelle, couleur: s.couleur })));
      $("note-rt-flux").textContent = `Pensions de droit direct entrées en paiement dans l'année ; fonctionnaires civils de l'État hors anciens fonctionnaires de La Poste et d'Orange. Les pics de 2003 et de 2011 coïncident avec les réformes des retraites de 2003 et de 2010 : de nombreux fonctionnaires sont partis avant l'entrée en vigueur des nouvelles règles. S'y ajoutent environ ${fmtNb(Math.round(F.ircantec[A.length - 1] * 10) * 100)} contractuels par an, encore en poste dans la fonction publique l'année précédant leur départ, qui liquident leur retraite complémentaire à l'Ircantec (leur retraite de base est versée par le régime général). Source : ${R.source}.`;
      const lignes = A.map((a, i) => ({ a, ...Object.fromEntries(DETAIL.map((d) => [d.cle, F.series[d.cle].direct[i]])), irc: F.ircantec[i] }));
      const t = PLF.tableau({
        legende: "Nouvelles pensions de droit direct (nombre)",
        colonnes: [{ titre: "Année", cle: "a" }].concat(DETAIL.map((d) => ({ titre: court(R, d.cle), cle: d.cle, format: (v) => fmtNb(v * 1000) })), [{ titre: "Contractuels (Ircantec)", cle: "irc", format: (v) => (v == null ? "n.d." : fmtNb(v * 1000)) }]),
        lignes: lignes.slice().reverse(),
      });
      PLF.blocDonnees($("donnees-rt-flux"), {
        table: t, csvNom: "retraites-fonctionnaires-nouvelles-pensions.csv",
        csvEntetes: ["annee", "regime", "droit_direct", "droit_derive"],
        csvLignes: () => { const out = []; A.forEach((a, i) => { DETAIL.forEach((d) => out.push([a, d.cle, Math.round(F.series[d.cle].direct[i] * 1000), Math.round(F.series[d.cle].derive[i] * 1000)])); if (F.ircantec[i] != null) out.push([a, "ircantec", Math.round(F.ircantec[i] * 1000), null]); }); return out; },
      });
    }
    const za = $("graphique-rt-age");
    if (za) {
      const Ag = R.age;
      const series = [
        { id: "ensemble", libelle: "Ensemble des nouveaux retraités fonctionnaires", libelleCourt: "Ensemble", couleur: "--ms-1", epaisseur: 3.5, valeurs: Ag.series.ensemble },
        { id: "sedentaire", libelle: "Emplois « sédentaires »", libelleCourt: "Sédentaires", couleur: "--ms-3", valeurs: Ag.series.sedentaire },
        { id: "actif", libelle: "Emplois « actifs » (policiers, aides-soignants…)", libelleCourt: "Actifs", couleur: "--ms-2", valeurs: Ag.series.actif },
        { id: "carriere_longue", libelle: "Carrières longues", libelleCourt: "Carrières longues", couleur: "--ms-4", valeurs: Ag.series.carriere_longue },
      ];
      G.courbes(za, {
        annees: Ag.annees, series, formatAxe: (v) => nfMax(0).format(v) + " ans", formatValeur: (v) => nf(1).format(v) + " ans", yMin: 56, hauteur: 320, titreAxeY: "Âge moyen au départ",
        titreAccessible: `Âge moyen de départ à la retraite des fonctionnaires, ${Ag.annees[0]}-${Ag.annees[Ag.annees.length - 1]}`,
      });
      legende($("legende-rt-age"), series.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: true })));
      $("note-rt-age").textContent = `Fonctionnaires civils de l'État (hors La Poste et Orange) et fonctionnaires territoriaux et hospitaliers partis à la retraite dans l'année (pensions de droit direct). Les emplois « actifs » (policiers, surveillants pénitentiaires, aides-soignants et infirmiers relevant de l'ancien statut, sapeurs-pompiers…) ouvrent droit à un départ plus précoce. « Ensemble » comprend aussi les départs pour invalidité, pour motifs familiaux et des fonctionnaires handicapés. Les militaires, qui partent beaucoup plus tôt, ne sont pas inclus. Source : ${R.source}.`;
      const t = PLF.tableau({
        legende: "Âge moyen de départ à la retraite des fonctionnaires (années)",
        colonnes: [{ titre: "Année", cle: "a" }].concat(series.map((s) => ({ titre: s.libelleCourt, cle: s.id, format: (v) => nf(1).format(v) }))),
        lignes: Ag.annees.map((a, i) => ({ a, ...Object.fromEntries(series.map((s) => [s.id, s.valeurs[i]])) })).reverse(),
      });
      PLF.blocDonnees($("donnees-rt-age"), {
        table: t, csvNom: "retraites-fonctionnaires-age-de-depart.csv",
        csvEntetes: ["annee"].concat(series.map((s) => s.id)), csvLignes: Ag.annees.map((a, i) => [a].concat(series.map((s) => arr(s.valeurs[i], 2)))),
      });
    }
  }

  /* ---------- Page d'accueil : chiffre clé ---------- */
  function demarrer() {
    const page = document.body.dataset.page;
    if (page !== "retraites" && page !== "accueil") return;
    let R;
    try { R = PLF.donnees("retraites"); } catch (e) {
      const m = document.getElementById("contenu");
      if (m && page === "retraites") m.insertAdjacentHTML("afterbegin", `<p class="conteneur erreur">${e.message}</p>`);
      return;
    }
    remplirCles(R.cles);
    if (page === "accueil") return;
    sectionDepenses(R);
    sectionStocks(R);
    sectionMontants(R);
    sectionRatio(R);
    sectionFinancement(R);
    sectionDeparts(R);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", demarrer);
  else demarrer();
})();
