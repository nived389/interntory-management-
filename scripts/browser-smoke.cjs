const {chromium}=require('/Users/nived/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:"chrome"});const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5056');
 await page.getByLabel('Your name',{exact:true}).fill('QA Owner');await page.getByLabel('Username',{exact:true}).fill('qaowner');await page.getByLabel('Password',{exact:true}).fill('local-testing-password');await page.getByRole('button',{name:'Create workspace'}).click();
 await page.getByRole('heading',{name:'Inventory overview',exact:true}).waitFor();await page.screenshot({path:'tmp/qa/dashboard-desktop.png',fullPage:true});
 for(const label of ['Inventory','Monthly count','Breakage','Reports','Team','Settings','Audit trail']){await page.getByRole('navigation').getByRole('button',{name:label,exact:true}).click();await page.waitForTimeout(200);if(await page.locator('#page-retry').count())throw new Error(label+': '+await page.locator('main').innerText())}
 await page.getByRole('navigation').getByRole('button',{name:'Inventory',exact:true}).click();await page.getByPlaceholder('Search item name or code…').fill('COFFEE MUG');await page.getByRole('button',{name:'View item'}).click();await page.getByRole('button',{name:'Edit details'}).waitFor();await page.getByRole('button',{name:'Close dialog'}).click();
 await page.setViewportSize({width:390,height:844});await page.getByRole('navigation').getByRole('button',{name:'Overview',exact:true}).click();await page.waitForTimeout(200);await page.screenshot({path:'tmp/qa/dashboard-mobile.png',fullPage:true});
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);if(overflow)throw new Error('Page overflows mobile viewport');
 await page.getByRole('navigation').getByRole('button',{name:'Settings',exact:true}).click();await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.getByRole('heading',{name:'Welcome back'}).waitFor();
 console.log(JSON.stringify({pageErrors:errors,mobileOverflow:overflow,result:'PASS'}));await browser.close();if(errors.length)process.exit(1);
})().catch(e=>{console.error(e);process.exit(1)});
