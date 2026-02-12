# Blackout Time API for Booked Scheduler

New functions added to `protohaven_api.integrations.booked` for managing blackout times.

## Functions

### `get_blackouts(start_date=None, end_date=None, resource_id=None, schedule_id=None)`
Get blackout times from Booked scheduler with optional filters.

**Parameters:**
- `start_date`: Optional datetime - filter blackouts starting after this date
- `end_date`: Optional datetime - filter blackouts ending before this date  
- `resource_id`: Optional int - filter by specific resource ID
- `schedule_id`: Optional int - filter by schedule ID

**Returns:** Dictionary with `'blackouts'` key containing list of blackout objects

**Example:**
```python
from protohaven_api.integrations import booked
from protohaven_api.config import safe_parse_datetime

start = safe_parse_datetime("2024-01-01")
end = safe_parse_datetime("2024-01-31")
blackouts = booked.get_blackouts(start_date=start, end_date=end)
```

### `get_blackout(blackout_id)`
Get a specific blackout by ID.

**Parameters:**
- `blackout_id`: int - The blackout ID

**Returns:** Blackout object

**Example:**
```python
blackout = booked.get_blackout(123)
```

### `create_blackout(start_date, end_date, resource_ids=None, schedule_id=None, repeat_options=None, title=None, description=None)`
Create a new blackout time.

**Parameters:**
- `start_date`: datetime - Start datetime of blackout
- `end_date`: datetime - End datetime of blackout
- `resource_ids`: Optional list[int] - List of resource IDs to black out
- `schedule_id`: Optional int - Schedule ID for blackout
- `repeat_options`: Optional dict - Repeat options (see Booked API docs)
- `title`: Optional str - Title for the blackout
- `description`: Optional str - Description for the blackout

**Returns:** Created blackout object

**Example:**
```python
from datetime import datetime

start = datetime(2024, 1, 15, 9, 0, 0)
end = datetime(2024, 1, 15, 17, 0, 0)
new_blackout = booked.create_blackout(
    start_date=start,
    end_date=end,
    resource_ids=[123, 456],
    title="System Maintenance",
    description="Monthly maintenance - all tools unavailable"
)
```

### `delete_blackout(blackout_id)`
Delete a blackout time.

**Parameters:**
- `blackout_id`: int - The blackout ID to delete

**Returns:** API response

**Example:**
```python
result = booked.delete_blackout(123)
```

## API Endpoints

These functions map to the following Booked Scheduler API endpoints:
- `GET /Blackouts/` - `get_blackouts()`
- `GET /Blackouts/{id}` - `get_blackout()`
- `POST /Blackouts/` - `create_blackout()`
- `DELETE /Blackouts/{id}` - `delete_blackout()`

## Error Handling

All functions will raise `RuntimeError` if the API returns a non-200 status code, consistent with other Booked API functions in the module.
