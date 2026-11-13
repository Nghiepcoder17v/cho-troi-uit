import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  getAdminRoleAssignments,
  getAdminRoleEvents,
  grantAdminRole,
  revokeAdminRole,
  searchAdminUsers,
} from "../api";
import type {
  AdminRoleAssignment,
  AdminRoleAssignmentEvent,
  AdminRoleCode,
  AdminUserSummary,
} from "../types";

function formatDate(value: string): string {
  return new Date(value).toLocaleString("vi-VN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function AdminControlsPage({ currentUserId }: { currentUserId: number }) {
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<AdminUserSummary[]>([]);
  const [selectedUser, setSelectedUser] = useState<AdminUserSummary | null>(null);
  const [assignments, setAssignments] = useState<AdminRoleAssignment[]>([]);
  const [events, setEvents] = useState<AdminRoleAssignmentEvent[]>([]);
  const [roleCode, setRoleCode] = useState<AdminRoleCode>("MODERATOR");
  const [grantReason, setGrantReason] = useState("");
  const [revokeReasons, setRevokeReasons] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [savingRole, setSavingRole] = useState(false);
  const [revokingId, setRevokingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refreshHistory = async (userId?: number) => {
    const [nextAssignments, nextEvents] = await Promise.all([
      getAdminRoleAssignments(userId),
      getAdminRoleEvents(userId),
    ]);
    setAssignments(nextAssignments.data);
    setEvents(nextEvents.data);
  };

  useEffect(() => {
    let active = true;
    Promise.all([getAdminRoleAssignments(), getAdminRoleEvents()])
      .then(([nextAssignments, nextEvents]) => {
        if (!active) return;
        setAssignments(nextAssignments.data);
        setEvents(nextEvents.data);
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "Không thể tải dữ liệu quản trị");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const submitSearch = async (event: FormEvent) => {
    event.preventDefault();
    const normalized = query.trim();
    if (normalized.length < 2) {
      setError("Nhập ít nhất 2 ký tự để tìm tài khoản.");
      return;
    }
    setSearching(true);
    setError("");
    setNotice("");
    try {
      const result = await searchAdminUsers(normalized);
      setSearchResults(result.data);
      setSelectedUser(null);
      setAssignments([]);
      if (!result.data.length) setNotice("Không tìm thấy tài khoản phù hợp.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể tìm tài khoản");
    } finally {
      setSearching(false);
    }
  };

  const selectUser = async (user: AdminUserSummary) => {
    setSelectedUser(user);
    setError("");
    setNotice("");
    setLoading(true);
    try {
      await refreshHistory(user.user_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể tải lịch sử phân quyền");
    } finally {
      setLoading(false);
    }
  };

  const submitGrant = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedUser) return;
    if (selectedUser.user_id === currentUserId) {
      setError("Không thể tự thay đổi quyền của chính mình.");
      return;
    }
    setSavingRole(true);
    setError("");
    setNotice("");
    try {
      await grantAdminRole(selectedUser.user_id, roleCode, grantReason.trim());
      setGrantReason("");
      await refreshHistory(selectedUser.user_id);
      setNotice(`Đã cấp quyền ${roleCode} cho ${selectedUser.full_name}.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể cấp quyền");
    } finally {
      setSavingRole(false);
    }
  };

  const submitRevoke = async (assignment: AdminRoleAssignment) => {
    const reason = (revokeReasons[assignment.assignment_id] ?? "").trim();
    if (!reason) {
      setError("Nhập lý do thu hồi quyền.");
      return;
    }
    if (assignment.user.user_id === currentUserId) {
      setError("Không thể tự thu hồi quyền của chính mình.");
      return;
    }
    setRevokingId(assignment.assignment_id);
    setError("");
    setNotice("");
    try {
      await revokeAdminRole(assignment.assignment_id, reason);
      setRevokeReasons((current) => ({ ...current, [assignment.assignment_id]: "" }));
      await refreshHistory(selectedUser?.user_id);
      setNotice(`Đã thu hồi quyền ${assignment.role_code} của ${assignment.user.full_name}.`);
    } catch (reasonValue) {
      setError(reasonValue instanceof Error ? reasonValue.message : "Không thể thu hồi quyền");
    } finally {
      setRevokingId(null);
    }
  };

  return <main className="admin-page">
    <div className="admin-page-header">
      <div>
        <p className="eyebrow">DB-6D · ADMIN CONTROLS</p>
        <h1>Quản lý phân quyền</h1>
        <p>Tra cứu tài khoản, cấp hoặc thu hồi vai trò và xem lịch sử thay đổi quyền.</p>
      </div>
      <span className="admin-authority-label">ADMIN</span>
    </div>

    {error && <p className="form-error admin-feedback" role="alert">{error}</p>}
    {notice && <p className="form-success admin-feedback" role="status">{notice}</p>}

    <section className="admin-panel">
      <div className="admin-panel-heading">
        <div><p className="eyebrow">TÀI KHOẢN UIT</p><h2>Tìm người dùng</h2></div>
      </div>
      <form className="admin-search-form" onSubmit={(event) => void submitSearch(event)}>
        <label htmlFor="admin-user-search">Họ tên, MSSV hoặc email</label>
        <div className="admin-search-controls">
          <input
            id="admin-user-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            minLength={2}
            maxLength={100}
            placeholder="Ví dụ: 25520001 hoặc tên sinh viên"
          />
          <button className="dark-button" type="submit" disabled={searching}>
            {searching ? "Đang tìm…" : "Tìm tài khoản"}
          </button>
        </div>
      </form>

      {searchResults.length > 0 && <div className="admin-user-results">
        {searchResults.map((user) => <button
          type="button"
          key={user.user_id}
          className={selectedUser?.user_id === user.user_id ? "admin-user-result selected" : "admin-user-result"}
          onClick={() => void selectUser(user)}
        >
          <span className="admin-user-avatar">{user.full_name.slice(0, 1)}</span>
          <span className="admin-user-result-copy">
            <strong>{user.full_name}</strong>
            <small>{user.student_id} · {user.email}</small>
          </span>
          <span className="admin-user-result-id">#{user.user_id}</span>
        </button>)}
      </div>}
    </section>

    {selectedUser && <section className="admin-panel">
      <div className="admin-panel-heading">
        <div><p className="eyebrow">NGƯỜI ĐƯỢC CHỌN</p><h2>{selectedUser.full_name}</h2>
          <p>{selectedUser.student_id} · {selectedUser.email}</p>
        </div>
        <span className="admin-user-result-id">ID #{selectedUser.user_id}</span>
      </div>

      {selectedUser.user_id === currentUserId
        ? <p className="admin-info-note">Bạn không thể cấp hoặc thu hồi vai trò của chính tài khoản đang đăng nhập.</p>
        : <form className="admin-grant-form" onSubmit={(event) => void submitGrant(event)}>
          <div>
            <label htmlFor="admin-role-code">Vai trò cần cấp</label>
            <select id="admin-role-code" value={roleCode} onChange={(event) => setRoleCode(event.target.value as AdminRoleCode)}>
              <option value="MODERATOR">MODERATOR · Kiểm duyệt báo cáo</option>
              <option value="ADMIN">ADMIN · Quản trị phân quyền</option>
            </select>
          </div>
          <div className="admin-reason-field">
            <label htmlFor="admin-grant-reason">Lý do cấp quyền (8–250 ký tự)</label>
            <input
              id="admin-grant-reason"
              value={grantReason}
              onChange={(event) => setGrantReason(event.target.value)}
              minLength={8}
              maxLength={250}
              required
              placeholder="Ghi rõ nhiệm vụ hoặc căn cứ cấp quyền"
            />
          </div>
          <button className="dark-button" type="submit" disabled={savingRole || grantReason.trim().length < 8}>
            {savingRole ? "Đang cấp quyền…" : "Cấp vai trò"}
          </button>
        </form>}

      <div className="admin-subsection-heading">
        <h3>Lịch sử phân quyền</h3>
        <span>{assignments.length} bản ghi</span>
      </div>
      {loading ? <p className="muted">Đang tải dữ liệu…</p> : assignments.length === 0
        ? <p className="muted">Tài khoản chưa có bản ghi phân quyền.</p>
        : <div className="admin-assignment-list">
          {assignments.map((assignment) => <article className="admin-assignment-card" key={assignment.assignment_id}>
            <div className="admin-assignment-main">
              <span className={assignment.revoked_at ? "admin-role-pill revoked" : "admin-role-pill"}>
                {assignment.role_code}
              </span>
              <span className={assignment.revoked_at ? "admin-assignment-state revoked" : "admin-assignment-state"}>
                {assignment.revoked_at ? "Đã thu hồi" : "Đang hoạt động"}
              </span>
            </div>
            <p><strong>Lý do cấp:</strong> {assignment.grant_reason}</p>
            <small>Cấp lúc {formatDate(assignment.granted_at)} · {assignment.granted_by_name ?? "Bootstrap vận hành"}</small>
            {assignment.revoked_at && <small>Thu hồi lúc {formatDate(assignment.revoked_at)} · {assignment.revoke_reason}</small>}
            {!assignment.revoked_at && assignment.user.user_id !== currentUserId && <div className="admin-revoke-controls">
              <input
                value={revokeReasons[assignment.assignment_id] ?? ""}
                onChange={(event) => setRevokeReasons((current) => ({
                  ...current,
                  [assignment.assignment_id]: event.target.value,
                }))}
                minLength={8}
                maxLength={250}
                placeholder="Lý do thu hồi quyền (8–250 ký tự)"
                aria-label={`Lý do thu hồi ${assignment.role_code}`}
              />
              <button
                type="button"
                className="outline-button danger-outline"
                disabled={revokingId === assignment.assignment_id || (revokeReasons[assignment.assignment_id] ?? "").trim().length < 8}
                onClick={() => void submitRevoke(assignment)}
              >
                {revokingId === assignment.assignment_id ? "Đang thu hồi…" : "Thu hồi"}
              </button>
            </div>}
          </article>)}
        </div>}
    </section>}

    <section className="admin-panel">
      <div className="admin-panel-heading">
        <div><p className="eyebrow">AUDIT LOG</p><h2>Sự kiện phân quyền gần đây</h2></div>
        <span>{events.length} sự kiện</span>
      </div>
      {events.length === 0 ? <p className="muted">Chưa có sự kiện phân quyền nào được ghi nhận.</p>
        : <div className="admin-event-list">
          {events.map((event) => <article className="admin-event-row" key={event.event_id}>
            <span className={event.event_code === "GRANTED" ? "admin-event-marker granted" : "admin-event-marker revoked"} />
            <div>
              <strong>{event.event_code === "GRANTED" ? "Cấp quyền" : "Thu hồi quyền"} {event.role_code}</strong>
              <p>{event.target_user.full_name} · {event.target_user.student_id}</p>
              <small>{event.reason}</small>
            </div>
            <div className="admin-event-meta">
              <strong>{event.actor_name}</strong>
              <small>{formatDate(event.occurred_at)}</small>
            </div>
          </article>)}
        </div>}
    </section>

    <p className="admin-safety-note">Không thể thay đổi quyền của chính mình. Quyền ADMIN cuối cùng được bảo vệ ở backend. Các thao tác chỉ áp dụng từ request tiếp theo sau khi transaction hoàn tất.</p>
  </main>;
}
