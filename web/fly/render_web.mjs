// Repeat the requested browser captures using the project's existing shot tool.
import {spawn} from 'node:child_process';
import {mkdir,writeFile,rm} from 'node:fs/promises';
import {dirname,resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';
const here=dirname(fileURLToPath(import.meta.url)),root=resolve(here,'../..'),temp=join(here,'.shots');
await mkdir(temp,{recursive:true});
const jobs=[
 ['web_rest','1280x520',0,0,'chromium'],['web_feed','1280x520',1,0,'chromium'],
 ['web_groom','1280x520',0,1,'chromium'],['web_both','1280x520',1,1,'chromium'],
 ['web_phone','390x420',0,0,'chromium'],['web_feed_close','2560x1040',1,0,'chromium'],
 ['web_safari','1280x520',1,1,'webkit'],['web_page','1440x900',0,0,'chromium','index.html'],
 ['web_neutral','1280x520',0,0,'chromium','fly/test.html?light=neutral'],
 ['web_neutral_feed','1280x520',1,0,'chromium','fly/test.html?light=neutral'],
];
const results=[];
function run([name,size,feed,groom,browser,page='fly/test.html']){
 return new Promise((resolve,reject)=>{
  const args=['scripts/shot.mjs',page,`web/fly/renders/${name}.png`,'--size',size,'--wait','3000','--browser',browser];
  if(feed||groom)args.push('--js',`(document.querySelector('#feed').value=${feed},document.querySelector('#groom').value=${groom},document.querySelector('#feed').dispatchEvent(new Event('input')))`);
  const child=spawn(process.execPath,args,{cwd:root,env:{...process.env,TMPDIR:temp}});let output='';
  child.stdout.on('data',b=>output+=b);child.stderr.on('data',b=>output+=b);child.on('error',reject);
  child.on('exit',code=>{const result={name,size,feed,groom,browser,page,exitCode:code,output};results.push(result);console.log(`${name}: ${code===0?'passed':'FAILED'}`);resolve(result)});
 });
}
for(let i=0;i<jobs.length;i+=2){const r=await Promise.allSettled(jobs.slice(i,i+2).map(run));for(const item of r)if(item.status==='rejected')throw item.reason;}
await writeFile(join(here,'screenshots.json'),JSON.stringify(results,null,2)+'\n');await rm(temp,{recursive:true,force:true});
if(results.some(r=>r.exitCode!==0))process.exitCode=1;
