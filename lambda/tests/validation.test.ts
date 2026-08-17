import { describe, expect, it } from 'vitest';

import { OrderError } from '../src/errors';
import {
  validateCreateOrder,
  validateListParams,
  validateOrderId,
  validateStatus,
  validateStatusUpdateBody,
} from '../src/validation';

const validBody = {
  customer: { name: 'Max Mustermann', email: 'max@example.com' },
  items: [{ sku: 'SKU-1001', quantity: 2, unitPrice: 1999 }],
  currency: 'EUR',
};

function expectValidationError(fn: () => unknown): OrderError {
  try {
    fn();
    throw new Error('expected validation error');
  } catch (err) {
    expect(err).toBeInstanceOf(OrderError);
    const orderError = err as OrderError;
    expect(orderError.code).toBe('VALIDATION_ERROR');
    expect(orderError.httpStatus).toBe(400);
    return orderError;
  }
}

describe('validateCreateOrder — POST /orders', () => {
  it('akzeptiert gültigen Body', () => {
    const input = validateCreateOrder(validBody);
    expect(input.customer.name).toBe('Max Mustermann');
    expect(input.items).toHaveLength(1);
    expect(input.currency).toBe('EUR');
  });

  it('lehnt fehlendes customer.name ab (T-02)', () => {
    expectValidationError(() =>
      validateCreateOrder({ ...validBody, customer: { email: 'max@example.com' } }),
    );
  });

  it('lehnt ungültige E-Mail ab (T-03)', () => {
    expectValidationError(() =>
      validateCreateOrder({
        ...validBody,
        customer: { name: 'Max', email: 'not-an-email' },
      }),
    );
  });

  it('lehnt leere items ab (T-04)', () => {
    expectValidationError(() => validateCreateOrder({ ...validBody, items: [] }));
  });

  it('lehnt quantity 0 ab (T-05)', () => {
    expectValidationError(() =>
      validateCreateOrder({
        ...validBody,
        items: [{ sku: 'SKU-1001', quantity: 0, unitPrice: 1999 }],
      }),
    );
  });

  it('lehnt quantity mit Nachkommastellen ab', () => {
    expectValidationError(() =>
      validateCreateOrder({
        ...validBody,
        items: [{ sku: 'SKU-1001', quantity: 1.5, unitPrice: 1999 }],
      }),
    );
  });

  it('lehnt unitPrice als Float ab (Beträge = ganze Cent)', () => {
    expectValidationError(() =>
      validateCreateOrder({
        ...validBody,
        items: [{ sku: 'SKU-1001', quantity: 1, unitPrice: 19.99 }],
      }),
    );
  });

  it('lehnt unbekanntes Top-Level-Feld ab (T-06)', () => {
    expectValidationError(() => validateCreateOrder({ ...validBody, extra: true }));
  });

  it('lehnt unbekanntes Feld in items ab', () => {
    expectValidationError(() =>
      validateCreateOrder({
        ...validBody,
        items: [{ sku: 'SKU-1001', quantity: 1, unitPrice: 100, discount: 10 }],
      }),
    );
  });

  it('lehnt ungültige currency ab', () => {
    expectValidationError(() => validateCreateOrder({ ...validBody, currency: 'EU' }));
  });

  it('lehnt Nicht-Objekt-Body ab', () => {
    expectValidationError(() => validateCreateOrder(null));
    expectValidationError(() => validateCreateOrder('text'));
  });
});

describe('validateOrderId — GET /orders/{orderId}', () => {
  it('akzeptiert ord_ + alphanumerisch', () => {
    expect(validateOrderId('ord_2f4b1c9e0000000000000000')).toBe('ord_2f4b1c9e0000000000000000');
  });

  it('lehnt ungültiges Format ab (T-09)', () => {
    expectValidationError(() => validateOrderId('order-123'));
    expectValidationError(() => validateOrderId(''));
    expectValidationError(() => validateOrderId(undefined));
  });
});

describe('validateStatus / validateStatusUpdateBody — PATCH status', () => {
  it('akzeptiert gültigen Status', () => {
    expect(validateStatus('CONFIRMED')).toBe('CONFIRMED');
    expect(validateStatusUpdateBody({ status: 'SHIPPED' })).toBe('SHIPPED');
  });

  it('lehnt ungültigen Status-String ab (T-15)', () => {
    expectValidationError(() => validateStatus('READY'));
    expectValidationError(() => validateStatusUpdateBody({ status: 'READY' }));
    expectValidationError(() => validateStatusUpdateBody({ status: 'CONFIRMED', extra: 1 }));
    expectValidationError(() => validateStatusUpdateBody({}));
  });
});

describe('validateListParams — GET /orders', () => {
  it('Default limit = 20', () => {
    expect(validateListParams(undefined)).toEqual({ limit: 20 });
    expect(validateListParams({})).toEqual({ limit: 20 });
  });

  it('akzeptiert limit im Bereich 1..100', () => {
    expect(validateListParams({ limit: '1' }).limit).toBe(1);
    expect(validateListParams({ limit: '100' }).limit).toBe(100);
  });

  it('lehnt limit außerhalb des Bereichs ab', () => {
    expectValidationError(() => validateListParams({ limit: '0' }));
    expectValidationError(() => validateListParams({ limit: '101' }));
    expectValidationError(() => validateListParams({ limit: 'abc' }));
  });

  it('reicht nextToken durch', () => {
    expect(validateListParams({ nextToken: 'eyJ9' }).nextToken).toBe('eyJ9');
  });
});