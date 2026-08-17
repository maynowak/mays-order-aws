import { describe, expect, it } from 'vitest';

import { canTransition } from '../src/stateMachine';
import { ORDER_STATUSES } from '../src/types';

describe('stateMachine — gültige Übergänge (transition-rules.md)', () => {
  const allowed: Array<[string, string]> = [
    ['PENDING', 'CONFIRMED'],
    ['PENDING', 'CANCELLED'],
    ['CONFIRMED', 'PROCESSING'],
    ['CONFIRMED', 'CANCELLED'],
    ['PROCESSING', 'SHIPPED'],
    ['SHIPPED', 'DELIVERED'],
  ];

  for (const [from, to] of allowed) {
    it(`erlaubt ${from} → ${to}`, () => {
      expect(canTransition(from as never, to as never)).toBe(true);
    });
  }
});

describe('stateMachine — ungültige Übergänge', () => {
  const disallowed: Array<[string, string]> = [
    ['PENDING', 'PROCESSING'],
    ['PENDING', 'SHIPPED'],
    ['PENDING', 'DELIVERED'],
    ['CONFIRMED', 'DELIVERED'],
    ['PROCESSING', 'CANCELLED'],
    ['SHIPPED', 'CANCELLED'],
  ];

  for (const [from, to] of disallowed) {
    it(`lehnt ${from} → ${to} ab`, () => {
      expect(canTransition(from as never, to as never)).toBe(false);
    });
  }

  it('lehnt Übergänge aus Endzuständen ab (DELIVERED, CANCELLED)', () => {
    for (const target of ORDER_STATUSES) {
      expect(canTransition('DELIVERED', target)).toBe(false);
      expect(canTransition('CANCELLED', target)).toBe(false);
    }
  });

  it('lehnt Übergang auf denselben Zustand ab (Idempotenz → 409, transition-rules §5)', () => {
    for (const status of ORDER_STATUSES) {
      expect(canTransition(status, status)).toBe(false);
    }
  });
});