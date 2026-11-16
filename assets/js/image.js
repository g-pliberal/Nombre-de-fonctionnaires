/* ==========================================================================
   « Télécharger l'image (PNG) » : sous chaque graphique, un bouton fabrique
   une image prête à partager sur les réseaux sociaux. L'image reprend le
   graphique tel qu'il est affiché (titre, légende, réglages choisis, note et
   source), et ajoute en bas un bandeau avec le logo, le nom du site et
   l'adresse de la page.

   Tout se passe dans le navigateur, sans dépendance ni envoi de données :
   les graphiques SVG sont copiés avec leurs styles calculés puis dessinés sur
   un <canvas>, et les textes, fonds et bordures HTML y sont redessinés à leur
   place exacte.
   ========================================================================== */
(function () {
  "use strict";

  const PLF = window.PLF || {};
  const SCRIPT = document.currentScript && document.currentScript.src;
  const ressource = (chemin) => new URL(chemin, SCRIPT || document.baseURI).href;
  const NS = "http://www.w3.org/2000/svg";

  const NOM_PARTI = "Parti Libéral Français";
  const NOM_SITE = "Fonction publique : les chiffres";
  // Charte graphique (assets/css/style.css), comme les images de partage.
  const BANDEAU = { fond: "#00242e", filet: "#e9c53d", parti: "#e9c53d", site: "#ffffff", adresse: "#c4d8dc" };
  const POLICE_TITRES = '"Jost", "Futura", "Century Gothic", "Avenir Next", system-ui, sans-serif';
  const POLICE_TEXTE = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

  // Une figure plus étroite (téléphone) est élargie le temps de la capture,
  // pour obtenir une image lisible, au format paysage.
  const LARGEUR_MIN = 640;
  const LARGEUR_ELARGIE = 760;
  const PIXELS_MIN = 1600; // largeur minimale de l'image, en pixels

  // Éléments de l'interface qui n'ont pas leur place dans l'image.
  const EXCLUS = [
    "form", "details", "button", "input", "select", "textarea", "label", "noscript", "script", "style", "template",
    "[hidden]", ".visuellement-cache", ".figure__actions", ".infobulle", ".fiche-dep", ".palmares",
    ".selecteur-dep", ".recherche", "[data-image-exclure]",
  ].join(",");

  /* ---------- Outils ---------- */
  const attendre = (ms) => new Promise((ok) => setTimeout(ok, ms));
  const image = () => new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok)));
  function chargerImage(src) {
    return new Promise((ok, ko) => {
      const im = new Image();
      im.onload = () => ok(im);
      im.onerror = () => ko(new Error("Image illisible : " + src.slice(0, 80)));
      im.src = src;
    });
  }
  function transparent(couleur) {
    return !couleur || couleur === "transparent" || /^rgba\([^,]+,[^,]+,[^,]+,\s*0(\.0*)?\)$/.test(couleur) || /\/\s*0(\.0*)?\)$/.test(couleur);
  }
  function fondDe(el) {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const c = getComputedStyle(n).backgroundColor;
      if (!transparent(c)) return c;
    }
    return getComputedStyle(document.body).backgroundColor || "#ffffff";
  }
  function nomFichier(titre) {
    const s = (titre || "graphique").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
      .replace(/œ/g, "oe").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    const court = s.length > 70 ? s.slice(0, 70).replace(/-+[^-]*$/, "") : s;
    return "fonction-publique-" + (court || "graphique") + ".png";
  }
  function adressePage(cible) {
    const meta = document.querySelector('meta[property="og:url"]');
    let url = (meta && meta.content) || location.href.split(/[?#]/)[0];
    const section = cible.closest("section[id]");
    const ancre = cible.id || (section ? section.id : "");
    if (ancre) url += "#" + ancre;
    return url.replace(/^https?:\/\//, "");
  }

  /* ---------- Polices intégrées aux SVG (une image SVG ne voit pas les polices de la page) ---------- */
  const POLICES = {
    Jost: [["jost-latin-variable.woff2", "400 800", "normal"]],
    "Atkinson Hyperlegible": [
      ["atkinson-hyperlegible-400.woff2", "400", "normal"],
      ["atkinson-hyperlegible-700.woff2", "700", "normal"],
      ["atkinson-hyperlegible-400-italic.woff2", "400", "italic"],
    ],
  };
  const cachePolices = {};
  function policeEnDataUrl(fichier) {
    if (!cachePolices[fichier]) {
      cachePolices[fichier] = fetch(ressource("../fonts/" + fichier))
        .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(r.status))))
        .then((b) => new Promise((ok) => { const l = new FileReader(); l.onload = () => ok(l.result); l.readAsDataURL(b); }))
        .catch(() => null);
    }
    return cachePolices[fichier];
  }
  async function cssPolices(familles) {
    const regles = [];
    for (const nom of Object.keys(POLICES)) {
      if (![...familles].some((f) => f.includes(nom))) continue;
      for (const [fichier, graisse, style] of POLICES[nom]) {
        const url = await policeEnDataUrl(fichier);
        if (url) regles.push(`@font-face{font-family:"${nom}";src:url(${url}) format("woff2");font-weight:${graisse};font-style:${style}}`);
      }
    }
    return regles.join("");
  }

  /* ---------- SVG -> image, avec les styles calculés ---------- */
  const PROPRIETES_SVG = [
    "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width", "stroke-opacity", "stroke-dasharray",
    "stroke-dashoffset", "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "opacity", "display",
    "visibility", "font-family", "font-size", "font-weight", "font-style", "text-anchor", "dominant-baseline",
    "letter-spacing", "paint-order", "vector-effect", "shape-rendering", "clip-path", "mask", "marker-start",
    "marker-mid", "marker-end", "stop-color", "stop-opacity",
  ];
  function copierStyles(source, copie, familles) {
    if (source.nodeType !== 1) return;
    const cs = getComputedStyle(source);
    const decl = PROPRIETES_SVG.map((p) => {
      const v = cs.getPropertyValue(p);
      return v ? `${p}:${v}` : "";
    }).filter(Boolean);
    if (source.tagName === "text" || source.tagName === "tspan") familles.add(cs.fontFamily);
    copie.setAttribute("style", decl.join(";"));
    copie.removeAttribute("class");
    for (let i = 0; i < source.children.length; i++) copierStyles(source.children[i], copie.children[i], familles);
  }
  async function svgEnImage(svg, rect) {
    const copie = svg.cloneNode(true);
    const familles = new Set();
    copierStyles(svg, copie, familles);
    copie.setAttribute("xmlns", NS);
    copie.setAttribute("width", rect.width);
    copie.setAttribute("height", rect.height);
    copie.style.overflow = "visible";
    copie.removeAttribute("aria-hidden");
    // Motifs ou dégradés définis ailleurs dans la page (ex. hachures de la carte).
    const references = new Set();
    const texte = new XMLSerializer().serializeToString(copie);
    texte.replace(/url\(\s*(?:["']|&quot;)?#([^"'&)]+)(?:["']|&quot;)?\s*\)/g, (_, id) => references.add(id));
    copie.querySelectorAll("use").forEach((u) => {
      const h = u.getAttribute("href") || u.getAttribute("xlink:href");
      if (h && h[0] === "#") references.add(h.slice(1));
    });
    const defs = document.createElementNS(NS, "defs");
    references.forEach((id) => {
      if (copie.querySelector(`[id="${CSS.escape(id)}"]`)) return;
      const original = document.getElementById(id);
      if (!original) return;
      const c = original.cloneNode(true);
      copierStyles(original, c, familles);
      defs.appendChild(c);
    });
    const css = await cssPolices(familles);
    if (css) {
      const style = document.createElementNS(NS, "style");
      style.textContent = css;
      defs.appendChild(style);
    }
    if (defs.childNodes.length) copie.insertBefore(defs, copie.firstChild);
    const blob = new Blob([new XMLSerializer().serializeToString(copie)], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    try {
      return await chargerImage(url);
    } finally {
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  }

  /* ---------- Relevé de ce qu'il faut dessiner (ordre du document) ---------- */
  function rayons(cs) {
    return ["borderTopLeftRadius", "borderTopRightRadius", "borderBottomRightRadius", "borderBottomLeftRadius"]
      .map((p) => parseFloat(cs[p]) || 0);
  }
  function relever(racine) {
    const ops = [];
    const o = racine.getBoundingClientRect();
    // Les réglages retirés de l'image (formulaire, boutons) ne laissent pas de blanc :
    // ce qui suit remonte d'autant.
    const trous = [];
    const enfants = Array.from(racine.children);
    enfants.forEach((el, k) => {
      if (!el.matches(EXCLUS) || getComputedStyle(el).display === "none") return;
      const suivant = enfants.slice(k + 1).find((n) => !n.matches(EXCLUS) && getComputedStyle(n).display !== "none");
      if (!suivant) return;
      const debut = el.getBoundingClientRect().top;
      const fin = suivant.getBoundingClientRect().top;
      if (fin > debut) trous.push({ debut, fin });
    });
    const decaler = (r) => {
      let d = 0;
      trous.forEach((t) => { if (r.top >= t.fin - 0.5) d += t.fin - t.debut; });
      return { left: r.left, top: r.top - d, width: r.width, height: r.height, bottom: r.bottom - d };
    };
    let bas = 0;
    const etendre = (r) => { if (r.width > 0 && r.height > 0) bas = Math.max(bas, r.bottom - o.top); };
    const plage = document.createRange();

    function texte(noeud) {
      const parent = noeud.parentElement;
      const cs = getComputedStyle(parent);
      if (cs.visibility !== "visible") return;
      const brut = noeud.textContent;
      if (!brut.trim()) return;
      const police = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      const casse = cs.textTransform;
      const tr = (s) => (casse === "uppercase" ? s.toLocaleUpperCase("fr") : casse === "lowercase" ? s.toLocaleLowerCase("fr") : s);
      const re = /\S+/g;
      let m;
      while ((m = re.exec(brut))) {
        plage.setStart(noeud, m.index);
        plage.setEnd(noeud, m.index + m[0].length);
        const rects = plage.getClientRects();
        if (rects.length <= 1) {
          const r = rects[0] && decaler(rects[0]);
          if (r && r.width) { ops.push({ t: "texte", s: tr(m[0]), r, police, couleur: cs.color, espacement: cs.letterSpacing }); etendre(r); }
        } else {
          // Mot coupé sur deux lignes (adresses, noms de fichiers) : lettre par lettre.
          for (let k = 0; k < m[0].length; k++) {
            plage.setStart(noeud, m.index + k);
            plage.setEnd(noeud, m.index + k + 1);
            const r = decaler(plage.getBoundingClientRect());
            if (r.width) { ops.push({ t: "texte", s: tr(m[0][k]), r, police, couleur: cs.color }); etendre(r); }
          }
        }
      }
    }

    function element(el, estRacine) {
      if (!estRacine && el.matches(EXCLUS)) return;
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.opacity === "0") return;
      const r = decaler(el.getBoundingClientRect());
      if (!estRacine && r.width <= 1 && r.height <= 1 && cs.overflow !== "visible") return;
      const opacite = parseFloat(cs.opacity);
      if (opacite < 1) ops.push({ t: "opacite+", v: opacite });

      if (el instanceof SVGSVGElement) {
        if (cs.visibility === "visible" && r.width > 0 && r.height > 0) {
          // Fond et cadre posés en CSS sur le <svg> lui-même (la mer, sur les cartes).
          if (!transparent(cs.backgroundColor)) ops.push({ t: "fond", r, couleur: cs.backgroundColor, rayons: rayons(cs) });
          ops.push({ t: "svg", el, r });
          const cotes = ["Top", "Right", "Bottom", "Left"].map((c) => ({
            l: parseFloat(cs[`border${c}Width`]) || 0, style: cs[`border${c}Style`], couleur: cs[`border${c}Color`],
          }));
          if (cotes.some((c) => c.l > 0 && c.style !== "none" && !transparent(c.couleur))) ops.push({ t: "bordure", r, cotes, rayons: rayons(cs) });
          etendre(r);
        }
      } else if (el instanceof SVGElement) {
        // élément SVG isolé hors d'un <svg> : ignoré
      } else {
        if (!estRacine && cs.visibility === "visible" && r.width > 0 && r.height > 0) {
          if (!transparent(cs.backgroundColor)) { ops.push({ t: "fond", r, couleur: cs.backgroundColor, rayons: rayons(cs) }); etendre(r); }
          const cotes = ["Top", "Right", "Bottom", "Left"].map((c) => ({
            l: parseFloat(cs[`border${c}Width`]) || 0, style: cs[`border${c}Style`], couleur: cs[`border${c}Color`],
          }));
          if (cotes.some((c) => c.l > 0 && c.style !== "none" && c.style !== "hidden" && !transparent(c.couleur))) {
            ops.push({ t: "bordure", r, cotes, rayons: rayons(cs) });
            etendre(r);
          }
          if ((el.tagName === "IMG" && el.complete && el.naturalWidth) || el.tagName === "CANVAS") {
            ops.push({ t: "img", el, r });
            etendre(r);
          }
        }
        const coupe = !estRacine && (cs.overflowX !== "visible" || cs.overflowY !== "visible");
        if (coupe) ops.push({ t: "coupe+", r, rayons: rayons(cs) });
        el.childNodes.forEach((n) => {
          if (n.nodeType === 3) texte(n);
          else if (n.nodeType === 1) element(n, false);
        });
        if (coupe) ops.push({ t: "coupe-" });
      }
      if (opacite < 1) ops.push({ t: "opacite-" });
    }

    element(racine, true);
    const retire = trous.reduce((a, t) => a + t.fin - t.debut, 0);
    return { ops, origine: o, bas, hauteur: o.height - retire };
  }

  /* ---------- Dessin ---------- */
  function cheminArrondi(ctx, x, y, l, h, r) {
    ctx.beginPath();
    if (ctx.roundRect && r.some((v) => v > 0)) ctx.roundRect(x, y, l, h, r.map((v) => Math.min(v, l / 2, h / 2)));
    else ctx.rect(x, y, l, h);
  }
  const metriques = {};
  function dessinerOps(ctx, ops, ox, oy, images) {
    for (const op of ops) {
      if (op.t === "opacite+") { ctx.save(); ctx.globalAlpha *= op.v; continue; }
      if (op.t === "opacite-") { ctx.restore(); continue; }
      if (op.t === "coupe+") {
        ctx.save();
        cheminArrondi(ctx, op.r.left - ox, op.r.top - oy, op.r.width, op.r.height, op.rayons);
        ctx.clip();
        continue;
      }
      if (op.t === "coupe-") { ctx.restore(); continue; }
      const r = op.r;
      const x = r.left - ox, y = r.top - oy;
      if (op.t === "fond") {
        ctx.fillStyle = op.couleur;
        cheminArrondi(ctx, x, y, r.width, r.height, op.rayons);
        ctx.fill();
      } else if (op.t === "bordure") {
        const [h, d, b, g] = op.cotes;
        const pareil = op.cotes.every((c) => c.l === h.l && c.style === h.style && c.couleur === h.couleur);
        const tirets = (c) => (c.style === "dashed" ? [c.l * 3, c.l * 2] : c.style === "dotted" ? [c.l, c.l] : []);
        if (pareil && h.l > 0) {
          ctx.strokeStyle = h.couleur;
          ctx.lineWidth = h.l;
          ctx.setLineDash(tirets(h));
          cheminArrondi(ctx, x + h.l / 2, y + h.l / 2, r.width - h.l, r.height - h.l, op.rayons.map((v) => Math.max(0, v - h.l / 2)));
          ctx.stroke();
        } else {
          const traits = [
            [h, x, y + h.l / 2, x + r.width, y + h.l / 2],
            [d, x + r.width - d.l / 2, y, x + r.width - d.l / 2, y + r.height],
            [b, x, y + r.height - b.l / 2, x + r.width, y + r.height - b.l / 2],
            [g, x + g.l / 2, y, x + g.l / 2, y + r.height],
          ];
          traits.forEach(([c, x1, y1, x2, y2]) => {
            if (!(c.l > 0) || c.style === "none" || c.style === "hidden" || transparent(c.couleur)) return;
            ctx.strokeStyle = c.couleur;
            ctx.lineWidth = c.l;
            ctx.lineCap = op.rayons.some((v) => v > 0) ? "round" : "butt";
            ctx.setLineDash(tirets(c));
            ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
          });
          ctx.lineCap = "butt";
        }
        ctx.setLineDash([]);
      } else if (op.t === "texte") {
        ctx.font = op.police;
        ctx.fillStyle = op.couleur;
        if ("letterSpacing" in ctx) ctx.letterSpacing = op.espacement && op.espacement !== "normal" ? op.espacement : "0px";
        let m = metriques[op.police];
        if (!m) {
          const t = ctx.measureText("Hg");
          const taille = parseFloat(ctx.font) || 16;
          m = metriques[op.police] = {
            asc: t.fontBoundingBoxAscent != null ? t.fontBoundingBoxAscent : taille * 0.8,
            desc: t.fontBoundingBoxDescent != null ? t.fontBoundingBoxDescent : taille * 0.2,
          };
        }
        ctx.textBaseline = "alphabetic";
        ctx.fillText(op.s, x, y + (r.height - m.asc - m.desc) / 2 + m.asc);
      } else if (op.t === "svg" || op.t === "img") {
        const im = op.t === "svg" ? images.get(op) : op.el;
        if (im) ctx.drawImage(im, x, y, r.width, r.height);
      }
    }
    if ("letterSpacing" in ctx) ctx.letterSpacing = "0px";
  }

  // Bandeau du bas : logo, nom du parti et du site, adresse de la page.
  function hauteurBandeau(ctx, largeur, adresse) {
    ctx.font = `400 15px ${POLICE_TEXTE}`;
    const lAdresse = ctx.measureText(adresse).width;
    ctx.font = `600 17px ${POLICE_TITRES}`;
    const lNoms = 52 + Math.max(ctx.measureText(NOM_PARTI).width, ctx.measureText(NOM_SITE).width + 2);
    const surUneLigne = 24 + lNoms + 32 + lAdresse + 24 <= largeur;
    return { h: surUneLigne ? 78 : 104, surUneLigne };
  }
  function dessinerBandeau(ctx, y, largeur, b, adresse, logo) {
    ctx.fillStyle = BANDEAU.fond;
    ctx.fillRect(0, y, largeur, b.h);
    ctx.fillStyle = BANDEAU.filet;
    ctx.fillRect(0, y, largeur, 4);
    let x = 24;
    const haut = y + 4 + (b.surUneLigne ? (b.h - 4) / 2 - 20 : 14);
    if (logo) {
      const hl = 34;
      const ll = (logo.naturalWidth / logo.naturalHeight) * hl || hl;
      ctx.drawImage(logo, x, haut + 3, ll, hl);
      x += ll + 14;
    }
    ctx.textBaseline = "alphabetic";
    ctx.font = `600 17px ${POLICE_TITRES}`;
    ctx.fillStyle = BANDEAU.parti;
    ctx.fillText(NOM_PARTI, x, haut + 16);
    ctx.font = `500 16px ${POLICE_TITRES}`;
    ctx.fillStyle = BANDEAU.site;
    ctx.fillText(NOM_SITE, x, haut + 37);
    ctx.font = `400 15px ${POLICE_TEXTE}`;
    ctx.fillStyle = BANDEAU.adresse;
    if (b.surUneLigne) {
      ctx.textAlign = "right";
      ctx.fillText(adresse, largeur - 24, y + 4 + (b.h - 4) / 2 + 5);
      ctx.textAlign = "left";
    } else {
      ctx.fillText(adresse, 24, y + b.h - 16, largeur - 48);
    }
  }

  let logoPromesse;
  function logo() {
    if (!logoPromesse) logoPromesse = chargerImage(ressource("../img/logo-plf.svg")).catch(() => null);
    return logoPromesse;
  }

  /* ---------- Fabrication de l'image d'une figure ---------- */
  async function fabriquer(cible) {
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    const largeurInitiale = cible.getBoundingClientRect().width;
    const elargir = largeurInitiale < LARGEUR_MIN;
    const styleInitial = cible.getAttribute("style");
    if (elargir) {
      cible.style.width = LARGEUR_ELARGIE + "px";
      cible.style.maxWidth = "none";
      await attendre(260); // les graphiques se redessinent à la nouvelle largeur
      await image();
    }
    let releve, images;
    try {
      releve = relever(cible);
      images = new Map();
      await Promise.all(releve.ops.filter((op) => op.t === "svg").map(async (op) => {
        try { images.set(op, await svgEnImage(op.el, op.r)); } catch (e) { /* graphique ignoré */ }
      }));
    } finally {
      if (elargir) {
        if (styleInitial == null) cible.removeAttribute("style");
        else cible.setAttribute("style", styleInitial);
      }
    }
    const { ops, origine, bas, hauteur } = releve;
    const cs = getComputedStyle(cible);
    const padding = parseFloat(cs.paddingBottom) || 0;
    const marge = padding >= 12 ? 0 : 24; // une zone sans marge intérieure (carte) reçoit une marge
    const largeurContenu = Math.ceil(origine.width);
    const hauteurContenu = Math.ceil(Math.min(hauteur, bas + Math.max(padding, 16)));
    const L = largeurContenu + 2 * marge;
    const adresse = adressePage(cible);
    const mesure = document.createElement("canvas").getContext("2d");
    const b = hauteurBandeau(mesure, L, adresse);
    const H = hauteurContenu + 2 * marge + b.h;
    const echelle = Math.min(3, Math.max(2, PIXELS_MIN / L));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(L * echelle);
    canvas.height = Math.round(H * echelle);
    const ctx = canvas.getContext("2d");
    ctx.scale(echelle, echelle);
    ctx.fillStyle = fondDe(cible);
    ctx.fillRect(0, 0, L, H - b.h);
    ctx.save();
    ctx.translate(marge, marge);
    ctx.beginPath();
    ctx.rect(0, 0, largeurContenu, hauteurContenu);
    ctx.clip();
    dessinerOps(ctx, ops, origine.left, origine.top, images);
    ctx.restore();
    dessinerBandeau(ctx, H - b.h, L, b, adresse, await logo());
    return new Promise((ok, ko) => canvas.toBlob((blob) => (blob ? ok(blob) : ko(new Error("Image vide"))), "image/png"));
  }

  function telecharger(blob, nom) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = nom;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }

  /* ---------- Boutons ---------- */
  const ICONE = '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 17-5-5-9 8"/></svg>';
  const LIBELLE = "Télécharger l'image (PNG)";

  function cibles() {
    const liste = Array.from(document.querySelectorAll("figure.figure"));
    document.querySelectorAll(".carte-zone").forEach((z) => { if (!z.closest("figure")) liste.push(z); });
    return liste.filter((f) => !f.querySelector("[data-image-figure]") && !f.hasAttribute("data-image-exclure"));
  }
  function titreDe(cible) {
    const t = cible.querySelector(".figure__titre, .carte-titre, h2, h3");
    return t ? t.textContent.replace(/\s+/g, " ").trim() : "";
  }

  function ajouterBouton(cible) {
    const p = document.createElement("p");
    p.className = "figure__actions figure__actions--image";
    const bouton = document.createElement("button");
    bouton.type = "button";
    bouton.className = "bouton bouton--secondaire";
    bouton.dataset.imageFigure = "";
    bouton.innerHTML = ICONE + `<span>${LIBELLE}</span>`;
    // Le nom du graphique complète le libellé pour les lecteurs d'écran.
    const idTitre = cible.getAttribute("aria-labelledby") || (cible.querySelector(".carte-titre") || {}).id;
    if (idTitre) bouton.setAttribute("aria-describedby", idTitre);
    let enCours = false;
    bouton.addEventListener("click", async () => {
      if (enCours) return;
      enCours = true;
      bouton.setAttribute("aria-busy", "true");
      const span = bouton.querySelector("span");
      span.textContent = "Préparation de l'image…";
      try {
        const nom = nomFichier(titreDe(cible));
        telecharger(await fabriquer(cible), nom);
        if (PLF.annoncer) PLF.annoncer(`Image du graphique téléchargée : ${nom}.`);
      } catch (e) {
        if (PLF.annoncer) PLF.annoncer("L'image n'a pas pu être créée par ce navigateur.");
        if (window.console) console.error(e);
      } finally {
        span.textContent = LIBELLE;
        bouton.removeAttribute("aria-busy");
        enCours = false;
      }
    });
    p.appendChild(bouton);
    if (cible.classList.contains("carte-zone")) {
      cible.insertAdjacentElement("afterend", p);
    } else {
      // Juste après la note (source), avant le tableau de données et son export CSV.
      const notes = Array.from(cible.children).filter((n) => n.classList.contains("figure__note"));
      const apres = notes[notes.length - 1];
      if (apres) apres.insertAdjacentElement("afterend", p);
      else cible.appendChild(p);
    }
  }

  function demarrer() {
    if (!document.createElement("canvas").getContext || !window.Blob || !window.XMLSerializer) return;
    cibles().forEach(ajouterBouton);
  }
  PLF.imageFigure = fabriquer;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", demarrer);
  else demarrer();
})();
