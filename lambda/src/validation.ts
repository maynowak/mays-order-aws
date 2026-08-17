import { validationError } from './errors';
import { ORDER_STATUSES, OrderStatus, type Customer, type OrderItem } from './types';

export interface CreateOrderInput {
  customer: Customer;
  items: Omit<OrderItem, 'lineTotal'>[];
  currency: string;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const ORDER_ID_RE = /^ord_[A-Za-z0-9]+$/;
const CURRENCY_RE = /^[A-Z]{3}$/;
const STATUS_SET: ReadonlySet<string> = new Set(ORDER_STATUSES);

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function rejectUnknownKeys(value: Record<string, unknown>, allowed: readonly string[], path: string): void {
  const unknown = Object.keys(value).filter((key) => !allowed.includes(key));
  if (unknown.length > 0) {
    throw validationError(`Unknown field '${unknown[0]}' at ${path}`, { path: `${path}.${unknown[0]}` });
  }
}

function assertString(value: unknown, path: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw validationError(`Field '${path}' must be a non-empty string`, { path });
  }
  return value;
}

function assertInteger(value: unknown, path: string, min: number): number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < min) {
    throw validationError(`Field '${path}' must be an integer >= ${min}`, { path });
  }
  return value;
}

export function validateCreateOrder(body: unknown): CreateOrderInput {
  if (!isPlainObject(body)) {
    throw validationError('Request body must be a JSON object');
  }

  rejectUnknownKeys(body, ['customer', 'items', 'currency'], 'body');

  const customer = body['customer'];
  if (!isPlainObject(customer)) {
    throw validationError("Field 'customer' must be an object", { path: 'customer' });
  }
  rejectUnknownKeys(customer, ['name', 'email'], 'customer');
  const name = assertString(customer['name'], 'customer.name');
  const email = assertString(customer['email'], 'customer.email');
  if (!EMAIL_RE.test(email)) {
    throw validationError("Field 'customer.email' must be a valid email address", { path: 'customer.email' });
  }

  const items = body['items'];
  if (!Array.isArray(items) || items.length < 1) {
    throw validationError("Field 'items' must be a non-empty array", { path: 'items' });
  }
  const validatedItems: Omit<OrderItem, 'lineTotal'>[] = items.map((raw, index) => {
    if (!isPlainObject(raw)) {
      throw validationError(`Field 'items[${index}]' must be an object`, { path: `items[${index}]` });
    }
    rejectUnknownKeys(raw, ['sku', 'quantity', 'unitPrice'], `items[${index}]`);
    const sku = assertString(raw['sku'], `items[${index}].sku`);
    const quantity = assertInteger(raw['quantity'], `items[${index}].quantity`, 1);
    const unitPrice = assertInteger(raw['unitPrice'], `items[${index}].unitPrice`, 1);
    return { sku, quantity, unitPrice };
  });

  const currency = assertString(body['currency'], 'currency');
  if (!CURRENCY_RE.test(currency)) {
    throw validationError("Field 'currency' must be a 3-letter ISO-4217 code (uppercase)", { path: 'currency' });
  }

  return { customer: { name, email }, items: validatedItems, currency };
}

export function validateOrderId(orderId: unknown): string {
  if (typeof orderId !== 'string' || !ORDER_ID_RE.test(orderId)) {
    throw validationError("Path parameter 'orderId' must match format 'ord_<alphanumeric>'", {
      path: 'orderId',
    });
  }
  return orderId;
}

export function validateStatus(status: unknown): OrderStatus {
  if (typeof status !== 'string' || !STATUS_SET.has(status)) {
    throw validationError(`Field 'status' must be one of: ${ORDER_STATUSES.join(', ')}`, { path: 'status' });
  }
  return status as OrderStatus;
}

export function validateStatusUpdateBody(body: unknown): OrderStatus {
  if (!isPlainObject(body)) {
    throw validationError('Request body must be a JSON object');
  }
  rejectUnknownKeys(body, ['status'], 'body');
  return validateStatus(body['status']);
}

export interface ListParams {
  limit: number;
  nextToken?: string;
}

export function validateListParams(query: Record<string, unknown> | undefined): ListParams {
  const rawLimit = query && query['limit'];
  const rawNextToken = query && query['nextToken'];

  let limit = 20;
  if (rawLimit !== undefined) {
    if (typeof rawLimit !== 'string' || !/^\d+$/.test(rawLimit)) {
      throw validationError("Query parameter 'limit' must be an integer", { path: 'limit' });
    }
    limit = Number.parseInt(rawLimit, 10);
    if (limit < 1 || limit > 100) {
      throw validationError("Query parameter 'limit' must be between 1 and 100", { path: 'limit' });
    }
  }

  let nextToken: string | undefined;
  if (rawNextToken !== undefined) {
    nextToken = assertString(rawNextToken, 'nextToken');
  }

  return { limit, nextToken };
}