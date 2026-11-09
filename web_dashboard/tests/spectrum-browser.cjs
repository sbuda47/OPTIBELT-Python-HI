const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const page=await browser.newPage({viewport:{width:1440,height:1050},acceptDownloads:true});
 const base=process.env.DASHBOARD_URL||'http://127.0.0.1:8766',output=path.resolve(__dirname,'../verification');
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const plot=()=>page.getByRole('group',{name:/Vibration .* spectrum plot/}).locator('.js-plotly-plot');
 async function generate(){
  const pending=page.waitForResponse(r=>r.url().endsWith('/spectrum')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Generate spectrum',exact:true}).click();const response=await pending;
  assert.equal(response.status(),200);const result=await response.json();await page.getByTestId('spectrum-summary').waitFor();
  await plot().waitFor();return result;
 }
 try{
  await page.goto(base);await page.getByRole('button',{name:'Play playback',exact:true}).waitFor();
  await page.getByRole('button',{name:'Analysis',exact:true}).click();
  await page.getByLabel('Plot type',{exact:true}).selectOption('fft');
  const fft=await generate();assert.equal(fft.sample_count,51200);assert.equal(fft.bin_spacing_hz,.5);
  await page.getByLabel('Assumed RPM',{exact:true}).fill('1800');
  await page.getByLabel('Maximum display frequency',{exact:true}).fill('500');
  await page.waitForFunction(()=>[...document.querySelectorAll('.js-plotly-plot')].some(p=>p.layout?.shapes?.length===10));
  const firstOrder=await plot().evaluate(e=>e.layout.shapes[0].x0);assert.equal(firstOrder,30);
  await page.getByLabel('Amplitude scale',{exact:true}).selectOption('log');
  await page.waitForFunction(()=>[...document.querySelectorAll('.js-plotly-plot')].some(p=>p.layout?.yaxis?.type==='log'));
  const rangeBefore=await plot().evaluate(e=>e._fullLayout.xaxis.range);
  const drag=plot().locator('.nsewdrag');await drag.scrollIntoViewIfNeeded();const box=await drag.boundingBox();
  await page.mouse.move(box.x+box.width*.2,box.y+box.height*.2);await page.mouse.down();await page.mouse.move(box.x+box.width*.65,box.y+box.height*.8,{steps:10});await page.mouse.up();
  await page.waitForTimeout(250);const rangeAfter=await plot().evaluate(e=>e._fullLayout.xaxis.range);assert.ok(rangeAfter[1]-rangeAfter[0]<rangeBefore[1]-rangeBefore[0]);
  await page.getByRole('button',{name:'Reset zoom',exact:true}).click();await page.waitForTimeout(200);
  assert.deepEqual(await plot().evaluate(e=>e._fullLayout.xaxis.range),[0,500]);
  const downloadEvent=page.waitForEvent('download');await page.getByRole('button',{name:'Export spectrum CSV'}).click();
  const download=await downloadEvent,rows=fs.readFileSync(await download.path(),'utf8').trim().split(/\r?\n/);
  assert.equal(rows.length,fft.frequencies.length+1);assert.ok(rows[0].includes('peak_amplitude_source_units'));assert.ok(rows[0].includes('source_sha256'));
  await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(output,'spectrum-fft.png'),fullPage:true});
  await page.getByLabel('Plot type',{exact:true}).selectOption('envelope');
  assert.equal(await page.getByTestId('spectrum-summary').count(),0);
  await page.getByRole('button',{name:'Generate spectrum',exact:true}).click();
  assert.equal(await page.getByLabel('Envelope lower frequency').evaluate(e=>e.validity.valueMissing),true);
  await page.getByLabel('Envelope lower frequency').fill('5000');await page.getByLabel('Envelope upper frequency').fill('3000');
  await page.getByRole('button',{name:'Generate spectrum',exact:true}).click();await page.getByRole('alert').filter({hasText:'at least 50 Hz'}).waitFor();
  await page.getByLabel('Envelope lower frequency').fill('3000');await page.getByLabel('Envelope upper frequency').fill('5000');
  const envelope=await generate();assert.deepEqual(envelope.band_hz,[3000,5000]);assert.equal(envelope.context_before_seconds,1);
  await page.getByLabel('Spectrum duration',{exact:true}).selectOption('10');assert.equal(await page.getByTestId('spectrum-summary').count(),0);
  const longer=await generate();assert.equal(longer.sample_count,256000);assert.equal(longer.bin_spacing_hz,.1);
  await page.getByRole('button',{name:'Dark appearance',exact:true}).click();await page.waitForTimeout(400);
  await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(output,'spectrum-envelope-dark.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(600);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  const geometry=await page.evaluate(()=>{
   const graph=document.querySelector('.spectrum-panel .plot-wrap').getBoundingClientRect();
   const footer=document.querySelector('.spectrum-panel .signal-footer').getBoundingClientRect();
   const hi=document.querySelector('.analysis-grid .plot-wrap').getBoundingClientRect();
   return {height:graph.height,hiHeight:hi.height,bottom:graph.bottom,footerTop:footer.top};
  });
  assert.ok(geometry.height>=390&&geometry.hiHeight>=225);assert.ok(geometry.footerTop>=geometry.bottom-1);
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:path.join(output,'spectrum-mobile.png'),fullPage:true});
  await page.setViewportSize({width:1440,height:1050});
  const catalogue=await page.evaluate(()=>fetch('/api/catalog').then(r=>r.json()));
  const variable=catalogue.recordings.find(r=>r.profile!=='invariant_speed');
  await page.getByLabel('Recording',{exact:true}).selectOption(variable.id);
  await page.waitForFunction(()=>document.querySelector('select[aria-label="Plot type"]')?.value==='waveform');
  assert.equal(await page.getByTestId('spectrum-summary').count(),0);
  await page.getByLabel('Plot type',{exact:true}).selectOption('fft');const variableResult=await generate();assert.equal(variableResult.recording_id,variable.id);
  await page.getByText(/Variable-speed recording: frequency peaks may spread/).waitFor();
  assert.deepEqual(errors,[]);
  const result={status:'passed',url:base,checks:['real FFT generation','manual RPM markers','log axis','drag zoom and reset','full precision CSV rows and metadata','envelope required band and invalid-band rejection','envelope context and 10-second analysis','processing changes clear results','recording switch clears results','variable-speed caution','dark theme','390px no overflow'],browser_errors:errors};
  fs.writeFileSync(path.join(output,'spectrum-browser.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }catch(e){await page.screenshot({path:path.join(output,'spectrum-failure.png'),fullPage:true});throw e}
 finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
