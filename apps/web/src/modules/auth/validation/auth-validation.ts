export type FieldErrors = Readonly<Record<string, string>>;

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateEmail(email: string): string | undefined {
  const normalized = email.trim();
  if (!normalized) return "Enter your email address.";
  if (normalized.length > 254 || !EMAIL_PATTERN.test(normalized)) {
    return "Enter a valid email address.";
  }
  return undefined;
}

export function validatePassword(password: string): string | undefined {
  if (!password) return "Enter your password.";
  if (password.length < 12) return "Use at least 12 characters.";
  if (password.length > 128) return "Use no more than 128 characters.";
  return undefined;
}

export function validateDisplayName(name: string): string | undefined {
  const normalized = name.trim();
  if (!normalized) return "Enter the name you want Meridian to use.";
  if (normalized.length > 100) return "Use no more than 100 characters.";
  return undefined;
}
