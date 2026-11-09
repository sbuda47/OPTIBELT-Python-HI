const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const page=await browser.newPage({viewport:{width:1440,height:1050}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const position=async()=>Number((await page.getByTestId('playback-position').textContent()).split('/')[0]);
 try{
  await page.goto(process.env.DASHBOARD_URL||'http://127.0.0.1:8765');await page.getByRole('button',{name:'Play playback',exact:true}).waitFor();
  await page.getByLabel('Recording',{exact:true}).selectOption('Coil40%_3HP_30%');
  await page.getByText('Recorded label: coil',{exact:true}).waitFor();
  await page.getByLabel('Playback speed',{exact:true}).selectOption('4');
  await page.getByRole('button',{name:'Play playback',exact:true}).click();
  const alarm=page.getByRole('dialog',{name:'Operator attention required'});await alarm.waitFor({timeout:15000});
  const entry=await position();await page.waitForTimeout(1100);
  assert.ok(await position()>entry,'Critical entry must not pause playback');
  await alarm.getByText('Confirmed critical alarm',{exact:true}).waitFor({timeout:5000});
  assert.equal(await page.locator('dialog:modal').count(),0,'Alarm must leave background controls accessible');
  assert.equal(await page.locator('.lamp.on').count(),1);
  const confirmed=await position();await page.waitForTimeout(650);assert.ok(await position()>confirmed,'Confirmed alarm must not pause playback');
  await page.getByRole('button',{name:'Pause playback',exact:true}).click();
  const paused=await position();await page.waitForTimeout(700);assert.equal(await position(),paused);
  await page.screenshot({path:path.join(__dirname,'../verification/alarm-continuous.png'),fullPage:true});
  await page.getByRole('button',{name:'Dismiss and inspect'}).click();assert.equal(await position(),paused);
  assert.equal(await page.locator('.lamp.fault').count(),1);
  await page.getByRole('button',{name:'Play playback',exact:true}).click();await page.waitForTimeout(600);
  assert.ok(await position()>paused);assert.equal(await alarm.count(),0);
  await page.getByRole('button',{name:'Pause playback',exact:true}).click();
  await page.getByRole('button',{name:'Restart playback'}).click();
  assert.equal(await position(),1);assert.equal(await page.getByTestId('hi-value').textContent(),'—');
  assert.deepEqual(errors,[]);
  const result={status:'passed',checks:['critical entry keeps advancing','confirmation updates open notification','confirmed alarm keeps advancing','background pause accessible','explicit pause stable','dismiss does not change cursor or latch','resume does not repeat notification','restart resets state'],browser_errors:errors};
  fs.writeFileSync(path.join(__dirname,'../verification/alarm-continuous.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
