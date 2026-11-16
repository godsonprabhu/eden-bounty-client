"use client";

import { useEffect, useRef } from "react";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "area[href]",
  "input:not([disabled]):not([type=\"hidden\"])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "button:not([disabled])",
  "iframe",
  "[tabindex]:not([tabindex=\"-1\"])",
  "[contenteditable]",
].join(",");

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
  ).filter((el) => {
    return el.offsetParent !== null || el.getClientRects().length > 0;
  });
}

export interface UseModalFocusTrapOptions {
  isOpen: boolean;
  onClose: () => void;
  initialFocusSelector?: string;
  isSubmitting?: boolean;
  isLoading?: boolean;
  preventScroll?: boolean;
}

/**
 * Custom hook providing accessible focus management for modal dialogs:
 * - Traps Tab and Shift+Tab navigation within the dialog container.
 * - Sets initial focus to a designated selector or first focusable child once not loading.
 * - Restores focus to the triggering element upon dialog closure/unmount.
 * - Handles Escape key dismissal (respecting isSubmitting guard).
 * - Prevents focus escaping to background DOM via document-level focusin listener.
 * - Locks background document scroll while the dialog is open.
 */
export function useModalFocusTrap<T extends HTMLElement = HTMLDivElement>({
  isOpen,
  onClose,
  initialFocusSelector,
  isSubmitting = false,
  isLoading = false,
  preventScroll = true,
}: UseModalFocusTrapOptions) {
  const containerRef = useRef<T | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  const onCloseRef = useRef(onClose);
  const isSubmittingRef = useRef(isSubmitting);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    isSubmittingRef.current = isSubmitting;
  }, [isSubmitting]);

  // 1. Lifecycle: Trigger element capture, background scroll lock, Tab trap, and focus restoration
  useEffect(() => {
    if (!isOpen) return;

    // Capture the element that held focus before the modal opened
    if (document.activeElement instanceof HTMLElement) {
      triggerRef.current = document.activeElement;
    }

    // Prevent background page scrolling
    const originalOverflow = document.body.style.overflow;
    if (preventScroll) {
      document.body.style.overflow = "hidden";
    }

    // Trap Tab / Shift+Tab keyboard navigation and Escape dismissal
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!containerRef.current) return;

      if (e.key === "Escape") {
        if (!isSubmittingRef.current) {
          e.preventDefault();
          onCloseRef.current();
        }
        return;
      }

      if (e.key === "Tab") {
        const focusable = getFocusableElements(containerRef.current);

        if (focusable.length === 0) {
          e.preventDefault();
          containerRef.current.focus();
          return;
        }

        const firstElement = focusable[0];
        const lastElement = focusable[focusable.length - 1];

        if (e.shiftKey) {
          // Shift + Tab: moving backward
          if (
            document.activeElement === firstElement ||
            !containerRef.current.contains(document.activeElement)
          ) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          // Tab: moving forward
          if (
            document.activeElement === lastElement ||
            !containerRef.current.contains(document.activeElement)
          ) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    // Prevent focus from escaping to background via mouse/tab
    const handleFocusIn = (e: FocusEvent) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) {
        e.preventDefault();
        const focusable = getFocusableElements(containerRef.current);
        if (focusable.length > 0) {
          focusable[0].focus();
        } else {
          containerRef.current.focus();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    document.addEventListener("focusin", handleFocusIn);

    // Cleanup on unmount or close
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("focusin", handleFocusIn);

      if (preventScroll) {
        document.body.style.overflow = originalOverflow;
      }

      // Restore focus to the trigger element
      const trigger = triggerRef.current;
      if (trigger && document.contains(trigger)) {
        requestAnimationFrame(() => {
          if (document.contains(trigger)) {
            trigger.focus();
          }
        });
      }
    };
  }, [isOpen, preventScroll]);

  // 2. Initial focus: Target specified element or first focusable child once loading completes
  useEffect(() => {
    if (!isOpen || isLoading) return;

    const initialFocusTimer = setTimeout(() => {
      if (!containerRef.current) return;

      let targetElement: HTMLElement | null = null;
      if (initialFocusSelector) {
        targetElement = containerRef.current.querySelector<HTMLElement>(
          initialFocusSelector
        );
      }

      if (!targetElement || targetElement.hasAttribute("disabled")) {
        const focusable = getFocusableElements(containerRef.current);
        targetElement = focusable.length > 0 ? focusable[0] : null;
      }

      if (targetElement && typeof targetElement.focus === "function") {
        targetElement.focus();
      } else if (containerRef.current) {
        containerRef.current.focus();
      }
    }, 40);

    return () => clearTimeout(initialFocusTimer);
  }, [isOpen, isLoading, initialFocusSelector]);

  return containerRef;
}
