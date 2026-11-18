import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { homeOf } from '../App';
import { ErrorBox, useAction, useApi, useAuth } from '../util';
import { Icon } from '../Icon';

/** L 로그인 */
export default function Login() {
  const api = useApi();
  const { setMe } = useAuth();
  const navigate = useNavigate();
  const [loginId, setLoginId] = useState('');
  const [password, setPassword] = useState('');
  const act = useAction();

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
        <div className="logo"><Icon name="checkmark.shield.fill" size={34} /></div>
        <h1>화재 점검 로봇</h1>
        <input placeholder="아이디" value={loginId} onChange={(e) => setLoginId(e.target.value)} autoFocus />
        <input placeholder="비밀번호" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button className="primary" disabled={act.busy || !loginId || !password}>로그인</button>
        <ErrorBox msg={act.error} />
      </form>
    </div>
  );
}
