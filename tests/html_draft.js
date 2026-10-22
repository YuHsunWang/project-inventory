// Exercise the actual node renderer, including branches, reviewed nodes and both labels.
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const page = fs.readFileSync(0, "utf8");
const source = [...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].find(m => m[1].includes("const D ="))[1];
if (process.argv.includes("--built")) {
  const context = {URL, window:{}, document:{}};
  vm.createContext(context);
  vm.runInContext(source.replace(/boot\(\);\s*$/, ""), context);
  const roads = vm.runInContext("D.projects.map(p => renderRoad(p))", context);
  assert.equal(roads.length, 3);
  assert.equal(roads.join("").match(/<span class="ai-updated">AI 草稿<\/span>/g).length, 15);
  console.log('BUILT HTML: 3 projects / 15 draft nodes; <span class="ai-updated">AI 草稿</span>');
} else {
  for (const lang of ["zh-TW", "en"]) {
    const context = {URL, window:{}, document:{}};
    vm.createContext(context);
    vm.runInContext(source.replace("/*__DATA__*/null", JSON.stringify({lang, projects:[]})).replace(/boot\(\);\s*$/, ""), context);
    const result = vm.runInContext(`(() => {
      const p = {key:"app",nodes:[{id:1,title:"Read",draft:true},
        {id:2,on:1,side:"l",title:"Check",draft:true,auto_updated:"2026-10-22"},
        {id:3,title:"Reviewed",draft:false},{id:4,title:"Existing"}],facts:{tickets:[]}};
      const before = renderRoad(p);
      delete p.nodes[0].draft; delete p.nodes[1].draft;
      return {before,after:renderRoad(p),label:T.ai_draft,keys:Object.keys(L),all:Object.values(L).every(t => !!t.ai_draft)};
    })()`, context);
    assert.equal(result.label, lang === "zh-TW" ? "AI 草稿" : "AI draft");
    assert.ok(result.all, "Every i18n language needs a draft label");
    assert.equal(result.before.split(`<span class="ai-updated">${result.label}</span>`).length - 1, 2);
    assert.ok(!result.after.includes(result.label), "Review removes draft labels");
    assert.ok(result.after.includes("2026-10-22"), "Review preserves the independent auto-update label");
    console.log(`RENDER ${lang}: <span class="ai-updated">${result.label}</span>; reviewed/existing nodes omit draft`);
  }
}
