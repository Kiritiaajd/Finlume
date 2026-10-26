import type { FieldErrors, FieldValues, Resolver } from "react-hook-form";
import type { z } from "zod";

/**
 * React Hook Form resolver that validates with a Zod schema.
 *
 * A local replacement for `@hookform/resolvers/zod`: that package's long list
 * of optional peer dependencies makes npm 10 write a lock file that `npm ci`
 * then rejects (ajv 6 vs 8). This covers what Finlume needs: the first issue
 * per field, nested paths, and parsed (transformed) values on success.
 */
export function zodResolver<TValues extends FieldValues>(
  schema: z.ZodType<TValues>,
): Resolver<TValues> {
  return async (values) => {
    const result = await schema.safeParseAsync(values);
    if (result.success) {
      return { values: result.data, errors: {} };
    }

    const errors: Record<string, unknown> = {};
    for (const issue of result.error.issues) {
      if (issue.path.length === 0) continue; // form-level issues are not field errors
      let target = errors;
      const keys = issue.path.map(String);
      keys.slice(0, -1).forEach((key) => {
        target[key] ??= {};
        target = target[key] as Record<string, unknown>;
      });
      const leaf = keys[keys.length - 1]!;
      target[leaf] ??= { type: issue.code, message: issue.message };
    }
    return { values: {}, errors: errors as FieldErrors<TValues> };
  };
}
