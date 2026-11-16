"use client";

import { useState } from "react";
import Image from "next/image";
import { useReducedMotion } from "motion/react";
import { cn } from "@/lib/utils";

export interface ServiceImageSliderProps {
  images?: string[];
  fallbackImage: string;
  alt: string;
  priority?: boolean;
  className?: string;
  staggerIndex?: number;
  sizes?: string;
}

/**
 * Reusable automatic image slider for EDEN BOUNTY commercial service cards and detail pages.
 * Inspired by the Uiverse.io card animation concept by javierBarroso:
 * - Seamless continuous horizontal sliding across 3 service images (4 slides with wrapped clone)
 * - Smooth transition with EDEN BOUNTY cubic-bezier curve (--ease-tide)
 * - Approximately 3 seconds display per image (~9.6s full cycle)
 * - Pauses on hover over the image area / card and on keyboard focus
 * - Strictly preserves card aspect ratio and dimensions with object-fit: cover (no layout shift)
 * - Full accessibility with prefers-reduced-motion support
 */
export function ServiceImageSlider({
  images,
  fallbackImage,
  alt,
  priority = false,
  className,
  staggerIndex = 0,
  sizes = "(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw",
}: ServiceImageSliderProps) {
  const reduce = useReducedMotion();
  const [isPaused, setIsPaused] = useState(false);

  // If no image list or fewer than 2 images, render a single static image
  if (!images || images.length < 2) {
    return (
      <div className={cn("relative h-full w-full overflow-hidden", className)}>
        <Image
          src={fallbackImage}
          alt={alt}
          fill
          priority={priority}
          sizes={sizes}
          className="object-cover transition-transform duration-700 ease-[var(--ease-tide)] group-hover:scale-[1.06] dark:brightness-[0.85]"
        />
      </div>
    );
  }

  // To create a seamless infinite loop across 3 images,
  // we append a clone of the first image at the end (total 4 slides).
  // Track width is 400%, and each slide takes 25% (100% of visible container).
  const slides = [...images, images[0]];

  return (
    <div
      className={cn(
        "eb-service-slider-container relative h-full w-full overflow-hidden select-none",
        className
      )}
      onPointerEnter={() => setIsPaused(true)}
      onPointerLeave={() => setIsPaused(false)}
      onFocusCapture={() => setIsPaused(true)}
      onBlurCapture={() => setIsPaused(false)}
      aria-label={`${alt} gallery`}
    >
      <div
        className={cn(
          "eb-service-slider-track flex h-full w-[400%]",
          reduce && "!animate-none !transform-none"
        )}
        style={{
          animationPlayState: isPaused ? "paused" : undefined,
          animationDelay: staggerIndex ? `${(staggerIndex % 3) * 0.75}s` : undefined,
        }}
      >
        {slides.map((src, idx) => {
          const isClone = idx === slides.length - 1;
          return (
            <div
              key={`${src}-${idx}`}
              className="relative h-full w-1/4 flex-shrink-0 overflow-hidden"
              aria-hidden={isClone ? "true" : undefined}
            >
              <Image
                src={src}
                alt={isClone ? "" : `${alt} — image ${idx + 1}`}
                fill
                priority={priority && idx === 0}
                sizes={sizes}
                className="object-cover transition-transform duration-700 ease-[var(--ease-tide)] group-hover:scale-[1.06] dark:brightness-[0.85]"
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
