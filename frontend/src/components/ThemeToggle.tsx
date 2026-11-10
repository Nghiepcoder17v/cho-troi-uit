export type Theme = "dark" | "light";

type ThemeToggleProps = {
  theme: Theme;
  onToggle: () => void;
};

export function ThemeToggle({ theme, onToggle }: ThemeToggleProps) {
  const nextTheme = theme === "dark" ? "light" : "dark";
  const label = nextTheme === "light" ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối";

  return (
    <button
      className="theme-toggle"
      type="button"
      onClick={onToggle}
      aria-label={label}
      aria-pressed={theme === "light"}
      title={label}
    >
      <span className="theme-toggle-icon" aria-hidden="true">
        {theme === "dark" ? "☼" : "☾"}
      </span>
      <span className="theme-toggle-label">{theme === "dark" ? "Sáng" : "Tối"}</span>
    </button>
  );
}
