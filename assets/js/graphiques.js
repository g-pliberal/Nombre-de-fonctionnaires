/* ==========================================================================
   Graphiques SVG accessibles, sans dépendance.
   - courbes()  : courbes ou aires empilées sur des années
   - barres()   : barres horizontales empilées (en nombre ou en %)
   - gaufre()   : grille de 100 carrés (« sur 100 agents… »)
   - sparkline(): petite courbe pour la fiche d'un département
   Chaque graphique est navigable au clavier (flèches) et annonce les
   valeurs aux lecteurs d'écran ; un tableau de données l'accompagne toujours.
   ========================================================================== */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const PLF = window.PLF;

  // Pour les textes, couleur, taille et graisse passent par l'attribut style :
  // sinon la feuille de style (.graph text) l'emporterait sur les attributs SVG.
  const STYLES_TEXTE = { fill: "fill", "font-size": "font-size", "font-weight": "font-weight" };
  function el(nom, attrs, parent) {
    const n = document.createElementNS(NS, nom);
    if (attrs) {
      for (const k in attrs) {
        if (attrs[k] == null) continue;
        if (nom === "text" && STYLES_TEXTE[k]) n.style.setProperty(STYLES_TEXTE[k], typeof attrs[k] === "number" && k === "font-size" ? attrs[k] + "px" : attrs[k]);
        else n.setAttribute(k, attrs[k]);
      }
    }
    if (parent) parent.appendChild(n);
    return n;
  }
  function echelle(d0, d1, r0, r1) {
    const f = (v) => (d1 === d0 ? (r0 + r1) / 2 : r0 + ((v - d0) * (r1 - r0)) / (d1 - d0));
    f.inverse = (p) => d0 + ((p - r0) * (d1 - d0)) / (r1 - r0);
    return f;
  }
  // Graduations « rondes » entre min et max.
  function graduations(min, max, cible) {
    const etendue = max - min || Math.abs(max) || 1;
    const brut = etendue / Math.max(1, cible);
    const p = Math.pow(10, Math.floor(Math.log10(brut)));
    const pas = [1, 2, 2.5, 5, 10].map((m) => m * p).find((s) => s >= brut) || 10 * p;
    const debut = Math.floor(min / pas) * pas;
    const fin = Math.ceil(max / pas) * pas;
    const res = [];
    for (let v = debut; v <= fin + pas / 1e6; v += pas) res.push(Math.round(v / pas) * pas);
    return res;
  }
  function pasAnnees(n, largeur) {
    const max = Math.max(2, Math.floor(largeur / 46));
    for (const p of [1, 2, 5, 10, 20]) if (n / p <= max) return p;
    return 25;
  }
  function infobulle(conteneur) {
    let ib = conteneur.querySelector(":scope > .infobulle");
    if (!ib) {
      ib = document.createElement("div");
      ib.className = "infobulle";
      ib.hidden = true;
      ib.setAttribute("aria-hidden", "true");
      conteneur.appendChild(ib);
    }
    return ib;
  }
  function placerInfobulle(ib, conteneur, x, y) {
    ib.hidden = false;
    const lc = conteneur.clientWidth;
    const lb = ib.offsetWidth;
    const hb = ib.offsetHeight;
    let gauche = x + 14;
    if (gauche + lb > lc) gauche = x - lb - 14;
    if (gauche < 0) gauche = Math.max(0, Math.min(lc - lb, x - lb / 2));
    let haut = y - hb - 12;
    if (haut < 0) haut = y + 16;
    ib.style.left = gauche + "px";
    ib.style.top = haut + "px";
  }
  function surRedimension(conteneur, rendu) {
    let largeur = conteneur.clientWidth;
    let attente;
    const obs = new ResizeObserver(() => {
      if (Math.abs(conteneur.clientWidth - largeur) < 4) return;
      largeur = conteneur.clientWidth;
      clearTimeout(attente);
      attente = setTimeout(rendu, 120);
    });
    obs.observe(conteneur);
    document.addEventListener("plf:affichage", () => setTimeout(rendu, 30));
    return obs;
  }

  /* ======================================================================
     Courbes / aires empilées
     cfg = { annees, series:[{id, libelle, valeurs, couleur, tirets}], empile,
             pourcent, formatAxe, formatValeur, titreAxeY, ruptures:[{annee, libelle}],
             hauteur, libelleCourt?, etiquettesFin? }
     ====================================================================== */
  function courbes(conteneur, cfgInitial) {
    let cfg = cfgInitial;
    let index = null; // année active (navigation clavier / survol)
    conteneur.classList.add("figure__graphique");
    conteneur.tabIndex = 0;
    conteneur.setAttribute("role", "group");
    conteneur.setAttribute("aria-roledescription", "graphique interactif");

    function valeursAffichees() {
      // Renvoie, pour chaque série, les valeurs (éventuellement en % et cumulées).
      const n = cfg.annees.length;
      let base = cfg.series.map((s) => s.valeurs.slice());
      if (cfg.pourcent) {
        const totaux = Array.from({ length: n }, (_, i) =>
          base.reduce((acc, v) => acc + (v[i] == null ? 0 : v[i]), 0));
        base = base.map((v) => v.map((x, i) => (x == null || !totaux[i] ? null : (100 * x) / totaux[i])));
      }
      let cumul = null;
      if (cfg.empile) {
        cumul = [];
        const acc = new Array(n).fill(0);
        base.forEach((v) => {
          const bas = acc.slice();
          v.forEach((x, i) => { acc[i] += x == null ? 0 : x; });
          cumul.push({ bas, haut: acc.slice() });
        });
      }
      return { base, cumul };
    }

    function rendu() {
      conteneur.querySelectorAll(":scope > svg").forEach((s) => s.remove());
      const L = Math.max(280, conteneur.clientWidth);
      const petit = L < 560;
      const H = Math.round(Math.max(260, Math.min(cfg.hauteur || 380, L * (petit ? 0.85 : 0.55))));
      const { base, cumul } = valeursAffichees();
      const fmtAxe = cfg.pourcent ? (v) => v + " %" : cfg.formatAxe || PLF.fmt.nombre;
      const fmtVal = cfg.pourcent ? (v) => PLF.fmt.pourcent(v, 1) : cfg.formatValeur || PLF.fmt.nombre;

      let maxY = 0;
      let minY = cfg.yMin != null ? cfg.yMin : 0;
      if (cfg.empile) cumul.forEach((c) => c.haut.forEach((v) => (maxY = Math.max(maxY, v))));
      else base.forEach((v) => v.forEach((x) => { if (x != null) { maxY = Math.max(maxY, x); minY = Math.min(minY, x); } }));
      if (cfg.pourcent) maxY = 100;
      if (cfg.yMax != null) maxY = cfg.yMax;
      const ticks = graduations(minY, maxY, petit ? 4 : 6);
      const yMax = ticks[ticks.length - 1];
      const yMin = ticks[0];
      const etiquettesFin = cfg.etiquettesFin !== false && !petit && !cfg.empile;
      const largeurEtiqY = Math.max(...ticks.map((t) => String(fmtAxe(t)).length)) * 7.4 + 14;
      const m = { haut: cfg.ruptures && cfg.ruptures.length ? 30 : 16, bas: 34, gauche: largeurEtiqY, droite: etiquettesFin ? 108 : 14 };
      const x = echelle(cfg.annees[0], cfg.annees[cfg.annees.length - 1], m.gauche, L - m.droite);
      const y = echelle(yMin, yMax, H - m.bas, m.haut);

      const svg = el("svg", { viewBox: `0 0 ${L} ${H}`, class: "graph", "aria-hidden": "true", focusable: "false" });
      conteneur.insertBefore(svg, conteneur.firstChild);

      // Grille et axe Y
      const gy = el("g", { class: "grille-y" }, svg);
      ticks.forEach((t) => {
        el("line", { x1: m.gauche, x2: L - m.droite, y1: y(t), y2: y(t) }, gy);
        const tx = el("text", { x: m.gauche - 8, y: y(t), "text-anchor": "end", "dominant-baseline": "middle" }, gy);
        tx.textContent = fmtAxe(t);
      });
      // Axe X
      const gx = el("g", { class: "axe" }, svg);
      el("line", { x1: m.gauche, x2: L - m.droite, y1: y(yMin), y2: y(yMin) }, gx);
      const pas = pasAnnees(cfg.annees.length, L - m.gauche - m.droite);
      cfg.annees.forEach((a, i) => {
        const dernier = i === cfg.annees.length - 1;
        if (a % pas !== 0 && !(dernier && pas <= 2)) return;
        el("line", { x1: x(a), x2: x(a), y1: y(yMin), y2: y(yMin) + 5 }, gx);
        const tx = el("text", { x: x(a), y: H - m.bas + 20, "text-anchor": "middle" }, gx);
        tx.textContent = a;
      });

      // Ruptures de série
      (cfg.ruptures || []).forEach((r, k) => {
        if (r.annee <= cfg.annees[0] || r.annee > cfg.annees[cfg.annees.length - 1]) return;
        const xr = (x(r.annee - 1) + x(r.annee)) / 2;
        const g = el("g", { class: "rupture" }, svg);
        el("line", { x1: xr, x2: xr, y1: m.haut - 6, y2: y(yMin) }, g);
        const t = el("text", { x: xr + 4, y: m.haut - 10 - (k % 2) * 0, "text-anchor": xr > L * 0.75 ? "end" : "start" }, g);
        if (xr > L * 0.75) t.setAttribute("x", xr - 4);
        t.textContent = r.court || "rupture de série";
      });

      // Séries
      const gs = el("g", {}, svg);
      cfg.series.forEach((s, k) => {
        const c = PLF.couleur(s.couleur);
        if (cfg.empile) {
          const { bas, haut } = cumul[k];
          let d = "";
          cfg.annees.forEach((a, i) => { d += (i ? "L" : "M") + x(a).toFixed(1) + " " + y(haut[i]).toFixed(1); });
          for (let i = cfg.annees.length - 1; i >= 0; i--) d += "L" + x(cfg.annees[i]).toFixed(1) + " " + y(bas[i]).toFixed(1);
          el("path", { d: d + "Z", fill: c, "fill-opacity": 0.9, stroke: PLF.couleur("--surface"), "stroke-width": 1 }, gs);
        } else {
          let d = "";
          let enCours = false;
          base[k].forEach((v, i) => {
            if (v == null) { enCours = false; return; }
            d += (enCours ? "L" : "M") + x(cfg.annees[i]).toFixed(1) + " " + y(v).toFixed(1);
            enCours = true;
          });
          el("path", { d, class: "serie", stroke: c, "stroke-dasharray": s.tirets ? "7 5" : null, "stroke-width": s.epaisseur || null }, gs);
          // points isolés (séries discontinues)
          base[k].forEach((v, i) => {
            const avant = base[k][i - 1], apres = base[k][i + 1];
            if (v != null && avant == null && apres == null) el("circle", { cx: x(cfg.annees[i]), cy: y(v), r: 3.5, fill: c }, gs);
          });
        }
      });

      // Étiquettes en bout de courbe (évite les allers-retours avec la légende)
      if (etiquettesFin) {
        const positions = [];
        cfg.series.forEach((s, k) => {
          let i = base[k].length - 1;
          while (i >= 0 && base[k][i] == null) i--;
          if (i < 0) return;
          positions.push({ s, yv: y(base[k][i]), xv: x(cfg.annees[i]) });
        });
        positions.sort((a, b) => a.yv - b.yv);
        for (let i = 1; i < positions.length; i++) {
          if (positions[i].yv - positions[i - 1].yv < 16) positions[i].yv = positions[i - 1].yv + 16;
        }
        positions.forEach((p) => {
          const t = el("text", { x: p.xv + 8, y: p.yv, "dominant-baseline": "middle", fill: PLF.couleur(p.s.couleur), "font-weight": 700 }, svg);
          t.textContent = p.s.libelleCourt || p.s.libelle;
        });
      }

      // Titre de l'axe Y
      if (cfg.titreAxeY) {
        const t = el("text", { x: m.gauche, y: m.haut - (cfg.ruptures && cfg.ruptures.length ? 20 : 4), class: "titre-axe" }, svg);
        if (!(cfg.ruptures && cfg.ruptures.length)) t.setAttribute("y", 11);
        t.textContent = cfg.pourcent ? "Part (%)" : cfg.titreAxeY;
      }

      // Survol / clavier
      const guide = el("line", { class: "guide", y1: m.haut, y2: y(yMin), visibility: "hidden" }, svg);
      const marques = cfg.series.map((s) => el("circle", { r: 5, fill: PLF.couleur(s.couleur), stroke: PLF.couleur("--surface"), "stroke-width": 2, visibility: "hidden" }, svg));
      const zone = el("rect", { class: "zone-survol", x: m.gauche, y: m.haut, width: L - m.gauche - m.droite, height: y(yMin) - m.haut }, svg);
      const ib = infobulle(conteneur);

      function montrer(i, annonce) {
        index = i;
        const a = cfg.annees[i];
        const xa = x(a);
        guide.setAttribute("x1", xa);
        guide.setAttribute("x2", xa);
        guide.setAttribute("visibility", "visible");
        let lignes = "";
        let texte = `${a} : `;
        const morceaux = [];
        let total = 0;
        cfg.series.forEach((s, k) => {
          const v = base[k][i];
          const yy = cfg.empile ? cumul[k].haut[i] : v;
          if (v == null) { marques[k].setAttribute("visibility", "hidden"); return; }
          total += v;
          marques[k].setAttribute("cx", xa);
          marques[k].setAttribute("cy", y(yy));
          marques[k].setAttribute("visibility", "visible");
          lignes += `<div class="infobulle__ligne"><span><i class="infobulle__pastille" style="background:${PLF.couleur(s.couleur)}"></i>${s.libelle}</span><b>${fmtVal(v)}</b></div>`;
          morceaux.push(`${s.libelle} ${fmtVal(v)}`);
        });
        if (cfg.empile && !cfg.pourcent && cfg.series.length > 1) {
          lignes += `<div class="infobulle__ligne" style="border-top:1px solid rgba(255,255,255,.25);margin-top:.25rem;padding-top:.25rem"><span>Total</span><b>${fmtVal(total)}</b></div>`;
          morceaux.push(`total ${fmtVal(total)}`);
        }
        const note = cfg.noteAnnee && cfg.noteAnnee(a);
        ib.innerHTML = `<span class="infobulle__titre">${cfg.etiquetteAnnee ? cfg.etiquetteAnnee(a) : a}</span>${lignes}${note ? `<div style="margin-top:.3rem;font-style:italic;opacity:.85">${note}</div>` : ""}`;
        const yTop = Math.min(...marques.filter((mq) => mq.getAttribute("visibility") === "visible").map((mq) => +mq.getAttribute("cy")), H / 2);
        placerInfobulle(ib, conteneur, (xa / L) * conteneur.clientWidth, (yTop / H) * svg.getBoundingClientRect().height);
        if (annonce) PLF.annoncer(texte + morceaux.join(", ") + (note ? `. ${note}` : ""));
      }
      function cacher() {
        guide.setAttribute("visibility", "hidden");
        marques.forEach((mq) => mq.setAttribute("visibility", "hidden"));
        ib.hidden = true;
      }
      function indexDepuisEvenement(evt) {
        const r = svg.getBoundingClientRect();
        const px = ((evt.clientX - r.left) / r.width) * L;
        const a = x.inverse(px);
        let best = 0;
        cfg.annees.forEach((an, i) => { if (Math.abs(an - a) < Math.abs(cfg.annees[best] - a)) best = i; });
        return best;
      }
      zone.addEventListener("pointermove", (evt) => montrer(indexDepuisEvenement(evt), false));
      zone.addEventListener("pointerdown", (evt) => montrer(indexDepuisEvenement(evt), false));
      zone.addEventListener("pointerleave", cacher);
      conteneur._montrer = montrer;
      conteneur._cacher = cacher;
      if (index != null && document.activeElement === conteneur) montrer(index, false);
    }

    conteneur.addEventListener("keydown", (evt) => {
      const n = cfg.annees.length;
      let i = index == null ? n - 1 : index;
      if (evt.key === "ArrowRight") i = Math.min(n - 1, i + 1);
      else if (evt.key === "ArrowLeft") i = Math.max(0, i - 1);
      else if (evt.key === "Home") i = 0;
      else if (evt.key === "End") i = n - 1;
      else if (evt.key === "Escape") { conteneur._cacher && conteneur._cacher(); return; }
      else return;
      evt.preventDefault();
      conteneur._montrer && conteneur._montrer(i, true);
    });
    conteneur.addEventListener("focus", () => {
      if (index == null) index = cfg.annees.length - 1;
      conteneur._montrer && conteneur._montrer(index, false);
    });
    conteneur.addEventListener("blur", () => conteneur._cacher && conteneur._cacher());

    function etiquetteAria() {
      conteneur.setAttribute("aria-label", `${cfg.titreAccessible || "Graphique"}. Utilisez les flèches gauche et droite pour parcourir les années ; les valeurs sont lues à voix haute. Le tableau de données est disponible juste après.`);
    }
    etiquetteAria();
    rendu();
    surRedimension(conteneur, rendu);
    return {
      maj(nouveau) { cfg = Object.assign({}, cfg, nouveau); etiquetteAria(); rendu(); },
      get cfg() { return cfg; },
    };
  }

  /* ======================================================================
     Barres horizontales empilées
     cfg = { categories:[libellés], series:[{id, libelle, valeurs, couleur}],
             pourcent, formatValeur, titreAccessible }
     ====================================================================== */
  function barres(conteneur, cfgInitial) {
    let cfg = cfgInitial;
    let actif = null; // [barre, segment]
    conteneur.classList.add("figure__graphique");
    conteneur.tabIndex = 0;
    conteneur.setAttribute("role", "group");
    conteneur.setAttribute("aria-roledescription", "graphique interactif");

    function rendu() {
      conteneur.querySelectorAll(":scope > svg").forEach((s) => s.remove());
      const L = Math.max(280, conteneur.clientWidth);
      const petit = L < 560;
      const hauteurBarre = petit ? 34 : 40;
      const ecart = petit ? 36 : 22;
      const largeurLib = petit ? 0 : Math.min(190, Math.max(...cfg.categories.map((c) => c.length)) * 8 + 16);
      const m = { haut: 6, bas: 28, gauche: largeurLib, droite: 12 };
      const H = m.haut + m.bas + cfg.categories.length * (hauteurBarre + ecart) - ecart + (petit ? 22 : 0);
      const fmtVal = cfg.formatValeur || PLF.fmt.nombre;

      const totaux = cfg.categories.map((_, i) => cfg.series.reduce((a, s) => a + (s.valeurs[i] || 0), 0));
      const maxTot = cfg.pourcent ? 100 : Math.max(...totaux);
      const ticks = graduations(0, maxTot, petit ? 4 : 5);
      const x = echelle(0, cfg.pourcent ? 100 : ticks[ticks.length - 1], m.gauche, L - m.droite);

      const svg = el("svg", { viewBox: `0 0 ${L} ${H}`, class: "graph", "aria-hidden": "true", focusable: "false" });
      conteneur.insertBefore(svg, conteneur.firstChild);
      const gy = el("g", { class: "grille-y" }, svg);
      ticks.forEach((t) => {
        el("line", { x1: x(t), x2: x(t), y1: m.haut, y2: H - m.bas }, gy);
        const tx = el("text", { x: x(t), y: H - m.bas + 18, "text-anchor": "middle" }, gy);
        tx.textContent = cfg.pourcent ? t + " %" : (cfg.formatAxe || PLF.fmt.nombre)(t);
      });

      const segments = [];
      cfg.categories.forEach((cat, i) => {
        const y0 = m.haut + i * (hauteurBarre + ecart) + (petit ? 22 : 0);
        const t = el("text", { x: petit ? m.gauche : m.gauche - 10, y: petit ? y0 - 7 : y0 + hauteurBarre / 2, "text-anchor": petit ? "start" : "end", "dominant-baseline": petit ? "auto" : "middle", "font-weight": 700, fill: PLF.couleur("--texte") }, svg);
        t.textContent = cat;
        let acc = 0;
        cfg.series.forEach((s, k) => {
          const brut = s.valeurs[i];
          if (brut == null || brut === 0) return;
          const v = cfg.pourcent ? (100 * brut) / totaux[i] : brut;
          const x0 = x(acc), x1 = x(acc + v);
          acc += v;
          const fond = PLF.couleur(s.couleur);
          const r = el("rect", { x: x0, y: y0, width: Math.max(0, x1 - x0), height: hauteurBarre, fill: fond, stroke: PLF.couleur("--surface"), "stroke-width": 1.5 }, svg);
          segments.push({ i, k, r, x0, x1, y0, v, brut });
          const texte = cfg.pourcent ? PLF.fmt.pourcent(v, 0) : fmtVal(v);
          if (x1 - x0 > texte.length * 7.5 + 10) {
            const tv = el("text", { x: (x0 + x1) / 2, y: y0 + hauteurBarre / 2, "text-anchor": "middle", "dominant-baseline": "central", class: "valeur-barre", fill: PLF.texteSur(fond) }, svg);
            tv.textContent = texte;
          }
        });
      });

      const ib = infobulle(conteneur);
      function montrer(seg, annonce) {
        segments.forEach((sg) => sg.r.setAttribute("stroke", PLF.couleur("--surface")));
        seg.r.setAttribute("stroke", PLF.couleur("--texte"));
        seg.r.parentNode.appendChild(seg.r);
        actif = [seg.i, seg.k];
        const s = cfg.series[seg.k];
        const part = (100 * seg.brut) / totaux[seg.i];
        ib.innerHTML = `<span class="infobulle__titre">${cfg.categories[seg.i]}</span><div class="infobulle__ligne"><span><i class="infobulle__pastille" style="background:${PLF.couleur(s.couleur)}"></i>${s.libelle}</span><b>${PLF.fmt.pourcent(part, 1)}</b></div>${cfg.valeursAbsolues !== false && !cfg.sansNombre ? `<div class="infobulle__ligne"><span>Effectif</span><b>${fmtVal(seg.brut)}</b></div>` : ""}`;
        const rr = svg.getBoundingClientRect();
        placerInfobulle(ib, conteneur, (((seg.x0 + seg.x1) / 2) / L) * rr.width, (seg.y0 / H) * rr.height);
        if (annonce) PLF.annoncer(`${cfg.categories[seg.i]}, ${s.libelle} : ${PLF.fmt.pourcent(part, 1)}${cfg.sansNombre ? "" : `, soit ${fmtVal(seg.brut)}`}.`);
      }
      function cacher() {
        segments.forEach((sg) => sg.r.setAttribute("stroke", PLF.couleur("--surface")));
        ib.hidden = true;
      }
      segments.forEach((seg) => {
        seg.r.addEventListener("pointerenter", () => montrer(seg, false));
        seg.r.addEventListener("pointerdown", () => montrer(seg, false));
      });
      svg.addEventListener("pointerleave", cacher);
      conteneur._segments = segments;
      conteneur._montrer = montrer;
      conteneur._cacher = cacher;
    }

    conteneur.addEventListener("keydown", (evt) => {
      const segs = conteneur._segments || [];
      if (!segs.length) return;
      let pos = actif ? segs.findIndex((s) => s.i === actif[0] && s.k === actif[1]) : -1;
      if (evt.key === "ArrowRight") pos = Math.min(segs.length - 1, pos + 1);
      else if (evt.key === "ArrowLeft") pos = Math.max(0, pos - 1);
      else if (evt.key === "ArrowDown" || evt.key === "ArrowUp") {
        const bar = actif ? actif[0] : 0;
        const cible = Math.max(0, Math.min(cfg.categories.length - 1, bar + (evt.key === "ArrowDown" ? 1 : -1)));
        const p = segs.findIndex((s) => s.i === cible);
        if (p >= 0) pos = p;
      } else if (evt.key === "Escape") { conteneur._cacher(); return; }
      else return;
      evt.preventDefault();
      conteneur._montrer(segs[Math.max(0, pos)], true);
    });
    conteneur.addEventListener("blur", () => conteneur._cacher && conteneur._cacher());
    function etiquetteAria() {
      conteneur.setAttribute("aria-label", `${cfg.titreAccessible || "Graphique en barres"}. Flèches gauche et droite pour parcourir les segments, haut et bas pour changer de barre. Le tableau de données est disponible juste après.`);
    }
    etiquetteAria();
    rendu();
    surRedimension(conteneur, rendu);
    return { maj(nouveau) { cfg = Object.assign({}, cfg, nouveau); etiquetteAria(); rendu(); } };
  }

  /* ======================================================================
     Gaufre : 100 carrés, un par point de pourcentage
     parts = [{libelle, valeur(en %), couleur}]
     ====================================================================== */
  function gaufre(conteneur, { parts, titre }) {
    conteneur.textContent = "";
    const cote = 10, ecart = 2.2, n = 10;
    const taille = n * cote + (n - 1) * ecart;
    const svg = el("svg", { viewBox: `0 0 ${taille} ${taille}`, role: "img", "aria-label": titre, class: "gaufre" });
    // Arrondi « au plus fort reste » pour que le total fasse exactement 100.
    const brut = parts.map((p) => p.valeur);
    const ent = brut.map(Math.floor);
    let reste = 100 - ent.reduce((a, b) => a + b, 0);
    brut.map((v, i) => [v - Math.floor(v), i]).sort((a, b) => b[0] - a[0]).forEach(([, i]) => { if (reste > 0) { ent[i]++; reste--; } });
    let k = 0;
    ent.forEach((nb, i) => {
      for (let j = 0; j < nb; j++, k++) {
        const ligne = Math.floor(k / n), col = k % n;
        el("rect", { x: col * (cote + ecart), y: ligne * (cote + ecart), width: cote, height: cote, rx: 2, fill: PLF.couleur(parts[i].couleur) }, svg);
      }
    });
    conteneur.appendChild(svg);
    return ent;
  }

  /* ======================================================================
     Sparkline : série d'un département et référence nationale
     ====================================================================== */
  function sparkline(conteneur, { annees, valeurs, reference, couleur, couleurRef, formatValeur, libelle, libelleRef }) {
    conteneur.textContent = "";
    const fmtv0 = formatValeur || PLF.fmt.decimal1;
    const derniere = valeurs.filter((v) => v != null).pop();
    const L = 300, H = 92, m = { g: 6, d: 14 + 7.2 * String(derniere == null ? "" : fmtv0(derniere)).length, h: 12, b: 18 };
    const toutes = valeurs.concat(reference || []).filter((v) => v != null);
    if (!toutes.length) return;
    let min = Math.min(...toutes), max = Math.max(...toutes);
    if (min === max) { min -= 1; max += 1; }
    const pad = (max - min) * 0.12;
    const x = echelle(annees[0], annees[annees.length - 1], m.g, L - m.d);
    const y = echelle(min - pad, max + pad, H - m.b, m.h);
    const svg = el("svg", { viewBox: `0 0 ${L} ${H}`, class: "graph sparkline", "aria-hidden": "true" });
    const trace = (vals, attrs) => {
      let d = "", ouvert = false;
      vals.forEach((v, i) => {
        if (v == null) { ouvert = false; return; }
        d += (ouvert ? "L" : "M") + x(annees[i]).toFixed(1) + " " + y(v).toFixed(1);
        ouvert = true;
      });
      return el("path", Object.assign({ d, fill: "none", "stroke-linejoin": "round", "stroke-linecap": "round" }, attrs), svg);
    };
    if (reference) trace(reference, { stroke: PLF.couleur(couleurRef || "--c-total"), "stroke-width": 1.8, "stroke-dasharray": "4 3" });
    trace(valeurs, { stroke: PLF.couleur(couleur || "--accent"), "stroke-width": 2.6 });
    const fmtv = formatValeur || PLF.fmt.decimal1;
    const der = valeurs.map((v, i) => [v, i]).filter(([v]) => v != null);
    if (der.length) {
      const [v, i] = der[der.length - 1];
      el("circle", { cx: x(annees[i]), cy: y(v), r: 3.5, fill: PLF.couleur(couleur || "--accent") }, svg);
      const t = el("text", { x: x(annees[i]) + 6, y: y(v), "dominant-baseline": "middle", "font-weight": 700, fill: PLF.couleur("--texte") }, svg);
      t.textContent = fmtv(v);
    }
    [annees[0], annees[annees.length - 1]].forEach((a, j) => {
      const t = el("text", { x: x(a), y: H - 3, "text-anchor": j ? "end" : "start", "font-size": 11 }, svg);
      t.textContent = a;
    });
    conteneur.appendChild(svg);
    const leg = document.createElement("p");
    leg.className = "figure__note";
    leg.style.marginTop = "0.2rem";
    leg.innerHTML = `<span style="color:${PLF.couleur(couleur || "--accent")};font-weight:700">━</span> ${libelle || "Département"} &nbsp; <span style="color:${PLF.couleur(couleurRef || "--c-total")};font-weight:700">╌</span> ${libelleRef || "France"}`;
    conteneur.appendChild(leg);
  }

  /* ======================================================================
     Colonnes : une valeur par année, positive ou négative (ex. variation
     annuelle du nombre d'agents)
     cfg = { annees, valeurs, couleurPositive, couleurNegative, formatValeur,
             formatAxe, titreAccessible, ruptures, noteAnnee }
     ====================================================================== */
  function colonnes(conteneur, cfgInitial) {
    let cfg = cfgInitial;
    let index = null;
    conteneur.classList.add("figure__graphique");
    conteneur.tabIndex = 0;
    conteneur.setAttribute("role", "group");
    conteneur.setAttribute("aria-roledescription", "graphique interactif");

    function rendu() {
      conteneur.querySelectorAll(":scope > svg").forEach((s) => s.remove());
      const L = Math.max(280, conteneur.clientWidth);
      const petit = L < 560;
      const H = Math.round(Math.max(240, Math.min(cfg.hauteur || 320, L * (petit ? 0.8 : 0.45))));
      const fmtVal = cfg.formatValeur || PLF.fmt.nombre;
      const fmtAxe = cfg.formatAxe || fmtVal;
      const vals = cfg.valeurs.filter((v) => v != null);
      const ticks = graduations(Math.min(0, ...vals), Math.max(0, ...vals), petit ? 4 : 6);
      const largeurEtiqY = Math.max(...ticks.map((t) => String(fmtAxe(t)).length)) * 7.4 + 14;
      const m = { haut: cfg.ruptures && cfg.ruptures.length ? 26 : 12, bas: 34, gauche: largeurEtiqY, droite: 12 };
      const n = cfg.annees.length;
      const pasX = (L - m.gauche - m.droite) / n;
      const xc = (i) => m.gauche + pasX * (i + 0.5);
      const y = echelle(ticks[0], ticks[ticks.length - 1], H - m.bas, m.haut);
      const svg = el("svg", { viewBox: `0 0 ${L} ${H}`, class: "graph", "aria-hidden": "true", focusable: "false" });
      conteneur.insertBefore(svg, conteneur.firstChild);
      const gy = el("g", { class: "grille-y" }, svg);
      ticks.forEach((t) => {
        el("line", { x1: m.gauche, x2: L - m.droite, y1: y(t), y2: y(t), style: t === 0 ? "stroke:var(--axe)" : null }, gy);
        const tx = el("text", { x: m.gauche - 8, y: y(t), "text-anchor": "end", "dominant-baseline": "middle" }, gy);
        tx.textContent = fmtAxe(t);
      });
      const pas = pasAnnees(n, L - m.gauche - m.droite);
      const gx = el("g", { class: "axe" }, svg);
      cfg.annees.forEach((a, i) => {
        if (a % pas !== 0) return;
        const tx = el("text", { x: xc(i), y: H - m.bas + 20, "text-anchor": "middle" }, gx);
        tx.textContent = a;
      });
      (cfg.ruptures || []).forEach((r) => {
        const i = cfg.annees.indexOf(r.annee);
        if (i <= 0) return;
        const xr = m.gauche + pasX * i;
        const g = el("g", { class: "rupture" }, svg);
        el("line", { x1: xr, x2: xr, y1: m.haut - 4, y2: H - m.bas }, g);
        const t = el("text", { x: xr + 4, y: m.haut - 8 }, g);
        if (xr > L * 0.75) { t.setAttribute("x", xr - 4); t.setAttribute("text-anchor", "end"); }
        t.textContent = r.court || "rupture de série";
      });
      const rects = cfg.valeurs.map((v, i) => {
        if (v == null) return null;
        const c = PLF.couleur(v >= 0 ? cfg.couleurPositive || "--c-fpt" : cfg.couleurNegative || "--c-fph");
        return el("rect", { x: xc(i) - pasX * 0.38, width: pasX * 0.76, y: Math.min(y(0), y(v)), height: Math.max(1, Math.abs(y(v) - y(0))), fill: c, rx: Math.min(3, pasX * 0.15) }, svg);
      });
      const zone = el("rect", { class: "zone-survol", x: m.gauche, y: m.haut, width: L - m.gauche - m.droite, height: H - m.bas - m.haut }, svg);
      const ib = infobulle(conteneur);
      function montrer(i, annonce) {
        index = i;
        rects.forEach((r, k) => r && r.setAttribute("stroke", k === i ? PLF.couleur("--texte") : "none"));
        const v = cfg.valeurs[i];
        const note = cfg.noteAnnee && cfg.noteAnnee(cfg.annees[i]);
        ib.innerHTML = `<span class="infobulle__titre">${cfg.etiquetteAnnee ? cfg.etiquetteAnnee(cfg.annees[i]) : cfg.annees[i]}</span><div class="infobulle__ligne"><span>${cfg.libelle || "Valeur"}</span><b>${v == null ? "n.d." : fmtVal(v)}</b></div>${note ? `<div style="margin-top:.3rem;font-style:italic;opacity:.85">${note}</div>` : ""}`;
        const rr = svg.getBoundingClientRect();
        placerInfobulle(ib, conteneur, (xc(i) / L) * rr.width, ((v == null ? y(0) : Math.min(y(0), y(v))) / H) * rr.height);
        if (annonce) PLF.annoncer(`${cfg.annees[i]} : ${v == null ? "donnée non disponible" : fmtVal(v)}${note ? `. ${note}` : ""}`);
      }
      function cacher() { rects.forEach((r) => r && r.setAttribute("stroke", "none")); ib.hidden = true; }
      const idx = (evt) => {
        const r = svg.getBoundingClientRect();
        const px = ((evt.clientX - r.left) / r.width) * L;
        return Math.max(0, Math.min(n - 1, Math.floor((px - m.gauche) / pasX)));
      };
      zone.addEventListener("pointermove", (e) => montrer(idx(e), false));
      zone.addEventListener("pointerdown", (e) => montrer(idx(e), false));
      zone.addEventListener("pointerleave", cacher);
      conteneur._montrer = montrer;
      conteneur._cacher = cacher;
    }
    conteneur.addEventListener("keydown", (evt) => {
      const n = cfg.annees.length;
      let i = index == null ? n - 1 : index;
      if (evt.key === "ArrowRight") i = Math.min(n - 1, i + 1);
      else if (evt.key === "ArrowLeft") i = Math.max(0, i - 1);
      else if (evt.key === "Home") i = 0;
      else if (evt.key === "End") i = n - 1;
      else if (evt.key === "Escape") { conteneur._cacher(); return; }
      else return;
      evt.preventDefault();
      conteneur._montrer(i, true);
    });
    conteneur.addEventListener("blur", () => conteneur._cacher && conteneur._cacher());
    conteneur.setAttribute("aria-label", `${cfg.titreAccessible || "Graphique en colonnes"}. Flèches gauche et droite pour parcourir les années. Le tableau de données est disponible juste après.`);
    rendu();
    surRedimension(conteneur, rendu);
    return { maj(nouveau) { cfg = Object.assign({}, cfg, nouveau); rendu(); } };
  }

  PLF.graphiques = { courbes, barres, colonnes, gaufre, sparkline, graduations, el };
})();
