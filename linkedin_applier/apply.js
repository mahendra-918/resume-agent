const { chromium } = require('playwright');
const readline = require('readline');
const fs = require('fs');
const { answersDatabase, saveAnswer, handleNewQuestion, calculateSimilarity, getMostSimilarQuestion, normalizeAndTokenize } = require('./utils_Numeric.js');
const { answerDropDown, handleNewAnswerDropDown } = require('./utils_DropDown');
const { answerBinaryQuestions, handleNewQuestionBinary } = require('./utils_Binary.js');

const LINKEDIN_EMAIL = process.env.LINKEDIN_EMAIL;
const LINKEDIN_PASSWORD = process.env.LINKEDIN_PASSWORD;
const LINKEDIN_PHONE = process.env.LINKEDIN_PHONE || '';
const JOB_URL = process.env.LINKEDIN_JOB_URL || '';
const RESUME_PATH = process.env.LINKEDIN_RESUME_PATH || '';
const JOB_KEYWORD = process.argv[2] || 'Software Engineer';
const SESSION_FILE = './linkedin_session.json';

if (!LINKEDIN_EMAIL || !LINKEDIN_PASSWORD) {
  console.error('LINKEDIN_EMAIL and LINKEDIN_PASSWORD env vars are required');
  process.exit(1);
}

function loadSession() {
  if (fs.existsSync(SESSION_FILE)) {
    try { return JSON.parse(fs.readFileSync(SESSION_FILE, 'utf8')); } catch {}
  }
  return null;
}

function saveSession(cookies) {
  fs.writeFileSync(SESSION_FILE, JSON.stringify(cookies, null, 2));
  console.log('Session saved');
}

async function answerNumericQuestions(page) {
  const questionElements = await page.$$('label.artdeco-text-input--label');
  for (let questionElement of questionElements) {
    const questionText = await questionElement.textContent();
    console.log("Question", questionText);
    const inputId = await questionElement.getAttribute('for');
    const answerElement = await page.$(`#${inputId}`);

    const result = getMostSimilarQuestion(questionText.trim());
    let mostSimilarQuestion = null;
    let maxSimilarity = 0;

    if (result) {
      mostSimilarQuestion = result.mostSimilarQuestion;
      maxSimilarity = result.maxSimilarity;
    }

    let answer = null;
    if (mostSimilarQuestion && maxSimilarity > 0.7) {
      answer = answersDatabase[mostSimilarQuestion];
    } else {
      answer = await handleNewQuestion(questionText.trim());
    }

    if (answerElement && answer !== null) {
      await answerElement.fill(answer);
    } else {
      console.log(`No answer found for: "${questionText.trim()}".`);
    }
  }
}

async function answerQuestions(page) {
  await answerNumericQuestions(page);
  await answerBinaryQuestions(page);
  await answerDropDown(page);
}

async function uploadResumeIfNeeded(page) {
  if (!RESUME_PATH) return;
  try {
    // Skip if a resume is already selected (LinkedIn shows a PDF card)
    const alreadySelected = await page.$('.jobs-document-upload__uploaded-file, [class*="uploaded-file"]');
    if (alreadySelected) {
      console.log('Resume already selected — skipping upload');
      return;
    }
    const fileInput = await page.$('input[type="file"][id*="upload-resume"]');
    if (fileInput) {
      await fileInput.evaluate(el => { el.style.display = 'block'; el.style.opacity = '1'; });
      await fileInput.setInputFiles(RESUME_PATH);
      console.log(`Resume uploaded: ${RESUME_PATH}`);
      await page.waitForTimeout(3000);
    }
  } catch (error) {
    console.log('Resume upload skipped:', error.message);
  }
}

async function handleNextOrReview(page) {
  let hasNextButton = true;

  while (hasNextButton) {
    try {
      await uploadResumeIfNeeded(page);
      const nextButton = await page.$('button[aria-label="Continue to next step"]');
      if (nextButton) {
        await nextButton.click();
        await page.waitForTimeout(3000);
        await answerQuestions(page);
      } else {
        hasNextButton = false;
      }
    } catch (error) {
      hasNextButton = false;
    }
  }

  try {
    const reviewButton = await page.$('button[aria-label="Review your application"]');
    if (reviewButton) {
      await reviewButton.click();
      console.log("Review button successfully clicked");

      const submitButton = await page.$('button[aria-label="Submit application"]');
      if (submitButton) {
        await submitButton.click();
        console.log("Submit button clicked");

        await page.waitForTimeout(5000);
        await page.waitForSelector('button[aria-label="Dismiss"]', { visible: true });
        let modalButton = await page.$('button[aria-label="Dismiss"]');
        let attempts = 0;
        const maxAttempts = 10;

        while (attempts < maxAttempts) {
          try {
            await modalButton.evaluate(b => b.click());
            console.log("Dismiss button clicked");
            break;
          } catch (error) {
            console.log(`Attempt ${attempts + 1} failed: ${error.message}`);
            attempts++;
            await page.waitForTimeout(500);
            modalButton = await page.$('button[aria-label="Dismiss"]');
          }
        }

        if (attempts === maxAttempts) {
          console.log("Failed to click the Dismiss button after multiple attempts.");
        }
      }
    }
  } catch (error) {
    console.log('Review button not found or failed to click:', error.message);
  }
}

async function fillPhoneNumber(page, phoneNumber) {
  if (!phoneNumber) return;
  try {
    // Try multiple label variations LinkedIn uses
    const labels = ["Mobile phone number", "Phone", "Phone number", "Phone*"];
    for (const label of labels) {
      try {
        const el = await page.getByLabel(label, { exact: false });
        if (await el.count() > 0) {
          await el.first().fill(phoneNumber);
          console.log(`Filled phone via label "${label}"`);
          return;
        }
      } catch {}
    }

    // Fallback: find input inside a label containing "Phone"
    const phoneLabel = await page.$('label:has-text("Phone")');
    if (phoneLabel) {
      const inputId = await phoneLabel.getAttribute('for');
      if (inputId) {
        await page.fill(`#${inputId}`, phoneNumber);
        console.log('Filled phone via for attribute');
        return;
      }
    }

    // Last resort: fill any visible text input that looks like a phone field
    const inputs = await page.$$('input[type="text"], input[type="tel"]');
    for (const input of inputs) {
      const id = (await input.getAttribute('id') || '').toLowerCase();
      const placeholder = (await input.getAttribute('placeholder') || '').toLowerCase();
      if (id.includes('phone') || placeholder.includes('phone')) {
        await input.fill(phoneNumber);
        console.log('Filled phone via id/placeholder match');
        return;
      }
    }
    console.log('Phone input field not found');
  } catch (error) {
    console.error("Error filling phone number:", error);
  }
}

async function getJobName(page) {
  try {
    const jobNameElement = await page.$('//h1[contains(@class,"t-24 t-bold")]//a[1]');
    if (jobNameElement) {
      return (await jobNameElement.textContent()).trim();
    }
    return "Unknown Job";
  } catch (error) {
    return "Unknown Job";
  }
}

async function doLogin(page, context) {
  await page.goto('https://www.linkedin.com/login', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(2000);

  // If already redirected to feed, we're already logged in
  if (page.url().includes('/feed') || page.url().includes('/jobs')) {
    console.log('Already logged in');
    const cookies = await context.cookies();
    saveSession(cookies);
    return;
  }

  await page.waitForSelector('input[name="session_key"]', { timeout: 30000 });
  await page.fill('input[name="session_key"]', LINKEDIN_EMAIL);
  await page.fill('input[name="session_password"]', LINKEDIN_PASSWORD);
  await page.click('button[type="submit"]');

  // Wait up to 3 minutes — user may need to solve CAPTCHA manually
  await page.waitForFunction(
    () => window.location.href.includes('/feed') || window.location.href.includes('/jobs'),
    { timeout: 180000 }
  );
  console.log('Login successful');
  const cookies = await context.cookies();
  saveSession(cookies);
}

async function applyToJob(page, jobUrl, context) {
  await page.goto(jobUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(5000);

  // Diagnostic: log the URL we actually landed on and the page title
  console.log(`Landed URL: ${page.url()}`);
  console.log(`Page title: ${await page.title()}`);

  // Detect "I'm interested" — appears on logged-out / promoted-preview layouts
  // when the session is stale. Force a re-login if so.
  const interestedOnly = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button, a[role="button"]'));
    const hasInterested = btns.some(el => (el.innerText || '').trim() === "I'm interested" || (el.innerText || '').trim() === "I’m interested");
    const hasApply = btns.some(el => {
      const t = (el.innerText || '').trim();
      const a = el.getAttribute('aria-label') || '';
      return t.includes('Apply') || a.includes('Apply');
    });
    return hasInterested && !hasApply;
  });

  if (interestedOnly && context) {
    console.log("Detected \"I'm interested\" without Apply — session likely stale, re-logging in");
    try { fs.unlinkSync(SESSION_FILE); } catch {}
    await doLogin(page, context);
    await page.goto(jobUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(5000);
    console.log(`After re-login URL: ${page.url()}`);
  }

  const alreadyApplied = await page.$('span.artdeco-inline-feedback__message:has-text("Applied")');
  if (alreadyApplied) {
    console.log('Already applied. Skipping.');
    return;
  }

  // Detect external "Apply" (non-Easy-Apply) — skip without retrying for 15s
  const isExternalApply = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button, a[role="button"], a, [role="button"], span'));
    const hasEasy = btns.some(el => {
      const t = (el.innerText || '').trim();
      const a = el.getAttribute('aria-label') || '';
      return t.includes('Easy Apply') || a.includes('Easy Apply');
    });
    if (hasEasy) return false;
    // External apply buttons typically have aria-label starting with "Apply to"
    // and an external-link icon. Plain "Apply" without "Easy" means external.
    return btns.some(el => {
      const t = (el.innerText || '').trim();
      const a = el.getAttribute('aria-label') || '';
      return /^Apply( to | on |$)/i.test(t) || /^Apply( to | on |$)/i.test(a);
    });
  });

  // Wait up to 15s for Easy Apply button to appear (lazy-loaded)
  let clicked = false;
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    try {
      // Method 1: aria-label match (most reliable — "Easy Apply to <Company>")
      const byAria = await page.$('button[aria-label*="Easy Apply"]');
      if (byAria) {
        await byAria.scrollIntoViewIfNeeded();
        await byAria.click();
        console.log('Easy Apply clicked (by aria-label)');
        clicked = true;
        break;
      }

      // Method 2: button containing text "Easy Apply"
      const byText = await page.$('button:has-text("Easy Apply")');
      if (byText) {
        await byText.scrollIntoViewIfNeeded();
        await byText.click();
        console.log('Easy Apply clicked (by text)');
        clicked = true;
        break;
      }

      // Method 3: scroll & re-check for lazy-rendered buttons
      await page.evaluate(() => window.scrollBy(0, 200));

      // Method 4: find the <span>Easy Apply</span>, walk up to the nearest
      // <button> / [role="button"] ancestor, get its on-page coordinates, and
      // click via Playwright (which dispatches real mouse events React listens to).
      const target = await page.evaluateHandle(() => {
        const all = document.querySelectorAll('span, button, a, [role="button"], div');
        for (const el of all) {
          const t = (el.innerText || '').trim();
          if (t === 'Easy Apply') {
            let cur = el;
            while (cur && cur !== document.body) {
              if (cur.tagName === 'BUTTON' || cur.getAttribute('role') === 'button' || cur.tagName === 'A') {
                return cur;
              }
              cur = cur.parentElement;
            }
            return el; // fallback
          }
        }
        return null;
      });
      const targetEl = target.asElement();
      if (targetEl) {
        await targetEl.scrollIntoViewIfNeeded();
        await targetEl.click({ timeout: 5000 });
        console.log('Easy Apply clicked (by ancestor walk + playwright click)');
        clicked = true;
        break;
      }
    } catch (e) { console.log('Click attempt error:', e.message); }

    if (isExternalApply) break; // no point retrying — it's an external apply page
    await page.waitForTimeout(1000);
  }

  if (!clicked) {
    if (isExternalApply) {
      console.log('External Apply job (not Easy Apply). Skipping cleanly.');
      return;
    }
    const btns = await page.evaluate(() =>
      Array.from(document.querySelectorAll('button, a[role="button"], [role="button"]'))
        .map(b => (b.innerText || '').trim() || b.getAttribute('aria-label') || '')
        .filter(t => t)
    );
    console.log('Clickables found on page:', JSON.stringify(btns));
    console.log('No Easy Apply button found. Skipping.');
    return;
  }

  // Wait for the Easy Apply modal to actually open. LinkedIn now renders the
  // modal inside a shadow-DOM (#interop-outlet) so the old selectors miss it.
  // Best signal: a "Next", "Continue to next step", "Review", or "Submit" button.
  try {
    await page.waitForFunction(() => {
      const all = document.querySelectorAll('button, [role="button"]');
      for (const el of all) {
        const t = (el.innerText || '').trim();
        const a = el.getAttribute('aria-label') || '';
        if (/^Next$/i.test(t) || /Continue to next step/i.test(a) || /Review your application/i.test(a) || /Submit application/i.test(a)) return true;
      }
      return !!document.querySelector('div[role="dialog"], .jobs-easy-apply-modal, .artdeco-modal, #interop-outlet');
    }, { timeout: 15000 });
    console.log('Easy Apply modal opened');
  } catch {
    console.log('Easy Apply modal did NOT open within 15s — aborting');
    return;
  }
  await page.waitForTimeout(2000);

  const emailLabel = await page.$('label:has-text("Email address")') || await page.$('label:has-text("Email")');
  if (emailLabel) {
    const emailInputId = await emailLabel.getAttribute('for');
    await page.selectOption(`#${emailInputId}`, LINKEDIN_EMAIL);
  }

  try {
    const phoneCountryLabel = await page.$('label:has-text("Phone country code")');
    if (phoneCountryLabel) {
      const phoneCountryInputId = await phoneCountryLabel.getAttribute('for');
      await page.selectOption(`#${phoneCountryInputId}`, 'India (+91)');
    }
  } catch (error) {
    console.log('Phone country code dropdown not found:', error.message);
  }

  await fillPhoneNumber(page, LINKEDIN_PHONE);

  await page.waitForTimeout(3000);
  await uploadResumeIfNeeded(page);
  await answerQuestions(page);
  await handleNextOrReview(page);
}

(async () => {
  const browser = await chromium.launch({ headless: false, channel: 'chrome' });

  const savedCookies = loadSession();
  const context = savedCookies
    ? await browser.newContext()
    : await browser.newContext();
  const page = await context.newPage();

  try {
    // Try restoring session from saved cookies
    if (savedCookies) {
      await context.addCookies(savedCookies);
      await page.goto('https://www.linkedin.com/feed/', { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(2000);
      const url = page.url();
      if (url.includes('/feed') || url.includes('/jobs') || url.includes('/in/')) {
        console.log('Session restored — skipping login');
      } else {
        console.log('Session expired — logging in again');
        await doLogin(page, context);
      }
    } else {
      await doLogin(page, context);
    }

    if (JOB_URL) {
      // ── Pipeline mode: apply to a single specific job ──
      await applyToJob(page, JOB_URL, context);
    } else {
      // ── Standalone mode: search and apply to all Easy Apply jobs ──
      const searchUrl = `https://www.linkedin.com/jobs/search/?keywords=${encodeURIComponent(JOB_KEYWORD)}&f_LF=f_AL`;
      await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForTimeout(5000);
      console.log("Easy Apply filter applied via URL");

      let currentPage = 1;
      let jobCounter = 0;

      while (true) {
        console.log(`Navigating to page ${currentPage}`);
        const jobListings = await page.$$('//div[contains(@class,"display-flex job-card-container")]');
        console.log(`Jobs on page ${currentPage}: ${jobListings.length}`);

        if (jobListings.length === 0) {
          console.log(`No jobs found on page ${currentPage}. Exiting.`);
          break;
        }

        for (let job of jobListings) {
          jobCounter++;
          console.log(`Processing job ${jobCounter} on page ${currentPage}`);
          await job.click();
          await page.waitForTimeout(2000);
          const jobUrl = page.url();
          await applyToJob(page, jobUrl, context);
        }

        currentPage++;
        const nextPageButton = await page.$(`button[aria-label="Page ${currentPage}"]`);
        if (nextPageButton) {
          await nextPageButton.click();
          await page.waitForTimeout(5000);
          console.log(`Navigated to page ${currentPage}`);
        } else {
          console.log(`No more pages. Exiting.`);
          break;
        }
      }
    }
  } catch (error) {
    console.error("Script error:", error);
  } finally {
    if (process.env.LINKEDIN_KEEP_OPEN === '1') {
      console.log('LINKEDIN_KEEP_OPEN=1 — leaving browser open for inspection');
    } else {
      await browser.close();
    }
  }
})();
