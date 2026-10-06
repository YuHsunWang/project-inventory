// Execute the template renderer so copy assertions check actual outputs.
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const template = fs.readFileSync(0, "utf8");
const source = [...template.matchAll(/<script>([\s\S]*?)<\/script>/g)].find(m => m[1].includes("const D ="))[1];
for (const lang of ["zh-TW", "en"]) {
  const context = {URL, window:{}, document:{}};
  vm.createContext(context);
  const data = {lang, date:"2026-10-06", projects:[]};
  vm.runInContext(source.replace("/*__DATA__*/null", JSON.stringify(data)).replace(/boot\(\);\s*$/, ""), context);
  const result = vm.runInContext(`(() => {
    const p = {key:"p", nodes:[{id:1,title:"Fetch"}], facts:{tickets:[],data:[],obsidian:[],prs:[],errors:[],repos:[
      {label:"checkout",path:"/demo",branch:"dev",dirty:2,has_origin:true,remote:"https://gitlab.com/demo/app",ahead:1,behind:1}]},
      history:[{week:"2026-09-28",items:[{date:"2026-09-29",kind:"commit",text:"old"}]}]};
    const road = renderRoad(p), facts = renderFacts(p), history = renderActivity(p);
    const tips = [];
    for (const week of ["2026-09-28", "2026-10-05"]) {
      const tip = {offsetWidth:20,style:{}};
      const svg = {getBoundingClientRect:()=>({left:0,width:100}),querySelector:()=>({setAttribute(){}})};
      const el = {dataset:{chart:"copy"},clientWidth:100,querySelector:s=>s === "svg" ? svg : tip};
      CHARTS.copy = {kind:"bar",bars:[{week,n:1}],n:1,W:100,xAt:()=>0,xOf:()=>50};
      hoverChart(el,{clientX:50}); tips.push(tip.innerHTML);
    }
    return {road,facts,history,tips,missing:icon(),unknown:icon("unknown"),prototype:icon("__proto__"),gear:icon("gear"),dirty:T.dirty,unpushed:T.unpushed,no_upstream:T.no_upstream};
  })()`, context);
  assert.equal(result.missing,result.gear);
  assert.equal(result.unknown,result.gear);
  assert.equal(result.prototype,result.gear);
  assert.ok(result.road.includes(result.gear));
  assert.ok(result.facts.includes("https://gitlab.com/demo/app"));
  assert.ok(result.facts.includes(lang === "zh-TW" ? "<th>遠端 · checkout" : "<th>Remote · checkout"));
  assert.ok(!result.facts.includes("GitHub · checkout"));
  assert.ok(!result.unpushed.includes("GitHub"));
  assert.ok(!result.no_upstream.includes("GitHub"));
  const current = lang === "zh-TW" ? "這週" : "this week";
  assert.ok(!result.tips[0].includes(current));
  assert.ok(result.tips[1].includes(current));
  assert.ok(!result.history.includes(current));
  if (lang === "zh-TW") assert.ok(result.dirty.includes("尚未提交"));
}
console.log("UI copy OK");
