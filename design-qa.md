# Design QA — interview-first navigation

Compared the selected first-page direction with the local desktop (1280 × 800) and mobile (390 × 844) preview on October 4, 2026. The preview used a disposable local account and database, not the deployed site.

| Check | Result |
| --- | --- |
| Missing API providers: connection card is primary, Start disabled | Passed on desktop and mobile |
| Connected provider: card disappears; a saved interview focus enables one-click Start | Passed with a simulated local provider; no external model request made |
| Mobile uses four bottom tabs; Profile and Recordings absent | Passed |
| Resume and Past interviews are separate pages; saved Q&A feedback expands in history | Passed with a disposable sample interview |
| Plant reflects completed interview count, with outward-positioned new leaves | Passed visually for the first leaf; later stages are code-defined, not end-to-end exercised |
| Live interview recording/feedback and leaf celebration | Not end-to-end tested because a real provider key, camera, and transcription service were intentionally not used |

The mockup named transcription providers that the backend does not support. The implementation correctly shows the actual provider choices, Groq and OpenAI. The original realistic PNG plant was replaced by a smaller blue-and-muted-green SVG inside a subtle card. On a small screen without providers, that card follows the connection action and disabled Start button, keeping onboarding visible above the bottom tabs. Existing recording-review and profile data/routes remain stored, but those features have no visible navigation entry in this version.
