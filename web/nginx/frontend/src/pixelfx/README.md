# pixelfx (복사본)

픽셀 모드에서 쓰는 이펙트 라이브러리. 원본은 https://github.com/patch-gg/pixelfx (v0.3.1, MIT).

- `core/`, `fx/` — 원본(쓰는 이펙트만: 전환 pixel-dissolve, 횃불 torch, 폭발 small-explosion). 원본 `src/core`, `src/fx` 에서 **그대로 복사**했다. 고치지 않는다(원본을 새로 받으면 덮어쓴다).
- `LICENSE`, `NOTICE.md` — 원본의 저작권 표기. 복사본과 함께 둬야 한다.
- `index.js`, `index.d.ts` — 우리가 쓴 창구와 타입 선언. 화면 코드는 여기서만 가져온다.

원본 갤러리의 글꼴(`PatchPixel`)은 MIT 가 아니라서 가져오지 않았다. 화면 글꼴은 Galmuri(OFL 1.1, npm `galmuri`)를 쓴다.
원본의 `tools/`(렌더 · 검사 도구)와 Claude 스킬 문서도 가져오지 않았다.
