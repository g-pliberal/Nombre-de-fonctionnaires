/* ==========================================================================
   Fiche d'un département (departements/<code>.html) : graphiques.
   Les chiffres et les tableaux sont déjà écrits dans la page par
   outils/construire_donnees.py ; ce script ne fait qu'ajouter les deux
   graphiques (taux comparé à la France, agents par versant).
   ========================================================================== */
(function () {
  "use strict";
  const PLF = window.PLF;
  const G = PLF.graphiques;

  function initialiser() {
    const code = document.body.dataset.dep;
    const zTaux = document.getElementById("graph-taux");
    const zVersants = document.getElementById("graph-versants");
    if (!code || !zTaux || !zVersants) return;
    let D;
    try {
      D = PLF.donnees("departements");
    } catch (e) {
      return; // les tableaux de la page suffisent
    }
    const d = D.departements[code];
    if (!d) return;
    const i0 = Math.max(0, D.annees.indexOf(D.debutHomogene));
    const annees = D.annees.slice(i0);
    const taux = (serie, pop) => serie.slice(i0).map((v, k) => (v == null || !pop[k + i0] ? null : (1000 * v) / pop[k + i0]));
    const periode = `${annees[0]} à ${annees[annees.length - 1]}`;

    G.courbes(zTaux, {
      annees,
      series: [
        { id: "dep", libelle: d.nom, couleur: "--accent", valeurs: taux(d.ensemble, d.population), epaisseur: 3.2 },
        { id: "fr", libelle: "France (hors Mayotte)", libelleCourt: "France", couleur: "--c-total", valeurs: taux(D.france.ensemble, D.france.population), tirets: true },
      ],
      formatAxe: (v) => PLF.fmt.nombre(v),
      formatValeur: PLF.fmt.decimal1,
      titreAxeY: "Agents pour 1 000 habitants",
      yMin: 0,
      hauteur: 320,
      titreAccessible: `Agents publics civils pour 1 000 habitants, ${d.nom} et France hors Mayotte, de ${periode}`,
    });
    G.courbes(zVersants, {
      annees,
      series: [
        { id: "fpe", libelle: "État", couleur: "--c-fpe", valeurs: d.fpe.slice(i0) },
        { id: "fpt", libelle: "Territoriale", couleur: "--c-fpt", valeurs: d.fpt.slice(i0) },
        { id: "fph", libelle: "Hospitalière", couleur: "--c-fph", valeurs: d.fph.slice(i0) },
      ],
      empile: true,
      formatAxe: (v) => PLF.fmt.nombre(v),
      formatValeur: PLF.fmt.nombre,
      titreAxeY: "Nombre d'agents",
      yMin: 0,
      hauteur: 320,
      titreAccessible: `Nombre d'agents publics civils par versant, ${d.nom}, de ${periode}`,
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialiser);
  else initialiser();
})();
