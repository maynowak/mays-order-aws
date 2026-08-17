export const ORDER_STATUSES = [
  'PENDING',
  'CONFIRMED',
  'PROCESSING',
  'SHIPPED',
  'DELIVERED',
  'CANCELLED',
] as const;

export type OrderStatus = (typeof ORDER_STATUSES)[number];

export const ORDER_ID_PREFIX = 'ord_';

export const ORDER_SK = '#ORDER';

export const GSI1_PK = 'LIST';

export const TABLE_INDEX_NAME = 'gsi1';

export interface Customer {
  name: string;
  email: string;
}

export interface OrderItem {
  sku: string;
  quantity: number;
  unitPrice: number;
  lineTotal: number;
}

export interface Order {
  orderId: string;
  status: OrderStatus;
  customer: Customer;
  items: OrderItem[];
  currency: string;
  totalAmount: number;
  createdAt: string;
  updatedAt: string;
}

export interface OrderDynamoItem extends Order {
  pk: string;
  sk: string;
  gsi1pk: string;
  gsi1sk: string;
  version: number;
}

export interface OrderListItem {
  orderId: string;
  status: OrderStatus;
  customer: Pick<Customer, 'name'>;
  totalAmount: number;
  createdAt: string;
  updatedAt: string;
}

export interface ListOrdersResult {
  orders: OrderListItem[];
  count: number;
  nextToken?: string;
}