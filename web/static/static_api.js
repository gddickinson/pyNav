// Static-site data layer: answers api() calls from the JSON exported by scripts/build_static.py, and runs log
// analysis in the browser with nmea_engine.js (the JS port of navmath, node-tested against the Python). The live GPS
// endpoints need the local app.
import { analyseLog } from './nmea_engine.js';

const files = new Map();
async function file(rel) {
  if (!files.has(rel)) files.set(rel, fetch('api/' + rel + '.json').then(r => { if (!r.ok) throw new Error(`${r.status} ${rel}`); return r.json(); }));
  return files.get(rel);
}

export const NEEDS_SERVER = 'needs the full app running locally (Python server): see the README, "Run the web app"';

export async function staticApi(path, body) {
  const clean = path.split('?')[0].replace(/^\/+/, '');
  if (clean === 'analyse') {
    try { return analyseLog(body.text, body.name || '', body.legs || 6); }
    catch (e) { throw new Error(`could not read ${body.name || 'the file'}: ${e.message}`); }
  }
  if (clean.startsWith('live')) throw new Error('Live GPS ' + NEEDS_SERVER + '.');
  return file(clean);
}
