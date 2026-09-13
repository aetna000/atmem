import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { progressCardComparison } from '../dist/src/tool-result-comparison.js';
const stable = v => Array.isArray(v) ? v.map(stable) : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>[k,stable(v)])) : v;
const digest = v => createHash('sha256').update(JSON.stringify(stable(v))).digest('hex');
const details = { revision: 3, steps: { completed: 3, total: 3 } };
const raw = {content:[{type:'text',text:'Progress card updated (rev 3, 3/3 done)'},{type:'text',text:JSON.stringify(details,null,2)}],details};
const relay = raw.content.map(v=>({...v,type:'input_text'}));
// These two fixture hashes match the independently inspected local incident.
assert.equal(digest(raw),'e54c38cf6df1f1cad2142cd9e79b47ad671d1071f0e862e125028b9c05332661');
assert.equal(digest(relay),'3e68cf47a1810f1b821b17c0eaae6ed118bfae847c13e47b8f3b3c762e8bd3ad');
const compare = v => progressCardComparison('progress_card',v,digest);
assert.equal(compare(raw).result_comparison_sha256,compare(relay).result_comparison_sha256);
for(const invalid of [{...raw,extra:true},{...raw,details:{...details,revision:4}},[...relay,{type:'input_text',text:'extra'}],relay.map((v,i)=>i===0?{...v,text:'different'}:v),{...raw,content:[{type:'text',text:'bad'},raw.content[1]]},null])assert.deepEqual(compare(invalid),{});
assert.deepEqual(progressCardComparison('exec',raw,digest),{});
for(const d of [{revision:4,steps:{completed:3,total:3}},{revision:3,steps:{completed:2,total:3}}]) {
 const v={details:d,content:[{type:'text',text:`Progress card updated (rev ${d.revision}, ${d.steps.completed}/${d.steps.total} done)`},{type:'text',text:JSON.stringify(d,null,2)}]};
 assert.notEqual(compare(v).result_comparison_sha256,compare(raw).result_comparison_sha256);
}
console.log('progress result comparison: exact incident reproduced; envelope-only equivalence and negative cases passed');
