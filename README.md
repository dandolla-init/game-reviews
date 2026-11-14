# Dandolla

**Ready-to-upload GitHub Pages website + automatic Discord announcements.** The homepage uses the supplied cat-and-man banner, with a pale periwinkle / near-black colour palette. The first catalogue entry is the complete 6,010-word **SIGNALIS** review, including the Camus/Adler section. The site does not need a database or paid hosting.

## Quick start: getting the website online

### A. If you already have a GitHub repository with the older version

1. Unzip this download.
2. Open your **existing local repository folder** in File Explorer. In GitHub Desktop, select **Repository → Show in Explorer**.
3. Copy **all the contents inside** the extracted `signalis-review-site` folder into the root of your existing repository, replacing the old project files. **Do not copy the outer folder itself. Do not remove your `.git` folder.** Make sure hidden `.github/workflows/publish.yml` is copied as well. Your GitHub settings, custom domain, webhook secret, and repository history are not deleted by replacing project files.
4. In GitHub Desktop, **Commit to main**, then **Push origin**. Wait for the **Publish reviews** workflow to finish under GitHub → Actions.
5. Reopen your GitHub Pages URL and refresh. The new banner, catalogue layout, and media sections will be live.

Changing these project files will **not** announce SIGNALIS again, because it was already published; announcements only happen when a review becomes newly public. To announce it intentionally, go to **GitHub → Actions → Publish reviews → Run workflow**, enter `signalis-alatyr` in **announce_slug**, and run the workflow.

### B. If this is your first GitHub Pages repository

1. On GitHub, create a **public** repository (for example, `game-reviews`), with `main` as its default branch. GitHub Pages on a free personal account requires a public repository.
2. On your computer, extract the ZIP and open GitHub Desktop. Create or clone the repository locally, and place **the contents** of the extracted `signalis-review-site` folder inside the local repository root. Make sure the hidden `.github` directory is included. **Commit to main** and **Push origin**. Alternatively, use Git commands to add, commit, and push those files.
3. On GitHub, open **Settings → Pages → Build and deployment → Source → GitHub Actions**. The included `publish.yml` will build and publish the website after each push to `main`.
4. Visit **Actions → Publish reviews** to monitor deployment. Your initial address will be `https://YOUR-USERNAME.github.io/YOUR-REPOSITORY/` (or `https://YOUR-USERNAME.github.io/` if you named the repository `YOUR-USERNAME.github.io`).
5. Set up the Discord webhook (below). You can then manually announce SIGNALIS once.

**Keep `.github/workflows/publish.yml` in the repository.** It is required for automatic building and announcements. You do not need to upload the generated `_site` directory; GitHub builds it automatically.

## Discord automatic announcements

1. In Discord, open your server → **Server Settings → Integrations → Webhooks → New Webhook**. Select the announcement channel, then copy the webhook URL. You need permission to manage webhooks in that server/channel.
2. In your GitHub repository open **Settings → Secrets and variables → Actions → Secrets → New repository secret**. Add a secret named **`DISCORD_WEBHOOK_URL`** and paste the webhook URL.
3. Whenever a review first becomes publicly listed in `catalogue.json` with `published: true`, the GitHub workflow deploys the updated website and **then** announces the review on Discord. Edits to already-public reviews, cover art, audio, and YouTube links don't trigger duplicate announcements.
4. For an existing review, use **Actions → Publish reviews → Run workflow → `announce_slug` = `signalis-alatyr`**. Leave the field blank for a deploy-only run. **Manual announcements intentionally can repeat** if you invoke them multiple times.

Optional: for a Discord **Forum channel**, create the webhook in that forum channel and add a GitHub Actions **repository variable** (not secret) `DISCORD_FORUM_MODE` set to `true`, so each announcement creates its own forum thread.

Never expose, commit, screenshot, or send anyone your webhook URL. Rotate it via Discord if compromised.

## Editing the homepage catalogue (manual order)

**`catalogue.json`** controls exactly which published reviews appear on the homepage **and** archive and in which order. It currently contains:

```json
{
  "review_order": [
    "signalis-alatyr"
  ]
}
```

To add a new review, publish its Markdown file in `posts/` (see below), then add its `slug` to this array. To put a review first, move its slug to the top. To hide one from public listings, remove its slug. A review marked `published: false` cannot be listed, and the build will explain the mistake if you try. The catalogue is intentionally hand-curated; merely creating a post file will not automatically add it to the homepage.

No coding is required to reorder the catalogue; the GitHub website's file editor can modify `catalogue.json` directly. Commit the edit to `main` to trigger deployment.

## Add a new written review

1. Duplicate **`posts/_TEMPLATE.md`** as `posts/the-game-name.md`.
2. Change its metadata fields: `title`, `slug`, `date`, `game`, `description`, `tags`, and `cover_image`. Write the article in Markdown below the second `---` line.
3. Put your game artwork in `assets/covers/` (create that folder when needed); set `cover_image: "/assets/covers/the-game-name.jpg"`. Alternatively, use an **HTTPS image URL**. Set `cover_alt` to an image description. Choose artwork you have permission to publish.
4. Set **`published: true`**, and add the matching slug to `catalogue.json`.
5. Commit and push the changes. Once deployment succeeds, the article is available and Discord automatically receives one announcement.

For the SIGNALIS post, `cover_image` currently points to its Steam promotional image. If visitors cannot load that external image, the page falls back to the included local portrait SIGNALIS-style SVG. You can replace this with your own local game cover at any time by updating the field.

## Audio voice-over: upload whenever it's ready

Each review supports a native HTML audio player for your narration. To add it to SIGNALIS:

1. Export the recording as MP3 (recommended), M4A, or OGG. For lengthy spoken-word recordings, **mono MP3 at 64–96 kbps** is normally good enough and keeps the file small.
2. Put the file into **`assets/audio/`** in your repository, for example `assets/audio/signalis-alatyr.mp3`.
3. Open `posts/signalis-alatyr.md` and change the front matter to:

```yaml
audio: "/assets/audio/signalis-alatyr.mp3"
```

4. Commit and push. The article's **Audio narration** section will now display an actual player with play/pause and seeking controls. Before the recording exists, it displays a quiet “Narrated edition coming soon” placeholder instead.

**File-size caveat:** Standard GitHub repositories reject individual files over **100 MB**, and GitHub recommends keeping individual files much smaller. For long recordings, compress the MP3 rather than uploading a raw WAV file. If you eventually have many audio files, consider dedicated audio storage; the site also accepts a direct HTTPS audio URL in the `audio` field.

If an `audio` field points to a missing local file, the site build deliberately fails with a descriptive error so the published site cannot contain a broken player.

## Add your YouTube video review later

In the review's Markdown front matter, set:

```yaml
youtube: "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
```

After you commit, the **Video review** section displays a “Watch on YouTube” link. Until then, the site displays “Video essay to follow.” No embedded YouTube tracker or third-party player is loaded into the article itself.

## Change colours and artwork

- `assets/home-banner.png` — the homepage hero image, copied directly from your uploaded file.
- `assets/styles.css` — global colours. The current design is deliberately keyed to the periwinkle blue and nearly black ink tones in your supplied banner.
- `site.json` — site name, author, description and homepage subtitle. The homepage headline and catalogue label can be edited in `scripts/build.py` (`render_index`).
- `posts/your-review.md` → optional `accent: "#7895c9"` — changes selected *accent details* on that article without replacing the site-wide visual identity. Each article can have its own accent later, if you decide you want it.
- `cover_image` in each post — the poster/reference image visible in the catalogue and article header.

## Optional: custom domain

Configure your domain under **GitHub → Repository Settings → Pages → Custom domain**. Then add the GitHub Actions **repository variable** `SITE_URL` set to your full public URL, e.g. `https://reviews.example.com`, for correct canonical links and Discord article URLs.

## Local preview (optional)

Install Python 3.12 or newer, then in the project folder:

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/build.py
cd _site
python -m http.server 8000
```

Open `http://localhost:8000/`. If using a custom domain or testing GitHub Pages subpaths, setting `SITE_URL` changes the generated paths, so for the simple local preview, **leave `SITE_URL` unset**.

## Project structure

```
.github/workflows/publish.yml  # GitHub Pages + Discord deployment
assets/
  home-banner.png             # Your supplied header artwork
  cover.svg                   # General placeholder artwork
  signalis-placeholder.svg    # SIGNALIS portrait fallback artwork
  favicon.svg
  audio/                      # Future narration MP3 files
  styles.css / site.js
catalogue.json                # Hand-curated homepage review list
posts/
  signalis-alatyr.md          # Full original review
  _TEMPLATE.md                # Template for future reviews
scripts/
  build.py                    # Builds HTML without a database
  announce.py                 # Posts Discord embed after deploy
tests/test_site.py
site.json
requirements.txt
```

Site implementation: Python + Markdown to pre-rendered HTML/CSS/vanilla JS, GitHub Pages and GitHub Actions. No CMS, database, cookies, analytics, or paid hosting required.

---

## ElevenLabs narration bridge (optional, new in Version 4)

The site's **Listen** player can now use your existing ElevenLabs voice. The narration is generated **once per article in GitHub Actions**, assembled into one MP3, committed to `assets/audio/`, and served as a normal static recording by GitHub Pages. Readers can play, pause, scrub and change speed using their browser's media controls. They **never need ElevenLabs credentials**, and replaying the file does not call ElevenLabs or consume further API credits.

**Why pre-generate instead of using a live on-page API request?** GitHub Pages is static; putting your ElevenLabs API key in frontend JavaScript would expose it to the public. A live pay-per-play reader would require a secure server-side gateway, access limits and spending controls. The included publishing-time generator avoids those extra services and risks.

### 1. Link your existing ElevenLabs voice to GitHub

1. Open [ElevenLabs](https://elevenlabs.io/) and find the **voice ID** for the cloned or chosen voice that you already use. This is the voice identifier, **not** the voice's friendly display name. You can use the ElevenLabs voice dashboard or its voices API to obtain it.
2. Create a dedicated **ElevenLabs API key** with only the permissions and credit limits you need (use the ElevenLabs account's API settings). This key is **not** your Discord webhook URL or voice ID.
3. In GitHub, go to your review repository → **Settings → Secrets and variables → Actions → Secrets → New repository secret**, then create `ELEVENLABS_API_KEY` and paste the ElevenLabs API key. Do **not** enter it in the website's Markdown, HTML, JavaScript, or `site.json`.
4. Under **Settings → Secrets and variables → Actions → Variables → New repository variable**, create `ELEVENLABS_VOICE_ID` and paste the voice ID.
5. Optionally add a variable `ELEVENLABS_MODEL_ID`. Default: `eleven_multilingual_v2` (a stable long-form model). Other supported IDs include `eleven_v4`, `eleven_v3`, `eleven_flash_v2_5`, and `eleven_turbo_v2_5`. Different models have different character limits and costs.
6. Your repository must permit GitHub Actions to commit generated MP3s to `main`. The workflow requests `contents: write`; on repositories with restrictive branch protection, adjust the rules or use manual upload instead.

### 2. Generate the existing SIGNALIS review once

The file `posts/signalis-alatyr.md` is **already opted in**:

```yaml
audio: ""
narration: elevenlabs
```

After configuring the API key and voice ID, navigate to **Actions → Publish reviews → Run workflow**, then set:

- `narrate_slug` = `signalis-alatyr`
- `confirm_tts_cost` = **checked / true**
- `regenerate_audio` = **unchecked / false**
- `announce_slug` = *(blank, unless you intentionally want another Discord announcement)*

Click **Run workflow**. It will convert the Markdown text to speakable prose, split it into safe-length chunks, synthesize them via ElevenLabs, join them with FFmpeg, commit `assets/audio/signalis-alatyr.mp3`, and deploy the new audio player. It only commits the audio file; **no secret or voice credentials go onto the website**. This manual run does not send a duplicate Discord announcement.

**Estimated input size:** SIGNALIS is approximately **40,674 narration characters**, divided into **five** API requests using the default model. ElevenLabs charges based on character/model usage, so review the available credits and current pricing **before checking the consent box**. The finished MP3 will probably be several tens of MB. The exact generation cost and file size cannot be determined without actually running the API.

### 3. Automatic narration for *new* reviews

For a future review, leave `audio: ""` and set `narration: elevenlabs` in its front matter. When you first publish that review (`published: true` and included in `catalogue.json`), the normal GitHub Pages publishing workflow will generate its narration automatically **if** the API key and voice ID have been configured. This consumes ElevenLabs credits once for that review. The finished MP3 is saved in the repository to prevent later builds charging again.

If you prefer to record your own voice or upload an ElevenLabs MP3 manually, keep `narration: manual` and set `audio: "/assets/audio/your-file.mp3"`. A manually specified file takes precedence, and the generator will not replace it.

### 4. Updating the narration after editing an article

- **Editing a review** updates its text on the site, but does **not** re-generate audio or spend credits again. The old narration remains until you intentionally replace it.
- **Regenerate on purpose:** Run the GitHub workflow with the same `narrate_slug`, check `confirm_tts_cost`, and check `regenerate_audio`. This **will** consume credits again and replace the MP3.
- **Switch back to your own recorded narration:** set `narration: manual` and supply a file in `audio:`. This overrides the auto-generated MP3, without deleting it from the repository.
- **Preview character usage without paid requests:** locally run `python scripts/narrate.py --slug signalis-alatyr --dry-run` after installing requirements.

### Limits, billing and privacy

- Site visitors never access your API key, and the review is always readable even if narration is not available.
- If GitHub secrets are missing, the workflow skips automatic narration on a new publication; you can run a manual generation later. The existing site and Discord notifications still work.
- Generating an article uses your ElevenLabs account's API credits. The generator is opt-in, enforces an input-size safety limit of 120,000 characters per review, and refuses to overwrite an existing MP3 unless you explicitly request regeneration.
- MP3 files are stored in your public GitHub repository and served publicly; do not put sensitive or private speech in them. GitHub disallows files over 100 MB, so the generator refuses files larger than 95 MB. For very long articles, reduce bitrate or use external audio storage.
- If generation fails partway through, any API requests already completed may still have consumed credits even though no finished MP3 is published. Before repeating a failed run, check your ElevenLabs usage.
- ElevenLabs' commercial use rights and API quotas depend on your subscription and voice rights. Make sure your voice and publication rights allow the intended use.

### Narration workflow in one line

`Review in posts/*.md → GitHub Actions → ElevenLabs (private API key) → one MP3 → GitHub Pages audio player`

**Version 4 files:** `scripts/narrate.py`, updates to `.github/workflows/publish.yml`, and the per-post `narration:` field. YouTube support, the manual catalogue, your banner and the Discord webhook remain unchanged.
