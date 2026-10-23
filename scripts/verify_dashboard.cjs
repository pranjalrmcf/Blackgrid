// Headless browser acceptance. Credentials stay in memory; no HAR/trace/storage export.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),https=require('https');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),out=process.env.BLACKGRID_BROWSER_EVIDENCE||path.join(root,'docs','production_phase6','evidence');
(async()=>{
 const ca=fs.readFileSync(path.join(root,'.secrets','server-cert.pem'));
 // Independent TLS preflight; never blanket-disable browser certificate validation.
 await new Promise((resolve,reject)=>https.get('https://127.0.0.1:8765/health/live',{ca},r=>{r.resume();r.statusCode===200?resolve():reject(new Error('not_ready'));}).on('error',reject));
 const pin=crypto.createHash('sha256').update(new crypto.X509Certificate(ca).publicKey.export({type:'spki',format:'der'})).digest('base64');
 const checked=require('child_process').execFileSync(path.join(root,'.venv','Scripts','python.exe'),['-c',"import sys;sys.path.insert(0,'scripts');from open_dashboard import spki_pin;from pathlib import Path;print(spki_pin(Path('.secrets/server-cert.pem').read_text()))"],{cwd:root,encoding:'utf8'}).trim();
 if(checked!==pin)throw new Error('launcher_certificate_pin_mismatch');
 const browser=await chromium.launch({executablePath:'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',headless:true,args:['--ignore-certificate-errors-spki-list='+pin,'--disable-background-networking','--disable-component-update']});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await context.newPage();let pageErrors=0,externalRequests=0;
  page.on('pageerror',()=>pageErrors++);
  page.on('request',request=>{const u=new URL(request.url());if(!['localhost','127.0.0.1'].includes(u.hostname))externalRequests++;});
  await page.goto('https://localhost:8765/api/v1/dashboard');
  await page.locator('#login:not([hidden])').waitFor();
  const token=fs.readFileSync(path.join(root,'.secrets','alice.token'),'utf8').trim();
  await page.locator('#token').fill(token);
  await page.getByRole('button',{name:'Open live dashboard'}).click();
  await page.locator('#view:not([hidden])').waitFor();
  await page.waitForFunction(()=>document.getElementById('connection').textContent.startsWith('Live'));
  await page.waitForFunction(()=>!document.getElementById('updated').textContent.includes('1 observed history points'),null,{timeout:20000});
  const first=await page.locator('#updated').textContent();
  await page.waitForTimeout(5500);
  const second=await page.locator('#updated').textContent();
  if(first===second)throw new Error('poll_did_not_update');
  if(await page.locator('#token').inputValue()!=='')throw new Error('token_retained_in_form');
  if(await page.locator('.card').count()<8)throw new Error('metrics_not_rendered');
  await page.screenshot({path:path.join(out,'dashboard-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(out,'dashboard-mobile.png'),fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
  if(overflow||pageErrors||externalRequests)throw new Error('dashboard_render_or_network_failure');
  await page.getByRole('button',{name:'Sign out'}).click();
  await page.locator('#login:not([hidden])').waitFor();
  const after=await page.evaluate(async()=>(await fetch('/api/v1/dashboard/data',{credentials:'same-origin',cache:'no-store'})).status);
  if(after!==401)throw new Error('logout_did_not_revoke');
  const result={browser:'Edge headless',certificate_key_pinned:true,launcher_pin_independently_verified:true,independent_tls_verified:true,login:true,live_updates:true,desktop:true,mobile_no_overflow:true,logout_revoked:true,page_errors:pageErrors,external_page_requests:externalRequests,credentials_exported:false};
  fs.writeFileSync(path.join(out,'browser_verification.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(()=>{console.error('Browser verification failed; inspect the page and sanitized evidence.');process.exitCode=1;});
