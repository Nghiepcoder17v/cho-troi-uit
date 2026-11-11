import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { getMe, login, register } from "../api";
import { useDialogFocus } from "../hooks/useDialogFocus";
import type { User } from "../types";

type AuthMode = "login" | "register";

type AuthModalProps = {
  mode: AuthMode;
  onClose: () => void;
  onModeChange: (mode: AuthMode) => void;
  onAuthenticated: (user: User) => void;
};

export function AuthModal({ mode, onClose, onModeChange, onAuthenticated }: AuthModalProps) {
  const dialogRef = useRef<HTMLFormElement>(null);
  const [form, setForm] = useState({ email: "", student_id: "", full_name: "", major: "", password: "" });
  const [error, setError] = useState("");
  useDialogFocus(dialogRef, onClose);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      if (mode === "register") await register(form);
      await login(form.email, form.password);
      onAuthenticated(await getMe());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Thông tin chưa hợp lệ");
    }
  };

  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <form ref={dialogRef} className="auth-modal" role="dialog" aria-modal="true" aria-labelledby="auth-modal-title" tabIndex={-1} onSubmit={(event) => void submit(event)}>
      <button type="button" className="close-button" aria-label="Đóng cửa sổ đăng nhập" onClick={onClose}>×</button>
      <p className="eyebrow">{mode === "login" ? "Chào mừng trở lại" : "Tham gia cộng đồng"}</p>
      <h2 id="auth-modal-title">{mode === "login" ? "Đăng nhập." : "Tạo tài khoản."}</h2>
      {error && <div className="form-error" role="alert">{error}</div>}
      {mode === "register" && <>
        <label>Họ và tên<input required autoComplete="name" value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} /></label>
        <label>MSSV<input required pattern="\d{8}" inputMode="numeric" autoComplete="username" value={form.student_id} onChange={(event) => setForm({ ...form, student_id: event.target.value })} placeholder="25520001" /></label>
        <label>Ngành học<input autoComplete="organization-title" value={form.major} onChange={(event) => setForm({ ...form, major: event.target.value })} /></label>
      </>}
      <label>Email UIT<input required type="email" autoComplete="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="mssv@gm.uit.edu.vn" /></label>
      <label>Mật khẩu<input required minLength={8} type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label>
      <button type="submit" className="dark-button submit-button">{mode === "login" ? "Đăng nhập ↗" : "Tạo tài khoản ↗"}</button>
      <p className="switch-auth">{mode === "login" ? "Chưa có tài khoản?" : "Đã có tài khoản?"} <button type="button" onClick={() => onModeChange(mode === "login" ? "register" : "login")}>{mode === "login" ? "Đăng ký" : "Đăng nhập"}</button></p>
    </form>
  </div>;
}
