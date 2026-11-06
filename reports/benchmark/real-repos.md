# Burner on real public repos (false-alarm check)

Run 2026-11-06 09:26 on a throwaway Vultr VM (vc2-2c-4gb, blr). Same engine and default candidate plan as the benchmark (no LLM). These repos were written by other people; none is malicious.

- **21 repos scanned**
- **0 false alarms** (MALICIOUS or SUSPICIOUS on a clean repo)
- 19 came back NO MALICIOUS BEHAVIOUR OBSERVED
- 2 INCONCLUSIVE (nothing Burner knows how to run): nuxt/starter, miguelgrinberg/microblog

**Honest note on tuning.** The first run (4 Nov) had 2 false alarms out of 21, both SUSPICIOUS for pm2 writing its normal state files (`~/.pm2/logs`, `pm2.pid`, `module_conf.json`) (hagopj13/node-express-boilerplate, danielfsousa/express-rest-boilerplate). Those pm2 files were then allowed (writes to `~/.pm2/dump.pm2`, which `pm2 resurrect` restarts after reboot, are still flagged) and the two repos were re-scanned on a fresh VM. The rule was fixed using this same set, so treat 0/21 as "after one fix", not as a blind result. First-run data: `real-repos-before-pm2-rule.json`.

**Rerun 6 Nov** with the new BINARY_SWAP and FINGERPRINT rules, the per-scan hostname and the pyenv/~/.local/bin bait: still 0 false alarms.

| Repo | What it is | Verdict | Findings | Time |
|---|---|---|---|---|
| [hagopj13/node-express-boilerplate](https://github.com/hagopj13/node-express-boilerplate) | Express + MongoDB REST boilerplate | NO MALICIOUS BEHAVIOUR OBSERVED | [low] Contacted version.pm2.io on port 443 | 214.4 s |
| [gothinkster/node-express-realworld-example-app](https://github.com/gothinkster/node-express-realworld-example-app) | RealWorld API (Express + Prisma) | NO MALICIOUS BEHAVIOUR OBSERVED | [low] Contacted binaries.prisma.sh on port 443 | 117.5 s |
| [nestjs/typescript-starter](https://github.com/nestjs/typescript-starter) | official NestJS starter | NO MALICIOUS BEHAVIOUR OBSERVED | — | 105.5 s |
| [sahat/hackathon-starter](https://github.com/sahat/hackathon-starter) | Express starter with many OAuth/API integrations | NO MALICIOUS BEHAVIOUR OBSERVED | [low] Contacted fastdl.mongodb.org on port 443 | 128.8 s |
| [danielfsousa/express-rest-boilerplate](https://github.com/danielfsousa/express-rest-boilerplate) | Express REST boilerplate | NO MALICIOUS BEHAVIOUR OBSERVED | [low] Contacted version.pm2.io on port 443 | 124.4 s |
| [remix-run/indie-stack](https://github.com/remix-run/indie-stack) | official Remix stack | NO MALICIOUS BEHAVIOUR OBSERVED | [low] Contacted binaries.prisma.sh on port 443<br>[low] Contacted download.cypress.io on port 443 | 212.2 s |
| [bradtraversy/proshop_mern](https://github.com/bradtraversy/proshop_mern) | MERN e-commerce tutorial app | NO MALICIOUS BEHAVIOUR OBSERVED | — | 46.5 s |
| [gothinkster/react-redux-realworld-example-app](https://github.com/gothinkster/react-redux-realworld-example-app) | RealWorld frontend (React + Redux) | NO MALICIOUS BEHAVIOUR OBSERVED | — | 268.0 s |
| [koajs/examples](https://github.com/koajs/examples) | official Koa examples | NO MALICIOUS BEHAVIOUR OBSERVED | — | 52.1 s |
| [fastify/demo](https://github.com/fastify/demo) | official Fastify demo app | NO MALICIOUS BEHAVIOUR OBSERVED | — | 85.7 s |
| [bezkoder/node-js-jwt-auth-mongodb](https://github.com/bezkoder/node-js-jwt-auth-mongodb) | JWT auth tutorial (Express + MongoDB) | NO MALICIOUS BEHAVIOUR OBSERVED | — | 25.4 s |
| [developit/express-es6-rest-api](https://github.com/developit/express-es6-rest-api) | ES6 REST API boilerplate | NO MALICIOUS BEHAVIOUR OBSERVED | — | 148.2 s |
| [antfu/vitesse-lite](https://github.com/antfu/vitesse-lite) | Vite + Vue starter | NO MALICIOUS BEHAVIOUR OBSERVED | — | 19.7 s |
| [sveltejs/realworld](https://github.com/sveltejs/realworld) | RealWorld app (SvelteKit) | NO MALICIOUS BEHAVIOUR OBSERVED | — | 112.9 s |
| [typicode/json-server](https://github.com/typicode/json-server) | json-server (fake REST API tool) | NO MALICIOUS BEHAVIOUR OBSERVED | — | 114.5 s |
| [nuxt/starter](https://github.com/nuxt/starter) | official Nuxt starter | INCONCLUSIVE | — | 10.5 s |
| [vercel/nextjs-subscription-payments](https://github.com/vercel/nextjs-subscription-payments) | Next.js + Stripe + Supabase starter | NO MALICIOUS BEHAVIOUR OBSERVED | — | 86.5 s |
| [w3tecch/express-typescript-boilerplate](https://github.com/w3tecch/express-typescript-boilerplate) | Express + TypeScript boilerplate | NO MALICIOUS BEHAVIOUR OBSERVED | — | 20.4 s |
| [jsynowiec/node-typescript-boilerplate](https://github.com/jsynowiec/node-typescript-boilerplate) | Node + TypeScript boilerplate | NO MALICIOUS BEHAVIOUR OBSERVED | — | 17.7 s |
| [miguelgrinberg/microblog](https://github.com/miguelgrinberg/microblog) | Flask Mega-Tutorial app (Python) | INCONCLUSIVE | — | 14.5 s |
| [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) | official FastAPI full-stack template (Python) | NO MALICIOUS BEHAVIOUR OBSERVED | — | 164.7 s |
