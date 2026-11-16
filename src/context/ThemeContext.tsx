"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from "react";

export type Theme = "light" | "dark";

export interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export interface ThemeProviderProps {
  children: React.ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  // Lazily initialize state on client to match what the inline pre-hydration script applied to DOM
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof window !== "undefined") {
      const domTheme = document.documentElement.getAttribute("data-theme");
      if (domTheme === "dark" || domTheme === "light") {
        return domTheme;
      }
      try {
        const stored = localStorage.getItem("eb_theme");
        if (stored === "dark" || stored === "light") {
          return stored;
        }
      } catch {
        // Fallback for sandboxed environments
      }
    }
    return "dark"; // Cinematic dark is the default for first-time visitors & SSR
  });

  // Apply theme to DOM and persist to localStorage
  const applyTheme = useCallback((newTheme: Theme) => {
    const validTheme: Theme = newTheme === "light" ? "light" : "dark";
    setThemeState(validTheme);

    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("eb_theme", validTheme);
      } catch {
        // Handle localStorage restrictions safely
      }

      const root = document.documentElement;
      root.classList.remove("light", "dark");
      root.classList.add(validTheme);
      root.setAttribute("data-theme", validTheme);
      root.style.colorScheme = validTheme;

      // Update theme-color meta tag for mobile browser chrome
      const metaThemeColor = document.querySelector('meta[name="theme-color"]');
      if (metaThemeColor) {
        metaThemeColor.setAttribute(
          "content",
          validTheme === "dark" ? "#07090c" : "#f6f9fb"
        );
      }

      // Dispatch custom event for 3D globe and non-React subscribers
      window.dispatchEvent(
        new CustomEvent<Theme>("eb:themechange", { detail: validTheme })
      );
    }
  }, []);

  const toggleTheme = useCallback(() => {
    applyTheme(theme === "dark" ? "light" : "dark");
  }, [theme, applyTheme]);

  // Synchronize with external changes (e.g. across multiple browser tabs)
  useEffect(() => {
    if (typeof window === "undefined") return;

    // Ensure DOM is in sync with state on initial mount
    const root = document.documentElement;
    const currentDomTheme = root.getAttribute("data-theme");
    if (currentDomTheme !== theme) {
      root.classList.remove("light", "dark");
      root.classList.add(theme);
      root.setAttribute("data-theme", theme);
      root.style.colorScheme = theme;
    }

    // Cross-tab synchronization via storage event
    const handleStorage = (e: StorageEvent) => {
      if (e.key === "eb_theme") {
        const newTheme: Theme = e.newValue === "light" ? "light" : "dark";
        setThemeState(newTheme);
        root.classList.remove("light", "dark");
        root.classList.add(newTheme);
        root.setAttribute("data-theme", newTheme);
        root.style.colorScheme = newTheme;
        window.dispatchEvent(
          new CustomEvent<Theme>("eb:themechange", { detail: newTheme })
        );
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, [theme]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      setTheme: applyTheme,
      toggleTheme,
    }),
    [theme, applyTheme, toggleTheme]
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
