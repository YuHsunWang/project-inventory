// Inspect the actual homepage renderer, including its cross-project row order.
const fs = require("node:fs"), vm = require("node:vm");
const page = fs.readFileSync(0, "utf8");
const source = [...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].find(m => m[1].includes("const D ="))[1];
const home = {innerHTML:""};
const sandbox = {URL, window:{}, document:{querySelector:() => home}};
vm.createContext(sandbox);
vm.runInContext(source.replace(/boot\(\);\s*$/, ""), sandbox);
vm.runInContext("renderHome()", sandbox);
process.stdout.write(JSON.stringify({home:home.innerHTML}));
