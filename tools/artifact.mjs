// Converts the single-file build into an Artifact page body (no doctype/html/head/body tags).
import { readFileSync, writeFileSync } from 'node:fs';
const [, , src = 'apps/client/dist/index.html', out = 'apps/client/dist/artifact.html'] = process.argv;
const html = readFileSync(src, 'utf8');
const pick = (re) => [...html.matchAll(re)].map((m) => m[0]).join('\n');
const title = '<title>Raivon Territory Wars</title>';
const styles = pick(/<style[\s\S]*?<\/style>/g);
const scripts = pick(/<script[\s\S]*?<\/script>/g);
const body = (html.match(/<body[^>]*>([\s\S]*?)<\/body>/) ?? [, ''])[1].replace(/<script[\s\S]*?<\/script>/g, '');
writeFileSync(out, `${title}\n${styles}\n${body}\n${scripts}\n`);
console.log('wrote', out, Math.round(readFileSync(out).length / 1024), 'KB');
