/* ==========================================================================
   Test d'accessibilité automatique (axe-core), règles WCAG 2.0, 2.1 et 2.2
   niveaux A et AA, que reprend le RGAA 4.1, et bonnes pratiques d'axe.

   Chaque page est ouverte dans Chromium (Playwright), une fois en thème clair
   et une fois en thème sombre, sur grand écran et sur écran de téléphone,
   après le dessin des graphiques ; sur la page d'accueil, le menu et le
   dialogue « Options d'affichage » sont aussi testés ouverts.
   Le test échoue s'il trouve une violation ou une erreur JavaScript.

   Usage :  npm install && npm run test:accessibilite
            node outils/test_accessibilite.mjs index.html carte.html   (pages choisies)

   Un test automatique ne couvre qu'une partie du RGAA (environ 30 % des
   critères) : il ne remplace pas un audit manuel.
   ========================================================================== */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { extname, join, normalize, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const require = createRequire(import.meta.url);
const RACINE = join(dirname(fileURLToPath(import.meta.url)), "..");
const AXE = await readFile(require.resolve("axe-core/axe.min.js"), "utf8");

const PAGES = process.argv.slice(2).length
  ? process.argv.slice(2)
  : ["index.html", "evolution.html", "carte.html", "composition.html",
     "masse-salariale.html", "salaires.html", "retraites.html", "europe.html", "idees-recues.html",
     "methode.html"];
const THEMES = ["clair", "sombre"];
const ECRANS = [
  { nom: "ordinateur", width: 1280, height: 900 },
  { nom: "téléphone", width: 375, height: 800 },
];
// Critères WCAG A et AA, plus les bonnes pratiques axe (repères uniques, titres…).
const NORMES = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"];

/* ---------- Petit serveur statique (le site n'en a pas besoin, le test oui) ---------- */
const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".woff2": "font/woff2",
  ".json": "application/json", ".csv": "text/csv; charset=utf-8",
};
const serveur = createServer(async (req, res) => {
  const chemin = normalize(decodeURIComponent(new URL(req.url, "http://x").pathname)).replace(/^([/\\])+/, "");
  try {
    const contenu = await readFile(join(RACINE, chemin || "index.html"));
    res.writeHead(200, { "Content-Type": TYPES[extname(chemin)] || "application/octet-stream" });
    res.end(contenu);
  } catch {
    res.writeHead(404); res.end();
  }
});
await new Promise((ok) => serveur.listen(0, "127.0.0.1", ok));
const base = `http://127.0.0.1:${serveur.address().port}/`;

/* ---------- Audit ---------- */
async function auditer(onglet, nom) {
  const resultat = await onglet.evaluate((normes) =>
    window.axe.run(document, { runOnly: { type: "tag", values: normes }, resultTypes: ["violations"] }), NORMES);
  for (const v of resultat.violations) {
    total += v.nodes.length;
    console.log(`\n✗ ${nom} ${v.id} (${v.impact}) : ${v.help}`);
    console.log(`  ${v.helpUrl}`);
    for (const n of v.nodes.slice(0, 10)) {
      console.log(`  - ${n.target.join(" ")}`);
      if (n.failureSummary) console.log("    " + n.failureSummary.split("\n").slice(1).join(" ").trim());
    }
    if (v.nodes.length > 10) console.log(`  … et ${v.nodes.length - 10} autres éléments`);
  }
  if (!resultat.violations.length) console.log(`✓ ${nom}`);
}

const navigateur = await chromium.launch();
let total = 0;
const erreursJs = [];
for (const ecran of ECRANS) {
  for (const theme of THEMES) {
    const contexte = await navigateur.newContext({
      viewport: { width: ecran.width, height: ecran.height },
      colorScheme: theme === "sombre" ? "dark" : "light",
      locale: "fr-FR",
    });
    for (const page of PAGES) {
      const onglet = await contexte.newPage();
      onglet.on("pageerror", (e) => erreursJs.push(`${page} : ${e.message}`));
      await onglet.goto(base + page, { waitUntil: "load" });
      await onglet.waitForTimeout(500); // laisse les graphiques se dessiner
      await onglet.addScriptTag({ content: AXE });
      await auditer(onglet, `${page} [${theme}, ${ecran.nom}]`);
      // États ouverts : menu de navigation (téléphone) puis dialogue « Options d'affichage ».
      if (page === "index.html") {
        const menu = onglet.locator("button[aria-controls][aria-expanded]:visible").first();
        if (await menu.count()) {
          await menu.click();
          await auditer(onglet, `${page} [${theme}, ${ecran.nom}, menu ouvert]`);
          await menu.click();
        }
        const options = onglet.locator("[data-ouvrir-options]:visible").first();
        if (await options.count()) {
          await options.click();
          await auditer(onglet, `${page} [${theme}, ${ecran.nom}, options d'affichage ouvertes]`);
          await onglet.keyboard.press("Escape");
        }
      }
      await onglet.close();
    }
    await contexte.close();
  }
}
await navigateur.close();
serveur.close();

if (erreursJs.length) {
  console.log("\nErreurs JavaScript :\n" + [...new Set(erreursJs)].map((e) => "  " + e).join("\n"));
}
console.log(total
  ? `\n${total} élément(s) en défaut. Voir le détail ci-dessus.`
  : "\nAucune violation détectée par axe-core (WCAG 2.2 A et AA, bonnes pratiques).");
process.exit(total || erreursJs.length ? 1 : 0);
