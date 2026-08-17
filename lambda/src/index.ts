import { errorBody, internalError, OrderError, validationError } from './errors';
import { createOrderService } from './orderService';
import { validateListParams, validateOrderId, validateStatusUpdateBody } from './validation';

export interface LambdaEvent {
  routeKey?: string;
  httpMethod?: string;
  rawPath?: string;
  body?: string | null;
  isBase64Encoded?: boolean;
  pathParameters?: { [name: string]: string | undefined } | null;
  queryStringParameters?: { [name: string]: string | undefined } | null;
}

export interface LambdaResponse {
  statusCode: number;
  headers: { 'Content-Type': string };
  body: string;
}

const JSON_HEADERS = { 'Content-Type': 'application/json' };

function parseBody(event: LambdaEvent): unknown {
  if (event.body === undefined || event.body === null) {
    return undefined;
  }
  const raw = event.isBase64Encoded ? Buffer.from(event.body, 'base64').toString('utf8') : event.body;
  try {
    return JSON.parse(raw);
  } catch {
    throw validationError('Request body must be valid JSON');
  }
}

function ok(statusCode: number, payload: unknown): LambdaResponse {
  return { statusCode, headers: JSON_HEADERS, body: JSON.stringify(payload) };
}

function fail(error: unknown): LambdaResponse {
  if (error instanceof OrderError) {
    return { statusCode: error.httpStatus, headers: JSON_HEADERS, body: JSON.stringify(errorBody(error)) };
  }
  console.error('Unexpected error', error);
  const err = internalError();
  return { statusCode: err.httpStatus, headers: JSON_HEADERS, body: JSON.stringify(errorBody(err)) };
}

function routeKey(event: LambdaEvent): string {
  if (event.routeKey) {
    return event.routeKey;
  }
  const method = event.httpMethod ?? 'GET';
  const path = event.rawPath ?? '/';
  return `${method} ${path}`;
}

export const handler = async (event: LambdaEvent): Promise<LambdaResponse> => {
  const tableName = process.env.ORDERS_TABLE;
  if (!tableName) {
    return fail(internalError('Lambda is not configured (ORDERS_TABLE missing)'));
  }

  const service = createOrderService({ tableName });

  try {
    const route = routeKey(event);

    if (route === 'POST /orders') {
      const order = await service.createOrder(parseBody(event));
      return ok(201, order);
    }

    if (route === 'GET /orders') {
      const { limit, nextToken } = validateListParams(event.queryStringParameters ?? undefined);
      const result = await service.listOrders(limit, nextToken);
      return ok(200, result);
    }

    if (route === 'GET /orders/{orderId}') {
      const orderId = validateOrderId(event.pathParameters?.orderId);
      const order = await service.getOrder(orderId);
      return ok(200, order);
    }

    if (route === 'PATCH /orders/{orderId}/status') {
      const orderId = validateOrderId(event.pathParameters?.orderId);
      const status = validateStatusUpdateBody(parseBody(event));
      const order = await service.updateOrderStatus(orderId, status);
      return ok(200, order);
    }

    return fail(validationError(`Unsupported route: ${route}`));
  } catch (err) {
    return fail(err);
  }
};