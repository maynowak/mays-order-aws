export type ErrorCode =
  | 'VALIDATION_ERROR'
  | 'ORDER_NOT_FOUND'
  | 'INVALID_TRANSITION'
  | 'CONFLICTED_UPDATE'
  | 'INTERNAL_ERROR';

export interface OrderErrorOptions {
  code: ErrorCode;
  message: string;
  details?: Record<string, unknown>;
  httpStatus: number;
}

export class OrderError extends Error {
  readonly code: ErrorCode;
  readonly details?: Record<string, unknown>;
  readonly httpStatus: number;

  constructor(options: OrderErrorOptions) {
    super(options.message);
    this.name = 'OrderError';
    this.code = options.code;
    this.details = options.details;
    this.httpStatus = options.httpStatus;
  }
}

export function validationError(message: string, details?: Record<string, unknown>): OrderError {
  return new OrderError({ code: 'VALIDATION_ERROR', message, details, httpStatus: 400 });
}

export function orderNotFound(orderId: string): OrderError {
  return new OrderError({
    code: 'ORDER_NOT_FOUND',
    message: `Order '${orderId}' does not exist`,
    httpStatus: 404,
  });
}

export function invalidTransition(current: string, requested: string): OrderError {
  return new OrderError({
    code: 'INVALID_TRANSITION',
    message: `Transition from ${current} to ${requested} is not allowed`,
    details: { currentStatus: current, requestedStatus: requested },
    httpStatus: 409,
  });
}

export function conflictedUpdate(): OrderError {
  return new OrderError({
    code: 'CONFLICTED_UPDATE',
    message: 'Concurrent update lost; the order status changed while the update was in flight',
    httpStatus: 409,
  });
}

export function internalError(message = 'Internal error'): OrderError {
  return new OrderError({ code: 'INTERNAL_ERROR', message, httpStatus: 500 });
}

export function errorBody(error: OrderError): Record<string, unknown> {
  return {
    error: {
      code: error.code,
      message: error.message,
      ...(error.details ? { details: error.details } : {}),
    },
  };
}