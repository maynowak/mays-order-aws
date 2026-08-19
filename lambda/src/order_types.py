from __future__ import annotations

from typing import Any, Dict, List, TypedDict

ORDER_STATUSES = [
    "PENDING",
    "CONFIRMED",
    "PROCESSING",
    "SHIPPED",
    "DELIVERED",
    "CANCELLED",
]

OrderStatus = str

ORDER_ID_PREFIX = "ord_"

ORDER_SK = "#ORDER"

GSI1_PK = "LIST"

TABLE_INDEX_NAME = "gsi1"


class Customer(TypedDict):
    name: str
    email: str


class OrderItem(TypedDict):
    sku: str
    quantity: int
    unitPrice: int
    lineTotal: int


class Order(TypedDict):
    orderId: str
    status: OrderStatus
    customer: Customer
    items: List[OrderItem]
    currency: str
    totalAmount: int
    createdAt: str
    updatedAt: str


class OrderDynamoItem(Order, total=False):
    pk: str
    sk: str
    gsi1pk: str
    gsi1sk: str
    version: int
    # isTestData: ausschließlich von Demo-Seed-Items gesetzt (orders_seed_demo_50.json).
    # KEIN Teil des produktiven Order-Modells; wird von create_order nie gesetzt und
    # über order_service.INTERNAL_FIELDS aus API-Antworten entfernt.
    isTestData: bool


class OrderListItem(TypedDict):
    orderId: str
    status: OrderStatus
    customer: Dict[str, str]
    totalAmount: int
    createdAt: str
    updatedAt: str


class ListOrdersResult(TypedDict, total=False):
    orders: List[OrderListItem]
    count: int
    nextToken: str


CreateOrderInput = Dict[str, Any]
