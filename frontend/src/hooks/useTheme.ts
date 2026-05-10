import { useState, useEffect } from "react";

export type Theme = "light" | "tech";

const STORAGE_KEY = "app-theme";

function applyTheme(theme: Theme) {
  if (theme === "tech") {
    document.documentElement.setAttribute("data-theme", "tech");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    const t: Theme = stored === "tech" ? "tech" : "light";
    applyTheme(t);
    return t;
  });

  useEffect(() => {
    applyTheme(theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "light" ? "tech" : "light"));

  return { theme, toggleTheme };
}
