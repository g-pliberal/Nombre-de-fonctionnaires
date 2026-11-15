/* ==========================================================================
   Page « En Europe » (europe.html), à partir de donnees/site/europe.js :
   emploi dans les administrations publiques (OCDE, Panorama des administrations
   publiques), population (Eurostat), sous-secteurs (OCDE ; France : Insee).
   Seuls calculs : emplois pour 1 000 habitants et parts des sous-secteurs.
   ========================================================================== */
(function () {
  "use strict";
  const PLF = window.PLF;
  const G = PLF.graphiques;

  const nf = (dec) => new Intl.NumberFormat("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  const fmtPct = (v, dec = 1) => PLF.fmt.pourcent(v, dec);
  const fmtAxePct = (v) => (v === 0 ? "0" : new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(v) + " %");
  const fmtTaux = (v) => (v == null || isNaN(v) ? "n.d." : nf(0).format(Math.round(v)));
  const fmtMilliers = (v) => (v == null || isNaN(v) ? "–" : nf(0).format(Math.round(v)));
  const $ = (id) => document.getElementById(id);

  function remplirCles(cles) {
    document.querySelectorAll("[data-cle]").forEach((n) => {
      const v = cles[n.dataset.cle];
      if (v != null) n.textContent = v;
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

  /* Dernière valeur disponible d'un pays (au plus tard l'année de référence). */
  function derniere(E, p, cle) {
    for (let i = E.annees.indexOf(E.fin); i >= 0; i--) {
      if (p[cle][i] != null) return { v: p[cle][i], annee: E.annees[i], i };
    }
    return null;
  }
  const nomAvecAnnee = (E, p, d) => (d.annee !== E.fin ? `${p.libelle} (${d.annee})` : p.libelle);

  /* ---------- Classement (part de l'emploi total ou pour 1 000 habitants) ---------- */
  function sectionClassement(E, cfg) {
    const zone = $(`graphique-${cfg.id}`);
    if (!zone) return;
    const lignes = E.pays.map((p) => ({ p, d: derniere(E, p, cfg.cle) })).filter((x) => x.d).sort((a, b) => b.d.v - a.d.v);
    const cat = lignes.map((x) => nomAvecAnnee(E, x.p, x.d));
    const ser = [
      { id: "fr", libelle: "France", couleur: "--ms-1", valeurs: lignes.map((x) => (x.p.code === "FR" ? x.d.v : null)) },
      { id: "ue", libelle: "Autres pays de l'Union européenne", couleur: "--ms-autre", valeurs: lignes.map((x) => (x.p.code !== "FR" && x.p.ue ? x.d.v : null)) },
      { id: "hors", libelle: "Pays européens hors Union", couleur: "--ms-3", valeurs: lignes.map((x) => (!x.p.ue ? x.d.v : null)) },
    ];
    G.barres(zone, {
      categories: cat, series: ser, formatValeur: cfg.format, formatAxe: cfg.formatAxe, sansPart: true, libelleValeur: cfg.libelleValeur,
      hauteurBarre: 17, ecart: 6, titreAccessible: cfg.titre,
    });
    legende($(`legende-${cfg.id}`), ser);
    const t = PLF.tableau({
      legende: cfg.titre,
      colonnes: [
        { titre: "Pays", cle: "lib", texte: true },
        { titre: "Année", cle: "annee", format: (v) => String(v) },
        { titre: cfg.titreColonne, cle: "v", format: cfg.format },
        { titre: "Emploi public (milliers)", cle: "emp", format: fmtMilliers },
      ],
      lignes: lignes.map((x) => ({ lib: x.p.libelle, annee: x.d.annee, v: x.d.v, emp: x.p.emploi[x.d.i] })),
      triable: true,
    });
    PLF.blocDonnees($(`donnees-${cfg.id}`), {
      table: t, csvNom: cfg.csv,
      csvEntetes: ["annee", "code_pays", "pays", "emploi_apu_milliers", "part_emploi_total_pct", "emplois_pour_1000_habitants"],
      csvLignes: () => {
        const l = [];
        E.pays.forEach((p) => E.annees.forEach((a, i) => {
          if (p.emploi[i] != null || p.part[i] != null) l.push([a, p.code, p.libelle, p.emploi[i], p.part[i], p.taux[i]]);
        }));
        return l;
      },
    });
  }

  /* ---------- Évolution depuis 2007 ---------- */
  function sectionEvolution(E) {
    const zone = $("graphique-evolution");
    if (!zone) return;
    const P = Object.fromEntries(E.pays.map((p) => [p.code, p]));
    const choix = [
      { code: "FR", couleur: "--ms-1", epaisseur: 3.6 }, { code: "SE", couleur: "--ms-5" }, { code: "UK", couleur: "--ms-4" },
      { code: "ES", couleur: "--ms-3" }, { code: "IT", couleur: "--ms-autre", tirets: true }, { code: "DE", couleur: "--ms-2" },
    ];
    const series = choix.filter((c) => P[c.code]).map((c) => ({
      id: c.code, libelle: P[c.code].libelle, libelleCourt: P[c.code].libelle, couleur: c.couleur,
      valeurs: P[c.code].part, epaisseur: c.epaisseur, tirets: c.tirets,
    }));
    G.courbes(zone, {
      annees: E.annees, series, formatAxe: fmtAxePct, formatValeur: (v) => fmtPct(v, 1), titreAxeY: "% de l'emploi total", yMin: 0, hauteur: 340,
      titreAccessible: `Part des administrations publiques dans l'emploi total, ${E.annees[0]}-${E.fin} : France, Suède, Royaume-Uni, Espagne, Italie, Allemagne`,
    });
    legende($("legende-evolution"), series.map((s) => ({ libelle: s.libelle, couleur: s.couleur, trait: true, tirets: s.tirets })));
    const t = PLF.tableau({
      legende: "Part des administrations publiques dans l'emploi total (%)",
      colonnes: [{ titre: "Année", cle: "a", format: (v) => String(v) }].concat(series.map((s) => ({ titre: s.libelle, cle: s.id, format: (v) => (v == null ? "–" : fmtPct(v, 1)) }))),
      lignes: E.annees.map((a, i) => Object.assign({ a }, Object.fromEntries(series.map((s) => [s.id, s.valeurs[i]])))),
    });
    PLF.blocDonnees($("donnees-evolution"), {
      table: t, csvNom: "part-emploi-public-europe-evolution.csv",
      csvEntetes: ["annee"].concat(series.map((s) => s.id)),
      csvLignes: E.annees.map((a, i) => [a].concat(series.map((s) => s.valeurs[i]))),
    });
  }

  /* ---------- Qui emploie : État, collectivités, sécurité sociale ---------- */
  function sectionEchelons(E) {
    const zone = $("graphique-echelons");
    if (!zone) return;
    const S = E.sousSecteurs.slice().sort((a, b) => (b.S1313 || 0) / b.total - (a.S1313 || 0) / a.total);
    const defs = [
      { cle: "S1311", libelle: "Administration centrale (État et ses agences)", couleur: "--ms-1" },
      { cle: "S1312", libelle: "États fédérés", couleur: "--ms-4" },
      { cle: "S1313", libelle: "Administrations locales", couleur: "--ms-2" },
      { cle: "S1314", libelle: "Sécurité sociale", couleur: "--ms-3" },
    ].filter((d) => S.some((s) => s[d.cle] != null));
    const ser = defs.map((d) => ({ id: d.cle, libelle: d.libelle, couleur: d.couleur, valeurs: S.map((s) => s[d.cle] == null ? null : s[d.cle] * 1000) }));
    G.barres(zone, {
      categories: S.map((s) => `${s.libelle} (${s.annee})`), series: ser, pourcent: true, libelleValeur: "Emplois",
      titreAccessible: "Répartition de l'emploi public entre administration centrale, administrations locales et sécurité sociale",
    });
    legende($("legende-echelons"), ser);
    const t = PLF.tableau({
      legende: "Emploi des administrations publiques par sous-secteur (milliers de personnes)",
      colonnes: [{ titre: "Pays", cle: "lib", texte: true }, { titre: "Année", cle: "annee", format: (v) => String(v) },
        { titre: "Total", cle: "total", format: fmtMilliers }]
        .concat(defs.map((d) => ({ titre: d.libelle, cle: d.cle, format: (v) => (v == null ? "–" : `${fmtMilliers(v)}`) }))),
      lignes: S.map((s) => Object.assign({ lib: s.libelle }, s)),
    });
    PLF.blocDonnees($("donnees-echelons"), {
      table: t, csvNom: "emploi-public-europe-sous-secteurs.csv",
      csvEntetes: ["annee", "code_pays", "pays", "total_milliers"].concat(defs.map((d) => d.cle + "_milliers")).concat(["source"]),
      csvLignes: S.map((s) => [s.annee, s.code, s.libelle, s.total].concat(defs.map((d) => s[d.cle])).concat([s.source])),
    });
  }

  function demarrer() {
    if (document.body.dataset.page !== "europe") return;
    let E;
    try { E = PLF.donnees("europe"); } catch (e) {
      const m = $("contenu");
      if (m) m.insertAdjacentHTML("afterbegin", `<p class="conteneur erreur">${e.message}</p>`);
      return;
    }
    remplirCles(E.cles);
    sectionClassement(E, {
      id: "part", cle: "part", format: (v) => fmtPct(v, 1), formatAxe: fmtAxePct, libelleValeur: "Part de l'emploi total",
      titreColonne: "Part de l'emploi total", csv: "emploi-public-europe.csv",
      titre: `Emploi dans les administrations publiques en % de l'emploi total, pays européens, ${E.fin} ou dernière année disponible`,
    });
    sectionClassement(E, {
      id: "habitants", cle: "taux", format: fmtTaux, formatAxe: (v) => nf(0).format(v), libelleValeur: "Pour 1 000 habitants",
      titreColonne: "Emplois publics pour 1 000 habitants", csv: "emploi-public-europe.csv",
      titre: `Emplois dans les administrations publiques pour 1 000 habitants, pays européens, ${E.fin} ou dernière année disponible`,
    });
    sectionEvolution(E);
    sectionEchelons(E);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", demarrer);
  else demarrer();
})();
