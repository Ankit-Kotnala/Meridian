import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "../internal/cn";

export const buttonStyles = {
  base: "inline-flex min-h-10 items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold transition duration-200 disabled:cursor-not-allowed disabled:opacity-55",
  primary:
    "bg-primary text-white shadow-[0_8px_24px_rgba(91,70,245,.24)] hover:bg-primary-strong",
  secondary:
    "border border-line bg-white text-foreground shadow-sm hover:border-primary/40 hover:bg-primary-soft/50",
  ghost: "text-muted hover:bg-slate-100 hover:text-foreground",
  dark: "bg-navy text-white hover:bg-navy-hover",
} as const;

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  variant?: keyof typeof buttonStyles;
};

export function Button({
  children,
  className,
  type = "button",
  variant = "primary",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(buttonStyles.base, buttonStyles[variant], className)}
      type={type}
      {...props}
    >
      {children}
    </button>
  );
}
