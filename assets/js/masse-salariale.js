/* ==========================================================================
   Page « La masse salariale » (et encadré de la page d'accueil), à partir de
   donnees/site/masse_salariale.js (comptes nationaux de l'Insee, DGAFP, Eurostat).
   Les seuls calculs sont des sommes, des parts, des divisions (par habitant,
   par emploi), des conversions en euros constants (indice des prix à la
   consommation de l'Insee) et l'estimation du salaire net signalée comme telle.
   ========================================================================== */
(function () {
  "use strict";
  const PLF = window.PLF;
  const G = PLF.graphiques;

  /* ---------- Formats ---------- */
  const nf = (dec) => new Intl.NumberFormat("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  const fmtMd = (v, dec = 1) => (v == null || isNaN(v) ? "n.d." : nf(dec).format(v) + " Md€");
  const fmtAxeMd = (v) => (v === 0 ? "0" : new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(v) + " Md€");
  const fmtEuro = (v) => (v == null || isNaN(v) ? "n.d." : nf(0).format(Math.round(v)) + " €");
  const fmtAxeEuro = (v) => (v === 0 ? "0" : nf(0).format(v) + " €");
  const fmtPct = (v, dec = 1) => PLF.fmt.pourcent(v, dec);
  const fmtAxePct = (v) => (v === 0 ? "0" : new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(v) + " %");
  const fmtVar = (v) => PLF.fmt.variation(v, 1);
  const arr = (v, dec = 3) => (v == null || isNaN(v) ? null : Math.round(v * 10 ** dec) / 10 ** dec);

  /* ---------- Outils communs ---------- */
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
  // Légende redessinée à chaque changement de thème (une seule écoute par liste).
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
  const $ = (id) => document.getElementById(id);
  const somme = (vals) => (vals.some((v) => v == null) ? null : vals.reduce((a, b) => a + b, 0));
  // Arrondi « au plus fort reste » : des parts entières qui totalisent exactement 100.
  function partsEntieres(valeurs) {
    const total = valeurs.reduce((a, b) => a + b, 0);
    const brut = valeurs.map((v) => (100 * v) / total);
    const ent = brut.map(Math.floor);
    let reste = 100 - ent.reduce((a, b) => a + b, 0);
    brut.map((v, i) => [v - Math.floor(v), i]).sort((a, b) => b[0] - a[0]).forEach(([, i]) => { if (reste > 0) { ent[i]++; reste--; } });
    return ent;
  }

  function contexte(M) {
    const CN = M.cn;
    const A = CN.annees;
    const iFin = A.length - 1;
    const AN = A[iFin];
    const prixRef = CN.prix[iFin];
    const cst = (v, i) => (v == null || CN.prix[i] == null ? null : (v * prixRef) / CN.prix[i]);
    const noteAnnee = (a) => (CN.statut[String(a)] ? `Résultats ${CN.statut[String(a)]}s.` : "");
    return { CN, A, iFin, AN, prixRef, cst, noteAnnee };
  }

  /* ======================================================================
     « Sur 100 € » : du coût total pour les employeurs au salaire net
     ====================================================================== */
  function composantesCentEuros(M) {
    const { CN, iFin } = contexte(M);
    const S = CN.secteurs.S13;
    const brut = S.D11[iFin];
    const net = brut * M.ratioNet.valeur;
    return [
      { cle: "net", libelle: "Salaire net versé aux agents", detail: "estimation, avant impôt sur le revenu", couleur: "--ms-1", v: net },
      { cle: "prelevements", libelle: "Cotisations salariales et CSG-CRDS", detail: "prélevées sur le salaire brut (estimation)", couleur: "--ms-3", v: brut - net },
      { cle: "D121", libelle: "Cotisations sociales des employeurs", detail: "retraite, maladie, famille…", couleur: "--ms-2", v: S.D121[iFin] },
      { cle: "D122", libelle: "Cotisations « imputées »", detail: "retraites des fonctionnaires de l'État, payées par l'État", couleur: "--ms-4", v: S.D122[iFin] },
      { cle: "D291", libelle: "Impôts sur les salaires", detail: "payés par les employeurs (taxe sur les salaires, versement mobilité…)", couleur: "--ms-5", v: S.D291[iFin] },
    ];
  }

  function barreCentEuros(barre, ul, M, avecMontants = true) {
    if (!barre) return;
    const { AN } = contexte(M);
    const comp = composantesCentEuros(M);
    const total = comp.reduce((a, c) => a + c.v, 0);
    const parts = partsEntieres(comp.map((c) => c.v));
    const estimation = (c) => c.cle === "net" || c.cle === "prelevements";
    const montant = (c) => (estimation(c) ? "environ " + nf(0).format(c.cle === "net" ? Math.round(c.v / 5) * 5 : c.v) : nf(0).format(c.v)) + " milliards d'euros";
    const dessiner = () => {
      barre.innerHTML = comp.map((c, k) => {
        const fond = PLF.couleur(c.couleur);
        const w = (100 * c.v) / total;
        return `<span style="width:${w}%;background:${fond};color:${PLF.texteSur(fond)}" title="${c.libelle} : ${parts[k]} €">${w >= 7 ? parts[k] + " €" : ""}</span>`;
      }).join("");
      if (ul) {
        ul.innerHTML = comp.map((c, k) => `<li><span class="legende__carre" style="background:${PLF.couleur(c.couleur)}"></span><span class="decomposition__part">${parts[k]} €</span><span><b>${c.libelle}</b>${avecMontants ? ` : ${montant(c)}` : ""}<br><small>${c.detail}</small></span></li>`).join("");
      }
    };
    dessiner();
    document.addEventListener("plf:affichage", dessiner);
    barre.setAttribute("aria-label", `Sur 100 euros consacrés aux agents publics en ${AN} : ` + comp.map((c, k) => `${parts[k]} euros de ${c.libelle.toLowerCase()}`).join(", "));
    return { comp, total, parts };
  }

  function sectionCentEuros(M) {
    const res = barreCentEuros($("barre-cent-euros"), $("legende-cent-euros"), M);
    if (!res) return;
    const { CN, iFin, AN } = contexte(M);
    const S = CN.secteurs.S13;
    $("note-cent-euros").textContent = `Coût total = rémunération des salariés des administrations publiques (${fmtMd(S.D1[iFin], 1)}) + impôts sur les salaires et la main-d'œuvre (${fmtMd(S.D291[iFin], 1)}) = ${fmtMd(res.total, 1)} en ${AN} (résultats provisoires). Le partage du salaire brut entre salaire net et prélèvements est une estimation : nous appliquons aux ${fmtMd(S.D11[iFin], 1)} de salaires bruts la part du net dans le brut mesurée par la DGAFP pour l'ensemble des agents publics en ${M.ratioNet.annee} (${fmtPct(100 * M.ratioNet.valeur, 1)}). Sources : ${CN.source} ; ${M.ratioNet.source}.`;
    const t = PLF.tableau({
      legende: `Du coût total au salaire net, administrations publiques, ${AN}`,
      colonnes: [
        { titre: "Composante", cle: "libelle", texte: true },
        { titre: "Milliards d'euros", cle: "v", format: (v) => nf(1).format(v) },
        { titre: "Sur 100 €", cle: "part", format: (v) => nf(1).format(v) + " €" },
        { titre: "Nature", cle: "nature", texte: true },
      ],
      lignes: res.comp.map((c) => ({ libelle: c.libelle, v: c.v, part: (100 * c.v) / res.total, nature: c.cle === "net" || c.cle === "prelevements" ? "estimation (DGAFP)" : "comptes nationaux (Insee)" }))
        .concat([{ libelle: "Coût total pour les employeurs", v: res.total, part: 100, nature: "somme", _classe: "total" }]),
    });
    PLF.blocDonnees($("donnees-cent-euros"), {
      table: t, csvNom: `masse-salariale-du-cout-au-net-${AN}.csv`,
      csvEntetes: ["composante", "milliards_euros", "sur_100_euros", "nature"],
      csvLignes: res.comp.map((c) => [c.libelle, arr(c.v, 3), arr((100 * c.v) / res.total, 2), c.cle === "net" || c.cle === "prelevements" ? "estimation" : "Insee"]),
    });
  }

  /* ======================================================================
     Évolution depuis 1949
     ====================================================================== */
  const SOUS_SECTEURS = [
    { id: "S1311", libelle: "État et organismes nationaux", court: "État et ODAC", couleur: "--ms-1" },
    { id: "S1313", libelle: "Administrations locales", court: "Locales", couleur: "--ms-2" },
    { id: "S1314", libelle: "Sécurité sociale et hôpitaux", court: "Sécu. et hôpitaux", couleur: "--ms-3" },
  ];
  const COMPOSANTES = {
    D1: "rémunérations totales (salaires bruts et cotisations des employeurs)",
    D11: "salaires bruts",
    D12: "cotisations sociales des employeurs (effectives et imputées)",
  };
  const MESURES = {
    courants: { titreAxe: "Milliards d'euros courants", fmt: (v) => fmtMd(v, 1), axe: fmtAxeMd },
    constants: { titreAxe: "Milliards d'euros constants", fmt: (v) => fmtMd(v, 1), axe: fmtAxeMd },
    pib: { titreAxe: "% du PIB", fmt: (v) => fmtPct(v, 2), axe: fmtAxePct },
    depenses: { titreAxe: "% des dépenses publiques", fmt: (v) => fmtPct(v, 1), axe: fmtAxePct },
    habitant: { titreAxe: "Euros constants par habitant", fmt: fmtEuro, axe: fmtAxeEuro },
  };

  function sectionEvolution(M) {
    const zone = $("graphique-1949");
    if (!zone) return;
    const { CN, A, AN, cst, noteAnnee } = contexte(M);
    const etat = { mesure: "constants", composante: "D1", mode: "empile" };
    const convertir = (vals) => vals.map((v, i) => {
      if (v == null) return null;
      switch (etat.mesure) {
        case "constants": return cst(v, i);
        case "pib": return (100 * v) / CN.pib[i];
        case "depenses": return CN.depenses[i] == null ? null : (100 * v) / CN.depenses[i];
        case "habitant": return (cst(v, i) * 1e9) / (CN.population[i] * 1e3);
        default: return v;
      }
    });
    function cfg() {
      const debut = etat.mesure === "depenses" ? CN.depenses.findIndex((v) => v != null) : 0;
      const garde = (x) => x.slice(debut);
      let series = SOUS_SECTEURS.map((s) => ({ id: s.id, libelle: s.libelle, libelleCourt: s.court, couleur: s.couleur, valeurs: garde(convertir(CN.secteurs[s.id][etat.composante])) }));
      if (etat.mode === "courbes") {
        series = [{ id: "S13", libelle: "Ensemble des administrations", libelleCourt: "Ensemble", couleur: "--ms-autre", valeurs: garde(convertir(CN.secteurs.S13[etat.composante])), epaisseur: 3.2 }].concat(series);
      }
      const m = MESURES[etat.mesure];
      return {
        annees: garde(A), series, empile: etat.mode === "empile",
        formatAxe: m.axe, formatValeur: m.fmt, titreAxeY: m.titreAxe, yMin: 0,
        noteAnnee, hauteur: 400,
        titreAccessible: `Rémunérations versées par les administrations publiques (${COMPOSANTES[etat.composante]}), ${m.titreAxe.toLowerCase()}, de ${A[debut]} à ${AN}`,
      };
    }
    const graphique = G.courbes(zone, cfg());
    const majLegende = () => legende($("legende-1949"), (etat.mode === "courbes" ? [{ libelle: "Ensemble des administrations publiques", couleur: "--ms-autre", trait: true }] : [])
      .concat(SOUS_SECTEURS.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: etat.mode === "courbes" }))));
    const majTextes = () => {
      const m = MESURES[etat.mesure];
      $("sous-titre-1949").textContent = `${m.titreAxe}${etat.mesure === "constants" || etat.mesure === "habitant" ? ` (euros de ${AN})` : ""}, ${COMPOSANTES[etat.composante]}.${etat.mode === "empile" ? " Les aires sont empilées : leur sommet donne le total." : ""}`;
      $("note-1949").textContent = `Administrations publiques au sens de la comptabilité nationale : « État et organismes nationaux » = administrations publiques centrales (État et organismes divers d'administration centrale) ; « administrations locales » = collectivités locales et leurs établissements ; « Sécurité sociale et hôpitaux » = administrations de sécurité sociale, dont les hôpitaux publics. ${AN - 1} : résultats semi-définitifs ; ${AN} : provisoires. Euros constants : indice des prix à la consommation de l'Insee. Par habitant : population moyenne de l'année. Sources : ${CN.source} ; ${CN.sourcePib} ; ${CN.sourceDepenses}.`;
    };
    majLegende();
    majTextes();
    document.querySelector("#figure-1949 .figure__controles").addEventListener("change", (e) => {
      if (e.target.name === "ms-mesure") etat.mesure = e.target.value;
      if (e.target.name === "ms-composante") etat.composante = e.target.value;
      if (e.target.name === "ms-mode") etat.mode = e.target.value;
      graphique.maj(cfg());
      majLegende();
      majTextes();
    });

    // Tableau : une ligne par année, l'ensemble des administrations publiques
    const S = CN.secteurs.S13;
    const lignes = A.map((a, i) => ({
      a, d1: S.D1[i], d11: S.D11[i], d12: S.D12[i], d122: S.D122[i], d291: S.D291[i],
      pib: (100 * S.D1[i]) / CN.pib[i], dep: CN.depenses[i] == null ? null : (100 * S.D1[i]) / CN.depenses[i],
      cst: cst(S.D1[i], i), hab: (cst(S.D1[i], i) * 1e9) / (CN.population[i] * 1e3),
      etat: CN.secteurs.S13111.D1[i], odac: CN.secteurs.S13112.D1[i], apul: CN.secteurs.S1313.D1[i], asso: CN.secteurs.S1314.D1[i],
    }));
    const f1 = (v) => (v == null ? "–" : nf(1).format(v));
    const t = PLF.tableau({
      legende: `Rémunérations versées par les administrations publiques, 1949-${AN} (milliards d'euros courants sauf mention)`,
      colonnes: [
        { titre: "Année", cle: "a" },
        { titre: "Rémunérations totales", cle: "d1", format: f1 },
        { titre: "dont salaires bruts", cle: "d11", format: f1 },
        { titre: "dont cotisations des employeurs", cle: "d12", format: f1 },
        { titre: "dont cotisations imputées", cle: "d122", format: f1 },
        { titre: "Impôts sur les salaires", cle: "d291", format: f1 },
        { titre: "État", cle: "etat", format: f1 },
        { titre: "Organismes nationaux", cle: "odac", format: f1 },
        { titre: "Administrations locales", cle: "apul", format: f1 },
        { titre: "Sécurité sociale et hôpitaux", cle: "asso", format: f1 },
        { titre: "% du PIB", cle: "pib", format: (v) => fmtPct(v, 2) },
        { titre: "% des dépenses publiques", cle: "dep", format: (v) => (v == null ? "–" : fmtPct(v, 1)) },
        { titre: `Md€ de ${AN}`, cle: "cst", format: f1 },
        { titre: `€ de ${AN} par habitant`, cle: "hab", format: fmtEuro },
      ],
      lignes,
    });
    PLF.blocDonnees($("donnees-1949"), {
      table: t, csvNom: `masse-salariale-administrations-publiques-1949-${AN}.csv`,
      csvEntetes: ["annee", "secteur", "remuneration_salaries_D1", "salaires_bruts_D11", "cotisations_employeurs_D12", "cotisations_effectives_D121", "cotisations_imputees_D122", "impots_sur_salaires_D291", "pib", "depenses_publiques", "population_milliers", `prix_base100_${AN}`],
      csvLignes: () => {
        const l = [];
        A.forEach((a, i) => ["S13", "S1311", "S13111", "S13112", "S1313", "S1314"].forEach((s) => {
          const X = CN.secteurs[s];
          if (X.D1[i] == null) return;
          l.push([a, s, X.D1[i], X.D11[i], X.D12[i], X.D121[i], X.D122[i], X.D291[i], CN.pib[i], CN.depenses[i], CN.population[i], CN.prix[i]]);
        }));
        return l;
      },
    });

    // Évolution annuelle en euros constants
    const zv = $("graphique-variation-ms");
    if (zv) {
      const an = A.slice(1);
      const valeurs = an.map((_, k) => 100 * (cst(S.D1[k + 1], k + 1) / cst(S.D1[k], k) - 1));
      G.colonnes(zv, {
        annees: an, valeurs, libelle: "Évolution en euros constants",
        formatValeur: fmtVar, formatAxe: (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(Math.abs(v)) + " %",
        couleurPositive: "--ms-1", couleurNegative: "--ms-3", noteAnnee,
        titreAccessible: "Évolution annuelle des rémunérations versées par les administrations publiques, en euros constants",
      });
      const baisses = an.filter((_, k) => valeurs[k] < 0);
      $("note-variation-ms").textContent = `Barres bleues : hausse ; barres ocre : baisse. La masse salariale publique a baissé en euros constants ${baisses.length} années sur ${an.length} depuis 1950 (${baisses.join(", ")}). Calcul : évolution des rémunérations totales des administrations publiques, corrigée de l'indice des prix à la consommation. Sources : ${CN.source} ; indice des prix à la consommation (Insee).`;
      const t2 = PLF.tableau({
        legende: "Évolution annuelle de la masse salariale publique en euros constants (%)",
        colonnes: [{ titre: "Année", cle: "a" }, { titre: "Évolution en euros constants", cle: "v", format: fmtVar }],
        lignes: an.map((a, k) => ({ a, v: valeurs[k] })),
      });
      PLF.blocDonnees($("donnees-variation-ms"), { table: t2 });
    }
  }

  /* ======================================================================
     Qui paie ? (par employeur) et coût moyen par emploi
     ====================================================================== */
  const EMPLOYEURS = [
    { id: "S13111", libelle: "État", couleur: "--ms-1" },
    { id: "S13112", libelle: "Organismes nationaux (ODAC)", couleur: "--ms-4" },
    { id: "S1313", libelle: "Administrations locales", couleur: "--ms-2" },
    { id: "S1314", libelle: "Sécurité sociale et hôpitaux", couleur: "--ms-3" },
  ];
  function sectionQuiPaie(M) {
    const zone = $("graphique-qui-paie");
    if (!zone) return;
    const { CN, iFin, AN } = contexte(M);
    const comp = [
      { op: "D11", libelle: "Salaires bruts", couleur: "--ms-1" },
      { op: "D121", libelle: "Cotisations sociales des employeurs", couleur: "--ms-2" },
      { op: "D122", libelle: "Cotisations imputées (retraites de l'État)", couleur: "--ms-4" },
      { op: "D291", libelle: "Impôts sur les salaires", couleur: "--ms-5" },
    ];
    G.barres(zone, {
      categories: EMPLOYEURS.map((e) => e.libelle),
      series: comp.map((c) => ({ id: c.op, libelle: c.libelle, couleur: c.couleur, valeurs: EMPLOYEURS.map((e) => CN.secteurs[e.id][c.op][iFin]) })),
      formatValeur: (v) => fmtMd(v, 1), formatAxe: fmtAxeMd, libelleValeur: "Montant", ligneTotal: "Coût total",
      titreAccessible: `Coût des rémunérations par employeur public en ${AN}, en milliards d'euros`,
    });
    legende($("legende-qui-paie"), comp);
    const d = CN.dont;
    const kd = d.annees.indexOf(AN);
    $("note-qui-paie").textContent = `Coût total = salaires bruts + cotisations des employeurs (effectives et imputées) + impôts sur les salaires. Comptes nationaux, ${AN} provisoire. ${kd >= 0 ? `Parmi les administrations locales, les collectivités locales versent ${fmtMd(d.collectivites[kd], 1)} de rémunérations ; parmi les administrations de sécurité sociale, les hôpitaux et autres organismes qui en dépendent (France Travail…) en versent ${fmtMd(d.hopitaux[kd], 1)} (DGAFP).` : ""} Sources : ${CN.source} ; ${M.etat.source}.`;
    const lignes = EMPLOYEURS.concat([{ id: "S13", libelle: "Ensemble des administrations publiques", _classe: "total" }]).map((e) => {
      const X = CN.secteurs[e.id];
      return { lib: e.libelle, d11: X.D11[iFin], d121: X.D121[iFin], d122: X.D122[iFin], d291: X.D291[iFin], d1: X.D1[iFin], cout: X.D1[iFin] + X.D291[iFin], part: (100 * X.D1[iFin]) / CN.secteurs.S13.D1[iFin], _classe: e._classe };
    });
    const f1 = (v) => nf(1).format(v);
    const t = PLF.tableau({
      legende: `Rémunérations par employeur public, ${AN} (milliards d'euros)`,
      colonnes: [
        { titre: "Employeur", cle: "lib", texte: true },
        { titre: "Salaires bruts", cle: "d11", format: f1 },
        { titre: "Cotisations effectives", cle: "d121", format: f1 },
        { titre: "Cotisations imputées", cle: "d122", format: f1 },
        { titre: "Rémunérations totales", cle: "d1", format: f1 },
        { titre: "Impôts sur les salaires", cle: "d291", format: f1 },
        { titre: "Coût total", cle: "cout", format: f1 },
        { titre: "Part des rémunérations", cle: "part", format: (v) => fmtPct(v, 1) },
      ],
      lignes,
    });
    PLF.blocDonnees($("donnees-qui-paie"), {
      table: t, csvNom: `remunerations-par-employeur-${AN}.csv`,
      csvEntetes: ["employeur", "salaires_bruts", "cotisations_effectives", "cotisations_imputees", "remunerations_totales", "impots_sur_salaires", "cout_total"],
      csvLignes: lignes.map((l) => [l.lib, l.d11, l.d121, l.d122, l.d1, l.d291, arr(l.cout, 3)]),
    });

    // Coût moyen par emploi en équivalent temps plein
    const ze = $("graphique-cout-etp");
    if (!ze) return;
    const { A, cst } = contexte(M);
    const debut = CN.etp.S13.findIndex((v) => v != null);
    const parEtp = (s, op) => A.map((_, i) => (CN.etp[s][i] == null || CN.secteurs[s][op][i] == null ? null : (cst(CN.secteurs[s][op][i], i) * 1e9) / (CN.etp[s][i] * 1e3) / 12)).slice(debut);
    const series = [
      { id: "S13", libelle: "Ensemble des administrations : coût total", libelleCourt: "Ensemble", couleur: "--ms-autre", valeurs: parEtp("S13", "D1"), epaisseur: 3.4 },
      { id: "S13-brut", libelle: "Ensemble : salaire brut seul", libelleCourt: "dont brut", couleur: "--ms-autre", valeurs: parEtp("S13", "D11"), tirets: true },
    ].concat(EMPLOYEURS.map((e) => ({ id: e.id, libelle: `${e.libelle} : coût total`, libelleCourt: e.libelle.replace(" (ODAC)", "").replace("Sécurité sociale et hôpitaux", "Sécu. et hôpitaux").replace("Organismes nationaux", "Org. nationaux").replace("Administrations locales", "Locales"), couleur: e.couleur, valeurs: parEtp(e.id, "D1") })));
    G.courbes(ze, {
      annees: A.slice(debut), series, formatAxe: fmtAxeEuro, formatValeur: fmtEuro, titreAxeY: `Euros de ${AN} par mois`, yMin: 0, hauteur: 380, noteAnnee: (a) => [noteAnnee_(CN, a), a === 2010 ? "Autonomie des universités (2009-2012) : une partie de leurs personnels, auparavant payés par l'État, est rémunérée par les universités (organismes nationaux)." : ""].filter(Boolean).join(" "),
      titreAccessible: "Coût mensuel moyen d'un emploi public en équivalent temps plein, en euros constants",
    });
    legende($("legende-cout-etp"), series.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: true, tirets: s.tirets })));
    const k06 = A.slice(debut).findIndex((_, k) => series[2].valeurs[k] != null);
    $("note-cout-etp").textContent = `Rémunérations (comptes nationaux) divisées par l'emploi en équivalent temps plein de chaque secteur (Insee, tableau 1.109), puis par 12 et converties en euros de ${AN} avec l'indice des prix à la consommation. Emploi par secteur disponible de ${A.slice(debut)[k06]} à ${A[A.length - 2]} seulement. Le coût inclut les cotisations des employeurs, dont les retraites des fonctionnaires de l'État, ce qui explique le niveau élevé pour l'État. Les écarts entre employeurs reflètent aussi les métiers (médecins, enseignants, agents d'exécution…). Sources : ${CN.source} ; ${CN.sourcePib}.`;
    const lignesEtp = A.slice(debut).map((a, k) => { const l = { a }; series.forEach((s) => (l[s.id] = s.valeurs[k])); return l; });
    const t2 = PLF.tableau({
      legende: `Coût mensuel moyen d'un emploi public en équivalent temps plein (euros de ${AN})`,
      colonnes: [{ titre: "Année", cle: "a" }].concat(series.map((s) => ({ titre: s.libelle, cle: s.id, format: (v) => (v == null ? "–" : fmtEuro(v)) }))),
      lignes: lignesEtp,
    });
    PLF.blocDonnees($("donnees-cout-etp"), {
      table: t2, csvNom: "cout-mensuel-moyen-par-emploi-public.csv",
      csvEntetes: ["annee"].concat(series.map((s) => s.id)),
      csvLignes: () => lignesEtp.map((l) => [l.a].concat(series.map((s) => arr(l[s.id], 0)))),
    });
  }
  const noteAnnee_ = (CN, a) => (CN.statut[String(a)] ? `Résultats ${CN.statut[String(a)]}s.` : "");

  /* ======================================================================
     L'État : titre 2 par nature et rémunérations par statut
     ====================================================================== */
  function sectionEtat(M) {
    const zone = $("graphique-etat");
    if (!zone) return;
    const E = M.etat;
    const { CN, A, prixRef } = contexte(M);
    const ann = E.annees;
    const fin = ann[ann.length - 1];
    const R = Object.fromEntries(E.rubriques.map((r) => [r.cle, r]));
    const sommeR = (cles) => ann.map((_, k) => cles.reduce((acc, c) => acc + (R[c] && R[c].valeurs[k] != null ? R[c].valeurs[k] : 0), 0));
    const groupes = [
      { id: "traitement", libelle: "Traitement indiciaire brut", couleur: "--ms-1", valeurs: sommeR(["traitement_brut"]) },
      { id: "primes", libelle: "Primes, indemnités et accessoires (NBI, résidence, supplément familial…)", couleur: "--ms-3", valeurs: sommeR(["nbi", "indemnite_residence", "supplement_familial", "majorations", "indemnites_indexees", "indemnites_non_indexees", "remunerations_non_ventilees"]) },
      { id: "retraites", libelle: "Cotisations retraite (compte « Pensions », RAFP…)", couleur: "--ms-4", valeurs: sommeR(["cas_pensions", "rafp", "cotisations_fspoeie", "cotisations_retraites_autres"]) },
      { id: "cotisations", libelle: "Autres cotisations sociales (maladie, famille, logement…)", couleur: "--ms-2", valeurs: sommeR(["cotisations_securite_sociale", "fnal_cnaf_csa", "cotisations_autres"]) },
      { id: "prestations", libelle: "Prestations sociales et allocations", couleur: "--ms-autre", valeurs: sommeR(["prestations"]) },
    ];
    // Contrôle : les groupes redonnent le total du titre 2
    ann.forEach((a, k) => {
      const s = groupes.reduce((acc, g) => acc + g.valeurs[k], 0);
      if (Math.abs(s - R.total_titre2.valeurs[k]) > 0.01) console.warn(`Titre 2 ${a} : écart ${s - R.total_titre2.valeurs[k]}`);
    });
    const prix = ann.map((a) => CN.prix[A.indexOf(a)]);
    const etat = { mesure: "courants" };
    const conv = (vals) => (etat.mesure === "constants" ? vals.map((v, k) => (v * prixRef) / prix[k]) : vals);
    const cfg = () => ({
      annees: ann, series: groupes.map((g) => ({ id: g.id, libelle: g.libelle, couleur: g.couleur, valeurs: conv(g.valeurs) })),
      empile: true, formatAxe: fmtAxeMd, formatValeur: (v) => fmtMd(v, 1), yMin: 0, hauteur: 380,
      titreAxeY: etat.mesure === "constants" ? `Milliards d'euros de ${A[A.length - 1]}` : "Milliards d'euros courants",
      noteAnnee: (a) => (a === fin ? "Exécution provisoire." : ""),
      titreAccessible: `Dépenses de personnel de l'État par nature, de ${ann[0]} à ${fin}`,
    });
    const g = G.courbes(zone, cfg());
    legende($("legende-etat"), groupes);
    document.querySelector("#figure-etat .figure__controles").addEventListener("change", (e) => {
      if (e.target.name === "etat-mesure") { etat.mesure = e.target.value; g.maj(cfg()); }
    });
    const kf = ann.length - 1;
    $("note-etat").textContent = `Budget général de l'État, dépenses de personnel (titre 2) en exécution, y compris l'enseignement privé sous contrat. En ${fin}, les contributions au compte d'affectation spéciale « Pensions » atteignent ${fmtMd(R.cas_pensions.valeurs[kf], 1)}, soit ${fmtPct((100 * R.cas_pensions.valeurs[kf]) / R.total_titre2.valeurs[kf], 0)} des dépenses de personnel. Les dépenses de personnel représentent ${fmtPct((100 * R.total_titre2.valeurs[kf]) / R.budget_etat.valeurs[kf], 1)} du budget de l'État. Source : ${E.source}.`;
    const lignes = ann.map((a, k) => {
      const l = { a, total: R.total_titre2.valeurs[k], pensions: R.pensions_versees.valeurs[k], part: (100 * R.total_titre2.valeurs[k]) / R.budget_etat.valeurs[k] };
      groupes.forEach((gr) => (l[gr.id] = gr.valeurs[k]));
      return l;
    });
    const f1 = (v) => nf(1).format(v);
    const t = PLF.tableau({
      legende: `Dépenses de personnel de l'État (titre 2) par nature, ${ann[0]}-${fin} (milliards d'euros courants)`,
      colonnes: [{ titre: "Année", cle: "a" }].concat(groupes.map((gr) => ({ titre: gr.libelle.replace(/ \(.*\)$/, ""), cle: gr.id, format: f1 })))
        .concat([{ titre: "Total titre 2", cle: "total", format: f1 }, { titre: "Part du budget de l'État", cle: "part", format: (v) => fmtPct(v, 1) }, { titre: "Pensions versées (pour mémoire)", cle: "pensions", format: f1 }]),
      lignes,
    });
    PLF.blocDonnees($("donnees-etat"), {
      table: t, csvNom: `depenses-personnel-etat-titre2-${ann[0]}-${fin}.csv`,
      csvEntetes: ["annee", "rubrique", "libelle", "groupe", "niveau", "milliards_euros"],
      csvLignes: () => { const l = []; ann.forEach((a, k) => E.rubriques.forEach((r) => { if (r.valeurs[k] != null) l.push([a, r.cle, r.libelle, r.groupe, r.niveau, r.valeurs[k]]); })); return l; },
    });
    // Détail ligne par ligne, quelques années
    const choix = [ann[0], 2015, 2020, ann[ann.length - 2], fin].filter((a, i, t) => ann.includes(a) && t.indexOf(a) === i);
    const retrait = (r) => (r.niveau >= 2 ? " ".repeat(r.niveau - 1) : "");
    const td = PLF.tableau({
      legende: `Détail des dépenses de personnel de l'État, ligne par ligne (milliards d'euros courants)`,
      colonnes: [{ titre: "Ligne de dépense", cle: "lib", texte: true }].concat(choix.map((a) => ({ titre: String(a), cle: "a" + a, format: (v) => (v == null ? "–" : nf(2).format(v)) })))
        .concat([{ titre: `Évolution ${choix[0]}-${fin}`, cle: "ev", format: (v) => (v == null ? "–" : fmtVar(v)) }]),
      lignes: E.rubriques.map((r) => {
        const l = { lib: retrait(r) + r.libelle, _classe: r.niveau <= 1 ? "total" : "" };
        choix.forEach((a) => (l["a" + a] = r.valeurs[ann.indexOf(a)]));
        const v0 = r.valeurs[ann.indexOf(choix[0])], v1 = r.valeurs[kf];
        l.ev = v0 && v1 != null && Math.abs(v0) > 0.05 ? 100 * (v1 / v0 - 1) : null;
        return l;
      }),
    });
    PLF.blocDonnees($("detail-etat"), { resume: "Afficher le détail ligne par ligne (traitement, primes, cotisations, prestations)", table: td });

    // Rémunérations principales par statut
    const zs = $("graphique-etat-statuts");
    if (!zs) return;
    const P = M.etat.statuts;
    const PP = Object.fromEntries(P.postes.map((p) => [p.cle, p]));
    const statuts = [
      { id: "fonctionnaires", libelle: "Fonctionnaires", couleur: "--ms-1" },
      { id: "enseignants_prive", libelle: "Enseignants du privé sous contrat", court: "Ens. du privé", couleur: "--ms-4" },
      { id: "militaires", libelle: "Militaires", couleur: "--ms-3" },
      { id: "contractuels", libelle: "Contractuels", couleur: "--ms-2" },
      { id: "ouvriers_etat", libelle: "Ouvriers d'État", couleur: "--ms-5" },
    ];
    const ser = statuts.map((s) => ({ id: s.id, libelle: s.libelle, libelleCourt: s.court, couleur: s.couleur, valeurs: PP[s.id].valeurs }));
    G.courbes(zs, {
      annees: P.annees, series: ser, formatAxe: fmtAxeMd, formatValeur: (v) => fmtMd(v, 2), titreAxeY: "Milliards d'euros courants", yMin: 0, hauteur: 340,
      ruptures: [{ annee: 2024, court: "contractuels en CDI ajoutés" }],
      noteAnnee: (a) => (a === 2024 ? "À partir de 2024, la ligne des contractuels inclut les contractuels en CDI (hors enseignement privé) : 2,8 milliards d'euros en 2024 selon la DGAFP." : a === 2012 ? "Depuis 2012, les stagiaires sont comptés avec les fonctionnaires." : ""),
      titreAccessible: "Rémunérations principales versées par l'État selon le statut des agents",
    });
    legende($("legende-etat-statuts"), ser.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: true })));
    $("note-etat-statuts").textContent = `Rémunérations principales (traitement ou salaire de base), hors primes et indemnités et hors charges connexes (supplément familial, heures supplémentaires…). Les stagiaires sont comptés avec les fonctionnaires depuis 2012. Rupture en 2024 : la DGAFP ajoute à la ligne des contractuels la rémunération des contractuels en CDI hors enseignement privé (0,9 milliard d'euros en 2019, 2,8 milliards en 2024). Source : ${E.source}.`;
    const lignesS = P.annees.map((a, k) => { const l = { a }; P.postes.forEach((p) => (l[p.cle] = p.valeurs[k])); return l; });
    const ts = PLF.tableau({
      legende: "Rémunérations d'activité de l'État par statut et par nature (milliards d'euros courants)",
      colonnes: [{ titre: "Année", cle: "a" }].concat(P.postes.filter((p) => p.niveau <= 2).map((p) => ({ titre: p.libelle, cle: p.cle, format: (v) => (v == null ? "–" : nf(2).format(v)) }))),
      lignes: lignesS,
    });
    PLF.blocDonnees($("donnees-etat-statuts"), {
      table: ts, csvNom: "remunerations-activite-etat-par-statut.csv",
      csvEntetes: ["annee"].concat(P.postes.map((p) => p.cle)),
      csvLignes: () => lignesS.map((l) => [l.a].concat(P.postes.map((p) => l[p.cle]))),
    });
  }

  /* ======================================================================
     Collectivités locales et hôpitaux
     ====================================================================== */
  function sectionCollectivitesHopitaux(M) {
    const C = M.collectivites;
    const zc = $("graphique-coll");
    if (zc) {
      const niveaux = [
        { id: "regions", libelle: "Régions et collectivités uniques", couleur: "--ms-1" },
        { id: "departements", libelle: "Départements", couleur: "--ms-2" },
        { id: "communes", libelle: "Communes", couleur: "--ms-3" },
        { id: "groupements", libelle: "Intercommunalités à fiscalité propre", couleur: "--ms-4" },
      ];
      const fin = C.annees[C.annees.length - 1];
      G.courbes(zc, {
        annees: C.annees, series: niveaux.map((n) => ({ id: n.id, libelle: n.libelle, couleur: n.couleur, valeurs: C[n.id] })),
        empile: true, formatAxe: fmtAxeMd, formatValeur: (v) => fmtMd(v, 1), titreAxeY: "Milliards d'euros courants", yMin: 0, hauteur: 360,
        noteAnnee: (a) => { const n = C.notes[String(a)]; return n ? n.charAt(0).toUpperCase() + n.slice(1) + "." : ""; },
        titreAccessible: `Dépenses de personnel des collectivités locales et de leurs groupements, de ${C.annees[0]} à ${fin}`,
      });
      legende($("legende-coll"), niveaux);
      const k = C.annees.length - 1;
      $("note-coll").textContent = `Dépenses de personnel, y compris les cotisations des employeurs (retraite CNRACL…), des régions, départements, communes et groupements à fiscalité propre (métropoles, communautés). En ${fin}, elles représentent ${fmtPct((100 * C.ensemble[k]) / C.depenses_totales[k], 1)} de leurs dépenses totales (${fmtPct((100 * C.ensemble[0]) / C.depenses_totales[0], 1)} en ${C.annees[0]}). Les changements de périmètre (collectivités uniques de Martinique et de Guyane en 2016, collectivité de Corse en 2018, Ville de Paris en 2019) déplacent des dépenses d'un niveau à l'autre sans changer le total. ${fin} : résultats provisoires. Source : ${C.source}.`;
      const lignes = C.annees.map((a, i) => ({ a, regions: C.regions[i], departements: C.departements[i], communes: C.communes[i], groupements: C.groupements[i], ensemble: C.ensemble[i], part: (100 * C.ensemble[i]) / C.depenses_totales[i], note: C.notes[String(a)] || "" }));
      const f1 = (v) => nf(2).format(v);
      const t = PLF.tableau({
        legende: "Dépenses de personnel des collectivités locales (milliards d'euros courants)",
        colonnes: [{ titre: "Année", cle: "a" }].concat(niveaux.map((n) => ({ titre: n.libelle, cle: n.id, format: f1 })))
          .concat([{ titre: "Ensemble", cle: "ensemble", format: f1 }, { titre: "Part des dépenses totales", cle: "part", format: (v) => fmtPct(v, 1) }, { titre: "Remarque", cle: "note", texte: true }]),
        lignes,
      });
      PLF.blocDonnees($("donnees-coll"), {
        table: t, csvNom: "depenses-personnel-collectivites-locales.csv",
        csvEntetes: ["annee", "regions", "departements", "communes", "groupements", "ensemble", "depenses_totales", "note"],
        csvLignes: C.annees.map((a, i) => [a, C.regions[i], C.departements[i], C.communes[i], C.groupements[i], C.ensemble[i], C.depenses_totales[i], C.notes[String(a)] || ""]),
      });
    }
    const H = M.hopitaux;
    const zh = $("graphique-hop");
    if (zh) {
      const postes = [
        { id: "remunerations_non_medical", libelle: "Rémunérations du personnel non médical", couleur: "--ms-1" },
        { id: "remunerations_medical", libelle: "Rémunérations des médecins (praticiens hospitaliers)", couleur: "--ms-3" },
        { id: "charges_sociales", libelle: "Cotisations sociales des employeurs", couleur: "--ms-2" },
        { id: "autres_charges", libelle: "Autres charges de personnel", couleur: "--ms-autre" },
        { id: "impots_taxes", libelle: "Impôts et taxes sur les salaires", couleur: "--ms-5" },
      ];
      const fin = H.annees[H.annees.length - 1];
      G.courbes(zh, {
        annees: H.annees, series: postes.map((p) => ({ id: p.id, libelle: p.libelle, couleur: p.couleur, valeurs: H[p.id] })),
        empile: true, formatAxe: fmtAxeMd, formatValeur: (v) => fmtMd(v, 1), titreAxeY: "Milliards d'euros courants", yMin: 0, hauteur: 360,
        noteAnnee: (a) => (H.notes[String(a)] ? "Résultats provisoires." : a === 2006 ? "Depuis 2006, les reports de charges ne sont plus comptés dans les autres charges." : ""),
        titreAccessible: `Charges de personnel des établissements publics de santé, de ${H.annees[0]} à ${fin}`,
      });
      legende($("legende-hop"), postes);
      const k = H.annees.length - 1;
      $("note-hop").textContent = `Établissements publics de santé (hôpitaux publics). Les charges de personnel représentent ${fmtPct((100 * H.ensemble[k]) / H.depenses_totales[k], 1)} de leurs dépenses totales en ${fin}. Les hôpitaux publics, qui ne sont pas soumis à la TVA, paient la taxe sur les salaires. ${fin} : résultats provisoires (comptes de résultat principaux). Source : ${H.source}.`;
      const lignes = H.annees.map((a, i) => { const l = { a, ensemble: H.ensemble[i], part: (100 * H.ensemble[i]) / H.depenses_totales[i] }; postes.forEach((p) => (l[p.id] = H[p.id][i])); return l; });
      const f1 = (v) => nf(2).format(v);
      const t = PLF.tableau({
        legende: "Charges de personnel des hôpitaux publics (milliards d'euros courants)",
        colonnes: [{ titre: "Année", cle: "a" }].concat(postes.map((p) => ({ titre: p.libelle, cle: p.id, format: f1 })))
          .concat([{ titre: "Ensemble", cle: "ensemble", format: f1 }, { titre: "Part des dépenses totales", cle: "part", format: (v) => fmtPct(v, 1) }]),
        lignes,
      });
      PLF.blocDonnees($("donnees-hop"), {
        table: t, csvNom: "charges-personnel-hopitaux-publics.csv",
        csvEntetes: ["annee"].concat(postes.map((p) => p.id)).concat(["ensemble", "depenses_totales"]),
        csvLignes: H.annees.map((a, i) => [a].concat(postes.map((p) => H[p.id][i])).concat([H.ensemble[i], H.depenses_totales[i]])),
      });
    }
  }

  /* ======================================================================
     Par fonction (COFOG)
     ====================================================================== */
  function sectionFonctions(M) {
    const F = M.fonctions;
    const zone = $("graphique-fonctions");
    if (!zone) return;
    const { CN, A, prixRef } = contexte(M);
    const k = F.annees.length - 1;
    const fin = F.annees[k];
    const tri = F.divisions.slice().sort((a, b) => b.valeurs[k] - a.valeurs[k]);
    G.barres(zone, {
      categories: tri.map((d) => d.court),
      series: [{ id: "d1", libelle: "Rémunérations", couleur: "--ms-1", valeurs: tri.map((d) => d.valeurs[k] / 1000) }],
      formatValeur: (v) => fmtMd(v, 1), formatAxe: fmtAxeMd, sansPart: true, libelleValeur: "Rémunérations", hauteurBarre: 26, ecart: 12,
      titreAccessible: `Rémunérations des administrations publiques par fonction en ${fin}, en milliards d'euros`,
    });
    const tot = F.total[k];
    $("note-fonctions").textContent = `Rémunération des salariés des administrations publiques classée selon la fonction (classification internationale COFOG). « Services généraux » : administration générale, finances publiques, affaires étrangères, recherche fondamentale… ; « Protection sociale » : notamment les agents des caisses de Sécurité sociale et des services sociaux. Total ${fin} : ${fmtMd(tot / 1000, 1)}. Source : ${F.source}.`;
    // Tableau : fonctions et sous-fonctions
    const prix = (a) => CN.prix[A.indexOf(a)];
    const a0 = F.annees[0];
    const lignes = [];
    tri.forEach((d) => {
      const ev = d.valeurs[0] ? 100 * ((d.valeurs[k] / prix(fin)) / (d.valeurs[0] / prix(a0)) - 1) : null;
      lignes.push({ lib: d.libelle, v0: d.valeurs[0] / 1000, v: d.valeurs[k] / 1000, part: (100 * d.valeurs[k]) / tot, ev, _classe: "total" });
      F.groupes.filter((g) => g.parent === d.code && g.valeurs[k]).sort((a, b) => b.valeurs[k] - a.valeurs[k]).forEach((g) => {
        const evg = g.valeurs[0] ? 100 * ((g.valeurs[k] / prix(fin)) / (g.valeurs[0] / prix(a0)) - 1) : null;
        lignes.push({ lib: " " + g.libelle, v0: g.valeurs[0] == null ? null : g.valeurs[0] / 1000, v: g.valeurs[k] / 1000, part: (100 * g.valeurs[k]) / tot, ev: evg });
      });
    });
    lignes.push({ lib: "Total", v0: F.total[0] / 1000, v: tot / 1000, part: 100, ev: 100 * ((tot / prix(fin)) / (F.total[0] / prix(a0)) - 1), _classe: "total" });
    const f2 = (v) => (v == null ? "–" : nf(2).format(v));
    const t = PLF.tableau({
      legende: `Rémunérations des administrations publiques par fonction et sous-fonction (milliards d'euros)`,
      colonnes: [
        { titre: "Fonction", cle: "lib", texte: true },
        { titre: String(a0), cle: "v0", format: f2 },
        { titre: String(fin), cle: "v", format: f2 },
        { titre: `Part en ${fin}`, cle: "part", format: (v) => fmtPct(v, 1) },
        { titre: `Évolution ${a0}-${fin} en euros constants`, cle: "ev", format: (v) => (v == null ? "–" : fmtVar(v)) },
      ],
      lignes,
    });
    PLF.blocDonnees($("donnees-fonctions"), {
      resume: "Afficher le détail par sous-fonction (tableau)", table: t, csvNom: "remunerations-par-fonction-cofog.csv",
      csvEntetes: ["annee", "code_cofog", "fonction", "millions_euros"],
      csvLignes: () => { const l = []; F.annees.forEach((a, i) => { l.push([a, "TOTAL", "Total", F.total[i]]); F.divisions.concat(F.groupes).forEach((d) => { if (d.valeurs[i] != null) l.push([a, d.code, d.libelle, d.valeurs[i]]); }); }); return l; },
    });

    // Évolution en euros constants
    const ze = $("graphique-fonctions-evol");
    if (!ze) return;
    const principales = [
      { code: "GF09", couleur: "--ms-1" }, { code: "GF07", couleur: "--ms-2" }, { code: "GF01", couleur: "--ms-3" },
      { code: "GF03", couleur: "--ms-4" }, { code: "GF10", couleur: "--ms-5" },
    ];
    const D = Object.fromEntries(F.divisions.map((d) => [d.code, d]));
    const cstF = (v, i) => (v == null ? null : (v / 1000) * prixRef / prix(F.annees[i]));
    const autres = F.annees.map((_, i) => F.divisions.filter((d) => !principales.some((p) => p.code === d.code)).reduce((a, d) => a + d.valeurs[i], 0));
    const series = principales.map((p) => ({ id: p.code, libelle: D[p.code].court, couleur: p.couleur, valeurs: D[p.code].valeurs.map(cstF) }))
      .concat([{ id: "autres", libelle: "Autres fonctions (défense, économie, culture…)", libelleCourt: "Autres", couleur: "--ms-autre", valeurs: autres.map(cstF), tirets: true }]);
    G.courbes(ze, {
      annees: F.annees, series, formatAxe: fmtAxeMd, formatValeur: (v) => fmtMd(v, 1), titreAxeY: `Milliards d'euros de ${A[A.length - 1]}`, yMin: 0, hauteur: 360,
      titreAccessible: "Rémunérations des administrations publiques par fonction, en euros constants, depuis 1995",
    });
    legende($("legende-fonctions-evol"), series.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: true, tirets: s.tirets })));
    $("note-fonctions-evol").textContent = `« Autres fonctions » : défense, affaires économiques, culture et loisirs, logement et équipements collectifs, environnement. Euros constants : indice des prix à la consommation de l'Insee. Les données Eurostat reprennent pour 1995-1998 et ${fin} une version des comptes légèrement différente de la dernière version de l'Insee (écart de 0,2 % à 1 % sur le total). Source : ${F.source}.`;
  }

  /* ======================================================================
     Salaires (DGAFP)
     ====================================================================== */
  function sectionSalaires(M) {
    const S = M.salaires;
    const P = S.populations;
    const zone = $("graphique-salaires");
    if (zone) {
      const pops = [
        { id: "ensemble", libelle: "Ensemble des agents" },
        { id: "fpe", libelle: "État" }, { id: "fpt", libelle: "Territoriale" }, { id: "fph", libelle: "Hospitalière" },
        { id: "fonctionnaires", libelle: "Fonctionnaires" }, { id: "fonctionnaires_a", libelle: "dont catégorie A" },
        { id: "fonctionnaires_b", libelle: "dont catégorie B" }, { id: "fonctionnaires_c", libelle: "dont catégorie C" },
        { id: "contractuels", libelle: "Contractuels" }, { id: "femmes", libelle: "Femmes" }, { id: "hommes", libelle: "Hommes" },
      ].filter((p) => P[p.id]);
      const ser = [
        { id: "net", libelle: "Salaire net", couleur: "--ms-1", valeurs: pops.map((p) => P[p.id].net_moyen) },
        { id: "prel", libelle: "Cotisations salariales et CSG-CRDS", couleur: "--ms-3", valeurs: pops.map((p) => P[p.id].brut_moyen - P[p.id].net_moyen) },
      ];
      G.barres(zone, {
        categories: pops.map((p) => p.libelle), series: ser, formatValeur: fmtEuro, formatAxe: fmtAxeEuro, libelleValeur: "Montant mensuel", ligneTotal: "Salaire brut",
        hauteurBarre: 28, ecart: 14, titreAccessible: `Salaire mensuel moyen brut et net dans la fonction publique en ${S.annee}, par population`,
      });
      legende($("legende-salaires"), ser);
      $("note-salaires").textContent = `Salaires mensuels moyens en équivalent temps plein (EQTP), y compris primes. Champ : France hors Mayotte, agents civils, y compris bénéficiaires de contrats aidés ; hors militaires, apprentis, assistants maternels et familiaux, internes et externes des hôpitaux. Source : ${S.source}.`;
      const lignes = pops.map((p) => ({ lib: p.libelle, brut: P[p.id].brut_moyen, net: P[p.id].net_moyen, med: P[p.id].net_median, d1: P[p.id].net_d1, d9: P[p.id].net_d9, part: P[p.id].part_eqtp_pct }));
      const t = PLF.tableau({
        legende: `Salaires mensuels dans la fonction publique en ${S.annee} (euros, en équivalent temps plein)`,
        colonnes: [
          { titre: "Population", cle: "lib", texte: true }, { titre: "Brut moyen", cle: "brut", format: fmtEuro }, { titre: "Net moyen", cle: "net", format: fmtEuro },
          { titre: "Net médian", cle: "med", format: fmtEuro }, { titre: "1er décile (net)", cle: "d1", format: fmtEuro }, { titre: "9e décile (net)", cle: "d9", format: fmtEuro },
          { titre: "Part des effectifs (EQTP)", cle: "part", format: (v) => fmtPct(v, 1) },
        ],
        lignes,
      });
      PLF.blocDonnees($("donnees-salaires"), {
        table: t, csvNom: `salaires-fonction-publique-${S.annee}.csv`,
        csvEntetes: ["population", "brut_moyen", "net_moyen", "net_median", "net_d1", "net_q1", "net_q3", "net_d9", "part_eqtp_pct"],
        csvLignes: Object.keys(P).map((k) => [k, P[k].brut_moyen, P[k].net_moyen, P[k].net_median, P[k].net_d1, P[k].net_q1, P[k].net_q3, P[k].net_d9, P[k].part_eqtp_pct]),
      });
    }

    // Du brut au net : cotisations et impôts (fonctionnaires)
    const zd = $("graphique-decomposition");
    if (zd) {
      const ordre = [
        { v: "fp", c: "ensemble", lib: "Ensemble" }, { v: "fpe", c: "ensemble", lib: "État" }, { v: "fpt", c: "ensemble", lib: "Territoriale" },
        { v: "fph", c: "ensemble", lib: "Hospitalière" }, { v: "fp", c: "A", lib: "Catégorie A" }, { v: "fp", c: "B", lib: "Catégorie B" }, { v: "fp", c: "C", lib: "Catégorie C" },
      ];
      const D = (o) => S.decomposition.find((d) => d.versant === o.v && d.categorie === o.c);
      const lignesD = ordre.map((o) => Object.assign({ lib: o.lib }, D(o)));
      const ser = [
        { id: "net", libelle: "Salaire net", couleur: "--ms-1", valeurs: lignesD.map((d) => d.salaire_net) },
        { id: "cot", libelle: "Cotisations salariales (retraite)", couleur: "--ms-3", valeurs: lignesD.map((d) => d.cotisations_salariales) },
        { id: "csg", libelle: "CSG et CRDS (impôts)", couleur: "--ms-5", valeurs: lignesD.map((d) => d.csg_crds) },
      ];
      G.barres(zd, {
        categories: lignesD.map((d) => d.lib), series: ser, formatValeur: fmtEuro, formatAxe: fmtAxeEuro, libelleValeur: "Montant mensuel", ligneTotal: "Salaire brut",
        hauteurBarre: 28, ecart: 14, titreAccessible: `Décomposition du salaire brut moyen des fonctionnaires en ${S.annee}`,
      });
      legende($("legende-decomposition"), ser);
      $("note-decomposition").textContent = `Fonctionnaires des trois versants, salaires mensuels moyens en équivalent temps plein. Cotisations salariales : retenue pour pension (11,10 % du traitement indiciaire) et retraite additionnelle sur les primes. CSG et CRDS : 9,7 % de 98,25 % du salaire brut. Source : ${S.source}.`;
      const t = PLF.tableau({
        legende: `Décomposition du salaire mensuel moyen des fonctionnaires, ${S.annee} (euros)`,
        colonnes: [
          { titre: "Fonctionnaires", cle: "lib", texte: true }, { titre: "Salaire brut", cle: "salaire_brut", format: fmtEuro },
          { titre: "dont traitement indiciaire", cle: "traitement_brut", format: fmtEuro }, { titre: "dont primes et indemnités", cle: "primes", format: fmtEuro },
          { titre: "Part des primes", cle: "pp", format: (v) => fmtPct(v, 1) },
          { titre: "Cotisations salariales", cle: "cotisations_salariales", format: fmtEuro }, { titre: "CSG et CRDS", cle: "csg_crds", format: fmtEuro },
          { titre: "Salaire net", cle: "salaire_net", format: fmtEuro },
        ],
        lignes: lignesD.map((d) => Object.assign({ pp: (100 * d.primes) / d.salaire_brut }, d)),
      });
      PLF.blocDonnees($("donnees-decomposition"), {
        table: t, csvNom: `decomposition-salaire-fonctionnaires-${S.annee}.csv`,
        csvEntetes: ["versant", "categorie", "salaire_brut", "traitement_brut", "primes", "cotisations_salariales", "csg_crds", "salaire_net"],
        csvLignes: S.decomposition.map((d) => [d.versant, d.categorie, d.salaire_brut, d.traitement_brut, d.primes, d.cotisations_salariales, d.csg_crds, d.salaire_net]),
      });
    }

    // Public et privé, euros constants
    const zp = $("graphique-public-prive");
    if (zp) {
      const PPv = S.publicPrive;
      const ser = [
        { id: "fpe", libelle: "Fonction publique de l'État", libelleCourt: "État", couleur: "--ms-1", valeurs: PPv.fpe },
        { id: "fph", libelle: "Fonction publique hospitalière", libelleCourt: "Hospitalière", couleur: "--ms-3", valeurs: PPv.fph },
        { id: "fonction_publique", libelle: "Ensemble de la fonction publique", libelleCourt: "Fonction publique", couleur: "--ms-autre", valeurs: PPv.fonction_publique, epaisseur: 3.4 },
        { id: "secteur_prive", libelle: "Secteur privé", libelleCourt: "Privé", couleur: "--ms-5", valeurs: PPv.secteur_prive, tirets: true, epaisseur: 3 },
        { id: "fpt", libelle: "Fonction publique territoriale", libelleCourt: "Territoriale", couleur: "--ms-2", valeurs: PPv.fpt },
      ];
      G.courbes(zp, {
        annees: PPv.annees, series: ser, formatAxe: fmtAxeEuro, formatValeur: fmtEuro, titreAxeY: `Euros de ${S.annee} par mois`, yMin: 2000, hauteur: 340,
        titreAccessible: "Salaire net mensuel moyen dans la fonction publique et dans le secteur privé, en euros constants",
      });
      legende($("legende-public-prive"), ser.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: true, tirets: s.tirets })));
      const k = PPv.annees.length - 1;
      const ev = (v) => 100 * (v[k] / v[0] - 1);
      $("note-public-prive").textContent = `Salaires nets moyens en équivalent temps plein, en euros constants de ${S.annee} (corrigés de l'inflation par la DGAFP). De ${PPv.annees[0]} à ${PPv.annees[k]} : ${fmtVar(ev(PPv.fonction_publique))} pour l'ensemble de la fonction publique (État ${fmtVar(ev(PPv.fpe))}, territoriale ${fmtVar(ev(PPv.fpt))}, hospitalière ${fmtVar(ev(PPv.fph))}), ${fmtVar(ev(PPv.secteur_prive))} dans le secteur privé. L'axe vertical commence à 2 000 €. Les métiers, les qualifications et les âges diffèrent entre public et privé. Source : ${S.sourceEvol}.`;
      const t = PLF.tableau({
        legende: `Salaire net mensuel moyen en euros constants de ${S.annee}`,
        colonnes: [{ titre: "Année", cle: "a" }].concat(ser.map((s) => ({ titre: s.libelle, cle: s.id, format: fmtEuro }))),
        lignes: PPv.annees.map((a, i) => { const l = { a }; ser.forEach((s) => (l[s.id] = s.valeurs[i])); return l; }),
      });
      PLF.blocDonnees($("donnees-public-prive"), {
        table: t, csvNom: "salaires-nets-public-prive-euros-constants.csv",
        csvEntetes: ["annee"].concat(ser.map((s) => s.id)),
        csvLignes: PPv.annees.map((a, i) => [a].concat(ser.map((s) => s.valeurs[i]))),
      });
    }

    // Déciles
    const zdc = $("graphique-deciles");
    if (zdc) {
      const D = S.deciles;
      const ser = [
        { id: "fpe", libelle: "Fonction publique de l'État", libelleCourt: "État", couleur: "--ms-1", valeurs: D.fpe },
        { id: "fph", libelle: "Fonction publique hospitalière", libelleCourt: "Hospitalière", couleur: "--ms-3", valeurs: D.fph },
        { id: "fonction_publique", libelle: "Ensemble de la fonction publique", libelleCourt: "Fonction publique", couleur: "--ms-autre", valeurs: D.fonction_publique, epaisseur: 3.4 },
        { id: "secteur_prive", libelle: "Secteur privé", libelleCourt: "Privé", couleur: "--ms-5", valeurs: D.secteur_prive, tirets: true, epaisseur: 3 },
        { id: "fpt", libelle: "Fonction publique territoriale", libelleCourt: "Territoriale", couleur: "--ms-2", valeurs: D.fpt },
      ];
      const nomsD = ["1er", "2e", "3e", "4e", "5e (médiane)", "6e", "7e", "8e", "9e"];
      G.courbes(zdc, {
        annees: [1, 2, 3, 4, 5, 6, 7, 8, 9], series: ser, formatX: (a) => "D" + a, etiquetteAnnee: (a) => `${nomsD[a - 1]} décile`,
        formatAxe: fmtAxeEuro, formatValeur: fmtEuro, titreAxeY: "Euros par mois", yMin: 1000, hauteur: 340,
        titreAccessible: `Déciles du salaire net mensuel dans la fonction publique et dans le secteur privé en ${S.annee}`,
      });
      legende($("legende-deciles"), ser.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: true, tirets: s.tirets })));
      const r = (v) => nf(1).format(v[8] / v[0]);
      $("note-deciles").textContent = `Rapport entre le 9e et le 1er décile : ${r(D.fonction_publique)} dans la fonction publique (État ${r(D.fpe)}, territoriale ${r(D.fpt)}, hospitalière ${r(D.fph)}), ${r(D.secteur_prive)} dans le secteur privé. Les bas salaires sont plus élevés dans le public, les hauts salaires plus élevés dans le privé. L'axe vertical commence à 1 000 €. Source : ${S.source}.`;
      const t = PLF.tableau({
        legende: `Déciles du salaire net mensuel en ${S.annee} (euros)`,
        colonnes: [{ titre: "Décile", cle: "d" }].concat(ser.map((s) => ({ titre: s.libelle, cle: s.id, format: fmtEuro }))),
        lignes: nomsD.map((n, i) => { const l = { d: "D" + (i + 1) }; ser.forEach((s) => (l[s.id] = s.valeurs[i])); return l; }),
      });
      PLF.blocDonnees($("donnees-deciles"), {
        table: t, csvNom: `deciles-salaires-public-prive-${S.annee}.csv`,
        csvEntetes: ["decile"].concat(ser.map((s) => s.id)),
        csvLignes: nomsD.map((n, i) => ["D" + (i + 1)].concat(ser.map((s) => s.valeurs[i]))),
      });
    }

    // Point d'indice
    const zpt = $("graphique-point");
    if (zpt) {
      const { CN, A, prixRef } = contexte(M);
      const PT = M.point;
      const prix = PT.annees.map((a) => CN.prix[A.indexOf(a)]);
      const ser = [
        { id: "constants", libelle: `En euros constants de ${A[A.length - 1]}`, libelleCourt: "Euros constants", couleur: "--ms-1", valeurs: PT.valeurs.map((v, i) => (v * prixRef) / prix[i]), epaisseur: 3.2 },
        { id: "courants", libelle: "En euros courants", libelleCourt: "Euros courants", couleur: "--ms-autre", valeurs: PT.valeurs, tirets: true },
      ];
      G.courbes(zpt, {
        annees: PT.annees, series: ser, formatAxe: fmtAxeEuro, formatValeur: fmtEuro, titreAxeY: "Euros par an (indice 100)", yMin: 0, hauteur: 320,
        noteAnnee: (a) => (a >= 2021 ? "Moyenne annuelle calculée à partir des dates de revalorisation publiées par la DGAFP." : ""),
        titreAccessible: "Valeur annuelle du point d'indice de la fonction publique, en euros courants et constants, depuis 1970",
      });
      legende($("legende-point"), ser.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: true, tirets: s.tirets })));
      $("note-point").textContent = `Valeur annuelle moyenne du traitement brut correspondant à l'indice majoré 100 (le traitement d'un agent est proportionnel à son indice). ${PT.annees[0]}-2020 : série longue de la DGAFP ; 2021-${PT.annees[PT.annees.length - 1]} : moyenne calculée à partir des revalorisations publiées (dernière hausse : 1er juillet 2023). Euros constants : indice des prix à la consommation de l'Insee. Sources : ${PT.source}.`;
      const t = PLF.tableau({
        legende: "Valeur annuelle moyenne du point d'indice (euros par an pour l'indice 100)",
        colonnes: [{ titre: "Année", cle: "a" }, { titre: "Euros courants", cle: "c", format: (v) => nf(2).format(v) }, { titre: `Euros de ${A[A.length - 1]}`, cle: "k", format: fmtEuro }],
        lignes: PT.annees.map((a, i) => ({ a, c: PT.valeurs[i], k: ser[0].valeurs[i] })),
      });
      PLF.blocDonnees($("donnees-point"), {
        table: t, csvNom: "point-indice-fonction-publique.csv",
        csvEntetes: ["annee", "valeur_annuelle_euros_courants", `valeur_euros_${A[A.length - 1]}`],
        csvLignes: PT.annees.map((a, i) => [a, PT.valeurs[i], arr(ser[0].valeurs[i], 2)]),
      });
    }
  }

  /* ======================================================================
     Comparaison européenne
     ====================================================================== */
  function sectionEurope(M) {
    const E = M.europe;
    const zone = $("graphique-europe");
    if (!zone) return;
    const k = E.annees.length - 1;
    const fin = E.annees[k];
    const moyennes = ["EU27_2020", "EA20"];
    const hors = ["IS", "NO", "CH"];
    const pays = E.pays.filter((p) => !hors.includes(p.code) && p.valeurs[k] != null).sort((a, b) => b.valeurs[k] - a.valeurs[k]);
    const nom = (p) => (p.code === "EU27_2020" ? "Union européenne (moyenne)" : p.code === "EA20" ? "Zone euro (moyenne)" : p.libelle);
    const ser = [
      { id: "fr", libelle: "France", couleur: "--ms-1", valeurs: pays.map((p) => (p.code === "FR" ? p.valeurs[k] : null)) },
      { id: "moy", libelle: "Moyennes européennes", couleur: "--ms-3", valeurs: pays.map((p) => (moyennes.includes(p.code) ? p.valeurs[k] : null)) },
      { id: "autres", libelle: "Autres pays de l'Union", couleur: "--ms-autre", valeurs: pays.map((p) => (p.code !== "FR" && !moyennes.includes(p.code) ? p.valeurs[k] : null)) },
    ];
    G.barres(zone, {
      categories: pays.map(nom), series: ser, formatValeur: (v) => fmtPct(v, 1), formatAxe: fmtAxePct, sansPart: true, libelleValeur: "Part du PIB",
      hauteurBarre: 17, ecart: 6, titreAccessible: `Rémunérations des administrations publiques en % du PIB, pays de l'Union européenne, ${fin}`,
    });
    legende($("legende-europe"), ser);
    $("note-europe").textContent = `Rémunération des salariés des administrations publiques (salaires bruts et cotisations des employeurs) en % du PIB. ${fin} : premières estimations transmises par les pays. Source : ${E.source}.`;
    const lignes = pays.map((p) => ({ lib: nom(p), v: p.valeurs[k], v0: p.valeurs[0] }));
    const t = PLF.tableau({
      legende: `Rémunérations des administrations publiques en % du PIB, ${E.annees[0]} et ${fin}`,
      colonnes: [{ titre: "Pays", cle: "lib", texte: true }, { titre: String(E.annees[0]), cle: "v0", format: (v) => (v == null ? "–" : fmtPct(v, 1)) }, { titre: String(fin), cle: "v", format: (v) => fmtPct(v, 1) }],
      lignes, triable: true,
    });
    PLF.blocDonnees($("donnees-europe"), {
      table: t, csvNom: "remuneration-publique-europe-pct-pib.csv",
      csvEntetes: ["annee", "code_pays", "pays", "remuneration_pct_pib"],
      csvLignes: () => { const l = []; E.pays.forEach((p) => E.annees.forEach((a, i) => { if (p.valeurs[i] != null) l.push([a, p.code, p.libelle, p.valeurs[i]]); })); return l; },
    });

    const ze = $("graphique-europe-evol");
    if (!ze) return;
    const P = Object.fromEntries(E.pays.map((p) => [p.code, p]));
    const choix = [
      { code: "FR", couleur: "--ms-1", epaisseur: 3.6 }, { code: "SE", couleur: "--ms-5" }, { code: "IT", couleur: "--ms-3" },
      { code: "ES", couleur: "--ms-4" }, { code: "DE", couleur: "--ms-2" }, { code: "EU27_2020", couleur: "--ms-autre", tirets: true },
    ];
    const series = choix.filter((c) => P[c.code]).map((c) => ({ id: c.code, libelle: nom(P[c.code]), libelleCourt: c.code === "EU27_2020" ? "UE" : P[c.code].libelle, couleur: c.couleur, valeurs: P[c.code].valeurs, epaisseur: c.epaisseur, tirets: c.tirets }));
    G.courbes(ze, {
      annees: E.annees, series, formatAxe: fmtAxePct, formatValeur: (v) => fmtPct(v, 1), titreAxeY: "% du PIB", yMin: 0, hauteur: 340,
      titreAccessible: "Rémunérations des administrations publiques en % du PIB depuis 1995 : France, Suède, Italie, Espagne, Allemagne et Union européenne",
    });
    legende($("legende-europe-evol"), series.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: true, tirets: s.tirets })));
    $("note-europe-evol").textContent = `La moyenne de l'Union européenne porte sur les 27 pays actuels sur toute la période. Source : ${E.source}.`;
  }

  /* ======================================================================
     Page d'accueil : encadré « Combien coûtent-ils ? »
     ====================================================================== */
  function accueil(M) {
    remplirCles(M.cles);
    barreCentEuros($("accueil-barre-cent-euros"), $("accueil-legende-cent-euros"), M, false);
    const zone = $("accueil-graphique-pib");
    if (zone) {
      const { CN, A, noteAnnee } = contexte(M);
      const S = CN.secteurs.S13;
      G.courbes(zone, {
        annees: A, series: [{ id: "pib", libelle: "Rémunérations publiques en % du PIB", libelleCourt: "% du PIB", couleur: "--ms-1", valeurs: S.D1.map((v, i) => (100 * v) / CN.pib[i]) }],
        formatAxe: fmtAxePct, formatValeur: (v) => fmtPct(v, 1), titreAxeY: "% du PIB", yMin: 0, hauteur: 260, etiquettesFin: false, noteAnnee,
        titreAccessible: "Rémunérations versées par les administrations publiques en % du PIB, depuis 1949",
      });
    }
  }

  function demarrer() {
    const page = document.body.dataset.page;
    if (page !== "masse-salariale" && page !== "accueil") return;
    let M;
    try { M = PLF.donnees("masse_salariale"); } catch (e) {
      const m = document.getElementById("contenu");
      if (m && page === "masse-salariale") m.insertAdjacentHTML("afterbegin", `<p class="conteneur erreur">${e.message}</p>`);
      return;
    }
    if (page === "accueil") { accueil(M); return; }
    remplirCles(M.cles);
    sectionCentEuros(M);
    sectionEvolution(M);
    sectionQuiPaie(M);
    sectionEtat(M);
    sectionCollectivitesHopitaux(M);
    sectionFonctions(M);
    sectionSalaires(M);
    sectionEurope(M);
  }
  PLF.masseSalariale = { composantesCentEuros, barreCentEuros };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", demarrer);
  else demarrer();
})();
