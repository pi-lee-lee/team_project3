import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { homeOf } from '../App';
import { ErrorBox, useAction, useApi, useAuth } from '../util';
import { Icon } from '../Icon';
import { ThemeToggle, useTheme } from '../theme';
import { PixelFx } from '../PixelFx';
import { torch } from '../pixelfx/index.js';

/** L 로그인 */
export default function Login() {
  const api = useApi();
  const { setMe } = useAuth();
  const navigate = useNavigate();
  const [loginId, setLoginId] = useState('');
  const [password, setPassword] = useState('');
  const act = useAction();
  const pixel = useTheme() === 'pixel';
  // 이스터 에그: 로고를 3초 안에 10번 누르면 픽셀 모드 단추가 나온다. 저장하지 않으므로 로그인 화면을 띄울 때마다 다시 해야 한다
  const [unlocked, setUnlocked] = useState(false);
  const taps = useRef<number[]>([]);
  const tapLogo = () => {
    const now = Date.now();
    taps.current = [...taps.current.filter((t) => now - t < 3000), now];
    if (taps.current.length >= 10) setUnlocked(true);
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    act.run(async () => {
      const me = await api.login(loginId, password);
      setMe(me);
      navigate(homeOf(me.role));
    });
  };

  return (
    <div className="login">
      <form onSubmit={submit} className="card">
        {/* 픽셀 모드에서는 방패 대신 타오르는 횃불(pixelfx fire/torch) */}
        <div className="logo" onClick={tapLogo}>{pixel ? <PixelFx fx={torch} title="횃불" /> : <Icon name="checkmark.shield.fill" size={34} />}</div>
        <h1>화재 점검 로봇</h1>
        <input placeholder="아이디" value={loginId} onChange={(e) => setLoginId(e.target.value)} autoFocus />
        <input placeholder="비밀번호" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button className="primary" disabled={act.busy || !loginId || !password}>로그인</button>
        <ErrorBox msg={act.error} />
        {/* 픽셀 모드인 채로 돌아온 경우에는 끌 수 있게 단추를 보인다 */}
        {(unlocked || pixel) && <ThemeToggle />}
      </form>
    </div>
  );
}
