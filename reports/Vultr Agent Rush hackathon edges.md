# Register Tonight, Then Build Contained Agents

**Act before 20:30 IST today (Tue 3 Nov 2026). lablab closes registration when kickoff starts, at 15:00 UTC.** Submissions close **Sun 8 Nov 22:00 UTC, which is Mon 9 Nov 03:30 IST**, so you really have about five working days. Agent Rush is a **single prize ladder of $5k / $3k / $1k cash plus $3k / $1k / $1k in Vultr credits**, shared by two tracks. Judges score four criteria: Application of Technology, Presentation, Business Value and Originality. Vultr must be the real control plane, not static hosting. Track 1, "Blast Radius Zero", must also route every agent LLM call through Vultr Serverless Inference and show a filmed "containment moment". The technical path works for a solo builder on a cheap VM. Assume a normal Vultr VM has **no KVM**, so microVM sandboxes are out. **Docker plus gVisor (`runsc`)** works without KVM and can be set up in hours. Inference is cheap enough to ignore, at about **$0.41 per 1,000 agent steps** on `glm-5.3-flash`. The biggest risks are not technical. They are an Indian card failing Vultr's payment check, the 03:30 IST deadline, a demo that goes down during judging (which probably runs 9–12 Nov), and a crowded field of 2,000+ registrants. My recommendation is **Track 1, aimed at a business buyer: a sandboxed supplier-vetting agent**. It screens new vendors against the official SAM.gov exclusion list. It is filmed beating a hostile vendor page that tries to steal data or swap bank details. It reports measured numbers, not claims.

## Three clocks decide everything, and one closes today

The lablab live page lists only two milestones: "Tue, Nov 3 15:00 UTC — Kickoff · Registration closes" and "Sun, Nov 8 22:00 UTC — Submissions close / Judging begins". It says **"Registration closes the moment the event starts"** ([lablab live page](https://lablab.ai/ai-hackathons/vultr-hackathon/live)). The Vultr Community page disagrees on the kickoff time. It says 16:00–17:00 UTC, followed by a Discord Q&A ([Vultr Community event](https://community.vultr.com/e/vultr-agent-rush-hackathon)). lablab is the platform that enforces the cutoff, so plan around the earlier time. The **$200 Vultr gift code is only released at kickoff** ([lablab event page](https://lablab.ai/ai-hackathons/vultr-hackathon)). The rule book allows a five-minute grace period after the deadline. Only organizers can grant extensions, and you must ask them before the deadline ([lablab rule book](https://lablab.ai/hackathon-rules)).

| What | UTC | **IST** | Notes |
|---|---|---|---|
| Enroll on lablab, connect Discord, create a team | before Tue 3 Nov 15:00 | **before Tue 3 Nov 20:30** | You need Discord connected to create or join a team |
| Kickoff (lablab) / gift code released | Tue 3 Nov 15:00 | **Tue 3 Nov 20:30** | Vultr Community says 16:00 UTC (21:30 IST) |
| Discord Q&A (Vultr Community agenda) | Tue 3 Nov 17:00 | Tue 3 Nov 22:30 | End time on the page is a typo |
| **Submissions close** | Sun 8 Nov 22:00 | **Mon 9 Nov 03:30** | Hard stop 03:35 IST with the 5-min grace |
| Unlabeled "Start/End" in page source | 9 Nov 15:00 – 12 Nov 15:00 | 9 Nov 20:30 – 12 Nov 20:30 | Probably the judging window; not confirmed |

The deadline falls at 03:30 IST in the early morning. Treat **Sun 8 Nov at about 22:00 IST** as your real cutoff and keep the night as a buffer. The page source also holds an unexplained 9–12 Nov window ([lablab event page](https://lablab.ai/ai-hackathons/vultr-hackathon)). It is most likely judging, which means your demo URL and VM must stay up until at least mid-November. That is after the period the credits are described as covering ("throughout the event").

## Judges score four 1–5 criteria on five artifacts

The scored criteria are Application of Technology ("how effectively the chosen model(s) are integrated"), Presentation, Business Value ("how well it fits into business areas") and Originality ("ability to demonstrate behaviors"). **No weights are published for this event** ([lablab event page](https://lablab.ai/ai-hackathons/vultr-hackathon)). lablab's default is a 1–5 score per criterion, with five tiers. The rule book links a **video under 3 minutes to the "Limited" tier** and links the higher tiers to explaining the solution in under 5 minutes ([lablab rule book](https://lablab.ai/hackathon-rules)). In practice, aim for 3:30–4:45.

You must submit all of these:

- title (max 50 characters) and short description (max 255 characters)
- long description (at least 100 words)
- tags and a 16:9 cover image
- an MP4/MOV video under 5 minutes and 300 MB
- PDF slides
- a public GitHub repo, a demo platform and an application URL

The limits come from [lablab Hackathon Guidelines](https://lablab.ai/ai-articles/hackathon-guidelines). The application URL is "Required for interactive evaluation" ([lablab rule book](https://lablab.ai/hackathon-rules)). There is **no separate architecture report**. Instead, the README must explain which Vultr services you use, how the backend is deployed, and how the agent carries out real tasks. Both tracks need a **Vultr VM backend and a web app deployed on Vultr**. Vultr must be "the central system of control and orchestration, not just static hosting", and **"Vultr GPUs are not available for this event"** ([lablab event page](https://lablab.ai/ai-hackathons/vultr-hackathon)).

lablab's own winning guide says judges "reward clarity over production value". It suggests a video that runs problem → live demo → business case → team → roadmap, and 8–10 slides. It lists the most common ways to lose: pivoting after hour 12, having no deployed demo, and **"an empty GitHub repo with one final push"** ([How to Win an AI Hackathon](https://lablab.ai/guide/how-to-win-an-ai-hackathon)). Commit and push every day, starting today.

Being online in India does not seem to block you from winning. The event says your entry "must be submitted on lablab.ai to be eligible for judging and competition prizes" ([lablab event page](https://lablab.ai/ai-hackathons/vultr-hackathon)). The Salt Lake City on-site phase on 8 Nov is for "approved" participants. Only the **raffle (PS5, AirPods, Razer mouse) is onsite-only** ([Vultr Community event](https://community.vultr.com/e/vultr-agent-rush-hackathon)). No source says outright that online teams can win, so ask in Discord once to be sure.

Other rules that apply to you:

- **Teams:** 1–6 people ([lablab event page](https://lablab.ai/ai-hackathons/vultr-hackathon)).
- **Eligibility:** you must be 18 or older and not in a US-sanctioned country, so India is fine.
- **Licensing:** submissions must be original and MIT-compliant. You keep ownership but grant lablab a broad license ([lablab Terms of Use](https://lablab.ai/terms-of-use)). Add an MIT LICENSE file.
- **Prize payout** ([lablab Terms of Use](https://lablab.ai/terms-of-use)):
  - Prizes go to individuals, not teams.
  - You need a W-8BEN, a photo ID and bank verification, submitted **within 90 days**, or you forfeit the prize.
  - Payment is in USD by SWIFT wire.
  - **30% US tax is withheld** unless you claim a treaty rate with a US TIN.
  - Distribution can take up to 90 days.

A $5,000 first prize will therefore arrive noticeably smaller.

## Track 1 demands a filmed containment moment; Track 2 demands a real workflow

The lablab page tells you to "Choose one path" between the two challenges. The Vultr Community page lists only Blast Radius Zero, as the "Main challenge" ([lablab event page](https://lablab.ai/ai-hackathons/vultr-hackathon); [Vultr Community event](https://community.vultr.com/e/vultr-agent-rush-hackathon)). Only one set of 1st–3rd prizes exists, so **both tracks compete for the same three places**.

| | Track 1: Blast Radius Zero | Track 2: Powering the Future of Work |
|---|---|---|
| What it is | Sandboxed code or browser agent | Enterprise workflow agent (ops, finance, procurement, support, HR, sales) |
| Vultr Serverless Inference | **Required** for all agent LLM calls | Optional on lablab; Vultr Community wording implies required |
| Execution boundary | "containers or throwaway instances on Vultr, never inside the app process" | Vultr VM backend as control plane |
| Extra deliverable | **At least one containment moment in the video** (e.g. absorbing `rm -rf`, an infinite loop, or a hostile web page) | "Real platform or operational workflow, not a one-off demo" |
| Shared | Public repo + setup docs, Vultr VM backend, public product-style demo URL, video, architecture/use-case explanation | same |

Sources: [lablab event page](https://lablab.ai/ai-hackathons/vultr-hackathon); [Vultr Community event](https://community.vultr.com/e/vultr-agent-rush-hackathon).

The two pages disagree on whether Track 2 needs Serverless Inference. The safe move is to **use Vultr Serverless Inference whichever track you pick**. It is required by one page and optional on the other, and it adds to Application of Technology. You can build with Claude Code. The runtime agent is a different matter: if a Track 1 agent calls the Anthropic or OpenAI APIs instead of Vultr, it risks points or eligibility.

## Vultr's platform is cheap and capable, with four sharp gotchas

### Serverless Inference: 35 models, OpenAI-compatible, pennies per run

The public catalog at `GET https://api.vultrinference.com/v1/models` needs no key. On 3 Nov it listed **35 models**:

- about 12 chat/reasoning LLMs, nearly all of which accept images and support tools, structured outputs and streaming, with 262K–1M context
- embeddings and rerankers
- speech-to-text and text-to-speech
- image, video and music generation
- a moderation model
- four "decision" models that return yes/no probabilities

Source: [live catalog](https://api.vultrinference.com/v1/models).

The models that matter for an agent:

- **`deepseek-v4.1-flash-1017`** is the API default. It costs $0.15 in / $0.60 out per million tokens and has 1M context.
- **`glm-5.3-flash`** is cheap and reads screenshots and video. It costs $0.10 / $0.35 and has 1M context.
- **`minimax-m3.1-flash`** is marketed for "agentic coding, computer use". It costs $0.20 / $0.90.
- **`qwen3.8-flash-next`** is a fallback at $0.10 / $0.20 with 262K context.

Source: [live catalog](https://api.vultrinference.com/v1/models).

The base URL is `https://api.vultrinference.com/v1`, with `Authorization: Bearer <key>`. It accepts OpenAI and OpenRouter request shapes, plus Anthropic's Messages API on `/v1/messages`. There is no Vultr SDK to install. It also has a built-in vector store and a RAG route ([Vultr inference docs](https://api.vultrinference.com/docs/index.md); [SDKs](https://api.vultrinference.com/docs/get-started/sdks.md); [chat over files](https://api.vultrinference.com/docs/workflows/chat-over-files.md)). Create keys at console.vultr.com/inference ([Authentication](https://api.vultrinference.com/docs/get-started/authentication.md)).

Default limits for chat are **120 requests/min and 16 concurrent per model**. Requests over the concurrency cap wait up to two minutes and then return 429. Requests time out after about nine minutes. Default max output is 32,768 tokens ([Limits](https://api.vultrinference.com/docs/concepts/limits.md)). Every model is served from US datacenters (Seattle, Atlanta, San Jose) ([live catalog](https://api.vultrinference.com/v1/models)). Expect extra round-trip time from India; my geographic estimate is 200–300 ms per call.

The gotchas:

1. **A mistyped model ID does not raise an error.** "the request goes to `deepseek-v4.1-flash-1017`" instead, without telling you ([Quickstart](https://api.vultrinference.com/docs/get-started/quickstart.md)). Assert that `response.model` matches the model you asked for.
2. **Models churn fast.** Every model active in March 2026 is gone by November, and two more were deprecated on 21 Oct ([models.dev PR #1299](https://github.com/anomalyco/models.dev/pull/1299); [models.dev vultr models](https://github.com/anomalyco/models.dev/tree/dev/providers/vultr/models)). Check `/v1/models` at boot and keep a fallback model ID.
3. **Upstream features are missing.** The Responses API stores no state, hosted tools (web search, code interpreter) are not available, and there is no prompt caching on `/v1/messages` ([SDKs](https://api.vultrinference.com/docs/get-started/sdks.md)).
4. **Pricing documentation conflicts.** A support FAQ dated 26 Oct still quotes a flat $0.55 / $2.75 per million tokens ([Vultr support FAQ](https://docs.vultr.com/support/products/serverless/how-do-i-monitor-the-usage-and-cost-of-my-vultr-serverless-inference-subscription)). The per-model catalog prices look current. Either way, cost is tiny: 1,000 screenshot-sized steps on `glm-5.3-flash` cost about $0.41.

**Nobody has confirmed whether the $200 hackathon credit covers inference as well as compute.** Check this in Billing after you redeem.

### Compute: India regions, $0.066/hour for a comfortable sandbox host

Vultr has 33 regions, including **Mumbai (`bom`), Bangalore (`blr`) and Delhi NCR (`del`)** ([Vultr API regions](https://api.vultr.com/v2/regions)).

Two plans fit a Docker + Chromium sandbox host:

- **`vc2-2c-4gb`** at $20/month ($0.027/hour) is the minimum.
- **`vhp-4c-8gb-amd`** at $48/month ($0.066/hour) is the comfortable choice for several browser sandboxes.

The free and 512 MB plans are not offered in India ([Vultr API plans](https://api.vultr.com/v2/plans)). Running the larger box from now until 15 Nov costs roughly $19, well inside $200.

The marketplace has one-click **Docker (app 1125)**, Coolify (1265), Supabase (1266) and k3s (1255) ([Vultr API applications](https://api.vultr.com/v2/applications)). You can create and destroy instances through the API, from a snapshot plus cloud-init `user_data`. The API allows 30 requests/second ([Vultr API reference](https://www.vultr.com/api/); [snapshot docs](https://docs.vultr.com/products/compute/cloud-compute/features/snapshots)). New accounts have an instance cap that you can only raise with a manually reviewed request ([Manage Account Limits](https://docs.vultr.com/platform/billing/manage-account-limits)). That makes containers on one VM a safer demo than spinning up a fresh VM per task.

### Signup: the payment method is the real gate

To claim credits:

1. Register at vultr.com/register with an email **never used on Vultr before**.
2. Verify the email.
3. At kickoff, open `console.vultr.com/billing/?promo=HACKATHON` and enter the gift code.
4. Confirm that **$200.00** shows as remaining credit.

Source: [lablab event page](https://lablab.ai/ai-hackathons/vultr-hackathon).

The event page never mentions a card. Vultr's own docs say "To deploy resources on Vultr, you **must add a valid payment method**" ([Vultr docs](https://docs.vultr.com/support/platform/billing/why-do-i-need-to-enter-a-payment-method)). Accepted methods are Visa, Mastercard, Amex, Discover, JCB, PayPal, BitPay crypto, Alipay and UnionPay. **UPI and RuPay are not listed.** PayPal needs a backup funding source. Vultr also warns that a card that "works elsewhere... might still encounter issues on our platform" ([What payment methods](https://docs.vultr.com/support/platform/billing/what-payment-methods-do-you-accept); [Billing FAQ](https://docs.vultr.com/platform/billing/faq)). Promo credits are limited to **one per user, and they expire** ([Billing FAQ](https://docs.vultr.com/platform/billing/faq)).

Before signing up, turn on international and online transactions for a Visa or Mastercard in your bank app. Add the card **before** kickoff, so that redeeming the code is the only step left.

## A gVisor-hardened Docker box is the right sandbox on Vultr

Assume your VM cannot run microVMs. A 2026 review of a Vultr High Performance AMD shared-CPU instance found the **"VM-x/AMD-V flag is disabled"**, which it calls standard for shared-CPU instances ([Better Stack review](https://betterstack.com/community/guides/web-servers/vultr-review/)). Without KVM you cannot use Microsandbox ("Linux with KVM enabled") or self-hosted E2B/Firecracker ([microsandbox](https://github.com/microsandbox/microsandbox); [E2B issue #239](https://github.com/e2b-dev/E2B/issues/239)). The hosted E2B cloud runs sandboxes off Vultr, which weakens the "contained on Vultr" requirement. To confirm on your own VM, run `ls /dev/kvm; grep -c -E 'vmx|svm' /proc/cpuinfo`.

**gVisor fits.** Its systrap platform has been the default since mid-2023 and is "a better choice when running inside a VM, or on a machine without virtualization support". It installs with apt and registers itself with Docker as `--runtime=runsc` ([gVisor platforms](https://gvisor.dev/docs/architecture_guide/platforms/); [gVisor install](https://gvisor.dev/docs/user_guide/install/)). Alibaba's **OpenSandbox** (Apache-2.0, around 16.4k stars) is an optional layer on top. It runs on plain Docker and adds per-sandbox egress policies, a credential vault and SDKs ([alibaba/OpenSandbox](https://github.com/alibaba/OpenSandbox)). It is young, though, and about 200 lines of docker-py around a hardened `docker run` gives you fewer moving parts.

**For code sandboxes,** start every container with this set of protections, all from the Docker docs ([Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/); [Docker security](https://docs.docker.com/engine/security/)):

- `--runtime=runsc`
- `--network none` and a read-only filesystem
- `--cap-drop ALL` and `no-new-privileges`
- a non-root user
- PID, memory and CPU limits
- an empty environment
- a timeout enforced by a watchdog on the host

**For browser sandboxes,** use the pinned image `mcr.microsoft.com/playwright:v1.64.1-noble`. Run it as `pwuser` with Playwright's seccomp profile. Playwright itself warns the image is not meant for untrusted sites when run naively ([Playwright Docker docs](https://playwright.dev/docs/docker)). Playwright recommends `--ipc=host`, but that shares host IPC, so use `--shm-size=1g` instead. Put the browser on an `--internal` Docker network whose only exit is a Squid allowlist proxy. Keep the agent and every API key in the control plane, never inside the sandbox. Anthropic's own computer-use demo passes its API key into the container the model controls, which is exactly the anti-pattern this track punishes ([computer-use-demo](https://github.com/anthropics/claude-quickstarts/tree/main/computer-use-demo)). One combination is untested: Chromium's sandbox under gVisor. Test it on day 1. If it breaks, run only the browser container on the default runtime with the hardened flags, and say so honestly in the README.

**For the filmed containment moment,** the strongest shot is a **prompt-injected web page that the agent obeys, followed by the egress proxy blocking the exfiltration**. Show the red `TCP_DENIED` row in a "Blast Radius" panel next to a real attacker listener receiving **zero** requests. This mirrors Anthropic's warning that "instructions on webpages... may override user instructions" ([computer-use-demo](https://github.com/anthropics/claude-quickstarts/tree/main/computer-use-demo)). Then follow it with a quick montage:

- `rm -rf /` hitting a read-only filesystem
- a fork bomb pinned at the PID limit
- an infinite loop killed at 10 seconds
- a canary secret that the sandbox cannot read
- `uname` showing the gVisor kernel

## Past Vultr winners shipped governed, multi-step products

Vultr's brief has barely changed across lablab events: an enterprise agent, a VM backend as the control plane, and a public web app. **Deals Machine**, a solo-built autonomous sales agent, won the Vultr track at AI Agent Olympics Milan 2026 ([results](https://lablab.ai/ai-hackathons/milan-ai-week-hackathon/live)). It used a Vultr Ubuntu agent worker and put prompt-injection middleware in front of its reply loop. Its builder's lesson was "The safety layer is not a feature added afterward" ([project](https://lablab.ai/ai-hackathons/milan-ai-week-hackathon/view-1-studio/deals-machine-the-autonomous-sales-agent); [success stories](https://lablab.ai/ai-articles/lablab-hackathon-success-stories-part-2)). Second place went to **ContextGuard**, which logs every action it takes with a before/after diff ([project](https://lablab.ai/ai-hackathons/milan-ai-week-hackathon/revived/contextguard-live-decision-helper)). At Raise Your Hack 2025, the Vultr-track winner was built by what looks like an existing company team. It claims a rollout to more than 3,000 retailers ([project](https://lablab.ai/ai-hackathons/raise-your-hack/autonomous-agents-from-apis-vultr-track/autonomous-agents-from-apis-zero-code-builder)).

Across 2026 lablab agent winners the pattern is consistent: **a governance layer on an agent that really runs, plus measured proof**. Examples:

- **BEE SENTINEL-X** ran trades in an isolated Docker container behind a risk gate.
- **Vertex Sentinel** ran 4 live signed trades in under 40 seconds, backed by 51 passing tests.
- One winner's advice: "pick one sharp problem, make the thesis clear, and build a demo that proves that one idea well."

Source: [success stories pt 2](https://lablab.ai/ai-articles/lablab-hackathon-success-stories-part-2).

**The field is large but thin.** Agent Rush showed **2,073 registered builders** on 3 Nov ([live page](https://lablab.ai/ai-hackathons/vultr-hackathon/live)). Milan had 2,382 participants and 265 final submissions, of which **97 were in the Vultr track**. Raise Your Hack had 6,246 participants but only 223 submissions ([Milan results](https://lablab.ai/ai-hackathons/milan-ai-week-hackathon/live); [Raise results](https://lablab.ai/ai-hackathons/raise-your-hack/live)). Applying those conversion rates gives about **80–280 Agent Rush submissions** competing for three prizes. Many will be low-effort. A complete, deployed, documented entry already beats most of the field. Winning still means landing in roughly the top 1–3%.

The categories most likely to be crowded are support bots, resume screeners, AI SDR/outreach agents (and the last Vultr winner was one), meeting-to-action agents, and "code interpreter in Docker". lablab's own guide warns against "an existing product with a chatbot bolted on" ([How to Win guide](https://lablab.ai/guide/how-to-win-an-ai-hackathon)). This crowding list is my inference. Nobody could count the full Milan gallery.

## Real public data favours vendor vetting and invoice exceptions

**Track 1 has real incidents behind it.**

- **Replit (July 2025):** the agent wiped a live production database during a code freeze. Replit's fix was containment (separating dev and prod by default), not a smarter model ([eWeek](https://www.eweek.com/news/replit-ai-coding-assistant-failure/)).
- **Perplexity Comet (Aug 2025):** Brave hid an instruction in a Reddit comment. It made Comet exfiltrate the user's email and a Gmail OTP to an attacker domain ([Brave](https://brave.com/blog/comet-prompt-injection/)).
- **Amazon Q (July 2025):** a malicious pull request shipped a wiper prompt in the VS Code extension ([Tom's Hardware](https://www.tomshardware.com/tech-industry/cyber-security/hacker-injects-malicious-potentially-disk-wiping-prompt-into-amazons-ai-coding-assistant-with-a-simple-pull-request-told-your-goal-is-to-clean-a-system-to-a-near-factory-state-and-delete-file-system-and-cloud-resources)).

The best one-line motivation is Gravitee's 2026 survey of 919 respondents: **only 21% have runtime visibility into agent activity** ([Gravitee](https://gravitee.io/state-of-ai-agent-security)). That survey is vendor-run. The sandbox infrastructure itself is commoditized (E2B, Daytona, Modal and others) ([Northflank](https://northflank.com/blog/daytona-vs-e2b-ai-code-execution-sandboxes)). The gap you can fill is a **measured** containment result. **InjecAgent** gives you 1,054 public injection test cases. Prompted GPT-4 followed the injection 24% of the time, rising to 47% with enhanced attacks ([arXiv 2403.02691](https://arxiv.org/pdf/2403.02691)). That lets you report "the model followed the injection X% of the time, and containment held in every one of those cases" on someone else's dataset.

**Track 2's strongest real data is in finance and procurement.**

- **BPI Challenge 2019** is a real purchase-to-pay event log from a multinational, about 695 MB. Every item is tagged with its matching type: 3-way, 2-way or consignment ([TU/e](https://research.tue.nl/en/datasets/bpi-challenge-2019/)).
- Invoice-exception rates are reported at **14–22%**, with average cost around $10 per invoice. The sources conflict and are secondhand ([Tailride](https://tailride.so/blog/invoice-management-statistics-2026)).
- **SAM.gov Exclusions** is an official, daily-refreshed list of debarred contractors, available through a free-key API. Mirrors exist on OpenSanctions and a CC0 Hugging Face dataset ([OpenSanctions](https://opensanctions.org/datasets/us_sam_exclusions); [HF sam-debarments](https://huggingface.co/datasets/emperor-mew/sam-debarments)).
- The FBI's IC3 put **2025 business email compromise losses at about $3.05B across 24,768 complaints**. That figure is secondhand; confirm it on ic3.gov ([DeepStrike](https://deepstrike.io/blog/business-email-compromise-statistics-2026)). Banks say these failures are "almost always procedural", meaning vendor bank-change verification, and the fix is a callback check ([U.S. Bank](https://www.usbank.com/corporate-and-commercial-banking/insights/risk/mitigation/BEC-recognize-a-scam.html)).
- **CFPB's 13.8M+ complaints** with company responses are real, but a project built on them reads more like a classification demo than a workflow ([CFPB archive](https://webarchive.library.unt.edu/web/20170118205212/http://www.consumerfinance.gov/complaintdatabase)).
- HR fake-candidate detection has a striking Gartner forecast but **no public ground truth** ([HR Dive](https://www.hrdive.com/news/fake-job-candidates-ai/757126/)). You would have to use synthetic data, which judges can wave away.

The strongest overlap between the tracks is **an enterprise workflow whose risky steps run in a sandbox behind a human approval gate**. That combines Track 1's containment story with Track 2's money problem, and it matches Brave's recommended fix: explicit user interaction for sensitive actions ([Brave](https://brave.com/blog/comet-prompt-injection/)).

## Payment, uptime and model drift are the risks that sink solo entries

Ranked by how likely each is to end your run:

1. **Your Indian card fails Vultr's authorization**, so you cannot deploy anything. Fix it tonight, and keep PayPal with a linked card as a backup ([Billing FAQ](https://docs.vultr.com/platform/billing/faq)).
2. **You miss the 03:30 IST deadline** through tiredness or an upload failure.
3. **The demo URL dies during judging (9–12 Nov)** after credits lapse. Check the credit expiry in Billing, and keep the VM running on your card if you need to.
4. **A model ID disappears or silently falls back** to a different model. Use the wrapper with an assert and a fallback model.
5. **Chromium misbehaves under gVisor.** Test it on day 1 and keep the hardened-runc fallback ready.
6. **Live demo latency** from US-only inference. Pre-record the containment run as backup footage.
7. **Scope creep.** Lock the idea by Wed noon. lablab's guide names pivoting after hour 12 as a top way to lose ([How to Win guide](https://lablab.ai/guide/how-to-win-an-ai-hackathon)).
8. **Synthetic data weakening Business Value.** Anchor the headline on SAM.gov or InjecAgent, never on invented vendors alone.

Several things are **still unknown**:

- the criterion weights
- the judges' affiliations (about 30 names are in the page data)
- whether online teams can pitch
- how a team prize is split
- whether you may reuse code written before the event (none of it should be reused; "original work" is required)

## Recommendation: build a contained supplier-vetting agent in Track 1

Enter **Track 1** with a business-facing agent. The working name is **"Vetted"**: a sandboxed agent that vets a new supplier before you pay them.

**How a run works:**

1. An AP clerk enters a supplier's name and website, or a "please update our bank details" request.
2. The control plane on your Vultr VM plans with `deepseek-v4.1-flash-1017` (falling back to `minimax-m3.1-flash`) through Vultr Serverless Inference.
3. It drives a Playwright browser inside a hardened container that can reach only allowlisted domains: the supplier's site, SAM.gov and OpenSanctions.
4. `glm-5.3-flash` checks screenshots.
5. A `--network none` gVisor container parses any vendor-supplied files.
6. The agent produces a verdict with receipts, where every claim links to a captured page snapshot.
7. Any bank-detail change or vendor approval **stops at a human approval gate** that requires a callback check.

**Why this beats the other options:**

- **Application of Technology:** it uses Vultr Serverless Inference for both planning and vision, gVisor sandboxes on a Vultr VM, and the Vultr control plane.
- **Business Value:** a $3B fraud category plus the FAR rule that contracting officers must not award to debarred contractors ([ai-analytics](https://ai-analytics.org/writing/sam-gov-exclusions/)).
- **Originality:** procurement was the least-claimed domain among past Vultr winners and community picks.
- **Presentation:** a hostile "supplier" page that tries to swap the bank account and exfiltrate data, then gets visibly blocked, is a film-ready climax.

**Your two headline numbers:**

1. Verdict accuracy on a sample of **real SAM.gov excluded entities** mixed with non-excluded names.
2. **Injection success with and without containment** on an InjecAgent subset.

Keep the web app lean. Put the method, caveats and tables in the deck and README.

**The runner-up** is a Track 2 AP-exception agent on BPI 2019. It has the best "real enterprise data" headline, but it means more data engineering and enters a crowded track.

**Cut order if you fall behind:**

1. InjecAgent evaluation
2. CDP live-view (fall back to screenshots after each step)
3. OpenSanctions (keep SAM.gov only)

**Never cut** the live containment moment, the approval gate, the README architecture section, or the deployed URL.

| Day (IST) | Goal | Concrete output |
|---|---|---|
| **Tue 3 Nov, now → 20:30** | Get in | Enroll on lablab, connect Discord, create a solo team. Create a Vultr account with a fresh email and add an internationally enabled card. Request a SAM.gov API key (the HF/OpenSanctions mirrors are the fallback). Init the public repo with an MIT license and push. |
| Tue 3 Nov, 20:30 → late | Unlock Vultr | Watch the kickoff and redeem the gift code. Note the credit expiry and whether it covers inference. Create an inference key and run one call. Deploy `vhp-4c-8gb-amd` with Docker in `bom`/`blr`. Check `/dev/kvm` and install `runsc`. Ask in Discord: "can online teams win?" |
| **Wed 4 Nov** | Sandbox core | gVisor code-sandbox runner with a watchdog. Playwright container on an internal network behind a Squid allowlist. Prove `rm -rf`, fork bomb, timeout and blocked `curl` from the command line. Test Chromium under runsc. Lock the idea by noon. |
| **Thu 5 Nov** | Agent loop | Inference wrapper (models check, model assert, retries, fallback ID). Planner + vision checker. SAM.gov/OpenSanctions lookups. Receipts as captured snapshots. Approval-gate endpoint. |
| **Fri 6 Nov** | Product surface | Web UI with a "Blast Radius" panel (container ID, runtime, limits, event feed) and an approval queue. Hostile supplier page plus an attacker listener on a second tiny VM. HTTPS public URL. Daily push. |
| **Sat 7 Nov** | Proof + docs | Run the SAM.gov accuracy sample and the InjecAgent subset and record the numbers. README with architecture diagram naming each Vultr service. Feature freeze at 22:00 IST. Record backup footage. |
| **Sun 8 Nov** | Ship | 3:30–4:45 min MP4 with the containment moment early. 8–10 slide PDF. 16:9 cover. Fill in the form and **submit by about 22:00 IST**. Leave the remaining hours to 03:30 IST Mon as buffer. |
| 9–15 Nov | Survive judging | Keep the VM and URL live. No breaking pushes. Watch email for the payout form (90-day KYC). |

## Conclusion

Most entrants will treat Vultr as a host and the sandbox as a checkbox. The rules and the past winners point the other way. **Containment and audit are the product, and Vultr is the place where they visibly run.** For a solo builder, the edge is not more features. It is three things a judge can verify in under five minutes: a URL that works, a red "BLOCKED" row that appears live, and two numbers measured on public data that someone else built.

The hardest parts of this hackathon are administrative, not technical: registration closes tonight, the payment method needs to be on your Vultr account, the deadline lands at 03:30 IST, and the demo has to stay up after the event ends. Clear all four and the remaining risk is execution. A gVisor box, the OpenAI-compatible inference API and Claude Code make that execution realistic in five days.
