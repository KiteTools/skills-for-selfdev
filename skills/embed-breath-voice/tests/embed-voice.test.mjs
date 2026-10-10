import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
const script=fileURLToPath(new URL('../scripts/embed-voice.mjs',import.meta.url));
function run(cmd,args,extra={}) {return spawnSync(cmd,args,{encoding:'utf8',...extra});}
function fixture(t) {
 const dir=mkdtempSync(join(tmpdir(),'breath-test-'));t.after(()=>rmSync(dir,{recursive:true,force:true}));
 const input=join(dir,'background.mp3'), voice=join(dir,'voice.mp3'), output=join(dir,'result.mp3');
 for (const [file,hz,duration] of [[input,220,4],[voice,880,1]]) {
  const r=run('ffmpeg',['-v','error','-f','lavfi','-i',`sine=frequency=${hz}:duration=${duration}`,'-c:a','libmp3lame',file]);assert.equal(r.status,0,r.stderr);
 }
 const args=['--input',input,'--at','00:01','--voice-file',voice,'--output',output];
 return {dir,input,voice,output,args};
}
function cli(args,extra={}) {const env={...process.env};delete env.ELEVENLABS_API_KEY;return run(process.execPath,[script,...args],{env,...extra});}
test('existing output is refused and all original bytes survive',t=>{
 const f=fixture(t);writeFileSync(f.output,'keep this result');const before=readFileSync(f.input);
 const r=cli(f.args);assert.notEqual(r.status,0);assert.equal(readFileSync(f.output,'utf8'),'keep this result');assert.deepEqual(readFileSync(f.input),before);
});
test('mix has the timed overlay, ducks background and preserves both inputs',t=>{
 const f=fixture(t), before=[readFileSync(f.input),readFileSync(f.voice)];const r=cli(f.args);assert.equal(r.status,0,r.stderr);const info=JSON.parse(r.stdout);
 assert.equal(info.start_sec,1);assert.equal(info.model_id,null);assert.equal(info.ducked_to,0.18);assert.ok(Math.abs(info.output_sec-info.source_sec)<0.12);
 assert.deepEqual(readFileSync(f.input),before[0]);assert.deepEqual(readFileSync(f.voice),before[1]);
 const decoded=run('ffmpeg',['-v','error','-i',f.output,'-f','f32le','-ac','1','-ar','8000','pipe:1'],{encoding:null});assert.equal(decoded.status,0);
 const b=decoded.stdout;
 function amplitude(hz,start,end){let re=0,im=0,n=0;for(let i=Math.round(start*8000);i<Math.round(end*8000);i++){const v=b.readFloatLE(i*4);re+=v*Math.cos(2*Math.PI*hz*i/8000);im+=v*Math.sin(2*Math.PI*hz*i/8000);n++;}return Math.hypot(re,im)*2/n;}
 const baseline=amplitude(220,0.2,0.6),duck=amplitude(220,1.3,1.7);assert.ok(duck/baseline>0.12&&duck/baseline<0.25,`duck ratio ${duck/baseline}`);
 assert.ok(amplitude(880,1.3,1.7)>0.07);assert.ok(amplitude(880,0.2,0.6)<0.01);assert.ok(amplitude(220,3,3.5)>baseline*0.85);
});
test('source and symlink destinations are refused',t=>{
 const f=fixture(t),before=readFileSync(f.input);assert.notEqual(cli([...f.args.slice(0,-1),f.input]).status,0);
 symlinkSync(f.input,f.output);assert.notEqual(cli(f.args).status,0);assert.deepEqual(readFileSync(f.input),before);
});
test('invalid or out-of-range timestamps fail without output',t=>{
 const f=fixture(t);for(const at of ['-1','00:60','4.2','9'.repeat(400)]){const args=[...f.args];args[3]=at;assert.notEqual(cli(args).status,0);}
});
test('overlay may continue beyond the source end',t=>{
 const f=fixture(t),args=[...f.args];args[3]='3.5';const r=cli(args);assert.equal(r.status,0,r.stderr);assert.ok(JSON.parse(r.stdout).output_sec>4.4);
});
test('help works without input files or API key',()=>{const r=cli(['--help']);assert.equal(r.status,0,r.stderr);assert.match(r.stdout,/Usage/);});
test('missing API key and conflicting modes fail',t=>{
 const f=fixture(t);const r=cli(['--input',f.input,'--at','1','--text','Тест.','--voice','male','--output',f.output]);assert.notEqual(r.status,0);assert.match(r.stderr,/ELEVENLABS_API_KEY is not set/);
 assert.notEqual(cli([...f.args,'--text','ambiguous']).status,0);
});
test('TTS request contract works with a local mocked response',t=>{
 const f=fixture(t),preload=join(f.dir,'mock.mjs');
 writeFileSync(preload,String.raw`import { readFileSync } from 'node:fs';
 import assert from 'node:assert/strict';
 globalThis.fetch=async(url,options)=>{assert.match(url,/^https:\/\/api[.]elevenlabs[.]io\/v1\/text-to-speech\/[A-Za-z0-9]+$/);assert.equal(options.method,'POST');assert.equal(options.headers['xi-api-key'],'synthetic-test-key');const body=JSON.parse(options.body);assert.equal(body.text,'Тест.');assert.equal(body.model_id,'eleven_multilingual_v2');return new Response(readFileSync(process.env.TEST_CLIP),{status:200});};`);
 const r=run(process.execPath,['--import',preload,script,'--input',f.input,'--at','1','--text','Тест.','--voice','female','--output',f.output],{env:{...process.env,ELEVENLABS_API_KEY:'synthetic-test-key',TEST_CLIP:f.voice}});
 assert.equal(r.status,0,r.stderr);assert.equal(JSON.parse(r.stdout).model_id,'eleven_multilingual_v2');assert.ok(!r.stdout.includes('synthetic-test-key'));
});
test('TTS error body containing secrets or private text is not echoed',t=>{
 const f=fixture(t),preload=join(f.dir,'mock-error.mjs');writeFileSync(preload,`globalThis.fetch=async()=>new Response('private sentence and synthetic-test-key',{status:403});`);
 const r=run(process.execPath,['--import',preload,script,'--input',f.input,'--at','1','--text','Тест.','--voice','male','--output',f.output],{env:{...process.env,ELEVENLABS_API_KEY:'synthetic-test-key'}});
 assert.notEqual(r.status,0);assert.match(r.stderr,/HTTP 403/);assert.ok(!r.stderr.includes('private sentence'));assert.ok(!r.stderr.includes('synthetic-test-key'));
});
