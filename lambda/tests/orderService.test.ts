import { describe, expect, it } from 'vitest';
import { DynamoDBDocumentClient } from '@aws-sdk/lib-dynamodb';

import { OrderError } from '../src/errors';
import { createOrderService } from '../src/orderService';
import { GSI1_PK, ORDER_ID_PREFIX, OrderDynamoItem } from '../src/types';

type CommandName = 'PutCommand' | 'GetCommand' | 'QueryCommand' | 'UpdateCommand';

class FakeDocClient {
  constructor(
    private handlers: Record<CommandName, (cmd: { input: Record<string, unknown> }) => unknown>,
  ) {}

  send(cmd: { constructor: { name: string }; input: Record<string, unknown> }): Promise<unknown> {
    const name = cmd.constructor.name as CommandName;
    const handler = this.handlers[name];
    if (!handler) {
      throw new Error(`No fake handler for ${name}`);
    }
    return Promise.resolve(handler(cmd));
  }
}

function makeClient(handlers: Partial<Record<CommandName, FakeDocClient['send']>>): DynamoDBDocumentClient {
  const allHandlers: Record<CommandName, FakeDocClient['send']> = {
    PutCommand: () => ({}),
    GetCommand: () => ({ Item: undefined }),
    QueryCommand: () => ({ Items: [], LastEvaluatedKey: undefined }),
    UpdateCommand: () => ({ Attributes: undefined }),
    ...handlers,
  };
  return new FakeDocClient(allHandlers) as unknown as DynamoDBDocumentClient;
}

function makeOrder(overrides: Partial<OrderDynamoItem> = {}): OrderDynamoItem {
  return {
    pk: `${ORDER_ID_PREFIX}ord_2f4b1c9e0000000000000000`,
    sk: '#ORDER',
    orderId: 'ord_2f4b1c9e0000000000000000',
    status: 'PENDING',
    customer: { name: 'Max Mustermann', email: 'max@example.com' },
    items: [{ sku: 'SKU-1001', quantity: 2, unitPrice: 1999, lineTotal: 3998 }],
    currency: 'EUR',
    totalAmount: 3998,
    createdAt: '2026-08-17T12:00:00.000Z',
    updatedAt: '2026-08-17T12:00:00.000Z',
    version: 1,
    gsi1pk: GSI1_PK,
    gsi1sk: '2026-08-17T12:00:00.000Z',
    ...overrides,
  };
}

describe('orderService.createOrder — AP1', () => {
  it('berechnet lineTotal und totalAmount server-seitig und speichert PENDING', async () => {
    let putItem: Record<string, unknown> | undefined;
    const service = createOrderService({
      tableName: 'mays-orders',
      client: makeClient({
        PutCommand: (cmd) => {
          putItem = cmd.input.Item as Record<string, unknown>;
          return {};
        },
      }),
    });

    const order = await service.createOrder({
      customer: { name: 'Max Mustermann', email: 'max@example.com' },
      items: [
        { sku: 'SKU-1001', quantity: 2, unitPrice: 1999 },
        { sku: 'SKU-1002', quantity: 1, unitPrice: 499 },
      ],
      currency: 'EUR',
    });

    expect(order.status).toBe('PENDING');
    expect(order.totalAmount).toBe(4497);
    expect(order.items[0].lineTotal).toBe(3998);
    expect(order.createdAt).toBe(order.updatedAt);

    expect(putItem).toMatchObject({
      pk: `${ORDER_ID_PREFIX}${order.orderId}`,
      sk: '#ORDER',
      gsi1pk: GSI1_PK,
      gsi1sk: order.createdAt,
      version: 1,
      status: 'PENDING',
    });
    expect(putItem?.orderId).toBe(order.orderId);
  });

  it('validiert den Body vor dem Schreiben', async () => {
    let called = false;
    const service = createOrderService({
      tableName: 'mays-orders',
      client: makeClient({
        PutCommand: () => {
          called = true;
          return {};
        },
      }),
    });

    await expect(service.createOrder({ customer: {}, items: [], currency: '' })).rejects.toMatchObject({
      code: 'VALIDATION_ERROR',
    });
    expect(called).toBe(false);
  });
});

describe('orderService.getOrder — AP2', () => {
  it('liefert Order-Objekt ohne interne Felder', async () => {
    const item = makeOrder();
    const service = createOrderService({
      tableName: 'mays-orders',
      client: makeClient({ GetCommand: () => ({ Item: item }) }),
    });

    const order = await service.getOrder('ord_2f4b1c9e0000000000000000');
    expect(order.orderId).toBe(item.orderId);
    expect(order.status).toBe('PENDING');
    expect((order as Record<string, unknown>)['pk']).toBeUndefined();
    expect((order as Record<string, unknown>)['version']).toBeUndefined();
  });

  it('wirft ORDER_NOT_FOUND, wenn Item fehlt (T-08)', async () => {
    const service = createOrderService({
      tableName: 'mays-orders',
      client: makeClient({ GetCommand: () => ({ Item: undefined }) }),
    });

    await expect(service.getOrder('ord_2f4b1c9e0000000000000000')).rejects.toMatchObject({
      code: 'ORDER_NOT_FOUND',
      httpStatus: 404,
    });
  });
});

describe('orderService.listOrders — AP3', () => {
  const item = makeOrder();

  it('queryt GSI1 absteigend und liefert kompakte Items', async () => {
    let queryInput: Record<string, unknown> | undefined;
    const service = createOrderService({
      tableName: 'mays-orders',
      client: makeClient({
        QueryCommand: (cmd) => {
          queryInput = cmd.input;
          return { Items: [item] };
        },
      }),
    });

    const result = await service.listOrders(20);
    expect(queryInput?.IndexName).toBe('gsi1');
    expect(queryInput?.ScanIndexForward).toBe(false);
    expect(queryInput?.Limit).toBe(20);
    expect(result.count).toBe(1);
    expect(result.orders[0]).toEqual({
      orderId: item.orderId,
      status: item.status,
      customer: { name: item.customer.name },
      totalAmount: item.totalAmount,
      createdAt: item.createdAt,
      updatedAt: item.updatedAt,
    });
    expect(result.nextToken).toBeUndefined();
  });

  it('kodiert LastEvaluatedKey als Base64 nextToken', async () => {
    const lek = { pk: `${ORDER_ID_PREFIX}abc`, sk: '#ORDER' };
    const service = createOrderService({
      tableName: 'mays-orders',
      client: makeClient({
        QueryCommand: () => ({ Items: [item], LastEvaluatedKey: lek }),
      }),
    });

    const result = await service.listOrders(5);
    expect(result.nextToken).toBe(Buffer.from(JSON.stringify(lek)).toString('base64'));
  });

  it('setzt ExclusiveStartKey aus nextToken', async () => {
    const lek = { pk: `${ORDER_ID_PREFIX}abc`, sk: '#ORDER' };
    const token = Buffer.from(JSON.stringify(lek)).toString('base64');
    let queryInput: Record<string, unknown> | undefined;
    const service = createOrderService({
      tableName: 'mays-orders',
      client: makeClient({
        QueryCommand: (cmd) => {
          queryInput = cmd.input;
          return { Items: [] };
        },
      }),
    });

    await service.listOrders(20, token);
    expect(queryInput?.ExclusiveStartKey).toEqual(lek);
  });

  it('lehnt ungültigen nextToken ab', async () => {
    const service = createOrderService({
      tableName: 'mays-orders',
      client: makeClient({ QueryCommand: () => ({ Items: [] }) }),
    });

    await expect(service.listOrders(20, '!!!not-base64-json!!!')).rejects.toMatchObject({
      code: 'VALIDATION_ERROR',
    });
  });
});

describe('orderService.updateOrderStatus — AP4', () => {
  it('führt validen Übergang per Conditional Update durch', async () => {
    const current = makeOrder({ status: 'PENDING' });
    const updated = makeOrder({ status: 'CONFIRMED', updatedAt: '2026-08-17T13:00:00.000Z', version: 2 });

    let updateInput: Record<string, unknown> | undefined;
    const service = createOrderService({
      tableName: 'mays-orders',
      client: makeClient({
        GetCommand: () => ({ Item: current }),
        UpdateCommand: (cmd) => {
          updateInput = cmd.input;
          return { Attributes: updated };
        },
      }),
    });

    const order = await service.updateOrderStatus('ord_2f4b1c9e0000000000000000', 'CONFIRMED');
    expect(order.status).toBe('CONFIRMED');
    expect(updateInput?.ConditionExpression).toContain('#status = :currentStatus');
    expect(updateInput?.ExpressionAttributeValues).toMatchObject({
      ':currentStatus': 'PENDING',
      ':newStatus': 'CONFIRMED',
    });
  });

  it('wirft INVALID_TRANSITION bei ungültigem Übergang (T-14)', async () => {
    const service = createOrderService({
      tableName: 'mays-orders',
      client: makeClient({
        GetCommand: () => ({ Item: makeOrder({ status: 'PROCESSING' }) }),
      }),
    });

    const error = await service
      .updateOrderStatus('ord_2f4b1c9e0000000000000000', 'CANCELLED')
      .catch((err: unknown) => err);
    expect(error).toBeInstanceOf(OrderError);
    const orderError = error as OrderError;
    expect(orderError.code).toBe('INVALID_TRANSITION');
    expect(orderError.details).toEqual({ currentStatus: 'PROCESSING', requestedStatus: 'CANCELLED' });
  });

  it('wirft ORDER_NOT_FOUND, wenn Order fehlt (T-16)', async () => {
    const service = createOrderService({
      tableName: 'mays-orders',
      client: makeClient({ GetCommand: () => ({ Item: undefined }) }),
    });

    await expect(
      service.updateOrderStatus('ord_2f4b1c9e0000000000000000', 'CONFIRMED'),
    ).rejects.toMatchObject({ code: 'ORDER_NOT_FOUND', httpStatus: 404 });
  });

  it('wirft CONFLICTED_UPDATE bei ConditionalCheckFailed (R-01)', async () => {
    const conditionalError = new Error('The conditional request failed');
    conditionalError.name = 'ConditionalCheckFailedException';

    const service = createOrderService({
      tableName: 'mays-orders',
      client: makeClient({
        GetCommand: () => ({ Item: makeOrder({ status: 'PENDING' }) }),
        UpdateCommand: () => {
          throw conditionalError;
        },
      }),
    });

    await expect(
      service.updateOrderStatus('ord_2f4b1c9e0000000000000000', 'CONFIRMED'),
    ).rejects.toMatchObject({ code: 'CONFLICTED_UPDATE', httpStatus: 409 });
  });
});