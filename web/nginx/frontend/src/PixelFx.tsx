import { useEffect, useRef } from 'react';
import { clearFrame, composite, createFrame, createFx, pixelDissolve } from './pixelfx/index.js';
import type { FxModule, FxOptions } from './pixelfx/index.js';

const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * 반복 재생하는 픽셀 이펙트 한 개(장식용). 이펙트 크기 그대로의 작은 캔버스에 그리고, CSS 로 정수 배(scale) 확대한다.
 * 화면 밖에 있거나 탭이 가려지면 멈춘다. '움직임 줄이기'를 켠 기기에서는 한 장면만 그린다.
 */
export function PixelFx({ fx, options, scale = 1, className = '', title }: {
  fx: FxModule; options?: FxOptions; scale?: number; className?: string; title?: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [w, h] = fx.meta.size;
  const optKey = JSON.stringify(options ?? {});

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    const frame = createFrame(w, h);
    const img = ctx.createImageData(w, h);
    const [ox, oy] = fx.meta.origin;
    const inst = createFx(fx, { x: ox, y: oy, ...(JSON.parse(optKey) as FxOptions) });
    const render = () => {
      clearFrame(frame);
      inst.draw(frame);
      composite(frame, img.data, null);
      ctx.putImageData(img, 0, 0);
    };
    if (reducedMotion()) {
      inst.update(fx.meta.duration / 2);
      render();
      return;
    }
    const step = 1 / fx.meta.fps;
    let raf = 0, last = 0, acc = 0, visible = true;
    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const dt = last ? Math.min((now - last) / 1000, 0.25) : step;
      last = now;
      if (!visible) return;
      acc += dt;
      if (acc < step) return;
      while (acc >= step) { inst.update(step); acc -= step; }
      render();
    };
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; });
    io.observe(canvas);
    render();
    raf = requestAnimationFrame(tick);   // 탭이 가려지면 브라우저가 스스로 멈춘다
    return () => { cancelAnimationFrame(raf); io.disconnect(); };
  }, [fx, optKey, w, h]);

  return (
    <canvas
      ref={ref} width={w} height={h} className={`pixelfx ${className}`}
      style={{ width: w * scale, height: h * scale }}
      role={title ? 'img' : undefined} aria-label={title} aria-hidden={title ? undefined : true}
    />
  );
}

// pixel-dissolve 가 화면을 다 덮는 시각(초). 원본 상수 IN1 0.8 + P 0.17 바로 뒤
const COVERED_AT = 1.0;
let playing = false;

/**
 * 화면 전체를 덮었다가 걷히는 전환 연출(pixel-dissolve). 화면 맨 위에 캔버스를 잠깐 올렸다가 끝나면 치운다.
 *  - reveal: 덮인 상태에서 시작해 걷히기만 한다(이미 바뀐 화면을 드러낼 때)
 *  - onCovered: 화면이 다 덮인 순간 한 번 부른다(그 뒤에서 화면을 바꾼다). 연출을 못 하는 경우에도 반드시 부른다
 * 비상 · 투척 승인 팝업(z-index 10000 이상)보다는 아래에 깔리고, 누르기를 막지 않는다.
 */
export function playTransition({ reveal = false, speed = 1.6, onCovered }: { reveal?: boolean; speed?: number; onCovered?: () => void } = {}) {
  if (playing || reducedMotion()) { onCovered?.(); return; }
  const [w, h] = pixelDissolve.meta.size;
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx) { onCovered?.(); return; }
  playing = true;
  canvas.width = w;
  canvas.height = h;
  canvas.className = 'pixelfx pixel-transition';
  canvas.setAttribute('aria-hidden', 'true');
  document.body.appendChild(canvas);

  const frame = createFrame(w, h);
  const img = ctx.createImageData(w, h);
  const inst = createFx(pixelDissolve, {});
  let covered = reveal;
  const render = () => {
    clearFrame(frame);
    inst.draw(frame);
    composite(frame, img.data, null);
    ctx.putImageData(img, 0, 0);
  };
  if (reveal) inst.update(COVERED_AT);
  render();   // 첫 장면은 바로 그린다(바뀐 화면이 한 번 비쳤다가 덮이지 않게)

  let last = 0;
  const tick = (now: number) => {
    const dt = last ? Math.min((now - last) / 1000, 0.1) * speed : 0;
    last = now;
    inst.update(dt);
    if (!covered && inst.t >= COVERED_AT) { covered = true; onCovered?.(); }
    if (inst.done()) {
      canvas.remove();
      playing = false;
      return;
    }
    render();
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
