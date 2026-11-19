import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const { base, email, password } = JSON.parse(input);
const browser = await chromium.launch();
try {
  for (const viewport of [{width:390,height:844},{width:1280,height:900}]) {
    const page = await browser.newPage({viewport,javaScriptEnabled:false});
    await page.goto(base+'/login');
    await page.getByRole('link',{name:'Create account',exact:true}).click();
    await page.getByRole('heading',{name:'Register for AtMem'}).waitFor();
    assert.equal(await page.getByLabel('Password',{exact:true}).getAttribute('minlength'),'12');
    await page.getByRole('link',{name:'Reset password',exact:true}).click();
    await page.getByRole('heading',{name:'Reset password'}).waitFor();
    await page.getByRole('link',{name:'Resend verification',exact:true}).click();
    await page.getByRole('heading',{name:'Resend verification'}).waitFor();
    await page.getByRole('link',{name:'Sign in',exact:true}).click();
    await page.getByLabel('Email',{exact:true}).fill(email);
    await page.getByLabel('Password',{exact:true}).fill('incorrect-password');
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await page.getByRole('alert').waitFor();
    await page.getByLabel('Email',{exact:true}).fill(email);
    await page.getByLabel('Password',{exact:true}).fill(password);
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await page.getByRole('heading',{name:'Signed in to AtMem'}).waitFor();
    await page.getByRole('button',{name:'Sign out'}).click();
    await page.getByRole('heading',{name:'Signed out'}).waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.close();
  }
  process.stdout.write(JSON.stringify({mobile:true,desktop:true,noJavaScript:true,loginRecoveryLogout:true}));
} finally { await browser.close(); }
