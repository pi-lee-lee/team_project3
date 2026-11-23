// pixelfx 는 타입 정의가 없어서, 화면에서 쓰는 만큼만 적어 둔다.

/** 색 버퍼(color)와 빛 버퍼(light)를 가진 w × h 픽셀 한 장 */
export interface FxFrame { w: number; h: number; ox: number; oy: number; color: Uint32Array; light: Uint32Array }

export interface FxMeta {
  name: string;
  size: [number, number];      // 캔버스 크기(픽셀)
  origin: [number, number];    // 기준점(발밑 · 횃불 밑동 등)
  duration: number;            // 초
  loop: boolean;
  fps: number;
  options?: Record<string, unknown>;
}

/** 이펙트 파일 하나(모듈) */
export interface FxModule { meta: FxMeta }

export interface FxOptions {
  x?: number; y?: number; flip?: boolean; angle?: number; seed?: number;
  palette?: string[];          // 어두운 색 → 밝은 색
  light?: number;              // 빛 세기(0..1+)
  [key: string]: unknown;
}

export interface FxInstance {
  readonly t: number;
  update(dt: number): void;
  draw(frame: FxFrame, layer?: 'back' | 'front'): void;
  stop(): void;
  done(): boolean;
}

export function createFrame(w: number, h: number, ox?: number, oy?: number): FxFrame;
export function clearFrame(frame: FxFrame): FxFrame;
export function createFx(mod: FxModule, options?: FxOptions): FxInstance;
/** 색 + 빛을 RGBA 바이트로 합친다. bg 가 null 이면 투명 바탕 */
export function composite(frame: FxFrame, out: Uint8ClampedArray, bg?: number | Uint32Array | null, lightK?: number): void;

export const pixelDissolve: FxModule;
export const torch: FxModule;
export const smallExplosion: FxModule;
