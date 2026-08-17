import { randomBytes } from 'node:crypto';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import {
  DynamoDBDocumentClient,
  GetCommand,
  PutCommand,
  QueryCommand,
  UpdateCommand,
} from '@aws-sdk/lib-dynamodb';

import {
  conflictedUpdate,
  invalidTransition,
  orderNotFound,
  validationError,
} from './errors';
import { canTransition } from './stateMachine';
import { validateCreateOrder } from './validation';
import {
  GSI1_PK,
  ORDER_ID_PREFIX,
  ORDER_SK,
  TABLE_INDEX_NAME,
  OrderStatus,
  OrderListItem,
  ListOrdersResult,
  Order,
  OrderDynamoItem,
} from './types';

export interface OrderServiceConfig {
  tableName: string;
  client?: DynamoDBDocumentClient;
}

function generateOrderId(): string {
  return `${ORDER_ID_PREFIX}${randomBytes(12).toString('hex')}`;
}

function nowIso(): string {
  return new Date().toISOString();
}

function toPublicOrder(item: OrderDynamoItem): Order {
  const { pk: _pk, sk: _sk, gsi1pk: _gsi1pk, gsi1sk: _gsi1sk, version: _version, ...order } = item;
  return order;
}

function toListItem(item: OrderDynamoItem): OrderListItem {
  return {
    orderId: item.orderId,
    status: item.status,
    customer: { name: item.customer.name },
    totalAmount: item.totalAmount,
    createdAt: item.createdAt,
    updatedAt: item.updatedAt,
  };
}

function encodeNextToken(lastEvaluatedKey: Record<string, unknown> | undefined): string | undefined {
  if (!lastEvaluatedKey) {
    return undefined;
  }
  return Buffer.from(JSON.stringify(lastEvaluatedKey), 'utf8').toString('base64');
}

function decodeNextToken(nextToken: string): Record<string, unknown> {
  try {
    const json = Buffer.from(nextToken, 'base64').toString('utf8');
    const parsed: unknown = JSON.parse(json);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      throw new Error('not an object');
    }
    return parsed as Record<string, unknown>;
  } catch {
    throw validationError("Query parameter 'nextToken' is not a valid pagination token", {
      path: 'nextToken',
    });
  }
}

function isConditionalCheckFailed(err: unknown): boolean {
  return err instanceof Error && err.name === 'ConditionalCheckFailedException';
}

function isValidationException(err: unknown): boolean {
  return err instanceof Error && err.name === 'ValidationException';
}

export function createOrderService(config: OrderServiceConfig) {
  const tableName = config.tableName;
  const docClient =
    config.client ??
    DynamoDBDocumentClient.from(new DynamoDBClient({ region: process.env.AWS_REGION ?? 'eu-central-1' }));

  async function createOrder(rawBody: unknown): Promise<Order> {
    const input = validateCreateOrder(rawBody);
    const now = nowIso();
    const orderId = generateOrderId();

    const items = input.items.map((item) => ({
      ...item,
      lineTotal: item.quantity * item.unitPrice,
    }));
    const totalAmount = items.reduce((sum, item) => sum + item.lineTotal, 0);

    const item: OrderDynamoItem = {
      pk: `${ORDER_ID_PREFIX}${orderId}`,
      sk: ORDER_SK,
      orderId,
      status: 'PENDING',
      customer: input.customer,
      items,
      currency: input.currency,
      totalAmount,
      createdAt: now,
      updatedAt: now,
      version: 1,
      gsi1pk: GSI1_PK,
      gsi1sk: now,
    };

    await docClient.send(
      new PutCommand({
        TableName: tableName,
        Item: item,
      }),
    );

    return toPublicOrder(item);
  }

  async function getOrder(orderId: string): Promise<Order> {
    const result = await docClient.send(
      new GetCommand({
        TableName: tableName,
        Key: { pk: `${ORDER_ID_PREFIX}${orderId}`, sk: ORDER_SK },
      }),
    );

    if (!result.Item) {
      throw orderNotFound(orderId);
    }

    return toPublicOrder(result.Item as OrderDynamoItem);
  }

  async function listOrders(limit: number, nextToken?: string): Promise<ListOrdersResult> {
    const command = new QueryCommand({
      TableName: tableName,
      IndexName: TABLE_INDEX_NAME,
      KeyConditionExpression: 'gsi1pk = :pk',
      ExpressionAttributeValues: { ':pk': GSI1_PK },
      ScanIndexForward: false,
      Limit: limit,
      ...(nextToken ? { ExclusiveStartKey: decodeNextToken(nextToken) } : {}),
    });

    let result;
    try {
      result = await docClient.send(command);
    } catch (err) {
      if (isValidationException(err)) {
        throw validationError('Invalid pagination token or query', { path: 'nextToken' });
      }
      throw err;
    }

    const orders = (result.Items ?? []).map((item) => toListItem(item as OrderDynamoItem));

    return {
      orders,
      count: orders.length,
      ...(encodeNextToken(result.LastEvaluatedKey)
        ? { nextToken: encodeNextToken(result.LastEvaluatedKey) }
        : {}),
    };
  }

  async function updateOrderStatus(orderId: string, status: OrderStatus): Promise<Order> {
    const current = await getOrder(orderId);

    if (!canTransition(current.status, status)) {
      throw invalidTransition(current.status, status);
    }

    try {
      const result = await docClient.send(
        new UpdateCommand({
          TableName: tableName,
          Key: { pk: `${ORDER_ID_PREFIX}${orderId}`, sk: ORDER_SK },
          UpdateExpression: 'SET #status = :newStatus, updatedAt = :now, #version = #version + :one',
          ConditionExpression: 'attribute_exists(pk) AND #status = :currentStatus',
          ExpressionAttributeNames: {
            '#status': 'status',
            '#version': 'version',
          },
          ExpressionAttributeValues: {
            ':newStatus': status,
            ':currentStatus': current.status,
            ':now': nowIso(),
            ':one': 1,
          },
          ReturnValues: 'ALL_NEW',
        }),
      );

      return toPublicOrder(result.Attributes as OrderDynamoItem);
    } catch (err) {
      if (isConditionalCheckFailed(err)) {
        throw conflictedUpdate();
      }
      throw err;
    }
  }

  return { createOrder, getOrder, listOrders, updateOrderStatus };
}

export type OrderService = ReturnType<typeof createOrderService>;