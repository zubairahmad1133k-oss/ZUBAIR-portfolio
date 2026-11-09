# ZUBAIR OS — Your Digital Headquarters

Your original portfolio design, served by Flask from a database, with a private admin dashboard
at `/admin`. Python · Flask · SQLAlchemy · SQLite locally · PostgreSQL in production.

---
## 1. Run it on your computer

```
python -m venv venv
venv\Scripts\activate            (Windows)      source venv/bin/activate   (Mac/Linux)
pip install -r requirements.txt
copy .env.example .env           (Windows)      cp .env.example .env       (Mac/Linux)

flask --app app init-db
flask --app app seed-projects
flask --app app create-admin
flask --app app run --port 5001
```
Open http://127.0.0.1:5001 — click **Admin** in the top menu (or go to `/admin`).
`create-admin` asks for a username, email and password (12+ characters, upper + lower case, a number).
The password is typed hidden and never stored in any file. Forgot it? `flask --app app reset-admin-password`.

New database tables are created automatically at start-up. (They are never altered; see "Changing tables later".)

## 2. Run the automated tests
```
pip install -r requirements-dev.txt
python -m pytest
```

## 3. What is in the admin
| Page | What it does |
|---|---|
| Overview | Real counts, notifications (unread counter, mark as read), activity feed, goals summary |
| Analytics | Visitors, page views, project views, contact clicks, enquiries; interactive chart; Today / 7 / 30 / 90 days / custom range |
| Projects | Add, edit, delete, publish/unpublish, reorder, preview drafts, thumbnail, links, **Code highlights** |
| Enquiries | Every form submission; status (new / contacted / in progress / completed), private notes, search, filter, delete |
| Media | Upload images and PDFs, rename, folders, attach to projects, delete. PDFs are private |
| Goals | Goals with your own progress %, target dates, completion, achievements |
| AI Analyst | Rule-based analysis of your real numbers (no key needed). Optional AI wording if you add a key |
| Account | Change email and password (signs out other devices) |

### Analytics — what is and is not recorded
* Recorded: a random visitor id in a first-party cookie, the page path, the referring website's host name, and button clicks.
* NOT recorded: IP address, browser/user-agent text, fingerprints.
* Not counted: visitors who send Do-Not-Track / Global-Privacy-Control, bots, and your own logged-in visits.
* A WhatsApp/email **button click** is a click only. A **confirmed enquiry** exists only when someone submits the form.
* All times are UTC. Nothing is estimated or random; with no visits you see zeros.

### Showing a project without giving it away
Each project page can show: description, technologies, screenshots, a live-demo link, and **Code highlights** —
short excerpts that *you* paste in (Admin → Projects → Code). Visitors only ever see those excerpts.
No download link, repository path or file listing is exposed, and the page says the full source is private.
Advice: keep your real GitHub repo **private**, never paste passwords/keys into an excerpt, and remember anything
shown on a web page can be copied, so only publish what you are happy to share.

---
## 4. Deploy for free (Render + Supabase)
You get a free hosting account, not guaranteed uptime. The free web service sleeps when idle (the first visit then takes ~30–60 s).

1. **GitHub:** create a *private* repository and upload this folder (`.env` is already ignored).
2. **Supabase:** create a project → *Project Settings → Database* → copy the connection string
   (use the pooled/IPv4 one) and make sure it ends with `?sslmode=require`. This is your `DATABASE_URL`.
3. **Render:** *New → Web Service* → pick your repo, then:
   * Build command: `pip install -r requirements-production.txt`
   * Start command: `gunicorn "app:create_app()" --workers 1 --threads 4 --timeout 60`
   * Health check path: `/health`
   * Environment variables:
     `APP_ENV=production`, `SECRET_KEY=<64 random characters>`, `DATABASE_URL=<from Supabase>`,
     `SITE_URL=https://your-app.onrender.com`, `ADMIN_SETUP_TOKEN=<another long random value>`,
     and `PYTHON_VERSION=3.12.3` if Render picks a version that fails.
   * Generate random values with: `python -c "import secrets; print(secrets.token_hex(32))"`
4. Open `https://your-app.onrender.com/admin/setup`, enter the setup token and create your admin account,
   then **delete `ADMIN_SETUP_TOKEN`** from Render. (The page only works while no admin exists.)
5. Add your projects, then publish.

### Persistent storage — please read
* **Uploaded images/PDFs on Render's free plan are NOT permanent.** The disk is wiped on every redeploy/restart.
  Your **database is safe** (it lives on Supabase), but uploaded files will disappear.
* Options: (a) Render's paid persistent disk and set `UPLOAD_FOLDER` to its mount path; (b) keep uploads minimal and
  re-upload after deploys. **Supabase Storage is NOT implemented** in this version.
* Free Supabase projects may pause after a period of inactivity. Check their current free-tier terms.

### Changing tables later
`create_all` only adds missing tables; it never changes existing ones. If a future version changes a table,
use the already-installed Flask-Migrate: `flask --app app db init` (once), `db migrate -m "msg"`, `db upgrade`.

## 4b. Deploy on Vercel (free) — works, with limits
Vercel runs your site as short-lived functions, so a few things differ from Render:

| Works on Vercel | Does NOT work on Vercel |
|---|---|
| Public portfolio, project pages, enquiry form, analytics, admin, goals, AI Analyst | **File uploads** (thumbnails, screenshots, PDFs): no permanent disk. The upload forms show a notice and refuse files |
| Everything stored in your Supabase PostgreSQL database | SQLite: you **must** use Supabase/PostgreSQL |

Steps:
1. Put the **whole** `ZUBAIR_OS` folder (not just `index.html`) in a private GitHub repository. The files `vercel.json` and `api/index.py` must be in the repository root.
2. Supabase → *Project Settings → Database* → copy the **Transaction pooler** connection string and add `?sslmode=require` at the end if it is not there.
3. Vercel → *Add New → Project* → import the repository. Framework preset: **Other**. Leave build/output settings empty.
4. Vercel → *Settings → Environment Variables* (then redeploy):
   `APP_ENV=production` · `SECRET_KEY=<64 random characters>` · `DATABASE_URL=<Supabase string>` ·
   `SITE_URL=https://your-project.vercel.app` · `ADMIN_SETUP_TOKEN=<long random value>`
5. Open `https://your-project.vercel.app/admin/setup`, create your admin, then delete `ADMIN_SETUP_TOKEN` and redeploy.
6. Log in → Projects → click **Add the 4 starter projects**, then edit each one and add its **Live website URL**.

If you see Vercel's own "404 NOT_FOUND" page, the repository root is wrong (missing `vercel.json` / `api/index.py`).
If you see a 500 error, open Vercel → Deployments → Logs; a missing `DATABASE_URL` is reported there in plain words.
**Honest note:** this Vercel set-up follows Vercel's documented Flask pattern but has NOT been deployed or tested by its author.

---
## 5. Settings (.env)
`APP_ENV` (development/production) · `SECRET_KEY` (required in production) · `DATABASE_URL` (blank = SQLite) ·
`SITE_URL` · `UPLOAD_FOLDER` · `ADMIN_SETUP_TOKEN` (hosts without a terminal) · `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` (optional AI wording).

## 6. Security summary
Hashed passwords · CSRF on every form · login rate limit (5/min, 30/hour, failures only) · secure/HTTP-only/SameSite cookies ·
sessions end on password change · all admin routes require login · uploads checked by real file content, random file names,
5 MB images / 10 MB PDFs · PDFs only served to the logged-in admin · output auto-escaped · security headers incl. CSP ·
no default credentials · production errors show a generic page.

## 7. Honest status
* Every template was render-tested with sample data, and all Python files compile.
* The test suite in `tests/` was written to cover every area in your brief, **but it has not been run by its author** in the
  environment this was built in (no internet to install Flask libraries). Run `python -m pytest` and report failures.
* The optional AI explanation (`ANTHROPIC_API_KEY`) is **untested**; the rule-based analysis is the main feature.
* Not implemented: Supabase Storage, e-mail alerts for new enquiries (dashboard notifications only), two-factor login.
