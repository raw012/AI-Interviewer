# Design QA — airy practice home

- Source visual truth: `/Users/chenmei/.codex/generated_images/019fe480-e4cb-75c1-9e03-2c43363d5533/exec-62738107-aa89-4fef-8b49-50fa11ba2632.png` (1586 × 992 px).
- Implementation evidence: in-app browser captures of `http://127.0.0.1:3000/` shown in this task, desktop tab at 1440 × 900 CSS px and mobile tab at 390 × 844 CSS px. The browser capture tool did not export a separate screenshot file.
- State: disposable local QA account, zero completed interviews, both providers unconfigured. The deployed site and real account were not changed.
- Normalization: source and desktop implementation share a 1.6 aspect ratio; source is approximately 1.10× the CSS viewport dimensions. Comparison was made at matched screen crop, without browser chrome.

## Findings

No remaining P0–P2 mismatch in the checked home state. The desktop keeps the selected design's left navigation, open plant illustration, one account action, restrained setup surface, two separated provider rows, and quieter disabled Start button. The existing count-driven SVG plant remains intentionally dynamic; a generated botanical background gives it the selected mockup's soft setting without enclosing it in a card.

The small caption under the plant is an intentional P3 difference: it keeps completed-interview progress legible. The mockup does not show the mobile arrangement, so mobile was checked for usability rather than pixel fidelity.

## Required fidelity surfaces

- Typography: system sans-serif, heading weight and two-line wrap, body sizing, and blue action labels remain close to the source. Mobile text stays readable without horizontal overflow.
- Spacing and layout: hero, settings strip, and setup section follow one horizontal grid on desktop. The setup rows use dividers instead of nested cards. Mobile keeps provider setup and disabled Start above the decorative plant.
- Colors and tokens: existing blue and muted green are retained; the setup surface is pale and the plant background fades into white.
- Image quality: the botanical background is a generated raster asset; the foreground plant stays vector-sharp and grows with interview history. No stretched or cropped image was observed.
- Copy and content: original English interview copy and actual provider roles are preserved. Exactly one Sign out action is rendered on Home and API settings.

## Comparison history

1. First desktop capture exposed a rectangular image edge and horizontal overflow (P2). The background was moved into a masked decorative layer and the app shell now clips overflow.
2. The first mobile capture showed a redundant global connection link (P2). It was removed; the two provider-specific Connect actions remain and both lead to API settings.
3. Post-fix desktop and mobile captures show no horizontal overflow or duplicate Sign out. The provider action was clicked in the browser and opened API settings; Home navigation returned correctly. A fresh preview tab reported no console errors.

## Limits

The provider-connected state, real model request, recording flow, and new-leaf celebration were not exercised in this visual pass. Existing automated tests cover the provider-ready one-click Start state and leaf-count behavior.

final result: passed
