# Release Danganronpa before SIGNALIS

The Danganronpa draft is UNPUBLISHED. This update adds a dark/light switch only; your live SIGNALIS page is still listed for now. No webhook or ElevenLabs key has been configured by this change.

1. Finish both reviews, editing `posts/signalis-alatyr.md` and replacing the Danganronpa placeholder.
2. To hide SIGNALIS until after Danganronpa: in ONE commit set SIGNALIS `published: false` and set `catalogue.json` to `{"review_order":[]}`. Homepage remains online but the catalogue is empty.
3. Set up Discord webhook URL as GitHub Actions secret `DISCORD_WEBHOOK_URL`.
4. FIRST publication: set Danganronpa `published: true` and catalogue to `{"review_order":["danganronpa-trigger-happy-havoc"]}`, commit/push. Let deployment succeed; Discord webhook will announce it.
5. SECOND publication (a separate push): set final SIGNALIS `published: true` and catalogue to `{"review_order":["danganronpa-trigger-happy-havoc","signalis-alatyr"]}`, commit/push. Discord will announce SIGNALIS.
6. Only then configure ElevenLabs secret `ELEVENLABS_API_KEY` and variable `ELEVENLABS_VOICE_ID`, or temporarily use `narration: manual` in both reviews until you approve the final text. Manually run `Publish reviews` with `narrate_slug` and `confirm_tts_cost` once per approved article.

The webhook sends channel announcements, not @everyone/@role pings. If you want actual role mentions, ask for an optional role ping setting. Editing a published article does not trigger another announcement. For a missed announcement, use `announce_slug` once manually.

## Discord role notification

GitHub → Settings → Secrets and variables → Actions:
- **Secret** `DISCORD_WEBHOOK_URL`: the webhook URL for your announcement channel
- **Variable** `DISCORD_ROLE_ID`: the numeric Discord role ID for **@the readers** (not its name)

Get the role ID in Discord by enabling Developer Mode (User Settings → Advanced), then go to Server Settings → Roles and copy the ID for `the readers`. The role must be mentionable or the webhook must have appropriate mention permissions. Only this role is allowed to ping. If no role ID is set, announcements are sent without pings. Members' notification settings may suppress push alerts.

To bring an existing Danganronpa review over from Discord, copy its full text into `posts/danganronpa-trigger-happy-havoc.md` below the YAML front matter, replace the draft title/description/cover, and keep `published: false` until the webhook and role are configured. Publish Danganronpa by setting `published: true` and adding its slug to `catalogue.json`, then commit to `main`. A separate later commit can release SIGNALIS. If a notification was missed, use Actions → Publish reviews → Run workflow → `announce_slug` for a one-time announcement.
