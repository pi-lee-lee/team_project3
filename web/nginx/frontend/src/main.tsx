import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import './styles.css'; // 전역 스타일을 먼저 — 화면별 CSS(App 이 불러옴)가 덮어쓸 수 있게
import App from './App';
import './pixel.css'; // 픽셀 모드 스킨은 맨 뒤에 — 화면별 CSS 를 덮어쓴다
import { applyTheme } from './theme';

applyTheme(); // 첫 화면이 그려지기 전에 고른 모드를 반영한다

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
