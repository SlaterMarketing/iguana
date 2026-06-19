import type { KintanaFormField } from "@kintana/sdk";
import { PhoneInput } from "@kintana/sdk/react";

const inputClass =
  "rounded-full border border-neutral-400/55 bg-neutral-50 px-4 py-3 text-base text-neutral-900 shadow-inner outline-none transition focus:border-brand";
const textareaClass =
  "rounded-3xl border border-neutral-400/55 bg-neutral-50 px-4 py-3 text-base text-neutral-900 shadow-inner outline-none transition focus:border-brand";

function acceptAttr(field: KintanaFormField): string | undefined {
  const mime = field.options?.acceptMimeTypes;
  if (!mime?.length) return undefined;
  return mime.join(",");
}

export function EmbedFormField({
  field,
  defaults,
  disabled,
}: {
  field: KintanaFormField;
  defaults: Record<string, string>;
  disabled?: boolean;
}) {
  const def = defaults[field.id];
  const help = field.helpText ? <p className="text-xs font-normal text-neutral-500">{field.helpText}</p> : null;
  const choices = field.options?.choices ?? [];

  switch (field.type) {
    case "textarea":
      return (
        <>
          <textarea
            id={field.id}
            name={field.id}
            required={field.required}
            disabled={disabled}
            rows={6}
            placeholder={field.placeholder}
            className={textareaClass}
            defaultValue={def ?? undefined}
          />
          {help}
        </>
      );

    case "boolean":
      return (
        <label className="flex cursor-pointer items-center gap-3 font-normal">
          <input
            id={field.id}
            type="checkbox"
            name={field.id}
            value="true"
            disabled={disabled}
            defaultChecked={def === "true" || def === "1"}
            className="size-5 rounded border-neutral-400 text-brand accent-brand"
          />
          <span className="text-base text-neutral-800">{field.placeholder ?? ""}</span>
          {help}
        </label>
      );

    case "select":
      return (
        <>
          <select
            id={field.id}
            name={field.id}
            required={field.required}
            disabled={disabled}
            className={inputClass}
            defaultValue={def ?? ""}
          >
            <option value="">—</option>
            {choices.map((choice) => (
              <option key={choice} value={choice}>
                {choice}
              </option>
            ))}
          </select>
          {help}
        </>
      );

    case "multiselect":
      return (
        <>
          <select
            id={field.id}
            name={field.id}
            multiple
            required={field.required && choices.length > 0}
            disabled={disabled}
            size={Math.min(Math.max(choices.length, 2), 8)}
            className={`${textareaClass} rounded-3xl`}
            defaultValue={
              def?.includes(",") ? def.split(",").map((s) => s.trim()) : def ? [def] : undefined
            }
          >
            {choices.map((choice) => (
              <option key={choice} value={choice}>
                {choice}
              </option>
            ))}
          </select>
          <p className="text-xs font-normal text-neutral-500">Hold Ctrl/Cmd to select multiple.</p>
          {help}
        </>
      );

    case "file":
      return (
        <>
          <input
            id={field.id}
            type="file"
            name={field.id}
            required={field.required}
            disabled={disabled}
            accept={acceptAttr(field)}
            data-max-bytes={field.options?.maxBytes ?? undefined}
            className="text-sm text-neutral-800 file:mr-4 file:rounded-full file:border-0 file:bg-neutral-200 file:px-4 file:py-2 file:text-xs file:font-semibold file:uppercase file:tracking-wide"
          />
          {help}
        </>
      );

    case "number":
      return (
        <>
          <input
            id={field.id}
            type="number"
            name={field.id}
            required={field.required}
            disabled={disabled}
            placeholder={field.placeholder}
            className={inputClass}
            defaultValue={def ?? undefined}
          />
          {help}
        </>
      );

    case "date":
      return (
        <>
          <input
            id={field.id}
            type="date"
            name={field.id}
            required={field.required}
            disabled={disabled}
            className={inputClass}
            defaultValue={def ?? undefined}
          />
          {help}
        </>
      );

    case "url":
      return (
        <>
          <input
            id={field.id}
            type="url"
            name={field.id}
            required={field.required}
            disabled={disabled}
            placeholder={field.placeholder}
            className={inputClass}
            defaultValue={def ?? undefined}
          />
          {help}
        </>
      );

    case "phone":
      return (
        <>
          <PhoneInput
            id={field.id}
            name={field.id}
            required={field.required}
            disabled={disabled}
            placeholder={field.placeholder ?? "412 345 678"}
          />
          {help}
        </>
      );

    case "email":
      return (
        <>
          <input
            id={field.id}
            type="email"
            name={field.id}
            required={field.required}
            disabled={disabled}
            placeholder={field.placeholder}
            className={inputClass}
            defaultValue={def ?? undefined}
          />
          {help}
        </>
      );

    case "text":
    default:
      return (
        <>
          <input
            id={field.id}
            type="text"
            name={field.id}
            required={field.required}
            disabled={disabled}
            placeholder={field.placeholder}
            className={inputClass}
            defaultValue={def ?? undefined}
          />
          {help}
        </>
      );
  }
}

export function validateFileField(field: KintanaFormField, file: File): string | null {
  const max = field.options?.maxBytes;
  if (typeof max === "number" && file.size > max) {
    return `File is too large (max ${Math.round(max / 1024)} KB).`;
  }
  const mime = field.options?.acceptMimeTypes;
  if (mime?.length && file.type && !mimeMatchesList(mime, file.type)) return "This file type is not allowed.";
  return null;
}

/** Basic mime check: wildcard image/* or exact match */
function mimeMatchesList(allowed: string[], fileMime: string): boolean {
  for (const pattern of allowed) {
    if (mimeMatches(pattern, fileMime)) return true;
  }
  return false;
}

function mimeMatches(pattern: string, fileMime: string): boolean {
  const p = pattern.trim().toLowerCase();
  if (p.endsWith("/*")) {
    const prefix = p.slice(0, -2);
    return fileMime.toLowerCase().startsWith(`${prefix}/`);
  }
  return p === fileMime.toLowerCase();
}
