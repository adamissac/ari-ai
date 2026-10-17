import { Ajv2020 } from 'ajv/dist/2020.js';
import { default as formatsModule } from 'ajv-formats';
import bundle from '../../../shared/generated/contracts.schema.json' with { type: 'json' };
export type * from '../../../shared/generated/ts/contracts.js';

export class ProtocolError extends Error {
  override name = 'ProtocolError';
}

// Generated TS DTOs require all properties, including Pydantic default fields.
// Server model_dump emits those properties. Reject partial wire DTOs rather than
// claiming absent fields exist. This alters no canonical source schema.
function completeObjects(value: unknown): void {
  if (!value || typeof value !== 'object') return;
  const obj = value as Record<string, unknown>;
  if (obj.properties && typeof obj.properties === 'object') {
    obj.required = Object.keys(obj.properties);
  }
  for (const child of Object.values(obj)) {
    if (Array.isArray(child)) child.forEach(completeObjects);
    else if (child && typeof child === 'object') completeObjects(child);
  }
}
const schema = structuredClone(bundle);
completeObjects(schema);
const ajv = new Ajv2020({ strict: false, allErrors: false, validateFormats: true });
// CJS/ESM interop: ajv-formats exposes its plugin through default.
const addFormats = formatsModule as unknown as (instance: Ajv2020) => void;
addFormats(ajv);
ajv.addSchema(schema, 'contracts');

export function decode<T>(name: keyof typeof bundle.$defs, value: unknown): T {
  const validate = ajv.getSchema(`contracts#/$defs/${name}`);
  if (!validate || !validate(value)) {
    // Do not include payloads or validation values (may contain sensitive data).
    throw new ProtocolError(`Invalid ${name} response`);
  }
  return value as T;
}
