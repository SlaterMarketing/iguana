"use client";

import React, { useEffect, useState } from "react";
import { KintanaProvider, useKintana } from "@kintana/sdk/react";

import type { KintanaPublicFormSchema } from "@kintana/sdk";

function StyledFormInner({
  formId,
  prefills,
}: {
  formId: string;
  prefills: Record<string, string>;
}) {
  const client = useKintana();
  const [schema, setSchema] = useState<KintanaPublicFormSchema | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    client
      .getFormSchema(formId, { cache: "force-cache" })
      .then((s) => {
        if (!alive) return;
        setSchema(s);
      })
      .catch(() => alive && setMessage("We could not load this form yet."))
      .finally(() => alive && setLoading(false));

    return () => {
      alive = false;
    };
  }, [client, formId]);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!schema) return;
    setSubmitting(true);
    setMessage(null);
    const fd = new FormData(e.currentTarget);
    const values: Record<string, string> = {};
    for (const field of schema.fields) {
      const raw = fd.get(field.id);
      values[field.id] = typeof raw === "string" ? raw : "";
    }
    try {
      const result = await client.submitForm(schema.id, values);
      if (result.redirectUrl) {
        window.location.assign(result.redirectUrl);
        return;
      }
      if (result.ok !== true) {
        setMessage("Something went sideways—try WhatsApp?");
        return;
      }
      setMessage(result.successMessage ?? "Got it—we will reply shortly.");
      e.currentTarget.reset();
      if (prefills) {
        for (const field of schema.fields) {
          const val = prefills[field.id];
          if (!val) continue;
          const el = e.currentTarget.elements.namedItem(field.id);
          if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
            el.value = val;
          }
        }
      }
    } catch {
      setMessage("Submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  const defaults = prefills ?? {};

  if (loading)
    return <p className="rounded-3xl bg-neutral-100 px-6 py-4 text-neutral-700">Loading form…</p>;
  if (!schema)
    return <p className="rounded-3xl border border-neutral-300 px-6 py-4 text-neutral-700">{message}</p>;

  return (
    <div className="max-w-xl">
      <h2 className="font-display text-2xl tracking-tight text-neutral-950" style={{ fontFamily: "var(--font-display)" }}>
        {schema.title}
      </h2>

      <form className="mt-8 grid gap-5" onSubmit={(e) => void submit(e)}>
        {schema.fields.map((field) => (
          <label key={field.id} className="grid gap-2 text-sm font-medium text-neutral-900">
            <span>
              {field.label}
              {field.required ? " *" : null}
            </span>
            {field.type === "textarea" ? (
              <textarea
                name={field.id}
                required={field.required}
                rows={6}
                className="rounded-3xl border border-neutral-400/55 bg-neutral-50 px-4 py-3 text-base text-neutral-900 shadow-inner outline-none transition focus:border-brand"
                defaultValue={defaults[field.id] ?? undefined}
              />
            ) : (
              <input
                type={field.type === "email" ? "email" : "text"}
                name={field.id}
                required={field.required}
                className="rounded-full border border-neutral-400/55 bg-neutral-50 px-4 py-3 text-base text-neutral-900 shadow-inner outline-none transition focus:border-brand"
                defaultValue={defaults[field.id] ?? undefined}
              />
            )}
          </label>
        ))}
        <button
          disabled={submitting}
          type="submit"
          className="rounded-full bg-neutral-950 px-12 py-[0.9rem] text-xs font-semibold uppercase tracking-[0.35em] text-white shadow-lg shadow-neutral-900/35 transition hover:opacity-[0.95] disabled:bg-neutral-500"
        >
          {submitting ? "Sending…" : "Send message"}
        </button>
      </form>
      {message ? <p className="mt-6 text-neutral-700">{message}</p> : null}
    </div>
  );
}

export function ContactFormIsland({
  apiKey,
  baseUrl,
  formId,
  prefills,
}: {
  apiKey: string;
  baseUrl: string;
  formId: string;
  prefills?: Record<string, string>;
}) {
  const merged = React.useMemo(() => prefills ?? {}, [prefills]);

  return (
    <KintanaProvider apiKey={apiKey} baseUrl={baseUrl}>
      <StyledFormInner formId={formId} prefills={merged} />
    </KintanaProvider>
  );
}
