// 화면에서 쓰는 pixelfx 창구. core/ 와 fx/ 는 https://github.com/patch-gg/pixelfx (MIT) 에서 그대로 복사한 것이라 고치지 않는다.
// 이펙트를 더 쓰려면 원본의 src/fx/<분류>/<이름>.js (와 같은 폴더의 _lib.js) 를 fx/ 아래에 복사하고 여기에 한 줄 더한다.
export { createFrame, clearFrame, createFx, composite } from './core/fx.js';
export * as pixelDissolve from './fx/transitions/pixel-dissolve.js';
export * as torch from './fx/fire/torch.js';
export * as smallExplosion from './fx/explosions/small-explosion.js';
