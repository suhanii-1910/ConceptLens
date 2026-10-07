import {test,expect,type Page} from '@playwright/test';
import {readFile} from 'node:fs/promises';
import {phase10Scenario,learner} from '../src/test/phase10Scenario';
const navigate=(page:Page,name:string)=>page.getByRole('navigation',{name:'Principal navigation'}).getByRole('link',{name,exact:true}).click();
test('TEST FIXTURE: diagnostic resume, exact sources, visual/table evidence, mixed practice and solver proof',async({page})=>{
  const server=phase10Scenario();const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(value=>localStorage.setItem('conceptlens:learner',value),learner);
  await page.route(url=>url.pathname.startsWith('/api/'),async route=>{
    const request=route.request();const url=new URL(request.url());
    if(url.pathname.endsWith('/preview') || url.pathname.endsWith('/asset'))return route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jN1sAAAAASUVORK5CYII=','base64')});
    if(url.pathname.endsWith('/file')) {
      const bytes=await readFile('../evaluation/datasets/sources/aster-demonstration.mp4');
      const range=/bytes=(\d+)-(\d*)/.exec(request.headers().range ?? '');
      if(range){const start=Number(range[1]),end=range[2]?Number(range[2]):bytes.length-1;return route.fulfill({status:206,contentType:'video/mp4',headers:{'Accept-Ranges':'bytes','Content-Range':`bytes ${start}-${end}/${bytes.length}`},body:bytes.subarray(start,end+1)});}
      return route.fulfill({contentType:'video/mp4',headers:{'Accept-Ranges':'bytes'},body:bytes});
    }
    const reply=server.handle(url.pathname.replace('/api','')+url.search,request.method(),request.postDataJSON()??{});
    await route.fulfill({status:reply.status,json:reply.body});
  });
  await page.goto('/dashboard');await expect(page.getByText('Untested',{exact:true}).first()).toBeVisible();
  await page.getByRole('button',{name:'Start short diagnostic'}).click();
  for(let i=0;i<3;i++){
    await expect(page.getByText(new RegExp(`${i} / 3 verified questions completed`))).toBeVisible();
    await page.getByRole('radio').first().check();await page.getByRole('button',{name:'Check my answer'}).click();
    if(i===0){await expect(page.getByText(/1 \/ 3 verified questions completed/)).toBeVisible();await page.reload();}
  }
  await expect(page.getByText(/Diagnostic complete/)).toBeVisible();
  await navigate(page,'Workspace');await page.getByRole('button',{name:'Inspect source evidence'}).first().click();
  await page.getByRole('button',{name:'figure · Page 4'}).click();
  await expect(page.getByRole('dialog')).toBeVisible();await expect(page.getByRole('img',{name:'CPU Scheduling.pdf, Page 4'})).toBeVisible();
  await expect(page.getByRole('cell',{name:'Burst'})).toBeVisible();await page.getByRole('button',{name:'Close source'}).click();
  await navigate(page,'Ask');await page.getByLabel('What would you like to understand?').fill('Explain remaining time');await page.getByRole('button',{name:'Ask ConceptLens'}).click();
  for(let i=0;i<3;i++){
    const row=page.locator('.citation').nth(i);await row.locator('summary').click();await row.getByRole('button',{name:'Open exact source'}).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    if(i===1)await expect(page.getByRole('img',{name:'Scheduling slides.pptx, Slide 2'})).toBeVisible();
    if(i===2)await expect.poll(()=>page.locator('video').evaluate((v:HTMLVideoElement)=>JSON.stringify({time:v.currentTime,duration:v.duration,error:v.error?.message,ready:v.readyState}))).toContain('"time":3');
    await page.getByRole('button',{name:'Close source'}).click();
  }
  await navigate(page,'Practice');await page.getByLabel('Question type').selectOption('short_answer');await page.getByLabel('What would you like to work on?').fill('SRTF remaining time');await page.getByRole('button',{name:'Find me a problem'}).click();
  await page.getByLabel('Your answer').fill('Use total execution minus completed work.');await page.getByRole('button',{name:'Check my answer'}).click();await expect(page.getByText('Correct response.',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Try a new problem'}).click();await page.getByLabel('Question type').selectOption('numerical');await page.getByLabel('What would you like to work on?').fill('SRTF completion time');await page.getByRole('button',{name:'Find me a problem'}).click();
  await page.getByLabel('Your answer').fill('9');await page.getByRole('button',{name:'Check my answer'}).click();await page.getByText('Deterministic scheduling proof').click();await expect(page.getByText('P1: 0 → 8')).toBeVisible();await expect(page.getByText('observed uncertain',{exact:false})).toBeVisible();
  await expect(page.getByRole('navigation').getByRole('link')).toHaveCount(5);expect(errors).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});

test('TEST FIXTURE: uncertain diagnosis continues into concept-level teaching',async({page})=>{
  const server=phase10Scenario();
  await page.addInitScript(value=>localStorage.setItem('conceptlens:learner',value),learner);
  await page.route(url=>url.pathname.startsWith('/api/'),async route=>{
    const request=route.request(),url=new URL(request.url());const reply=server.handle(url.pathname.replace('/api',''),request.method(),request.postDataJSON()??{});
    if(url.pathname.includes('/reasoning-diagnoses'))reply.body={...(reply.body as object),status:'no_clear_break',hypothesis_text:null,first_break_excerpt:null,first_break_step_index:null,probe:null};
    await route.fulfill({status:reply.status,json:reply.body});
  });
  await page.goto('/practice');await page.getByLabel('Question type').selectOption('numerical');await page.getByLabel('What would you like to work on?').fill('SRTF');await page.getByRole('button',{name:'Find me a problem'}).click();await page.getByLabel('Your answer').fill('9');await page.getByRole('button',{name:'Check my answer'}).click();await page.getByRole('button',{name:'Debug my reasoning'}).click();
  await page.getByLabel(/Explain your thinking/).fill('I compared the new burst with the original burst, but I am not sure.');await page.getByRole('button',{name:'Debug my reasoning'}).click();
  await page.getByRole('button',{name:'See recommended next step'}).click();await expect(page.getByText(/This teaching uses observed concept performance/)).toBeVisible();
  await page.getByRole('button',{name:/Still confused/}).click();await expect(page.getByRole('heading',{name:'Let’s look at this visually.'})).toBeVisible();
});
