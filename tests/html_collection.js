// Evaluate the actual page renderers without a browser or network.
const fs = require("node:fs"), vm = require("node:vm");
const page = fs.readFileSync(0, "utf8");
const source = [...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].find(m => m[1].includes("const D ="))[1];
const home = {};
const sandbox = {URL, window:{}, document:{querySelector:()=>home}};
vm.createContext(sandbox);
vm.runInContext(source.replace(/boot\(\);\s*$/, ""), sandbox);
vm.runInContext("renderHome()", sandbox);
const rendered = vm.runInContext(`D.projects.map(p => ({
  facts: renderFacts(p), tickets: renderTickets(p), trends: renderTrends(p), now: nowLine(p), project: renderProject(p), history: renderActivity(p)
}))`, sandbox);
process.stdout.write(JSON.stringify(rendered.map(p => ({...p, home:home.innerHTML}))));
