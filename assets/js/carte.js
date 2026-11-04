/* ==========================================================================
   Carte interactive des départements
   - Taux d'administration (agents pour 1 000 habitants) : carte choroplèthe
     à classes fixes pour toutes les années (comparables dans le temps).
   - Nombre d'agents : cercles proportionnels (règle cartographique : une
     quantité absolue ne se représente pas par des aplats de couleur).
   - Évolution du nombre d'agents depuis une année de référence : palette
     divergente centrée sur la stabilité.
   Accessibilité : navigation au clavier entre départements (flèches),
   annonces vocales, sélecteur de département, tableau complet triable.
   ========================================================================== */
(function () {
  "use strict";
  const PLF = window.PLF;
  const G = PLF.graphiques;
  const NS = "http://www.w3.org/2000/svg";

  // Palette séquentielle : safran pâle -> turquoise -> pétrole (lisible par les
  // daltoniens car la luminosité décroît régulièrement d'une classe à l'autre).
  const SEQUENTIELLE = ["#fdf6d8", "#dce5ac", "#97d6a4", "#50baa1", "#21968b", "#006e73", "#014855"];
  // Limites de classes : quantiles (sixièmes) + une classe pour les valeurs extrêmes (4 % les plus élevées).
  const QUANTILES = [1 / 6, 2 / 6, 3 / 6, 4 / 6, 5 / 6, 0.96];
  // Palette divergente : ocre (baisse) / neutre / turquoise-pétrole (hausse).
  const DIVERGENTE = ["#845a0f", "#b48c2b", "#dbc276", "#f3f2e9", "#91d4c6", "#3d9e98", "#00626a"];
  const SEUILS_EVOLUTION = [-10, -5, -1, 1, 5, 10];

  const LIBELLES_VERSANT = {
    ensemble: "ensemble des trois versants",
    fpe: "fonction publique de l'État",
    fpt: "fonction publique territoriale",
    fph: "fonction publique hospitalière",
  };
  const INDICATEURS = {
    taux: { titre: "Agents publics civils pour 1 000 habitants", court: "pour 1 000 hab." },
    effectif: { titre: "Nombre d'agents publics civils", court: "agents" },
    evolution: { titre: "Évolution du nombre d'agents civils", court: "%" },
  };

  function el(nom, attrs, parent) {
    const n = document.createElementNS(NS, nom);
    if (attrs) for (const k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function quantile(trie, q) {
    if (!trie.length) return null;
    const pos = (trie.length - 1) * q;
    const b = Math.floor(pos), r = pos - b;
    return trie[b + 1] !== undefined ? trie[b] + r * (trie[b + 1] - trie[b]) : trie[b];
  }
  // Seuils « ronds » issus des quantiles de toutes les années réunies.
  function seuilsRonds(valeurs, quantiles) {
    const trie = valeurs.filter((v) => v != null && isFinite(v)).sort((a, b) => a - b);
    const med = quantile(trie, 0.5) || 1;
    const pas = med >= 40 ? 5 : med >= 12 ? 2 : med >= 4 ? 1 : 0.5;
    const seuils = [];
    quantiles.forEach((q) => {
      const s = Math.round(quantile(trie, q) / pas) * pas;
      if (!seuils.length || s > seuils[seuils.length - 1]) seuils.push(s);
    });
    return seuils;
  }
  function classe(v, seuils) {
    let i = 0;
    while (i < seuils.length && v >= seuils[i]) i++;
    return i;
  }

  function initialiser() {
    const racine = document.getElementById("carte-app");
    if (!racine) return;
    let geo, D;
    try {
      geo = PLF.donnees("fond_de_carte");
      D = PLF.donnees("departements");
    } catch (e) {
      racine.innerHTML = `<p class="erreur">${e.message}</p>`;
      return;
    }
    const annees = D.annees;
    const ordreCode = (c) => (c === "2A" ? 20.1 : c === "2B" ? 20.2 : Number(c));
    const codes = Object.keys(geo.departements).filter((c) => D.departements[c]).sort((a, b) => ordreCode(a) - ordreCode(b));
    const nomDe = (c) => D.departements[c].nom || geo.departements[c].nom;

    /* ---------- État (mémorisé dans l'adresse pour pouvoir partager une vue) ---------- */
    const iHomogene = Math.max(0, annees.indexOf(D.debutHomogene));
    const etat = {
      indicateur: "taux",
      versant: "ensemble",
      i: annees.length - 1,
      ref: iHomogene,
      selection: null,
      numeros: false,
      anciennes: false, // années avant la période homogène (ancienne méthode)
    };
    const premierIndice = () => (etat.anciennes ? 0 : iHomogene);
    function lireAdresse() {
      const p = new URLSearchParams(location.hash.slice(1));
      if (INDICATEURS[p.get("indicateur")]) etat.indicateur = p.get("indicateur");
      if (LIBELLES_VERSANT[p.get("versant")]) etat.versant = p.get("versant");
      const a = annees.indexOf(Number(p.get("annee")));
      if (a >= 0) etat.i = a;
      const r = annees.indexOf(Number(p.get("depuis")));
      if (r >= 0) etat.ref = r;
      if (D.departements[p.get("dep")]) etat.selection = p.get("dep");
      if (p.get("anciennes") === "1" || etat.i < iHomogene || etat.ref < iHomogene) etat.anciennes = true;
    }
    function ecrireAdresse() {
      const p = new URLSearchParams();
      p.set("indicateur", etat.indicateur);
      p.set("versant", etat.versant);
      p.set("annee", annees[etat.i]);
      if (etat.indicateur === "evolution") p.set("depuis", annees[etat.ref]);
      if (etat.selection) p.set("dep", etat.selection);
      if (etat.anciennes) p.set("anciennes", "1");
      history.replaceState(null, "", "#" + p.toString());
    }
    lireAdresse();
    if (etat.ref >= etat.i) etat.ref = premierIndice();

    /* ---------- Valeurs ---------- */
    function effectif(code, v, i) {
      const s = (code === "FR" ? D.france : D.departements[code])[v];
      return s ? s[i] : null;
    }
    function population(code, i) {
      const s = (code === "FR" ? D.france : D.departements[code]).population;
      return s ? s[i] : null;
    }
    function taux(code, v, i) {
      const e = effectif(code, v, i), p = population(code, i);
      return e == null || !p ? null : (1000 * e) / p;
    }
    function evolution(code, v, i, ref) {
      const a = effectif(code, v, ref), b = effectif(code, v, i);
      return a == null || b == null || !a ? null : 100 * (b / a - 1);
    }
    function valeur(code, i = etat.i) {
      if (etat.indicateur === "taux") return taux(code, etat.versant, i);
      if (etat.indicateur === "effectif") return effectif(code, etat.versant, i);
      return evolution(code, etat.versant, i, etat.ref);
    }
    function formatValeur(v) {
      if (v == null) return "donnée non disponible";
      if (etat.indicateur === "taux") return PLF.fmt.decimal1(v);
      if (etat.indicateur === "effectif") return PLF.fmt.nombre(v);
      return PLF.fmt.variation(v, 1);
    }
    function phraseValeur(v) {
      if (v == null) return "donnée non disponible";
      if (etat.indicateur === "taux") return `${PLF.fmt.decimal1(v)} agents pour 1 000 habitants`;
      if (etat.indicateur === "effectif") return `${PLF.fmt.nombre(v)} agents`;
      return `${PLF.fmt.variation(v, 1)} depuis ${annees[etat.ref]}`;
    }

    // Seuils fixes par versant (toutes années confondues).
    const seuilsTaux = {};
    Object.keys(LIBELLES_VERSANT).forEach((v) => {
      const toutes = [];
      // Classes calculées sur la période homogène, puis appliquées à toutes les années.
      codes.forEach((c) => annees.forEach((_, i) => { if (i >= iHomogene) toutes.push(taux(c, v, i)); }));
      seuilsTaux[v] = seuilsRonds(toutes, QUANTILES);
    });
    const maxEffectif = {};
    Object.keys(LIBELLES_VERSANT).forEach((v) => {
      let m = 0;
      codes.forEach((c) => annees.forEach((_, i) => { const e = effectif(c, v, i); if (e > m) m = e; }));
      maxEffectif[v] = m;
    });

    function paletteTaux() {
      const n = seuilsTaux[etat.versant].length + 1;
      return n >= SEQUENTIELLE.length ? SEQUENTIELLE : SEQUENTIELLE.slice(SEQUENTIELLE.length - n);
    }
    function couleurDe(v) {
      if (v == null) return null;
      if (etat.indicateur === "taux") return paletteTaux()[classe(v, seuilsTaux[etat.versant])];
      if (etat.indicateur === "evolution") return DIVERGENTE[classe(v, SEUILS_EVOLUTION)];
      return null;
    }

    /* ---------- Construction du DOM ---------- */
    racine.innerHTML = "";
    const formulaire = document.createElement("form");
    formulaire.className = "carte-controles";
    formulaire.setAttribute("aria-label", "Réglages de la carte");
    formulaire.addEventListener("submit", (e) => e.preventDefault());
    formulaire.innerHTML = `
      <fieldset>
        <legend>Que voulez-vous voir ?</legend>
        <div class="choix" role="radiogroup">
          <label><input type="radio" name="indicateur" value="taux">Agents pour 1&nbsp;000 habitants</label>
          <label><input type="radio" name="indicateur" value="effectif">Nombre d'agents</label>
          <label><input type="radio" name="indicateur" value="evolution">Évolution</label>
        </div>
      </fieldset>
      <fieldset>
        <legend>Quelle fonction publique ?</legend>
        <div class="choix">
          <label><input type="radio" name="versant" value="ensemble">Les trois</label>
          <label><input type="radio" name="versant" value="fpe"><span class="pastille" style="background:var(--c-fpe)"></span>État</label>
          <label><input type="radio" name="versant" value="fpt"><span class="pastille" style="background:var(--c-fpt)"></span>Territoriale</label>
          <label><input type="radio" name="versant" value="fph"><span class="pastille" style="background:var(--c-fph)"></span>Hospitalière</label>
        </div>
      </fieldset>
      <div class="curseur-annee">
        <label class="etiquette" for="carte-annee">Année (au 31 décembre)</label>
        <div class="curseur-annee__ligne">
          <span class="curseur-annee__valeur" aria-hidden="true" id="carte-annee-affichee"></span>
          <button type="button" class="bouton bouton--secondaire bouton-rond" data-pas="-1" aria-label="Année précédente"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m15 18-6-6 6-6"/></svg></button>
          <input type="range" id="carte-annee" min="${iHomogene}" max="${annees.length - 1}" step="1">
          <button type="button" class="bouton bouton--secondaire bouton-rond" data-pas="1" aria-label="Année suivante"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m9 18 6-6-6-6"/></svg></button>
          <button type="button" class="bouton" id="carte-lecture" aria-pressed="false"><svg aria-hidden="true" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg><span>Animer</span></button>
        </div>
        <p class="figure__note" id="carte-plage" style="margin-top:.35rem"></p>
        <label style="display:flex;align-items:center;gap:.5rem;font-weight:600;min-height:44px;margin:0"><input type="checkbox" id="carte-anciennes" style="width:1.2rem;height:1.2rem"> Afficher aussi ${annees[0]}-${annees[iHomogene - 1]} (ancienne méthode, métropole seulement)</label>
        <div class="encadre encadre--attention" id="carte-avertissement" hidden style="margin:.5rem 0 0"></div>
      </div>
      <div class="selecteur-dep" id="carte-ref-bloc" hidden>
        <div>
          <label for="carte-ref">Évolution depuis l'année</label>
          <select id="carte-ref"></select>
        </div>
      </div>
      <div class="selecteur-dep">
        <div>
          <label for="carte-dep">Aller à un département</label>
          <select id="carte-dep"><option value="">— Choisir —</option></select>
        </div>
        <label style="display:flex;align-items:center;gap:.5rem;font-weight:600;min-height:44px;margin:0"><input type="checkbox" id="carte-numeros" style="width:1.2rem;height:1.2rem"> Numéros des départements</label>
      </div>`;
    racine.appendChild(formulaire);

    const zone = document.createElement("div");
    zone.className = "carte-zone";
    racine.appendChild(zone);

    const panneauCarte = document.createElement("div");
    panneauCarte.className = "carte-panneau";
    panneauCarte.style.position = "relative";
    zone.appendChild(panneauCarte);
    const titre = document.createElement("h2");
    titre.className = "carte-titre";
    titre.id = "carte-titre";
    panneauCarte.appendChild(titre);

    const cadres = document.createElement("div");
    cadres.className = "carte-cadres";
    cadres.tabIndex = 0;
    cadres.setAttribute("role", "group");
    cadres.setAttribute("aria-roledescription", "carte interactive");
    cadres.setAttribute("aria-label", "Carte des départements. Utilisez les flèches pour passer d'un département à son voisin, Entrée pour afficher sa fiche, Échap pour désélectionner. Les mêmes données figurent dans le tableau sous la carte.");
    panneauCarte.appendChild(cadres);

    const encarts = document.createElement("div");
    encarts.className = "carte-encarts";
    cadres.appendChild(encarts);
    const metroBloc = document.createElement("div");
    cadres.appendChild(metroBloc);

    const mention = document.createElement("p");
    mention.className = "carte-mention";
    panneauCarte.appendChild(mention);

    const ib = document.createElement("div");
    ib.className = "infobulle";
    ib.hidden = true;
    ib.setAttribute("aria-hidden", "true");
    panneauCarte.appendChild(ib);

    const lateral = document.createElement("section");
    lateral.className = "carte-panneau";
    lateral.setAttribute("aria-label", "Légende et fiche du département");
    lateral.innerHTML = `<p class="legende-titre" id="legende-titre"></p><ul class="legende-carte" id="legende-carte"></ul><div id="legende-cercles"></div>
      <div class="fiche-dep" id="fiche-dep"></div>
      <div class="palmares" id="palmares"></div>`;
    zone.appendChild(lateral);

    // Motif hachuré « données non disponibles » (défini une fois, partagé).
    const defs = el("svg", { width: 0, height: 0, "aria-hidden": "true", style: "position:absolute" }, document.body);
    const pattern = el("pattern", { id: "hachures-sans-donnee", patternUnits: "userSpaceOnUse", width: 6, height: 6, patternTransform: "rotate(45)" }, el("defs", {}, defs));
    el("rect", { width: 6, height: 6, fill: "var(--sans-donnee)" }, pattern);
    el("line", { x1: 0, y1: 0, x2: 0, y2: 6, stroke: "var(--texte-doux)", "stroke-width": 1.4, "stroke-opacity": 0.6 }, pattern);

    /* ---------- Cadres SVG ---------- */
    const chemins = {}; // code -> [path, ...] (métropole/encart + zoom)
    const svgs = {};
    const groupesCercles = {};
    const groupesEtiquettes = {};
    const ordreEncarts = ["idf", "971", "972", "973", "974", "976"];

    function creerCadre(cle, parent, estMetro) {
      const c = geo.cadres[cle];
      const fig = document.createElement(estMetro ? "div" : "figure");
      if (!estMetro) {
        fig.className = "encart";
        const cap = document.createElement("figcaption");
        cap.textContent = c.nom;
        fig.appendChild(cap);
      }
      const svg = el("svg", {
        viewBox: `0 0 ${c.largeur} ${c.hauteur}`,
        class: "cadre-svg" + (estMetro ? " cadre-svg--metro" : ""),
        "aria-hidden": "true",
        focusable: "false",
        preserveAspectRatio: "xMidYMid meet",
      });
      // Les traits gardent la même épaisseur à l'écran (vector-effect) ; les
      // textes sont remis à une taille constante en pixels par ajusterTextes().
      svg._textes = [];
      const fond = el("g", {}, svg);
      c.contexte.forEach((p) => el("path", { d: p.d, class: p.departement ? "dep-contexte" : "pays-voisin" }, fond));
      if (estMetro) {
        c.reperes.forEach((r) => {
          const t = el("text", { x: r.x, y: r.y, "text-anchor": "middle", class: r.type === "mer" ? "repere-mer" : "repere-pays" }, fond);
          t.textContent = r.texte;
          svg._textes.push({ n: t, px: r.type === "mer" ? 13 : 10 });
        });
      }
      const gDeps = el("g", {}, svg);
      codes.forEach((code) => {
        const g = geo.departements[code];
        const forme = cle === "idf" ? g.zoom : g.cadre === cle ? g : null;
        if (!forme) return;
        const p = el("path", { d: forme.d, class: "dep", "data-code": code }, gDeps);
        p._pt = forme.pt;
        p._cadre = cle;
        (chemins[code] = chemins[code] || []).push(p);
      });
      if (c.limites_regions) el("path", { d: c.limites_regions, class: "limites-regions" }, svg);
      if (c.rappel_zoom_idf) {
        const [x, y, w, h] = c.rappel_zoom_idf;
        el("rect", { x, y, width: w, height: h, class: "rappel-zoom" }, svg);
      }
      groupesCercles[cle] = el("g", {}, svg);
      groupesEtiquettes[cle] = el("g", {}, svg);
      // Échelle graphique
      const e = el("g", { class: "echelle" }, svg);
      const x0 = c.largeur * 0.05, y0 = c.hauteur * (estMetro ? 0.955 : 0.93);
      el("line", { x1: x0, x2: x0 + c.echelle_km, y1: y0, y2: y0 }, e);
      const tiques = [x0, x0 + c.echelle_km].map((xx) => el("line", { x1: xx, x2: xx, y1: y0, y2: y0 }, e));
      const te = el("text", { x: x0, y: y0 }, e);
      te.textContent = `${c.echelle_km} km`;
      svg._echelle = { y0, tiques, te };
      fig.appendChild(svg);
      parent.appendChild(fig);
      svgs[cle] = svg;
    }
    ordreEncarts.forEach((cle) => creerCadre(cle, encarts, false));
    creerCadre("metro", metroBloc, true);

    // Sélecteurs
    const selDep = formulaire.querySelector("#carte-dep");
    codes.slice().sort((a, b) => nomDe(a).localeCompare(nomDe(b), "fr")).forEach((c) => {
      const o = document.createElement("option");
      o.value = c;
      o.textContent = `${nomDe(c)} (${c})`;
      selDep.appendChild(o);
    });
    const selRef = formulaire.querySelector("#carte-ref");
    annees.forEach((a, i) => {
      const o = document.createElement("option");
      o.value = i;
      o.textContent = a;
      selRef.appendChild(o);
    });
    const curseur = formulaire.querySelector("#carte-annee");
    const anneeAffichee = formulaire.querySelector("#carte-annee-affichee");
    const plage = formulaire.querySelector("#carte-plage");
    const majPlage = () => {
      plage.textContent = etat.anciennes
        ? `Données de ${annees[0]} à ${annees[annees.length - 1]}. Avant ${D.debutHomogene}, ancienne méthode statistique et outre-mer non détaillé : comparez avec prudence.`
        : `Période homogène : ${D.debutHomogene} à ${annees[annees.length - 1]} (même source statistique, Siasp).`;
    };

    /* ---------- Tableau ---------- */
    const sectionTableau = document.getElementById("carte-tableau");
    let table;
    function lignesTableau() {
      const i = etat.i;
      const vals = codes.map((c) => ({ c, v: valeur(c) }));
      const rangs = rangsDe(vals);
      return codes.map((c) => ({
        nom: `${nomDe(c)} (${c})`,
        code: c,
        ordre: ordreCode(c),
        population: population(c, i),
        effectif: effectif(c, etat.versant, i),
        taux: taux(c, etat.versant, i),
        evol: evolution(c, etat.versant, i, etat.ref),
        rang: rangs[c],
      }));
    }
    function rangsDe(vals) {
      const tries = vals.filter((x) => x.v != null).sort((a, b) => b.v - a.v);
      const r = {};
      tries.forEach((x, k) => { r[x.c] = k + 1; });
      return r;
    }
    function construireTableau() {
      if (!sectionTableau) return;
      sectionTableau.innerHTML = "";
      const recherche = document.createElement("div");
      recherche.className = "recherche";
      recherche.innerHTML = `<div><label for="filtre-dep">Filtrer les départements</label><input type="search" id="filtre-dep" placeholder="Nom ou numéro, ex. : Gironde, 33" autocomplete="off"></div><button type="button" class="bouton bouton--secondaire" id="export-carte"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v12m0 0-5-5m5 5 5-5M4 21h16"/></svg>Télécharger le tableau (CSV)</button>`;
      sectionTableau.appendChild(recherche);
      table = PLF.tableau({
        legende: "",
        triable: true,
        colonnes: [
          { titre: "Département", cle: "nom", texte: true, cleTri: "ordre" },
          { titre: "Population", cle: "population", format: PLF.fmt.nombre },
          { titre: "Agents", cle: "effectif", format: PLF.fmt.nombre },
          { titre: "Pour 1 000 hab.", cle: "taux", format: PLF.fmt.decimal1 },
          { titre: "Rang", cle: "rang", format: (v) => (v == null ? "–" : v) },
          { titre: "Évolution", cle: "evol", format: (v) => PLF.fmt.variation(v, 1) },
        ],
        lignes: lignesTableau(),
      });
      sectionTableau.appendChild(PLF.enveloppe(table, true));
      const filtre = recherche.querySelector("#filtre-dep");
      filtre.addEventListener("input", () => appliquerFiltre(filtre.value));
      recherche.querySelector("#export-carte").addEventListener("click", () => {
        const l = lignesTableau();
        PLF.csv(`fonction-publique-departements-${etat.versant}-${annees[etat.i]}.csv`,
          ["code", "departement", "annee", "versant", "population", "agents", "agents_pour_1000_hab", "evolution_agents_pct_depuis_" + annees[etat.ref]],
          l.map((r) => [r.code, nomDe(r.code), annees[etat.i], etat.versant, r.population, r.effectif, r.taux == null ? null : Math.round(r.taux * 10) / 10, r.evol == null ? null : Math.round(r.evol * 10) / 10]));
      });
    }
    function appliquerFiltre(texte) {
      const t = texte.trim().toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
      Array.from(table.tBodies[0].rows).forEach((r) => {
        const s = r.cells[0].textContent.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
        r.hidden = t && !s.includes(t);
      });
    }
    function majTableau() {
      if (!table) return;
      table.caption.textContent = `Fonction publique (${LIBELLES_VERSANT[etat.versant]}) par département, au 31 décembre ${annees[etat.i]}. Rang selon l'indicateur affiché sur la carte ; évolution du nombre d'agents depuis ${annees[etat.ref]}.`;
      PLF.majTableau(table, lignesTableau());
      const f = document.getElementById("filtre-dep");
      if (f && f.value) appliquerFiltre(f.value);
    }

    /* ---------- Rendu ---------- */
    function rendu() {
      const i = etat.i;
      const vals = {};
      codes.forEach((c) => (vals[c] = valeur(c)));
      const modeCercles = etat.indicateur === "effectif";

      // Aplats
      codes.forEach((c) => {
        const col = modeCercles ? null : couleurDe(vals[c]);
        (chemins[c] || []).forEach((p) => {
          p.classList.toggle("sans-donnee", !modeCercles && vals[c] == null);
          p.style.fill = modeCercles ? "var(--surface-2)" : col || "";
          p.classList.toggle("selection", c === etat.selection);
        });
      });

      // Cercles proportionnels (même échelle en pixels dans tous les cadres)
      Object.values(groupesCercles).forEach((g) => (g.textContent = ""));
      if (modeCercles) {
        const metroPx = svgs.metro.getBoundingClientRect().width || 800;
        const rMaxPx = Math.max(16, Math.min(34, metroPx * 0.042));
        const vmax = maxEffectif[etat.versant] || 1;
        const tries = codes.filter((c) => vals[c] != null).sort((a, b) => vals[b] - vals[a]);
        tries.forEach((c) => {
          (chemins[c] || []).forEach((p) => {
            const svg = svgs[p._cadre];
            const largeurPx = svg.getBoundingClientRect().width || 150;
            const unitesParPx = geo.cadres[p._cadre].largeur / largeurPx;
            const r = rMaxPx * Math.sqrt(vals[c] / vmax) * unitesParPx;
            const cercle = el("circle", { cx: p._pt[0], cy: p._pt[1], r: Math.max(r, 1.2 * unitesParPx), class: "cercle-prop" + (c === etat.selection ? " selection" : ""), "data-code": c }, groupesCercles[p._cadre]);
            cercle._chemin = p;
          });
        });
        cadres._rMaxPx = rMaxPx;
      }

      // Numéros
      Object.values(groupesEtiquettes).forEach((g) => (g.textContent = ""));
      if (etat.numeros) {
        codes.forEach((c) => (chemins[c] || []).forEach((p) => {
          const svg = svgs[p._cadre];
          const k = unitesParPixel(p._cadre);
          const fondCol = modeCercles ? PLF.couleur("--surface-2") : couleurDe(vals[c]) || PLF.couleur("--sans-donnee");
          const t = el("text", { x: p._pt[0], y: p._pt[1], "text-anchor": "middle", "dominant-baseline": "central", class: "etiquette-dep", "font-size": (p._cadre === "metro" ? 10 : 11) * k, fill: PLF.texteSur(fondCol), stroke: fondCol, "stroke-width": 2.6 * k }, groupesEtiquettes[p._cadre]);
          t.textContent = c;
          void svg;
        }));
      }

      // Titre, mention, légende, fiche, palmarès, tableau
      const ind = INDICATEURS[etat.indicateur];
      const periode = etat.indicateur === "evolution" ? `entre ${annees[etat.ref]} et ${annees[i]}` : `au 31 décembre ${annees[i]}`;
      titre.textContent = `${ind.titre} ${periode} — ${LIBELLES_VERSANT[etat.versant]}`;
      mention.innerHTML = `${D.champ || ""} <br>Sources : ${D.source || ""}. Fond de carte : IGN – Admin Express (Etalab, Licence Ouverte 2.0), Natural Earth. Projections : Lambert-93 (métropole), UTM (outre-mer). Réalisation : Parti Libéral Français.`;
      legende(vals);
      fiche();
      palmares(vals);
      majTableau();

      curseur.value = String(i);
      curseur.setAttribute("aria-valuetext", String(annees[i]));
      anneeAffichee.textContent = annees[i];
      formulaire.querySelectorAll('input[name="indicateur"]').forEach((r) => (r.checked = r.value === etat.indicateur));
      formulaire.querySelectorAll('input[name="versant"]').forEach((r) => (r.checked = r.value === etat.versant));
      formulaire.querySelector("#carte-ref-bloc").hidden = etat.indicateur !== "evolution";
      selRef.value = String(etat.ref);
      Array.from(selRef.options).forEach((o) => {
        o.disabled = Number(o.value) >= etat.i;
        o.hidden = Number(o.value) < premierIndice();
      });
      selDep.value = etat.selection || "";
      formulaire.querySelector("#carte-numeros").checked = etat.numeros;
      formulaire.querySelector("#carte-anciennes").checked = etat.anciennes;
      curseur.min = String(premierIndice());
      majPlage();
      avertissement();
      ecrireAdresse();
    }

    // Avertissements de comparabilité (ancienne méthode, changement de source).
    function avertissement() {
      const zoneAv = formulaire.querySelector("#carte-avertissement");
      const messages = [];
      const debut = D.debutHomogene;
      if (annees[etat.i] < debut) {
        messages.push(`<strong>${annees[etat.i]} : ancienne méthode statistique.</strong> Avant ${debut}, les effectifs proviennent d'autres sources (fichier de paie de l'État, enquêtes) et l'outre-mer n'est pas détaillé : ne comparez pas directement avec ${debut} et après.`);
      } else if (etat.indicateur === "evolution" && annees[etat.ref] < debut) {
        messages.push(`<strong>Évolution peu fiable :</strong> la source statistique change entre ${debut - 1} et ${debut}. Une partie de l'écart entre ${annees[etat.ref]} et ${annees[etat.i]} vient de ce changement, pas d'une vraie évolution (jusqu'à +43 % dans certains départements).`);
      }
      zoneAv.innerHTML = messages.map((m) => `<p>${m}</p>`).join("");
      zoneAv.hidden = !messages.length;
    }

    function legende(vals) {
      const ul = lateral.querySelector("#legende-carte");
      const titreLeg = lateral.querySelector("#legende-titre");
      const cercles = lateral.querySelector("#legende-cercles");
      ul.textContent = "";
      cercles.textContent = "";
      const compte = (pred) => codes.filter((c) => pred(vals[c])).length;
      const ajouter = (couleur, texte, nb, hachure) => {
        const li = document.createElement("li");
        li.innerHTML = `<span class="legende-carte__case" style="${hachure ? "background:repeating-linear-gradient(45deg,var(--sans-donnee) 0 3px,var(--texte-doux) 3px 4px)" : `background:${couleur}`}"></span><span>${texte}</span><span class="legende-carte__nb">${nb} dép.</span>`;
        ul.appendChild(li);
      };
      if (etat.indicateur === "taux") {
        titreLeg.textContent = "Agents civils pour 1 000 habitants";
        const s = seuilsTaux[etat.versant];
        const f = (v) => PLF.fmt.nombre(v);
        paletteTaux().forEach((col, k) => {
          const bas = s[k - 1], haut = s[k];
          const texte = k === 0 ? `moins de ${f(haut)}` : k === s.length ? `${f(bas)} ou plus` : `de ${f(bas)} à moins de ${f(haut)}`;
          ajouter(col, texte, compte((v) => v != null && classe(v, s) === k));
        });
      } else if (etat.indicateur === "evolution") {
        titreLeg.textContent = `Évolution du nombre d'agents depuis ${annees[etat.ref]}`;
        const s = SEUILS_EVOLUTION;
        const f = (v) => PLF.fmt.variation(v, 0);
        DIVERGENTE.forEach((col, k) => {
          const bas = s[k - 1], haut = s[k];
          const texte = k === 0 ? `baisse de plus de ${Math.abs(haut)} %` : k === s.length ? `hausse de plus de ${bas} %` : bas === -1 && haut === 1 ? "stable (entre −1 % et +1 %)" : `de ${f(bas)} à ${f(haut)}`;
          ajouter(col, texte, compte((v) => v != null && classe(v, s) === k));
        });
      } else {
        titreLeg.textContent = "Nombre d'agents (surface des cercles proportionnelle)";
        const vmax = maxEffectif[etat.versant];
        const rMax = cadres._rMaxPx || 30;
        const ronds = G.graduations(0, vmax, 3).filter((v) => v > 0 && v <= vmax * 1.05);
        const choix = [ronds[ronds.length - 1], ronds[Math.floor(ronds.length / 2)] / 2, ronds[0] / 4].filter((v, k, a) => v > 0 && a.indexOf(v) === k).sort((a, b) => b - a);
        const L = 2 * rMax + 120, H = 2 * rMax + 8;
        const svg = el("svg", { viewBox: `0 0 ${L} ${H}`, width: L, height: H, "aria-hidden": "true", class: "graph" });
        choix.forEach((v) => {
          const r = rMax * Math.sqrt(v / vmax);
          const cy = H - 4 - r;
          el("circle", { cx: rMax + 2, cy, r, class: "cercle-prop", style: "cursor:default" }, svg);
          el("line", { x1: rMax + 2, x2: 2 * rMax + 14, y1: H - 4 - 2 * r, y2: H - 4 - 2 * r, stroke: "var(--texte-doux)", "stroke-dasharray": "2 2" }, svg);
          const t = el("text", { x: 2 * rMax + 18, y: H - 4 - 2 * r, "dominant-baseline": "middle", "font-size": 12 }, svg);
          t.textContent = PLF.fmt.nombre(v);
        });
        cercles.appendChild(svg);
        const p = document.createElement("p");
        p.className = "visuellement-cache";
        p.textContent = `Cercles de référence : ${choix.map((v) => PLF.fmt.nombre(v) + " agents").join(", ")}.`;
        cercles.appendChild(p);
      }
      const nd = compte((v) => v == null);
      if (nd && etat.indicateur !== "effectif") ajouter(null, "données non disponibles", nd, true);
    }

    function fiche() {
      const zoneFiche = lateral.querySelector("#fiche-dep");
      const c = etat.selection;
      const libFrance = D.couverture[etat.i] === "metropole" ? "France métropolitaine" : "France (hors Mayotte)";
      if (!c) {
        const vf = valeurFrance();
        zoneFiche.innerHTML = `<h3>${libFrance}</h3><p class="fiche-dep__valeur">${formatValeur(vf)}</p><p class="figure__note" style="margin-top:.2rem">${INDICATEURS[etat.indicateur].titre.toLowerCase()} — ${LIBELLES_VERSANT[etat.versant]}, ${etat.indicateur === "evolution" ? `${annees[etat.ref]}-${annees[etat.i]}` : annees[etat.i]}</p><p class="fiche-dep__vide">Survolez ou sélectionnez un département (clic, clavier ou liste « Aller à un département ») pour afficher sa fiche.</p>`;
        return;
      }
      const i = etat.i;
      const v = valeur(c);
      if (effectif(c, "ensemble", i) == null && effectif(c, "fpe", i) == null) {
        zoneFiche.innerHTML = `<h3>${nomDe(c)} <span style="font-weight:500;color:var(--texte-doux)">(${c})</span></h3>
          <p>${messageSansDonnee(c)}</p>
          <p><button type="button" class="bouton bouton--secondaire" id="fiche-fermer">Revenir à la France entière</button></p>`;
        zoneFiche.querySelector("#fiche-fermer").addEventListener("click", () => selectionner(null, true));
        return;
      }
      const vals = codes.map((cc) => ({ c: cc, v: valeur(cc) }));
      const rangs = rangsDe(vals);
      const nb = vals.filter((x) => x.v != null).length;
      const vf = valeurFrance();
      const alerte = (D.alertes[c] || {})[annees[i]];
      const lignesVersants = ["fpe", "fpt", "fph"].map((vv) => {
        const e = effectif(c, vv, i);
        return `<dt><span class="pastille-versant" style="background:var(--c-${vv})"></span>${vv === "fpe" ? "État" : vv === "fpt" ? "Territoriale" : "Hospitalière"}</dt><dd>${PLF.fmt.nombre(e)} <span style="font-weight:400;color:var(--texte-doux)">(${PLF.fmt.decimal1(taux(c, vv, i))} ‰)</span></dd>`;
      }).join("");
      zoneFiche.innerHTML = `<h3>${nomDe(c)} <span style="font-weight:500;color:var(--texte-doux)">(${c})</span></h3>
        <p class="fiche-dep__valeur">${formatValeur(v)}</p>
        <p class="figure__note" style="margin-top:.2rem">${etat.indicateur === "taux" ? "agents pour 1 000 habitants" : etat.indicateur === "effectif" ? "agents" : `évolution du nombre d'agents depuis ${annees[etat.ref]}`} — ${LIBELLES_VERSANT[etat.versant]}, ${annees[i]}</p>
        <dl>
          <dt>Rang</dt><dd>${rangs[c] ? `${rangs[c]}<sup>${rangs[c] === 1 ? "er" : "e"}</sup> sur ${nb}` : "–"}</dd>
          <dt>${libFrance}</dt><dd>${formatValeur(vf)}</dd>
          <dt>Population</dt><dd>${PLF.fmt.nombre(population(c, i))}</dd>
          <dt>Agents (3 versants)</dt><dd>${PLF.fmt.nombre(effectif(c, "ensemble", i))}</dd>
          ${lignesVersants}
        </dl>
        ${alerte ? `<p class="encadre encadre--attention" style="font-size:.9em"><strong>À noter :</strong> ${alerte}</p>` : ""}
        <div class="sparkline" id="fiche-spark"></div>
        <p><button type="button" class="bouton bouton--secondaire" id="fiche-fermer">Revenir à la France entière</button></p>`;
      // La petite courbe suit la période affichée (homogène par défaut).
      const k0 = premierIndice();
      const anneesS = annees.slice(k0);
      const serie = anneesS.map((_, j) => (etat.indicateur === "effectif" ? effectif(c, etat.versant, j + k0) : taux(c, etat.versant, j + k0)));
      const ref = etat.indicateur === "effectif" ? null : anneesS.map((_, j) => taux("FR", etat.versant, j + k0));
      G.sparkline(zoneFiche.querySelector("#fiche-spark"), {
        annees: anneesS, valeurs: serie, reference: ref,
        formatValeur: etat.indicateur === "effectif" ? PLF.fmt.nombre : PLF.fmt.decimal1,
        libelle: etat.indicateur === "effectif" ? `Agents, ${nomDe(c)}` : `Pour 1 000 hab., ${nomDe(c)}`,
        libelleRef: "France entière",
      });
      zoneFiche.querySelector("#fiche-fermer").addEventListener("click", () => selectionner(null, true));
    }

    function messageSansDonnee(c) {
      if (c === "976" && D.mayotte) {
        const k = D.mayotte.annees.indexOf(annees[etat.i]);
        const j = k >= 0 ? k : D.mayotte.annees.length - 1;
        return D.mayotte.texte.replace("{v}", PLF.fmt.nombre(D.mayotte.valeurs[j])).replace("{a}", D.mayotte.annees[j]);
      }
      if (annees[etat.i] < D.debutHomogene && ["971", "972", "973", "974"].includes(c)) {
        return `Pas de données par département pour l'outre-mer avant ${D.debutHomogene} dans la source.`;
      }
      return "Donnée non disponible pour cette année dans la source.";
    }

    function valeurFrance() {
      if (etat.indicateur === "taux") return taux("FR", etat.versant, etat.i);
      if (etat.indicateur === "effectif") return effectif("FR", etat.versant, etat.i);
      return evolution("FR", etat.versant, etat.i, etat.ref);
    }

    function palmares(vals) {
      const zoneP = lateral.querySelector("#palmares");
      const tries = codes.filter((c) => vals[c] != null).sort((a, b) => vals[b] - vals[a]);
      const liste = (cs) => cs.map((c) => `<li><button type="button" data-code="${c}">${nomDe(c)}</button> : ${formatValeur(vals[c])}</li>`).join("");
      const plus = etat.indicateur === "evolution" ? "Plus fortes hausses" : "Valeurs les plus élevées";
      const moins = etat.indicateur === "evolution" ? "Plus fortes baisses (ou plus faibles hausses)" : "Valeurs les plus faibles";
      zoneP.innerHTML = `<div><h3>${plus}</h3><ol>${liste(tries.slice(0, 5))}</ol></div><div><h3>${moins}</h3><ol>${liste(tries.slice(-5).reverse())}</ol></div>`;
      zoneP.querySelectorAll("button[data-code]").forEach((b) => b.addEventListener("click", () => selectionner(b.dataset.code, true)));
    }

    /* ---------- Interactions ---------- */
    function codeDepuisCible(t) {
      return t && t.dataset && t.dataset.code;
    }
    function montrerInfobulle(code, evt) {
      const v = valeur(code);
      const i = etat.i;
      if (effectif(code, "ensemble", i) == null && effectif(code, "fpe", i) == null) {
        ib.innerHTML = `<span class="infobulle__titre">${nomDe(code)} (${code})</span><div style="max-width:16rem">${messageSansDonnee(code)}</div>`;
      } else ib.innerHTML = `<span class="infobulle__titre">${nomDe(code)} (${code})</span>
        <div class="infobulle__ligne"><span>${etat.indicateur === "taux" ? "Pour 1 000 hab." : etat.indicateur === "effectif" ? "Agents" : `Depuis ${annees[etat.ref]}`}</span><b>${formatValeur(v)}</b></div>
        ${etat.indicateur !== "effectif" ? `<div class="infobulle__ligne"><span>Agents</span><b>${PLF.fmt.nombre(effectif(code, etat.versant, i))}</b></div>` : `<div class="infobulle__ligne"><span>Pour 1 000 hab.</span><b>${PLF.fmt.decimal1(taux(code, etat.versant, i))}</b></div>`}
        <div class="infobulle__ligne"><span>Population</span><b>${PLF.fmt.nombre(population(code, i))}</b></div>`;
      ib.hidden = false;
      const r = panneauCarte.getBoundingClientRect();
      let x, y;
      if (evt && evt.clientX != null) { x = evt.clientX - r.left; y = evt.clientY - r.top; }
      else {
        const p = (chemins[code] || [])[0];
        const b = p.getBoundingClientRect();
        x = b.left + b.width / 2 - r.left; y = b.top + b.height / 2 - r.top;
      }
      const lb = ib.offsetWidth, hb = ib.offsetHeight;
      let gauche = x + 16;
      if (gauche + lb > panneauCarte.clientWidth) gauche = x - lb - 16;
      let haut = y - hb - 10;
      if (haut < 0) haut = y + 18;
      ib.style.left = Math.max(4, gauche) + "px";
      ib.style.top = haut + "px";
    }
    function cacherInfobulle() { ib.hidden = true; }
    let survole = null;
    function marquerSurvol(code) {
      if (survole) (chemins[survole] || []).forEach((p) => p.classList.remove("survol"));
      survole = code;
      if (code) (chemins[code] || []).forEach((p) => { p.classList.add("survol"); p.parentNode.appendChild(p); });
      // garde la sélection au premier plan
      if (etat.selection) (chemins[etat.selection] || []).forEach((p) => p.parentNode.appendChild(p));
    }
    cadres.addEventListener("pointermove", (evt) => {
      const code = codeDepuisCible(evt.target);
      if (!code) { marquerSurvol(null); cacherInfobulle(); return; }
      if (code !== survole) marquerSurvol(code);
      montrerInfobulle(code, evt);
    });
    cadres.addEventListener("pointerleave", () => { marquerSurvol(null); cacherInfobulle(); });
    cadres.addEventListener("click", (evt) => {
      const code = codeDepuisCible(evt.target);
      if (code) selectionner(code === etat.selection ? null : code, false);
    });

    function selectionner(code, annonce) {
      etat.selection = code;
      rendu();
      if (code) {
        (chemins[code] || []).forEach((p) => p.parentNode.appendChild(p));
        if (annonce) PLF.annoncer(`${nomDe(code)} : ${phraseValeur(valeur(code))}, en ${annees[etat.i]}.`);
      }
    }

    // Navigation au clavier : flèche = voisin le plus proche dans cette direction (à l'écran).
    function centre(code) {
      const p = (chemins[code] || []).find((pp) => pp._cadre !== "idf") || (chemins[code] || [])[0];
      const b = p.getBoundingClientRect();
      return [b.left + b.width / 2, b.top + b.height / 2];
    }
    function voisin(depuis, dx, dy) {
      const [x0, y0] = centre(depuis);
      let meilleur = null, score = Infinity;
      codes.forEach((c) => {
        if (c === depuis) return;
        const [x, y] = centre(c);
        const vx = x - x0, vy = y - y0;
        const d = Math.hypot(vx, vy);
        if (!d) return;
        const cos = (vx * dx + vy * dy) / d;
        if (cos < 0.35) return;
        const s = d * (1 + 2.2 * (1 - cos));
        if (s < score) { score = s; meilleur = c; }
      });
      return meilleur;
    }
    cadres.addEventListener("keydown", (evt) => {
      const dirs = { ArrowRight: [1, 0], ArrowLeft: [-1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
      if (dirs[evt.key]) {
        evt.preventDefault();
        const depart = etat.selection || survole || "75";
        const cible = etat.selection || survole ? voisin(depart, ...dirs[evt.key]) || depart : "75";
        marquerSurvol(null);
        selectionner(cible, true);
        montrerInfobulle(cible);
      } else if (evt.key === "Escape") {
        cacherInfobulle();
        selectionner(null, false);
        PLF.annoncer("Aucun département sélectionné.");
      } else if (evt.key === "Enter" || evt.key === " ") {
        evt.preventDefault();
        if (!etat.selection) selectionner("75", true);
        else PLF.annoncer(`${nomDe(etat.selection)} : ${phraseValeur(valeur(etat.selection))}, en ${annees[etat.i]}. La fiche du département est affichée à côté de la carte.`);
      }
    });
    cadres.addEventListener("focus", () => {
      if (!etat.selection) PLF.annoncer("Carte : appuyez sur une flèche pour sélectionner un département.");
    });
    cadres.addEventListener("blur", cacherInfobulle);

    // Contrôles
    formulaire.addEventListener("change", (evt) => {
      const t = evt.target;
      if (t.name === "indicateur") {
        etat.indicateur = t.value;
        if (etat.indicateur === "evolution" && etat.ref >= etat.i) etat.ref = premierIndice();
      } else if (t.name === "versant") etat.versant = t.value;
      else if (t.id === "carte-dep") { selectionner(t.value || null, true); return; }
      else if (t.id === "carte-ref") etat.ref = Number(t.value);
      else if (t.id === "carte-numeros") etat.numeros = t.checked;
      else if (t.id === "carte-anciennes") {
        etat.anciennes = t.checked;
        if (!etat.anciennes) {
          etat.i = Math.max(etat.i, iHomogene);
          etat.ref = Math.max(etat.ref, iHomogene);
          if (etat.ref >= etat.i) etat.ref = iHomogene;
        }
      }
      else return;
      rendu();
      annoncerResume();
    });
    curseur.addEventListener("input", () => {
      etat.i = Math.max(premierIndice(), Number(curseur.value));
      if (etat.ref >= etat.i) etat.ref = premierIndice();
      rendu();
    });
    curseur.addEventListener("change", annoncerResume);
    formulaire.querySelectorAll("[data-pas]").forEach((b) => b.addEventListener("click", () => {
      etat.i = Math.max(premierIndice(), Math.min(annees.length - 1, etat.i + Number(b.dataset.pas)));
      if (etat.ref >= etat.i) etat.ref = premierIndice();
      rendu();
      annoncerResume();
    }));

    // Animation
    const lecture = formulaire.querySelector("#carte-lecture");
    let minuteur = null;
    function arreter() {
      clearInterval(minuteur);
      minuteur = null;
      lecture.setAttribute("aria-pressed", "false");
      lecture.querySelector("span").textContent = "Animer";
      lecture.querySelector("svg").innerHTML = '<path d="M8 5v14l11-7z"/>';
    }
    lecture.addEventListener("click", () => {
      if (minuteur) { arreter(); annoncerResume(); return; }
      if (etat.i >= annees.length - 1) etat.i = etat.indicateur === "evolution" ? Math.min(etat.ref + 1, annees.length - 1) : premierIndice();
      rendu();
      lecture.setAttribute("aria-pressed", "true");
      lecture.querySelector("span").textContent = "Pause";
      lecture.querySelector("svg").innerHTML = '<path d="M7 5h4v14H7zM13 5h4v14h-4z"/>';
      minuteur = setInterval(() => {
        if (etat.i >= annees.length - 1) { arreter(); annoncerResume(); return; }
        etat.i += 1;
        rendu();
      }, 1300);
    });

    function annoncerResume() {
      const vals = codes.map((c) => ({ c, v: valeur(c) })).filter((x) => x.v != null).sort((a, b) => b.v - a.v);
      if (!vals.length) return;
      const haut = vals[0], bas = vals[vals.length - 1];
      const vf = valeurFrance();
      PLF.annoncer(`${titre.textContent}. France entière : ${formatValeur(vf)}. Valeur la plus élevée : ${nomDe(haut.c)}, ${formatValeur(haut.v)}. La plus faible : ${nomDe(bas.c)}, ${formatValeur(bas.v)}.`);
    }

    // Taille des textes constante à l'écran, quelle que soit la largeur de la carte.
    function unitesParPixel(cle) {
      const largeur = svgs[cle].getBoundingClientRect().width;
      return largeur ? geo.cadres[cle].largeur / largeur : geo.cadres[cle].largeur / (cle === "metro" ? 700 : 110);
    }
    function ajusterTextes() {
      Object.keys(svgs).forEach((cle) => {
        const svg = svgs[cle];
        const k = unitesParPixel(cle);
        const etroit = svg.getBoundingClientRect().width < 480;
        svg._textes.forEach((t) => {
          t.n.setAttribute("font-size", t.px * k);
          // Sur petit écran, les noms des mers et des pays voisins encombreraient la carte.
          t.n.style.display = etroit ? "none" : "";
        });
        const { y0, tiques, te } = svg._echelle;
        tiques.forEach((l) => { l.setAttribute("y1", y0 - 4 * k); l.setAttribute("y2", y0 + 1 * k); });
        te.setAttribute("y", y0 - 7 * k);
        te.setAttribute("font-size", (cle === "metro" ? 12 : 10.5) * k);
      });
    }
    // Recalcule textes et cercles quand la carte change de largeur.
    let largeurPrec = 0;
    new ResizeObserver(() => {
      const l = svgs.metro.getBoundingClientRect().width;
      if (Math.abs(l - largeurPrec) > 8) {
        largeurPrec = l;
        ajusterTextes();
        if (etat.indicateur === "effectif" || etat.numeros) rendu();
      }
    }).observe(svgs.metro);
    document.addEventListener("plf:affichage", () => rendu());

    // Un lien partagé (#indicateur=…&annee=…) ouvert dans un onglet déjà chargé.
    window.addEventListener("hashchange", () => {
      lireAdresse();
      if (etat.ref >= etat.i) etat.ref = premierIndice();
      rendu();
    });

    construireTableau();
    ajusterTextes();
    rendu();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialiser);
  else initialiser();
})();
