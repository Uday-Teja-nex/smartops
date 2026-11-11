# SmartOps: 10-minute client demo

For facility, security and operations teams at offices, malls and campuses.
Everything on screen comes from the live pipeline running on this laptop. If a
step below says *(needs footage)*, skip it until that clip is in
`sample-data/streams.json`.

## Before the meeting (10 minutes earlier)

1. Plug in the laptop and join the venue Wi-Fi if you will use the phone.
2. In PowerShell, in the project folder:

   ```powershell
   .\demo.ps1 up
   ```

   Wait for `READY -> http://localhost:3000`. The first start of the day
   loads the AI model (about 2 minutes); later starts take seconds.
3. For a clean slate:

   ```powershell
   .\demo.ps1 reset
   ```

   Then give the pipeline 3–4 minutes so the mall has fresh incidents.
4. Open two browser windows: one for you, one to show "another operator".
5. Projector check: the console is designed for 1280×720 and up.

## The script

| Min | Do | Say |
|---|---|---|
| 0:00 | Sign in as `operator@mall.demo` (password `smartops-demo`). Overview. | "This is one workspace: a shopping mall. Every number here is counted from incidents the system recorded today. Nothing is sample data." Point at "Computed from N stored incidents". |
| 1:00 | **Camera view**. | "Live video from the store camera, under two seconds behind real time. The boxes are what the detector sees right now: people and objects. Track IDs are anonymous and forgotten when someone leaves the frame. There's no face recognition and no identity." |
| 2:00 | **Sources → the store camera → Zones**. | "Your team draws zones on a frozen frame: a checkout queue, an aisle, a fire exit. Each zone gets rules: more than 2 people for 8 seconds is a queue, someone entering after hours, a bag left alone for 60 seconds." |
| 3:00 | **Live Ops**. Wait for the next incident (queue or crowding; at most 2 minutes). | "That arrived by itself, about a second after the situation was on camera (measured: 1.2 s). No refresh." |
| 4:00 | Open the incident. Play the clip. | "Five seconds before and after, with the boxes burned in, so you see exactly what the rule saw." |
| 4:45 | Point at **Measured by rule** and **AI review**. | "The rule decides; it's deterministic and auditable. Then a vision model looks at the frame and gives a second opinion: what it sees, and whether the image looks consistent. It's labelled with the model name, and it never changes the decision. If the model is down, it says so and the alert still stands." |
| 5:30 | Click **Acknowledge**, **Assign to me**, add a note, **Resolve**. Show the second window. | "Every action goes into the audit trail and appears on every other screen instantly. That's how a control room and a guard's tablet stay in sync." |
| 6:30 | Show a phone notification *(needs the Telegram bot set up in Settings → Notifications)*. | "Per-workspace rules: who gets what severity, which categories, which hours." |
| 7:00 | **Add phone camera** *(needs venue Wi-Fi)*: create, paste the RTMP URL into Larix Broadcaster, draw a zone, walk into it. | "Any camera works: a phone, an IP camera over RTSP, an existing NVR." |
| 8:00 | Sign out; sign in as `viewer@mall.demo`. Then sign in as `operator@smartops.local` and open Live Ops. | "Viewers can see but not act. And this is a different client, an office tower: none of the mall's data is visible, enforced by the server, not just hidden in the UI. Here someone walked into the restricted wing; a rule caught it within a second." (Campus: `operator@campus.demo`, lab entrance.) |
| 8:45 | **Reports**: Export CSV, Print / Save PDF. | "Daily and weekly summaries computed from the stored incidents." |
| 9:15 | **Monitoring**. | "If a camera or a service drops, the console says exactly what's down and what that means, and recovers by itself." |
| 9:45 | Close. | "It all ran on this laptop today. In your building it runs on a small server or a cloud GPU with the same software; nothing gets rewritten." |

## Talking points

- **Privacy:** no face recognition, identity tracking or demographic
  inference. Track IDs are temporary numbers. Evidence clips are restricted
  by role, and every access is logged.
- **Rules first, AI second:** an alert never depends on a language model.
  AI output is always labelled, and its failures are stated, not hidden.
- **Local first, cloud ready:** runs offline on a laptop. The same compose
  files deploy behind HTTPS on a GPU server; switching AI or detection to a
  GPU is a configuration change.
- **Honest numbers:** every KPI, box and sentence traces to a stored record.

## If X breaks mid-demo, do Y

| What you see | Do |
|---|---|
| Amber "degraded" banner naming a service | Say "this is the self-diagnosis you'd see in production", then `.\demo.ps1 status`. Most components recover automatically within 10–30 s. |
| "Live connection unavailable" on every page | The API is down: `docker compose restart api` (about 15 s). The page reconnects on its own. |
| Camera tile frozen or black | `docker compose restart stream-publisher`. The processor reconnects in a few seconds. |
| No new incident for 3+ minutes | Queue and crowding have a 2-minute cooldown. Open an earlier incident from Live Ops instead. |
| AI review says "unavailable: daily request limit" | The hosted free tier is used up for the day. The local fallback answers instead, about 10 s later. If both fail, say "the rule result stands on its own" and move on. |
| AI review says "skipped: this camera was reviewed N s ago" | Expected on the laptop: the local model reviews at most one incident per camera every 2 minutes. Open an incident that has a review. |
| AI review says "model did not answer in time" | Same: the alert stands. Run `.\demo.ps1 up` again before the next meeting to warm the model. |
| Sign-in says "Too many sign-in attempts" | Wait 60 s. That's the brute-force protection working. |
| Docker Desktop won't start ("cannot be accessed by the system") | `.\demo.ps1 fix-docker`, then `.\demo.ps1 up`. Never choose "Reset to factory defaults". |
| Everything is wrong | `.\demo.ps1 reset` (about 8 s), sign in again, and wait 2–3 minutes for fresh incidents. |
