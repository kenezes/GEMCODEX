# API Examples

All endpoints are served under `https://<host>/api`. Authenticate using the OAuth2 password flow to retrieve a JWT token.

## Authentication

### Request
```http
POST /api/auth/token
Content-Type: application/x-www-form-urlencoded

username=admin@example.com&password=secret
```

### Response
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_at": "2024-03-20T10:00:00Z"
}
```

## Parts catalogue

### List parts
```http
GET /api/parts?page=1&page_size=25&search=нож
Authorization: Bearer <jwt>
```

Response snippet:
```json
{
  "items": [
    {
      "id": 1,
      "name": "Нож для слайсера",
      "sku": "KNF-001",
      "qty": 5,
      "min_qty": 2,
      "price": 3500.0,
      "category_id": 1,
      "analog_group_id": null,
      "created_at": "2024-03-18T09:00:00+00:00",
      "updated_at": "2024-03-18T09:00:00+00:00"
    }
  ],
  "total": 27,
  "page": 1,
  "page_size": 25
}
```

### Retrieve part details
```http
GET /api/parts/1
Authorization: Bearer <jwt>
```

```json
{
  "id": 1,
  "name": "Нож для слайсера",
  "sku": "KNF-001",
  "qty": 5,
  "min_qty": 2,
  "price": 3500.0,
  "category_id": 1,
  "analog_group_id": null,
  "created_at": "2024-03-18T09:00:00+00:00",
  "updated_at": "2024-03-18T09:00:00+00:00",
  "replacements": []
}
```

## Real-time channel

Open a WebSocket connection to `/realtime` with the JWT token in the `Authorization` header. Example using JavaScript:

```js
const socket = new WebSocket("wss://<host>/realtime", ["jwt", "<token>"]);
socket.onmessage = (event) => console.log("Notification", event.data);
```

Back-end broadcasts entity change notifications (parts/orders/tasks) that clients can use to refresh local state.
