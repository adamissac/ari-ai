import { describe, expect, it } from 'vitest';
import { CREATE_INCIDENT_NOTE } from '@/lib/create-incident';

describe('create incident note', () => {
  it('names the record and does not claim containment, notify, or linked evidence', () => {
    expect(CREATE_INCIDENT_NOTE).toContain('records a title and initial report');
    expect(CREATE_INCIDENT_NOTE).toContain('does not contain or recover systems');
    expect(CREATE_INCIDENT_NOTE).toContain('notify outsiders');
    expect(CREATE_INCIDENT_NOTE).toContain('until you link them');
    expect(CREATE_INCIDENT_NOTE).toContain('simulated drill');
  });
});
