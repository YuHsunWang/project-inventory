// Execute the built page's rendering code, then inspect its output in Python.
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const page = fs.readFileSync(0, "utf8");
const scripts = [...page.matchAll(/<script>([\s\S]*?)<\/script>/g)];
const source = scripts.find(m => m[1].includes("const D ="))[1];
const sandbox = {URL, window:{}, document:{}};
vm.createContext(sandbox);
vm.runInContext(source.replace(/boot\(\);\s*$/, ""), sandbox);
const output = vm.runInContext(String.raw`(() => {
  const attack = '\" onmouseover=\"window.__audit_xss=1';
  const p = D.projects[0];
  p.key = attack; p.nodes[0].id = attack;
  p.facts.tickets = [{id:attack, node:attack, state:attack, title:attack}];
  const fragments = [renderProject(p), todoRows([{go:attack, color:"#c00", kind:"git", parts:[], where:"x"}]),
    renderMedia([{src:attack}, {src:"javascript:window.__audit_xss=1"},
      {src:"data:image/svg+xml;base64,PHN2Zz4="},
      {mock:'<img src="x" onerror="window.__audit_xss=1"><script>window.__audit_xss=1<\/script>'},
      {mock:[{text:"<img onerror=x>", emphasis:"bold"}, {text:"safe", emphasis:attack}]}])];
  for (const url of ["javascript:window.__audit_xss=1", "JaVaScRiPt:alert(1)", "java\nscript:alert(1)",
    "data:text/html,x", "file:///secret", "https://example.com/\" onmouseover=\"x"])
    fragments.push(ext(url, "label", attack));
  fragments.push(ext("https://example.com", "allowed"));
  return fragments;
})()`, sandbox);
assert.equal(sandbox.window.__audit_xss, undefined);
assert.equal(sandbox.__audit_xss, undefined);
process.stdout.write(JSON.stringify(output));
