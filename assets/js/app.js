/* ==========================================================================
   Fonctions communes à toutes les pages : options d'affichage, menu,
   formats de nombres à la française, tableaux accessibles, export CSV.
   Aucune dépendance externe, aucun cookie, aucun traceur.
   ========================================================================== */
(function () {
  "use strict";

  const racine = document.documentElement;
  const CLE_OPTIONS = "plf-fp-options";
  const DEFAUT = { theme: "auto", taille: "normal", police: "standard", interligne: "normal" };

  /* ---------- Options d'affichage (mémorisées dans ce navigateur seulement) ---------- */
  function lireOptions() {
    try {
      return Object.assign({}, DEFAUT, JSON.parse(localStorage.getItem(CLE_OPTIONS) || "{}"));
    } catch (e) {
      return Object.assign({}, DEFAUT);
    }
  }
  function ecrireOptions(options) {
    try { localStorage.setItem(CLE_OPTIONS, JSON.stringify(options)); } catch (e) { /* navigation privée */ }
  }
  const prefereSombre = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  function appliquerOptions(options) {
    const sombre = options.theme === "sombre" || (options.theme === "auto" && prefereSombre && prefereSombre.matches);
    const avant = racine.dataset.theme;
    racine.dataset.theme = sombre ? "sombre" : "clair";
    racine.dataset.taille = options.taille;
    racine.dataset.police = options.police;
    racine.dataset.interligne = options.interligne;
    if (avant !== racine.dataset.theme || PLF._initialise) {
      document.dispatchEvent(new CustomEvent("plf:affichage"));
    }
  }

  function initialiserOptions() {
    const options = lireOptions();
    appliquerOptions(options);
    if (prefereSombre && prefereSombre.addEventListener) {
      prefereSombre.addEventListener("change", () => appliquerOptions(lireOptions()));
    }
    const dialogue = document.getElementById("options-affichage");
    const ouvrir = document.querySelectorAll("[data-ouvrir-options]");
    if (!dialogue) return;
    // Pré-coche les choix courants.
    Object.keys(DEFAUT).forEach((cle) => {
      const champ = dialogue.querySelector(`input[name="${cle}"][value="${options[cle]}"]`);
      if (champ) champ.checked = true;
    });
    dialogue.addEventListener("change", (evt) => {
      const cible = evt.target;
      if (!cible.name || !(cible.name in DEFAUT)) return;
      const nouvelles = lireOptions();
      nouvelles[cible.name] = cible.value;
      ecrireOptions(nouvelles);
      appliquerOptions(nouvelles);
    });
    ouvrir.forEach((bouton) => {
      bouton.addEventListener("click", () => {
        if (typeof dialogue.showModal === "function") dialogue.showModal();
        else dialogue.setAttribute("open", "");
      });
    });
    dialogue.querySelectorAll("[data-fermer]").forEach((b) =>
      b.addEventListener("click", () => (dialogue.close ? dialogue.close() : dialogue.removeAttribute("open")))
    );
    const reinit = dialogue.querySelector("[data-reinitialiser]");
    if (reinit) {
      reinit.addEventListener("click", () => {
        ecrireOptions(DEFAUT);
        appliquerOptions(DEFAUT);
        Object.keys(DEFAUT).forEach((cle) => {
          const champ = dialogue.querySelector(`input[name="${cle}"][value="${DEFAUT[cle]}"]`);
          if (champ) champ.checked = true;
        });
      });
    }
    // Clic sur le fond : ferme le dialogue.
    dialogue.addEventListener("click", (evt) => {
      if (evt.target === dialogue && dialogue.close) dialogue.close();
    });
  }

  /* ---------- Menu sur petit écran ---------- */
  function initialiserMenu() {
    const nav = document.querySelector(".navigation");
    const bouton = document.querySelector(".navigation__bouton");
    if (!nav || !bouton) return;
    bouton.addEventListener("click", () => {
      const ouvert = nav.classList.toggle("ouverte");
      bouton.setAttribute("aria-expanded", String(ouvert));
    });
  }

  /* ---------- Formats français ---------- */
  const nf0 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const nf2 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmt = {
    nombre: (v) => (v == null || isNaN(v) ? "n.d." : nf0.format(Math.round(v))),
    // Arrondi au millier : « 5 663 400 » -> « 5 663 400 » ; option : arrondi lisible
    millier: (v) => (v == null || isNaN(v) ? "n.d." : nf0.format(Math.round(v / 100) * 100)),
    millions: (v, dec = 2) => (v == null || isNaN(v) ? "n.d." :
      new Intl.NumberFormat("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(v / 1e6) + " million" + (v >= 2e6 ? "s" : "")),
    axeMillions: (v) => (v === 0 ? "0" : new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(v / 1e6) + " M"),
    axeMilliers: (v) => (v === 0 ? "0" : nf0.format(v / 1000) + " k"),
    decimal1: (v) => (v == null || isNaN(v) ? "n.d." : nf1.format(v)),
    decimal2: (v) => (v == null || isNaN(v) ? "n.d." : nf2.format(v)),
    pourcent: (v, dec = 1) => (v == null || isNaN(v) ? "n.d." :
      new Intl.NumberFormat("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(v) + " %"),
    variation: (v, dec = 1) => (v == null || isNaN(v) ? "n.d." :
      (v > 0 ? "+" : v < 0 ? "−" : "") + new Intl.NumberFormat("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(Math.abs(v)) + " %"),
    ecart: (v, dec = 0) => (v == null || isNaN(v) ? "n.d." :
      (v > 0 ? "+" : v < 0 ? "−" : "") + new Intl.NumberFormat("fr-FR", { maximumFractionDigits: dec }).format(Math.abs(v))),
  };

  /* ---------- Couleurs définies dans la feuille de style ---------- */
  function couleur(nom) {
    if (!nom) return "#888";
    if (nom.startsWith("#") || nom.startsWith("rgb")) return nom;
    const v = getComputedStyle(racine).getPropertyValue(nom.startsWith("--") ? nom : "--" + nom).trim();
    return v || "#888";
  }
  // Texte lisible (noir ou blanc) sur une couleur de fond donnée.
  function texteSur(fond) {
    const hex = couleur(fond).replace("#", "");
    if (hex.length < 6) return "#fff";
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((c) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)));
    const l = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    return l > 0.22 ? "#0f2930" : "#ffffff";
  }

  /* ---------- Données ---------- */
  function donnees(nom) {
    const d = window.PLF_DONNEES && window.PLF_DONNEES[nom];
    if (!d) throw new Error(`Données « ${nom} » introuvables : le fichier donnees/site/${nom}.js est-il chargé ?`);
    return d;
  }

  /* ---------- Tableau de données accessible ---------- */
  // colonnes : [{titre, cle, format?, texte?(bool), tri?(bool)}], lignes : [{...}]
  function tableau({ legende, colonnes, lignes, triable = false, entetesLignes = true }) {
    const t = document.createElement("table");
    if (legende != null) {
      const c = t.createCaption();
      c.textContent = legende;
    }
    const thead = t.createTHead();
    const tr = thead.insertRow();
    colonnes.forEach((col, i) => {
      const th = document.createElement("th");
      th.scope = "col";
      if (col.texte) th.className = "texte";
      if (triable && col.tri !== false) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "tri";
        b.textContent = col.titre;
        b.addEventListener("click", () => trier(t, i, col));
        th.appendChild(b);
        th.setAttribute("aria-sort", "none");
      } else {
        th.textContent = col.titre;
      }
      tr.appendChild(th);
    });
    const tbody = t.createTBody();
    remplirCorps(tbody, colonnes, lignes, entetesLignes);
    t._colonnes = colonnes;
    t._lignes = lignes.slice();
    t._entetesLignes = entetesLignes;
    return t;
  }
  function remplirCorps(tbody, colonnes, lignes, entetesLignes) {
    tbody.textContent = "";
    lignes.forEach((ligne) => {
      const r = tbody.insertRow();
      if (ligne._classe) r.className = ligne._classe;
      colonnes.forEach((col, i) => {
        const cell = document.createElement(i === 0 && entetesLignes ? "th" : "td");
        if (i === 0 && entetesLignes) cell.scope = "row";
        if (col.texte) cell.className = "texte";
        const v = ligne[col.cle];
        cell.textContent = col.format ? col.format(v, ligne) : v == null ? "n.d." : v;
        r.appendChild(cell);
      });
    });
  }
  function trier(table, index, col) {
    const ths = table.tHead.rows[0].cells;
    const actuel = ths[index].getAttribute("aria-sort");
    const sens = actuel === "ascending" ? "descending" : "ascending";
    Array.from(ths).forEach((th) => th.hasAttribute("aria-sort") && th.setAttribute("aria-sort", "none"));
    ths[index].setAttribute("aria-sort", sens);
    const cle = col.cleTri || col.cle;
    const lignes = table._lignes.slice().sort((a, b) => {
      const va = a[cle], vb = b[cle];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const r = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb), "fr", { numeric: true });
      return sens === "ascending" ? r : -r;
    });
    remplirCorps(table.tBodies[0], table._colonnes, lignes, table._entetesLignes);
    annoncer(`Tableau trié par ${col.titre}, ordre ${sens === "ascending" ? "croissant" : "décroissant"}.`);
  }
  function majTableau(table, lignes) {
    table._lignes = lignes.slice();
    const th = Array.from(table.tHead.rows[0].cells).findIndex((c) => c.getAttribute("aria-sort") && c.getAttribute("aria-sort") !== "none");
    if (th >= 0) {
      const sens = table.tHead.rows[0].cells[th].getAttribute("aria-sort");
      table.tHead.rows[0].cells[th].setAttribute("aria-sort", sens === "ascending" ? "descending" : "ascending");
      trier(table, th, table._colonnes[th]);
    } else {
      remplirCorps(table.tBodies[0], table._colonnes, lignes, table._entetesLignes);
    }
  }
  function enveloppe(table, haut) {
    const div = document.createElement("div");
    div.className = "tableau-defilant" + (haut ? " tableau-defilant--haut" : "");
    div.tabIndex = 0;
    div.setAttribute("role", "region");
    div.setAttribute("aria-label", (table.caption && table.caption.textContent) || "Tableau de données");
    div.appendChild(table);
    return div;
  }

  /* ---------- Export CSV (séparateur « ; » et virgule décimale, comme Excel en français) ---------- */
  function csv(nomFichier, entetes, lignes) {
    const echap = (v) => {
      if (v == null) return "";
      const s = typeof v === "number" ? String(v).replace(".", ",") : String(v);
      return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const contenu = "﻿" + [entetes, ...lignes].map((l) => l.map(echap).join(";")).join("\r\n");
    const blob = new Blob([contenu], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = nomFichier;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }

  /* ---------- Annonces pour les lecteurs d'écran ---------- */
  let zoneAnnonce;
  function annoncer(texte) {
    if (!zoneAnnonce) {
      zoneAnnonce = document.createElement("div");
      zoneAnnonce.className = "visuellement-cache";
      zoneAnnonce.setAttribute("aria-live", "polite");
      zoneAnnonce.setAttribute("aria-atomic", "true");
      document.body.appendChild(zoneAnnonce);
    }
    zoneAnnonce.textContent = "";
    window.setTimeout(() => { zoneAnnonce.textContent = texte; }, 60);
  }

  /* ---------- Bloc « Afficher les données » sous un graphique ---------- */
  function blocDonnees(parent, { resume = "Afficher les données sous forme de tableau", table, csvNom, csvEntetes, csvLignes }) {
    const details = document.createElement("details");
    details.className = "donnees";
    const summary = document.createElement("summary");
    summary.textContent = resume;
    details.appendChild(summary);
    details.appendChild(enveloppe(table));
    if (csvNom) {
      const p = document.createElement("p");
      p.className = "figure__actions";
      const b = document.createElement("button");
      b.type = "button";
      b.className = "bouton bouton--secondaire";
      b.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v12m0 0-5-5m5 5 5-5M4 21h16"/></svg>Télécharger ces données (CSV)';
      b.addEventListener("click", () => csv(csvNom, csvEntetes, typeof csvLignes === "function" ? csvLignes() : csvLignes));
      p.appendChild(b);
      details.appendChild(p);
    }
    parent.appendChild(details);
    return details;
  }

  const PLF = (window.PLF = window.PLF || {});
  Object.assign(PLF, { fmt, couleur, texteSur, donnees, tableau, majTableau, enveloppe, csv, annoncer, blocDonnees, lireOptions });

  function demarrer() {
    initialiserOptions();
    initialiserMenu();
    PLF._initialise = true;
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", demarrer);
  else demarrer();
})();
