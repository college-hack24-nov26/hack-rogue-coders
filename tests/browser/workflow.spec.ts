import {test,expect,Page} from '@playwright/test';
async function searchVillage(page:Page){await page.getByText('Hello,').waitFor();await page.waitForLoadState('networkidle');await page.waitForTimeout(400);if(!(await page.getByLabel('Search village / district / LGD code').count()))return;await page.getByLabel('Search village / district / LGD code').fill('TEST FIXTURE');await page.getByRole('button',{name:'Search directory'}).click()}
async function openFarmer(page:Page){
 // Forward browser test traffic to the isolated API fixture. The production
 // bundle keeps its environment-configured address, with no URL-editing UI.
 await page.route('**/api/v1/**',async route=>{
  const url=new URL(route.request().url());url.protocol='http:';url.hostname='127.0.0.1';url.port='8011';
  const response=await route.fetch({url:url.toString()});await route.fulfill({response});
 });
 await page.goto('http://localhost:8088');await page.getByRole('button',{name:'Get Started',exact:true}).click();
}
test('farmer opens signup, validates fields, creates an account and signs back in',async({page})=>{
 await openFarmer(page);let submissions=0;
 page.on('request',request=>{if(request.method()==='POST'&&request.url().endsWith('/auth/register'))submissions++});
 await page.getByRole('button',{name:'Create farmer account',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Create your farmer account'})).toBeVisible();
 await page.getByRole('button',{name:'Create account',exact:true}).click();
 await expect(page.getByText('Enter your email address.',{exact:true})).toBeVisible();
 await expect(page.getByText('Use a password with at least 10 characters.',{exact:true})).toBeVisible();
 expect(submissions).toBe(0);
 await page.getByLabel('Email',{exact:true}).fill('not-an-email');
 await page.getByLabel('Password (10+ characters)',{exact:true}).fill('tiny');
 await page.getByRole('button',{name:'Create account',exact:true}).click();
 await expect(page.getByText('Enter a valid email address.',{exact:true})).toBeVisible();
 expect(submissions).toBe(0);
 await page.getByLabel('Email',{exact:true}).fill(' New.Farmer@Fixture.test ');
 await page.getByLabel('Password (10+ characters)',{exact:true}).fill('TEST-signup-password-123');
 await page.getByLabel('Confirm password',{exact:true}).fill('TEST-different-password');
 await page.getByRole('button',{name:'Create account',exact:true}).click();
 await expect(page.getByText('Passwords do not match.',{exact:true})).toBeVisible();expect(submissions).toBe(0);
 await page.getByLabel('Confirm password',{exact:true}).fill('TEST-signup-password-123');
 await page.getByRole('button',{name:'Create account',exact:true}).click();
 await expect(page.getByText('Account created. Welcome to JalSathi.',{exact:true})).toBeVisible();expect(submissions).toBe(1);
 await searchVillage(page);await expect(page.getByText('TEST FIXTURE VILLAGE',{exact:true})).toBeVisible();
 await page.getByText('Profile',{exact:true}).click();
 await expect(page.getByText('new.farmer@fixture.test',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Sign out & clear native session',exact:true}).click();
 await page.getByLabel('Email',{exact:true}).fill('NEW.FARMER@fixture.test');
 await page.getByLabel('Password (10+ characters)',{exact:true}).fill('TEST-signup-password-123');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await searchVillage(page);await expect(page.getByText('TEST FIXTURE VILLAGE',{exact:true})).toBeVisible();
});
test('existing account signup gives a clear error and allows sign-in',async({page})=>{
 await openFarmer(page);await page.getByRole('button',{name:'Create farmer account',exact:true}).click();
 await page.getByLabel('Email',{exact:true}).fill('farmer@fixture.test');
 await page.getByLabel('Password (10+ characters)',{exact:true}).fill('fixture-password-123');
 await page.getByLabel('Confirm password',{exact:true}).fill('fixture-password-123');
 await page.getByRole('button',{name:'Create account',exact:true}).click();
 await expect(page.getByRole('alert')).toHaveText('An account with this email already exists. Sign in instead.');
 await page.getByRole('button',{name:'Back to sign in',exact:true}).click();
 await expect(page.getByLabel('Email',{exact:true})).toHaveValue('farmer@fixture.test');
 await page.getByLabel('Password (10+ characters)',{exact:true}).fill('fixture-password-123');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await searchVillage(page);await expect(page.getByText('TEST FIXTURE VILLAGE',{exact:true})).toBeVisible();
});
test('signup connection failure retains input and can be retried',async({page})=>{
 await openFarmer(page);await page.getByRole('button',{name:'Create farmer account',exact:true}).click();
 await page.getByLabel('Email',{exact:true}).fill('retry-signup@fixture.test');
 await page.getByLabel('Password (10+ characters)',{exact:true}).fill('TEST-retry-password-123');
 await page.getByLabel('Confirm password',{exact:true}).fill('TEST-retry-password-123');
 await page.route('**/api/v1/auth/register',route=>route.abort('connectionfailed'));
 await page.getByRole('button',{name:'Create account',exact:true}).click();
 await expect(page.getByRole('alert')).toHaveText('Could not connect to JalSathi. Check your connection and try again.');
 await expect(page.getByLabel('Email',{exact:true})).toHaveValue('retry-signup@fixture.test');
 await expect(page.getByLabel('Confirm password',{exact:true})).toHaveValue('TEST-retry-password-123');
 await page.unroute('**/api/v1/auth/register');await page.getByRole('button',{name:'Create account',exact:true}).click();
 await expect(page.getByText('Account created. Welcome to JalSathi.',{exact:true})).toBeVisible();
});
test('system administrator sees missing integration configuration and explicit district refresh',async({page})=>{
 await portal(page,'http://localhost:5183','operator@fixture.test');
 await page.getByRole('button',{name:'Sources & data flow',exact:false}).click();
 await expect(page.getByRole('heading',{name:'Live integration setup'})).toBeVisible();
 await expect(page.getByText('GEMINI_API_KEY, GEMINI_MODEL',{exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'Source',exact:true}).selectOption('villages');
 await page.getByLabel('Official district code').fill('473');
 await page.getByRole('button',{name:'Queue source refresh'}).click();
 await expect(page.getByText(/"district_code": "473"/)).toBeVisible();
});
async function portal(page:Page,url:string,email:string){await page.goto(url);await page.getByLabel('API address').fill('http://127.0.0.1:8011');await page.getByLabel('Email',{exact:true}).fill(email);await page.getByLabel('Password',{exact:true}).fill('fixture-password-123');await page.getByRole('button',{name:'Sign in →'}).click();await expect(page.getByRole('heading',{name:'Overview',exact:true})).toBeVisible()}
test('farmer report → scoped review → officials demo → farmer timeline',async({browser})=>{
 const farmer=await browser.newPage();const admin=await browser.newPage();const official=await browser.newPage();
 await openFarmer(farmer);await farmer.getByLabel('Email',{exact:true}).fill('farmer@fixture.test');await farmer.getByLabel('Password (10+ characters)',{exact:true}).fill('fixture-password-123');await farmer.getByRole('button',{name:'Sign in',exact:true}).click();
 await searchVillage(farmer);await expect(farmer.getByText('TEST FIXTURE VILLAGE',{exact:true})).toBeVisible();await farmer.getByText('TEST FIXTURE VILLAGE',{exact:true}).click();
 await farmer.getByRole('button',{name:'Today'+String.fromCharCode(39)+'s Action Card'}).click();await farmer.getByText('Submit report',{exact:true}).click();await farmer.getByLabel('Problem description').fill('TEST E2E FIXTURE: water interruption in this locality');await farmer.getByRole('switch').check();await farmer.getByRole('button',{name:'Review & submit report'}).click();await expect(farmer.getByText('TEST E2E FIXTURE: water interruption in this locality',{exact:true})).toBeVisible();
 const referenceText=await farmer.getByText(/^Ticket [0-9a-f-]{36}$/).innerText();
 const reference=referenceText.replace('Ticket ','');
 await farmer.getByRole('button',{name:'Link WhatsApp complaints',exact:true}).click();
 await expect(farmer.getByText(/Send this from your WhatsApp to JalSathi within 10 minutes: LINK /)).toBeVisible();
 await farmer.getByLabel('Find by reference ID').fill(reference);
 await farmer.getByRole('button',{name:'Track reference',exact:true}).click();
 await expect(farmer.getByText('Ticket '+reference,{exact:true})).toBeVisible();
 await portal(admin,'http://localhost:5183','admin@fixture.test');await admin.getByRole('button',{name:'Complaint inbox',exact:false}).click();await admin.getByRole('button').filter({hasText:'TEST E2E FIXTURE: water interruption'}).click();await admin.getByLabel('Sanitized public report').fill('TEST E2E FIXTURE: reviewed water interruption');await admin.getByLabel('Reason',{exact:true}).fill('Reviewed test report for demonstration');await admin.getByRole('button',{name:'Save review'}).click();await expect(admin.locator('.badge.accepted').first()).toBeVisible();
 await portal(official,'http://localhost:5184','official@fixture.test');await official.getByRole('button',{name:'Accepted complaints'}).click();await official.getByRole('button').filter({hasText:'TEST E2E FIXTURE: reviewed water interruption'}).click();await official.getByLabel('Progress note').fill('Acknowledged in isolated demonstration test');await official.getByRole('button',{name:'Save demo action'}).click();await expect(official.getByText('Acknowledged in isolated demonstration test',{exact:true})).toBeVisible();
 await farmer.getByRole('button',{name:'Refresh tickets'}).click();await farmer.getByText('TEST E2E FIXTURE: reviewed water interruption',{exact:true}).click();await expect(farmer.getByText('Acknowledged in isolated demonstration test',{exact:true})).toBeVisible();
 await admin.screenshot({path:'docs/admin-preview.png',fullPage:true});await official.screenshot({path:'docs/official-preview.png',fullPage:true});await farmer.screenshot({path:'docs/farmer-preview.png',fullPage:true});
 await farmer.close();await admin.close();await official.close();
});
test('farmer edits an owned farm and calculates an explicit economics scenario',async({page})=>{
 await openFarmer(page);await page.getByLabel('Email',{exact:true}).fill('farmer@fixture.test');await page.getByLabel('Password (10+ characters)',{exact:true}).fill('fixture-password-123');await page.getByRole('button',{name:'Sign in',exact:true}).click();await searchVillage(page);await page.getByText(/^TEST FIXTURE VILLAGE/).first().click();await page.getByText('My Farms',{exact:true}).click();
 await page.getByLabel('Crop',{exact:true}).fill('TEST bean');await page.getByLabel('Area (hectares)',{exact:true}).fill('1');await page.getByLabel('Sowing date YYYY-MM-DD').fill('2026-10-01');await page.getByRole('button',{name:'Save farm',exact:true}).click();await expect(page.getByText('TEST bean · 1 ha',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Edit farm',exact:true}).click();await page.getByLabel('Area (hectares)',{exact:true}).fill('2');await page.getByRole('button',{name:'Save farm changes'}).click();await expect(page.getByText('TEST bean · 2 ha',{exact:true})).toBeVisible();
 await page.getByText('Market',{exact:true}).click();for(const [label,value] of [['yield kg','100'],['price per kg','20'],['cultivation cost','500'],['transport cost','200'],['assumptions','TEST FIXTURE assumed yield, price and costs']])await page.getByLabel(label,{exact:true}).fill(value);await page.getByRole('button',{name:'Calculate assumed margin (INR)'}).click();await expect(page.getByText(/Assumed revenue ₹2000 · margin ₹1300/)).toBeVisible();
});
test('admin marks a duplicate and reopens a resolved demonstration case',async({page,request})=>{
 const auth=async(email:string)=>(await request.post('http://127.0.0.1:8011/api/v1/auth/login',{data:{email,password:'fixture-password-123'}})).json();const farmer=await auth('farmer@fixture.test');const admin=await auth('admin@fixture.test');const official=await auth('official@fixture.test');const base='http://127.0.0.1:8011/api/v1';
 const create=async(description:string,key:string)=>(await request.post(base+'/complaints',{headers:{Authorization:'Bearer '+farmer.access_token,'Idempotency-Key':key},data:{village_id:'TEST-E2E',description,category:'shortage',consent:true}})).json();
 const canonical=await create('TEST canonical reopen report','TEST-reopen-canonical');let latest=(await request.post(base+'/admin/complaints/'+canonical.id+'/review',{headers:{Authorization:'Bearer '+admin.access_token},data:{status:'accepted',reason:'TEST reviewed canonical','sanitized_description':'TEST canonical reopen report','expected_version':canonical.version,jurisdiction:'TEST-SCOPE'}})).json();let value=await latest;
 for(const status of ['acknowledged','in_progress','resolved'])value=await(await request.post(base+'/official/complaints/'+canonical.id+'/actions',{headers:{Authorization:'Bearer '+official.access_token},data:{status,note:'TEST demonstration progress',expected_version:value.version}})).json();
 const duplicate=await create('TEST duplicate report needing review','TEST-duplicate-review');await portal(page,'http://localhost:5183','admin@fixture.test');await page.getByRole('button',{name:'Complaint inbox',exact:false}).click();await page.getByRole('button').filter({hasText:'TEST duplicate report needing review'}).click();await page.getByRole('combobox',{name:'Decision'}).selectOption('duplicate');await page.getByLabel('Canonical ticket ID').fill(canonical.id);await page.getByLabel('Reason',{exact:true}).fill('TEST duplicate of reviewed canonical report');await page.getByRole('button',{name:'Save review'}).click();await expect(page.locator('.badge.duplicate').first()).toBeVisible();
 await page.getByRole('button').filter({hasText:'TEST canonical reopen report'}).click();await page.getByLabel('Reason',{exact:true}).fill('TEST new evidence justifies reopening');await page.getByRole('button',{name:'Reopen resolved case using review reason'}).click();await expect(page.getByText('service:reopened',{exact:true})).toBeVisible();
 const invisible=await request.get(base+'/official/complaints/'+duplicate.id,{headers:{Authorization:'Bearer '+official.access_token}});expect(invisible.status()).toBe(404);
});
